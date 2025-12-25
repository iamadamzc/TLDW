"""
Integration tests for job lifecycle tracking with structured JSON logging.

Tests the complete job lifecycle from job_received to job_finished events,
including video processing events and error classification.
"""

import unittest
import logging
import json
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from io import StringIO
from contextlib import contextmanager

# Import the modules we're testing
from log_events import (
    job_received, job_finished, job_failed, video_processed, 
    classify_error_type, evt
)
from logging_setup import configure_logging, set_job_ctx, clear_job_ctx, JsonFormatter


class TestJobLifecycleTracking(unittest.TestCase):
    """Test job lifecycle event tracking and structured logging."""
    
    def setUp(self):
        """Set up test environment with JSON logging."""
        # Capture log output
        self.log_stream = StringIO()
        self.handler = logging.StreamHandler(self.log_stream)
        self.handler.setFormatter(JsonFormatter())
        
        # Configure logger
        self.logger = logging.getLogger()
        self.logger.handlers.clear()
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)
        
        # Clear any existing context
        clear_job_ctx()
    
    def tearDown(self):
        """Clean up test environment."""
        clear_job_ctx()
        self.logger.handlers.clear()
    
    def get_log_events(self):
        """Parse logged JSON events."""
        log_content = self.log_stream.getvalue()
        events = []
        for line in log_content.strip().split('\n'):
            if line.strip():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return events
    
    def test_job_received_event(self):
        """Test job_received event emission."""
        set_job_ctx(job_id="test-job-123")
        
        job_received(video_count=5, use_cookies=True, proxy_enabled=False)
        
        events = self.get_log_events()
        self.assertEqual(len(events), 1)
        
        event = events[0]
        self.assertEqual(event['event'], 'job_received')
        self.assertEqual(event['job_id'], 'test-job-123')
        self.assertEqual(event['video_count'], 5)
        self.assertTrue(event['use_cookies'])
        self.assertFalse(event['proxy_enabled'])
        self.assertIn('ts', event)
        self.assertEqual(event['lvl'], 'INFO')
    
    def test_job_finished_success_event(self):
        """Test job_finished event for successful job."""
        set_job_ctx(job_id="test-job-456")
        
        job_finished(
            total_duration_ms=45000,
            processed_count=5,
            video_count=5,
            outcome="success",
            email_sent=True,
            error_count=0
        )
        
        events = self.get_log_events()
        self.assertEqual(len(events), 1)
        
        event = events[0]
        self.assertEqual(event['event'], 'job_finished')
        self.assertEqual(event['job_id'], 'test-job-456')
        self.assertEqual(event['total_duration_ms'], 45000)
        self.assertEqual(event['processed_count'], 5)
        self.assertEqual(event['video_count'], 5)
        self.assertEqual(event['outcome'], 'success')
        self.assertTrue(event['email_sent'])
        self.assertEqual(event['error_count'], 0)
    
    def test_job_finished_partial_success_event(self):
        """Test job_finished event for partially successful job."""
        set_job_ctx(job_id="test-job-789")
        
        job_finished(
            total_duration_ms=60000,
            processed_count=3,
            video_count=5,
            outcome="partial_success",
            email_sent=True,
            error_count=2
        )
        
        events = self.get_log_events()
        self.assertEqual(len(events), 1)
        
        event = events[0]
        self.assertEqual(event['event'], 'job_finished')
        self.assertEqual(event['outcome'], 'partial_success')
        self.assertEqual(event['processed_count'], 3)
        self.assertEqual(event['error_count'], 2)
    
    def test_job_failed_event(self):
        """Test job_failed event for critical job errors."""
        set_job_ctx(job_id="test-job-error")
        
        job_failed(
            total_duration_ms=5000,
            processed_count=0,
            video_count=5,
            error_type="auth_error",
            error_detail="User not found"
        )
        
        events = self.get_log_events()
        self.assertEqual(len(events), 1)
        
        event = events[0]
        self.assertEqual(event['event'], 'job_failed')
        self.assertEqual(event['job_id'], 'test-job-error')
        self.assertEqual(event['total_duration_ms'], 5000)
        self.assertEqual(event['processed_count'], 0)
        self.assertEqual(event['video_count'], 5)
        self.assertEqual(event['error_type'], 'auth_error')
        self.assertEqual(event['detail'], 'User not found')
    
    def test_video_processed_success_event(self):
        """Test video_processed event for successful video processing."""
        set_job_ctx(job_id="test-job-video", video_id="abc123")
        
        video_processed(
            video_id="abc123",
            outcome="success",
            duration_ms=8500,
            transcript_source="youtubei",
            summary_length=250,
            progress="1/5"
        )
        
        events = self.get_log_events()
        self.assertEqual(len(events), 1)
        
        event = events[0]
        self.assertEqual(event['event'], 'video_processed')
        self.assertEqual(event['job_id'], 'test-job-video')
        self.assertEqual(event['video_id'], 'abc123')
        self.assertEqual(event['outcome'], 'success')
        self.assertEqual(event['dur_ms'], 8500)
        self.assertEqual(event['transcript_source'], 'youtubei')
        self.assertEqual(event['summary_length'], 250)
        self.assertEqual(event['progress'], '1/5')
    
    def test_video_processed_error_event(self):
        """Test video_processed event for failed video processing."""
        set_job_ctx(job_id="test-job-video-error", video_id="def456")
        
        video_processed(
            video_id="def456",
            outcome="error",
            duration_ms=2000,
            transcript_source="none",
            error_type="network_error",
            error_detail="Connection timeout",
            progress="2/5"
        )
        
        events = self.get_log_events()
        self.assertEqual(len(events), 1)
        
        event = events[0]
        self.assertEqual(event['event'], 'video_processed')
        self.assertEqual(event['video_id'], 'def456')
        self.assertEqual(event['outcome'], 'error')
        self.assertEqual(event['dur_ms'], 2000)
        self.assertEqual(event['transcript_source'], 'none')
        self.assertEqual(event['error_type'], 'network_error')
        self.assertEqual(event['error_detail'], 'Connection timeout')
    
    def test_error_classification(self):
        """Test error type classification for different exception types."""
        # Authentication errors
        auth_error = Exception("Authentication token expired")
        self.assertEqual(classify_error_type(auth_error), "auth_error")
        
        # Network errors
        network_error = Exception("Connection timeout occurred")
        self.assertEqual(classify_error_type(network_error), "network_error")
        
        # Transcript errors
        transcript_error = Exception("YouTube transcript not available")
        self.assertEqual(classify_error_type(transcript_error), "transcript_error")
        
        # Summarization errors
        summary_error = Exception("OpenAI API rate limit exceeded")
        self.assertEqual(classify_error_type(summary_error), "summarization_error")
        
        # Email errors
        email_error = Exception("Resend API key invalid")
        self.assertEqual(classify_error_type(email_error), "email_error")
        
        # Configuration errors
        config_error = Exception("Missing API key configuration")
        self.assertEqual(classify_error_type(config_error), "config_error")
        
        # Resource errors
        resource_error = Exception("Memory limit exceeded")
        self.assertEqual(classify_error_type(resource_error), "resource_error")
        
        # Generic service error
        generic_error = Exception("Unexpected service failure")
        self.assertEqual(classify_error_type(generic_error), "service_error")
    
    def test_complete_job_lifecycle(self):
        """Test complete job lifecycle with multiple events."""
        job_id = "complete-job-test"
        set_job_ctx(job_id=job_id)
        
        # Job starts
        job_received(video_count=3, use_cookies=False, proxy_enabled=True)
        
        # Process first video successfully
        set_job_ctx(job_id=job_id, video_id="video1")
        video_processed("video1", "success", 5000, "yt_api", progress="1/3")
        
        # Process second video with error
        set_job_ctx(job_id=job_id, video_id="video2")
        video_processed("video2", "error", 3000, "none", 
                       error_type="transcript_error", error_detail="No captions available",
                       progress="2/3")
        
        # Process third video successfully
        set_job_ctx(job_id=job_id, video_id="video3")
        video_processed("video3", "success", 7000, "timedtext", progress="3/3")
        
        # Job finishes with partial success
        set_job_ctx(job_id=job_id)
        job_finished(15000, 2, 3, "partial_success", email_sent=True, error_count=1)
        
        events = self.get_log_events()
        self.assertEqual(len(events), 5)
        
        # Verify event sequence
        self.assertEqual(events[0]['event'], 'job_received')
        self.assertEqual(events[1]['event'], 'video_processed')
        self.assertEqual(events[1]['video_id'], 'video1')
        self.assertEqual(events[1]['outcome'], 'success')
        
        self.assertEqual(events[2]['event'], 'video_processed')
        self.assertEqual(events[2]['video_id'], 'video2')
        self.assertEqual(events[2]['outcome'], 'error')
        
        self.assertEqual(events[3]['event'], 'video_processed')
        self.assertEqual(events[3]['video_id'], 'video3')
        self.assertEqual(events[3]['outcome'], 'success')
        
        self.assertEqual(events[4]['event'], 'job_finished')
        self.assertEqual(events[4]['outcome'], 'partial_success')
        
        # Verify all events have the same job_id
        for event in events:
            self.assertEqual(event['job_id'], job_id)
    
    def test_thread_isolation(self):
        """Test that job context is properly isolated between threads."""
        # This test verifies that thread-local context works correctly
        # We'll use a simpler approach with the main logger
        
        results = {}
        
        def job_thread_1():
            set_job_ctx(job_id="job-thread-1")
            from logging_setup import get_job_ctx
            results['thread1'] = get_job_ctx()
        
        def job_thread_2():
            set_job_ctx(job_id="job-thread-2")
            from logging_setup import get_job_ctx
            results['thread2'] = get_job_ctx()
        
        # Run threads concurrently
        thread1 = threading.Thread(target=job_thread_1)
        thread2 = threading.Thread(target=job_thread_2)
        
        thread1.start()
        thread2.start()
        
        thread1.join()
        thread2.join()
        
        # Verify thread isolation
        self.assertEqual(results['thread1']['job_id'], 'job-thread-1')
        self.assertEqual(results['thread2']['job_id'], 'job-thread-2')
        
        # Verify contexts are different
        self.assertNotEqual(results['thread1'], results['thread2'])
    
    def test_event_field_order_consistency(self):
        """Test that events maintain consistent field order."""
        set_job_ctx(job_id="field-order-test", video_id="test123")
        
        job_received(video_count=1, config_param="test")
        video_processed("test123", "success", 1000, "yt_api")
        job_finished(5000, 1, 1, "success", email_sent=True)
        
        events = self.get_log_events()
        
        # Verify all events have required base fields in correct order
        for event in events:
            keys = list(event.keys())
            
            # Check that base fields appear first
            expected_start = ['ts', 'lvl']
            actual_start = keys[:2]
            self.assertEqual(actual_start, expected_start)
            
            # Check that job_id appears early (after ts, lvl)
            self.assertIn('job_id', keys)
            job_id_index = keys.index('job_id')
            self.assertLessEqual(job_id_index, 3)  # Should be within first few fields
    
    def test_duration_calculation_accuracy(self):
        """Test that duration calculations are accurate and in milliseconds."""
        set_job_ctx(job_id="duration-test")
        
        # Test with known duration
        video_processed("test123", "success", 1500, "yt_api")
        
        events = self.get_log_events()
        self.assertEqual(len(events), 1)
        
        event = events[0]
        self.assertEqual(event['dur_ms'], 1500)
        self.assertIsInstance(event['dur_ms'], int)  # Should be integer milliseconds


class TestJobLifecycleIntegration(unittest.TestCase):
    """Integration tests for job lifecycle with actual job processing simulation."""
    
    def setUp(self):
        """Set up integration test environment."""
        # Configure JSON logging
        configure_logging("INFO", use_json=True)
        
        # Capture log output
        self.log_stream = StringIO()
        self.handler = logging.StreamHandler(self.log_stream)
        self.handler.setFormatter(JsonFormatter())
        
        # Add handler to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(self.handler)
        
        clear_job_ctx()
    
    def tearDown(self):
        """Clean up integration test environment."""
        clear_job_ctx()
        # Remove our test handler
        root_logger = logging.getLogger()
        if self.handler in root_logger.handlers:
            root_logger.removeHandler(self.handler)
    
    def get_log_events(self):
        """Parse logged JSON events."""
        log_content = self.log_stream.getvalue()
        events = []
        for line in log_content.strip().split('\n'):
            if line.strip():
                try:
                    event = json.loads(line)
                    events.append(event)
                except json.JSONDecodeError:
                    continue
        return events
    
    @patch('routes.YouTubeService')
    @patch('routes.TranscriptService')
    @patch('routes.VideoSummarizer')
    @patch('routes.EmailService')
    def test_simulated_job_processing(self, mock_email, mock_summarizer, mock_transcript, mock_youtube):
        """Test job lifecycle events in simulated job processing."""
        # Mock service responses
        mock_youtube_instance = Mock()
        mock_youtube_instance.get_video_details.return_value = {
            "id": "test123",
            "title": "Test Video",
            "thumbnail": "http://example.com/thumb.jpg"
        }
        mock_youtube.return_value = mock_youtube_instance
        
        mock_transcript_instance = Mock()
        mock_transcript_instance.get_transcript.return_value = "Test transcript content"
        mock_transcript.return_value = mock_transcript_instance
        
        mock_summarizer_instance = Mock()
        mock_summarizer_instance.summarize_video.return_value = "Test summary"
        mock_summarizer.return_value = mock_summarizer_instance
        
        mock_email_instance = Mock()
        mock_email_instance.send_digest_email.return_value = True
        mock_email.return_value = mock_email_instance
        
        # Simulate job processing
        job_id = "integration-test-job"
        video_ids = ["test123", "test456"]
        
        # Import and use the lifecycle functions
        from log_events import job_received, job_finished, video_processed
        
        set_job_ctx(job_id=job_id)
        
        # Start job
        job_received(video_count=len(video_ids), use_cookies=False)
        
        # Process videos
        for i, vid in enumerate(video_ids):
            set_job_ctx(job_id=job_id, video_id=vid)
            
            # Simulate processing time
            time.sleep(0.01)  # 10ms
            
            video_processed(
                video_id=vid,
                outcome="success",
                duration_ms=10,
                transcript_source="yt_api",
                progress=f"{i+1}/{len(video_ids)}"
            )
        
        # Finish job
        set_job_ctx(job_id=job_id)
        job_finished(
            total_duration_ms=50,
            processed_count=2,
            video_count=2,
            outcome="success",
            email_sent=True,
            error_count=0
        )
        
        # Verify events
        events = self.get_log_events()
        
        # Should have: job_received + 2 video_processed + job_finished = 4 events
        lifecycle_events = [e for e in events if e.get('event') in 
                           ['job_received', 'video_processed', 'job_finished']]
        
        self.assertGreaterEqual(len(lifecycle_events), 4)
        
        # Verify job_received event
        job_received_events = [e for e in lifecycle_events if e.get('event') == 'job_received']
        self.assertEqual(len(job_received_events), 1)
        self.assertEqual(job_received_events[0]['video_count'], 2)
        
        # Verify video_processed events
        video_events = [e for e in lifecycle_events if e.get('event') == 'video_processed']
        self.assertEqual(len(video_events), 2)
        
        # Verify job_finished event
        job_finished_events = [e for e in lifecycle_events if e.get('event') == 'job_finished']
        self.assertEqual(len(job_finished_events), 1)
        self.assertEqual(job_finished_events[0]['outcome'], 'success')
        self.assertEqual(job_finished_events[0]['processed_count'], 2)


if __name__ == '__main__':
    unittest.main()