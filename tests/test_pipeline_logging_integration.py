"""
Integration tests for pipeline logging flow.

Tests the complete logging flow through the transcript pipeline,
verifying that structured logging works correctly with real pipeline
components and provides proper observability.
"""

import json
import logging
import time
import unittest
from io import StringIO
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logging_setup import (
    JsonFormatter, configure_logging, set_job_ctx, clear_job_ctx
)
from log_events import (
    evt, StageTimer, job_received, job_finished, job_failed, 
    video_processed, classify_error_type
)


class TestPipelineLoggingIntegration(unittest.TestCase):
    """Integration tests for pipeline logging flow."""
    
    def setUp(self):
        """Set up pipeline integration test environment."""
        # Configure logging to capture all output
        self.log_buffer = StringIO()
        self.handler = logging.StreamHandler(self.log_buffer)
        self.handler.setFormatter(JsonFormatter())
        
        self.logger = logging.getLogger()
        # Clear existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)
        
        # Clear context
        clear_job_ctx()
    
    def tearDown(self):
        """Clean up pipeline integration test environment."""
        self.logger.removeHandler(self.handler)
        self.handler.close()
        clear_job_ctx()
    
    def _parse_log_events(self):
        """Parse log events from buffer."""
        log_output = self.log_buffer.getvalue()
        events = []
        for line in log_output.strip().split('\n'):
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return events
    
    def test_requirement_10_5_complete_job_lifecycle_trace(self):
        """Test Requirement 10.5: Complete job lifecycle tracking."""
        job_id = 'j-integration-test'
        video_id = 'test-video-123'
        
        # Set job context
        set_job_ctx(job_id=job_id, video_id=video_id)
        
        # Simulate complete job lifecycle
        start_time = time.time()
        
        # 1. Job received
        job_received(video_count=1, use_cookies=True, proxy_enabled=False)
        
        # 2. Transcript pipeline stages
        transcript_stages = [
            ('youtube-transcript-api', 'no_captions', 500),
            ('timedtext', 'blocked', 800),
            ('youtubei', 'success', 2500),
        ]
        
        for stage, outcome, expected_duration in transcript_stages:
            if outcome == 'success':
                with StageTimer(stage, attempt=1, use_proxy=False):
                    time.sleep(0.01)  # Simulate work
            elif outcome == 'blocked':
                evt('stage_result', 
                    stage=stage, 
                    outcome=outcome, 
                    dur_ms=expected_duration,
                    detail='Access blocked by YouTube')
            else:  # no_captions
                evt('stage_result',
                    stage=stage,
                    outcome=outcome,
                    dur_ms=expected_duration,
                    detail='No captions available')
        
        # 3. Video processing completion
        video_processed(
            video_id=video_id,
            outcome='success',
            duration_ms=3800,
            transcript_source='youtubei'
        )
        
        # 4. Job completion
        total_duration = int((time.time() - start_time) * 1000)
        job_finished(
            total_duration_ms=total_duration,
            processed_count=1,
            video_count=1,
            outcome='success',
            email_sent=True
        )
        
        # Parse and validate events
        events = self._parse_log_events()
        
        # Should have multiple events
        self.assertGreater(len(events), 5)
        
        # Verify job correlation
        for event in events:
            self.assertEqual(event['job_id'], job_id)
            self.assertEqual(event['video_id'], video_id)
        
        # Verify event sequence
        event_types = [event.get('event') for event in events]
        self.assertIn('job_received', event_types)
        self.assertIn('stage_result', event_types)
        self.assertIn('video_processed', event_types)
        self.assertIn('job_finished', event_types)
        
        # Verify stage results
        stage_results = [e for e in events if e.get('event') == 'stage_result']
        self.assertEqual(len(stage_results), 3)
        
        stages_found = {r['stage'] for r in stage_results}
        expected_stages = {'youtube-transcript-api', 'timedtext', 'youtubei'}
        self.assertEqual(stages_found, expected_stages)
        
        # Verify outcomes
        outcomes = {r['outcome'] for r in stage_results}
        expected_outcomes = {'no_captions', 'blocked', 'success'}
        self.assertEqual(outcomes, expected_outcomes)
    
    def test_pipeline_error_handling_integration(self):
        """Test pipeline error handling with structured logging."""
        job_id = 'j-error-test'
        video_id = 'error-video-456'
        
        set_job_ctx(job_id=job_id, video_id=video_id)
        
        # Start job
        job_received(video_count=1, use_cookies=False, proxy_enabled=True)
        
        # Simulate pipeline failure
        try:
            with StageTimer('youtubei', attempt=2, use_proxy=True, profile='mobile'):
                # Simulate network error
                raise ConnectionError("Connection timeout occurred")
        except ConnectionError as e:
            # Log job failure
            job_failed(
                total_duration_ms=5000,
                processed_count=0,
                video_count=1,
                error_type=classify_error_type(e),
                error_detail=str(e)
            )
        
        # Parse events
        events = self._parse_log_events()
        
        # Should have job_received, stage_start, stage_result (error), job_failed
        self.assertGreaterEqual(len(events), 4)
        
        # Find error events
        error_events = [e for e in events if e.get('outcome') == 'error']
        self.assertGreater(len(error_events), 0)
        
        # Find job failure event
        job_failed_events = [e for e in events if e.get('event') == 'job_failed']
        self.assertEqual(len(job_failed_events), 1)
        
        job_failed_event = job_failed_events[0]
        self.assertEqual(job_failed_event['error_type'], 'network_error')
        self.assertIn('timeout', job_failed_event['detail'])
    
    def test_multi_video_job_integration(self):
        """Test multi-video job processing with proper correlation."""
        job_id = 'j-multi-video'
        video_ids = ['video-1', 'video-2', 'video-3']
        
        # Start job
        set_job_ctx(job_id=job_id)
        job_received(video_count=len(video_ids), use_cookies=True, proxy_enabled=True)
        
        processed_count = 0
        
        # Process each video
        for i, video_id in enumerate(video_ids):
            # Set video context
            set_job_ctx(job_id=job_id, video_id=video_id)
            
            # Simulate different outcomes for each video
            if i == 0:
                # Success case
                with StageTimer('youtube-transcript-api', attempt=1):
                    time.sleep(0.005)
                
                video_processed(
                    video_id=video_id,
                    outcome='success',
                    duration_ms=500,
                    transcript_source='youtube-transcript-api'
                )
                processed_count += 1
                
            elif i == 1:
                # Failure case
                evt('stage_result',
                    stage='youtube-transcript-api',
                    outcome='error',
                    dur_ms=200,
                    detail='Video not found')
                
                video_processed(
                    video_id=video_id,
                    outcome='transcript_failed',
                    duration_ms=200
                )
                
            else:
                # Timeout case
                evt('stage_result',
                    stage='youtubei',
                    outcome='timeout',
                    dur_ms=30000,
                    detail='Request timed out')
                
                video_processed(
                    video_id=video_id,
                    outcome='transcript_failed',
                    duration_ms=30000
                )
        
        # Complete job
        set_job_ctx(job_id=job_id)  # Clear video_id for job-level event
        job_finished(
            total_duration_ms=30700,
            processed_count=processed_count,
            video_count=len(video_ids),
            outcome='partial_success'
        )
        
        # Parse and validate events
        events = self._parse_log_events()
        
        # Should have events for all videos
        video_events = {}
        for event in events:
            if 'video_id' in event:
                video_id = event['video_id']
                if video_id not in video_events:
                    video_events[video_id] = []
                video_events[video_id].append(event)
        
        # Should have events for all 3 videos
        self.assertEqual(len(video_events), 3)
        
        # Each video should have at least one event
        for video_id in video_ids:
            self.assertIn(video_id, video_events)
            self.assertGreater(len(video_events[video_id]), 0)
        
        # Job-level events should not have video_id
        job_events = [e for e in events if 'video_id' not in e]
        self.assertGreater(len(job_events), 0)
        
        # All events should have the same job_id
        for event in events:
            self.assertEqual(event['job_id'], job_id)
    
    def test_proxy_and_profile_context_integration(self):
        """Test proxy and profile context in pipeline logging."""
        job_id = 'j-proxy-test'
        video_id = 'proxy-video-789'
        
        set_job_ctx(job_id=job_id, video_id=video_id)
        
        # Simulate proxy attempts with different profiles
        profiles = ['desktop', 'mobile', 'tablet']
        
        for attempt, profile in enumerate(profiles, 1):
            use_proxy = attempt > 1  # First attempt direct, then proxy
            
            if attempt < 3:
                # Failed attempts
                evt('stage_result',
                    stage='youtubei',
                    outcome='blocked' if attempt == 1 else 'timeout',
                    dur_ms=5000 + (attempt * 1000),
                    detail=f'Attempt {attempt} failed',
                    attempt=attempt,
                    use_proxy=use_proxy,
                    profile=profile)
            else:
                # Successful attempt
                with StageTimer('youtubei', 
                              attempt=attempt, 
                              use_proxy=use_proxy, 
                              profile=profile):
                    time.sleep(0.01)
        
        # Parse events
        events = self._parse_log_events()
        
        # Find stage result events
        stage_results = [e for e in events if e.get('event') == 'stage_result']
        self.assertEqual(len(stage_results), 3)
        
        # Verify context fields are present
        for i, result in enumerate(stage_results):
            expected_attempt = i + 1
            expected_profile = profiles[i]
            expected_proxy = expected_attempt > 1
            
            self.assertEqual(result['attempt'], expected_attempt)
            self.assertEqual(result['profile'], expected_profile)
            self.assertEqual(result['use_proxy'], expected_proxy)
    
    def test_performance_metrics_separation_integration(self):
        """Test performance metrics channel separation in pipeline context."""
        from log_events import perf_evt, log_cpu_memory_metrics
        
        # Capture both main and performance logs
        main_buffer = StringIO()
        perf_buffer = StringIO()
        
        main_handler = logging.StreamHandler(main_buffer)
        perf_handler = logging.StreamHandler(perf_buffer)
        
        main_handler.setFormatter(JsonFormatter())
        perf_handler.setFormatter(JsonFormatter())
        
        # Configure loggers
        main_logger = logging.getLogger()
        perf_logger = logging.getLogger('perf')
        
        # Clear existing handlers
        for handler in main_logger.handlers[:]:
            main_logger.removeHandler(handler)
        for handler in perf_logger.handlers[:]:
            perf_logger.removeHandler(handler)
        
        # Ensure perf logger doesn't propagate to root logger
        perf_logger.propagate = False
        
        main_logger.addHandler(main_handler)
        perf_logger.addHandler(perf_handler)
        
        main_logger.setLevel(logging.INFO)
        perf_logger.setLevel(logging.INFO)
        
        # Set job context
        set_job_ctx(job_id='j-perf-test', video_id='perf-video-123')
        
        # Emit pipeline events
        job_received(video_count=1)
        
        with StageTimer('youtubei'):
            # Emit performance metrics during stage
            perf_evt(cpu=25.5, mem_mb=512, stage='youtubei')
            log_cpu_memory_metrics(cpu_percent=30.2, memory_mb=600)
            time.sleep(0.01)
        
        job_finished(total_duration_ms=1000, processed_count=1, video_count=1)
        
        # Parse outputs
        main_output = main_buffer.getvalue()
        perf_output = perf_buffer.getvalue()
        
        main_events = []
        for line in main_output.strip().split('\n'):
            if line:
                main_events.append(json.loads(line))
        
        perf_events = []
        for line in perf_output.strip().split('\n'):
            if line:
                perf_events.append(json.loads(line))
        
        # Verify separation
        self.assertGreater(len(main_events), 0)
        self.assertGreater(len(perf_events), 0)
        
        # Main events should not contain performance metrics
        for event in main_events:
            self.assertNotEqual(event.get('event'), 'performance_metric')
        
        # Performance events should all be performance metrics
        for event in perf_events:
            self.assertEqual(event.get('event'), 'performance_metric')
        
        # Performance events should still have job context
        for event in perf_events:
            if 'job_id' in event:  # Context might not be set for all perf events
                self.assertEqual(event['job_id'], 'j-perf-test')
        
        # Cleanup
        main_logger.removeHandler(main_handler)
        perf_logger.removeHandler(perf_handler)
    
    def test_ffmpeg_error_handling_integration(self):
        """Test FFmpeg error handling integration with structured logging."""
        job_id = 'j-ffmpeg-test'
        video_id = 'ffmpeg-video-456'
        
        set_job_ctx(job_id=job_id, video_id=video_id)
        
        # Simulate FFmpeg failure
        try:
            with StageTimer('ffmpeg', attempt=1):
                # Simulate FFmpeg error
                raise RuntimeError("FFmpeg process failed with exit code 1")
        except RuntimeError:
            pass
        
        # Log FFmpeg-specific error details
        evt('stage_result',
            stage='ffmpeg',
            outcome='error',
            dur_ms=5000,
            detail='exit_code=1',
            stderr_tail='Last 40 lines of stderr output...')
        
        # Parse events
        events = self._parse_log_events()
        
        # Find FFmpeg error events
        ffmpeg_errors = [e for e in events 
                        if e.get('stage') == 'ffmpeg' and e.get('outcome') == 'error']
        
        self.assertGreater(len(ffmpeg_errors), 0)
        
        # Verify FFmpeg-specific fields
        for error in ffmpeg_errors:
            if 'stderr_tail' in error:
                self.assertIn('stderr', error['stderr_tail'])
            if 'detail' in error and 'exit_code' in error['detail']:
                self.assertIn('exit_code=1', error['detail'])
    
    def test_backward_compatibility_integration(self):
        """Test backward compatibility with existing logging calls."""
        job_id = 'j-compat-test'
        video_id = 'compat-video-789'
        
        set_job_ctx(job_id=job_id, video_id=video_id)
        
        # Test that standard logging calls still work
        logger = logging.getLogger('compatibility_test')
        
        # Standard log calls
        logger.info("Starting transcript extraction")
        logger.warning("Retrying with proxy")
        logger.error("Failed to extract transcript")
        
        # Log calls with extra fields (structured logging style)
        logger.info("Stage completed", extra={
            'stage': 'youtubei',
            'outcome': 'success',
            'dur_ms': 1500
        })
        
        # Parse events
        events = self._parse_log_events()
        
        # Should have all log events
        self.assertEqual(len(events), 4)
        
        # All should have job context
        for event in events:
            self.assertEqual(event['job_id'], job_id)
            self.assertEqual(event['video_id'], video_id)
        
        # Structured event should have extra fields
        structured_events = [e for e in events if 'stage' in e]
        self.assertEqual(len(structured_events), 1)
        
        structured_event = structured_events[0]
        self.assertEqual(structured_event['stage'], 'youtubei')
        self.assertEqual(structured_event['outcome'], 'success')
        self.assertEqual(structured_event['dur_ms'], 1500)


if __name__ == '__main__':
    unittest.main(verbosity=2)