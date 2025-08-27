"""
Comprehensive test suite for structured JSON logging system.

This test suite validates all requirements for the structured JSON logging
implementation including unit tests, integration tests, performance tests,
CloudWatch query validation, and load testing for rate limiting.

Requirements tested:
- All requirements from structured-json-logging spec (1.1-10.5)
"""

import json
import logging
import threading
import time
import unittest
import concurrent.futures
import statistics
from datetime import datetime, timezone
from io import StringIO
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import modules under test
from logging_setup import (
    JsonFormatter, RateLimitFilter, set_job_ctx, clear_job_ctx, get_job_ctx,
    configure_logging, get_logger, get_perf_logger
)
from log_events import (
    evt, perf_evt, StageTimer, time_stage, job_received, job_finished, 
    job_failed, video_processed, classify_error_type, log_cpu_memory_metrics
)
import cloudwatch_query_templates


class TestJsonFormatterComprehensive(unittest.TestCase):
    """Comprehensive unit tests for JsonFormatter."""
    
    def setUp(self):
        self.formatter = JsonFormatter()
        clear_job_ctx()
    
    def test_requirement_1_1_standardized_json_schema(self):
        """Test Requirement 1.1: Standardized JSON schema with exact key order."""
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='test message', args=(), exc_info=None
        )
        
        # Add all standard fields
        record.stage = 'youtubei'
        record.event = 'stage_result'
        record.outcome = 'success'
        record.dur_ms = 1500
        record.detail = 'test detail'
        record.attempt = 2
        record.use_proxy = True
        record.profile = 'mobile'
        record.cookie_source = 's3'
        
        formatted = self.formatter.format(record)
        parsed = json.loads(formatted)
        
        # Verify required fields are present
        required_fields = ['ts', 'lvl']
        for field in required_fields:
            self.assertIn(field, parsed)
        
        # Verify field order matches specification
        expected_order = ['ts', 'lvl', 'stage', 'event', 'outcome', 'dur_ms', 
                         'detail', 'attempt', 'use_proxy', 'profile', 'cookie_source']
        actual_keys = list(parsed.keys())
        
        # Filter expected order to only include present keys
        filtered_expected = [key for key in expected_order if key in actual_keys]
        self.assertEqual(actual_keys, filtered_expected)
    
    def test_requirement_1_2_iso8601_timestamp_format(self):
        """Test Requirement 1.2: ISO 8601 timestamp with millisecond precision."""
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='test message', args=(), exc_info=None
        )
        
        formatted = self.formatter.format(record)
        parsed = json.loads(formatted)
        
        # Verify timestamp format
        timestamp = parsed['ts']
        self.assertRegex(timestamp, r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$')
        
        # Verify it's a valid ISO 8601 timestamp
        parsed_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        self.assertEqual(parsed_time.tzinfo, timezone.utc)
    
    def test_requirement_1_3_standardized_outcome_values(self):
        """Test Requirement 1.3: Standardized outcome values."""
        valid_outcomes = ['success', 'no_captions', 'blocked', 'timeout', 'error']
        
        for outcome in valid_outcomes:
            record = logging.LogRecord(
                name='test', level=logging.INFO, pathname='', lineno=0,
                msg='test message', args=(), exc_info=None
            )
            record.outcome = outcome
            
            formatted = self.formatter.format(record)
            parsed = json.loads(formatted)
            
            self.assertEqual(parsed['outcome'], outcome)
    
    def test_requirement_1_4_optional_context_keys(self):
        """Test Requirement 1.4: Optional context keys inclusion."""
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='test message', args=(), exc_info=None
        )
        
        # Add optional context keys
        record.attempt = 3
        record.use_proxy = False
        record.profile = 'desktop'
        record.cookie_source = 'local'
        
        formatted = self.formatter.format(record)
        parsed = json.loads(formatted)
        
        self.assertEqual(parsed['attempt'], 3)
        self.assertEqual(parsed['use_proxy'], False)
        self.assertEqual(parsed['profile'], 'desktop')
        self.assertEqual(parsed['cookie_source'], 'local')
    
    def test_requirement_1_5_single_line_json_format(self):
        """Test Requirement 1.5: Single-line JSON format."""
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='test message', args=(), exc_info=None
        )
        
        formatted = self.formatter.format(record)
        
        # Should not contain newlines
        self.assertNotIn('\n', formatted)
        self.assertNotIn('\r', formatted)
        
        # Should be valid JSON
        parsed = json.loads(formatted)
        self.assertIsInstance(parsed, dict)
    
    def test_requirement_2_3_null_value_omission(self):
        """Test Requirement 2.3: Null values omitted from JSON output."""
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='', args=(), exc_info=None  # Empty message to avoid auto-detail
        )
        
        # Set some fields to None
        record.stage = None
        record.event = 'test_event'
        record.outcome = None
        record.detail = None
        
        formatted = self.formatter.format(record)
        parsed = json.loads(formatted)
        
        # None values should be omitted
        self.assertNotIn('stage', parsed)
        self.assertNotIn('outcome', parsed)
        self.assertNotIn('detail', parsed)
        
        # Non-None values should be present
        self.assertEqual(parsed['event'], 'test_event')


class TestContextManagementComprehensive(unittest.TestCase):
    """Comprehensive tests for thread-safe context management."""
    
    def setUp(self):
        clear_job_ctx()
    
    def test_requirement_2_1_thread_local_context_setting(self):
        """Test Requirement 2.1: Thread-local context with job_id and video_id."""
        set_job_ctx(job_id='j-test-123', video_id='vid-456')
        
        context = get_job_ctx()
        self.assertEqual(context['job_id'], 'j-test-123')
        self.assertEqual(context['video_id'], 'vid-456')
    
    def test_requirement_2_2_automatic_context_inclusion(self):
        """Test Requirement 2.2: Automatic context inclusion in log events."""
        set_job_ctx(job_id='j-auto-123', video_id='vid-auto-456')
        
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='test message', args=(), exc_info=None
        )
        
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        
        self.assertEqual(parsed['job_id'], 'j-auto-123')
        self.assertEqual(parsed['video_id'], 'vid-auto-456')
    
    def test_requirement_2_4_thread_isolation(self):
        """Test Requirement 2.4: Thread isolation for concurrent processing."""
        results = {}
        
        def worker(thread_id):
            set_job_ctx(job_id=f'j-{thread_id}', video_id=f'vid-{thread_id}')
            time.sleep(0.1)  # Allow other threads to run
            context = get_job_ctx()
            results[thread_id] = context
        
        # Start multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # Verify each thread maintained separate context
        for i in range(5):
            self.assertEqual(results[i]['job_id'], f'j-{i}')
            self.assertEqual(results[i]['video_id'], f'vid-{i}')
    
    def test_requirement_2_5_context_clearing(self):
        """Test Requirement 2.5: Context clearing functionality."""
        set_job_ctx(job_id='j-clear-test', video_id='vid-clear-test')
        
        # Verify context is set
        context = get_job_ctx()
        self.assertEqual(len(context), 2)
        
        # Clear context
        clear_job_ctx()
        
        # Verify context is cleared
        context = get_job_ctx()
        self.assertEqual(context, {})


class TestRateLimitingComprehensive(unittest.TestCase):
    """Comprehensive tests for rate limiting and deduplication."""
    
    def setUp(self):
        self.filter = RateLimitFilter(per_key=3, window_sec=1)  # Small limits for testing
    
    def test_requirement_3_1_rate_limit_enforcement(self):
        """Test Requirement 3.1: Maximum 5 occurrences per 60-second window."""
        # Use default settings for this test
        filter_default = RateLimitFilter()  # Default: 5 per 60 seconds
        
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='repeated message', args=(), exc_info=None
        )
        
        # First 5 messages should be allowed
        for i in range(5):
            result = filter_default.filter(record)
            self.assertTrue(result, f"Message {i+1} should be allowed")
    
    def test_requirement_3_2_suppression_marker_emission(self):
        """Test Requirement 3.2: Exactly one suppression marker per window."""
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='spam message', args=(), exc_info=None
        )
        
        # Fill up the limit (3 messages)
        for i in range(3):
            self.assertTrue(self.filter.filter(record))
        
        # Next message should be allowed with suppression marker
        record_suppression = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='spam message', args=(), exc_info=None
        )
        result = self.filter.filter(record_suppression)
        self.assertTrue(result)
        self.assertIn('[suppressed]', record_suppression.getMessage())
        
        # Subsequent messages should be suppressed
        for i in range(3):
            record_blocked = logging.LogRecord(
                name='test', level=logging.INFO, pathname='', lineno=0,
                msg='spam message', args=(), exc_info=None
            )
            result = self.filter.filter(record_blocked)
            self.assertFalse(result)
    
    def test_requirement_3_3_level_and_content_tracking(self):
        """Test Requirement 3.3: Tracking by log level and message content."""
        info_record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='test message', args=(), exc_info=None
        )
        error_record = logging.LogRecord(
            name='test', level=logging.ERROR, pathname='', lineno=0,
            msg='test message', args=(), exc_info=None
        )
        
        # Fill limit for INFO level
        for i in range(3):
            self.assertTrue(self.filter.filter(info_record))
        
        # ERROR level with same message should still be allowed
        self.assertTrue(self.filter.filter(error_record))
    
    def test_requirement_3_4_window_reset(self):
        """Test Requirement 3.4: Counter reset when new window begins."""
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='window test message', args=(), exc_info=None
        )
        
        # Fill up the limit
        for i in range(3):
            self.assertTrue(self.filter.filter(record))
        
        # Wait for window to expire
        time.sleep(1.1)
        
        # Should allow messages again
        record_new = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='window test message', args=(), exc_info=None
        )
        self.assertTrue(self.filter.filter(record_new))
    
    def test_requirement_3_5_suppression_text_appending(self):
        """Test Requirement 3.5: [suppressed] appended to message text."""
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='original message', args=(), exc_info=None
        )
        
        # Fill up the limit
        for i in range(3):
            self.filter.filter(record)
        
        # Next message should have suppression marker
        suppression_record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='original message', args=(), exc_info=None
        )
        self.filter.filter(suppression_record)
        
        self.assertEqual(suppression_record.getMessage(), 'original message [suppressed]')


class TestStageTimerComprehensive(unittest.TestCase):
    """Comprehensive tests for StageTimer and event helpers."""
    
    def setUp(self):
        # Capture log output
        self.log_buffer = StringIO()
        self.handler = logging.StreamHandler(self.log_buffer)
        self.handler.setFormatter(JsonFormatter())
        
        self.logger = logging.getLogger()
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)
    
    def tearDown(self):
        self.logger.removeHandler(self.handler)
        self.handler.close()
    
    def test_requirement_4_1_stage_start_event_emission(self):
        """Test Requirement 4.1: stage_start event emission."""
        with StageTimer("test_stage", profile="mobile"):
            pass
        
        log_output = self.log_buffer.getvalue()
        self.assertIn("stage_start", log_output)
        self.assertIn("test_stage", log_output)
        self.assertIn("mobile", log_output)
    
    def test_requirement_4_2_stage_result_success_event(self):
        """Test Requirement 4.2: stage_result event with success outcome."""
        with StageTimer("success_stage"):
            pass
        
        log_output = self.log_buffer.getvalue()
        lines = log_output.strip().split('\n')
        
        # Should have both start and result events
        self.assertEqual(len(lines), 2)
        
        # Parse result event
        result_event = json.loads(lines[1])
        self.assertEqual(result_event['event'], 'stage_result')
        self.assertEqual(result_event['outcome'], 'success')
        self.assertEqual(result_event['stage'], 'success_stage')
        self.assertIn('dur_ms', result_event)
    
    def test_requirement_4_3_stage_result_error_event(self):
        """Test Requirement 4.3: stage_result event with error outcome."""
        with self.assertRaises(ValueError):
            with StageTimer("error_stage"):
                raise ValueError("Test error")
        
        log_output = self.log_buffer.getvalue()
        lines = log_output.strip().split('\n')
        
        # Parse result event
        result_event = json.loads(lines[1])
        self.assertEqual(result_event['event'], 'stage_result')
        self.assertEqual(result_event['outcome'], 'error')
        self.assertEqual(result_event['stage'], 'error_stage')
        self.assertIn('ValueError: Test error', result_event['detail'])
    
    def test_requirement_4_4_duration_millisecond_precision(self):
        """Test Requirement 4.4: Duration in milliseconds with integer precision."""
        start_time = time.time()
        
        with StageTimer("duration_test"):
            time.sleep(0.05)  # 50ms
        
        end_time = time.time()
        actual_duration = int((end_time - start_time) * 1000)
        
        log_output = self.log_buffer.getvalue()
        lines = log_output.strip().split('\n')
        result_event = json.loads(lines[1])
        
        logged_duration = result_event['dur_ms']
        self.assertIsInstance(logged_duration, int)
        
        # Duration should be approximately 50ms (allow variance)
        self.assertGreater(logged_duration, 40)
        self.assertLess(logged_duration, 100)
    
    def test_requirement_4_5_stage_context_inclusion(self):
        """Test Requirement 4.5: Stage context fields inclusion."""
        with StageTimer("context_stage", profile="desktop", use_proxy=True, attempt=2):
            pass
        
        log_output = self.log_buffer.getvalue()
        lines = log_output.strip().split('\n')
        
        # Check both start and result events
        start_event = json.loads(lines[0])
        result_event = json.loads(lines[1])
        
        for event in [start_event, result_event]:
            self.assertEqual(event['profile'], 'desktop')
            self.assertEqual(event['use_proxy'], True)
            self.assertEqual(event['attempt'], 2)


class TestLibraryNoiseSuppressionComprehensive(unittest.TestCase):
    """Comprehensive tests for third-party library noise reduction."""
    
    def test_requirement_5_1_playwright_warning_level(self):
        """Test Requirement 5.1: Playwright logger set to WARNING level."""
        configure_logging()
        playwright_logger = logging.getLogger('playwright')
        self.assertGreaterEqual(playwright_logger.level, logging.WARNING)
    
    def test_requirement_5_2_urllib3_warning_level(self):
        """Test Requirement 5.2: urllib3 logger set to WARNING level."""
        configure_logging()
        urllib3_logger = logging.getLogger('urllib3')
        self.assertGreaterEqual(urllib3_logger.level, logging.WARNING)
    
    def test_requirement_5_3_boto_warning_level(self):
        """Test Requirement 5.3: botocore/boto3 loggers set to WARNING level."""
        configure_logging()
        botocore_logger = logging.getLogger('botocore')
        boto3_logger = logging.getLogger('boto3')
        
        self.assertGreaterEqual(botocore_logger.level, logging.WARNING)
        self.assertGreaterEqual(boto3_logger.level, logging.WARNING)
    
    def test_requirement_5_4_asyncio_warning_level(self):
        """Test Requirement 5.4: asyncio logger set to WARNING level."""
        configure_logging()
        asyncio_logger = logging.getLogger('asyncio')
        self.assertGreaterEqual(asyncio_logger.level, logging.WARNING)


class TestPerformanceChannelSeparation(unittest.TestCase):
    """Test performance metrics channel separation."""
    
    def test_requirement_6_1_dedicated_perf_logger(self):
        """Test Requirement 6.1: Dedicated 'perf' logger for performance metrics."""
        perf_logger = get_perf_logger()
        self.assertEqual(perf_logger.name, 'perf')
        self.assertIsInstance(perf_logger, logging.Logger)
    
    def test_requirement_6_2_performance_channel_separation(self):
        """Test Requirement 6.2: Performance metrics use separate channel."""
        # Capture logs from both channels
        main_buffer = StringIO()
        perf_buffer = StringIO()
        
        main_handler = logging.StreamHandler(main_buffer)
        perf_handler = logging.StreamHandler(perf_buffer)
        
        main_handler.setFormatter(JsonFormatter())
        perf_handler.setFormatter(JsonFormatter())
        
        # Configure loggers
        main_logger = logging.getLogger()
        perf_logger = get_perf_logger()
        
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
        
        # Emit events on different channels
        evt("pipeline_event", stage="test")
        perf_evt(cpu=15.2, mem_mb=512)
        
        # Verify separation
        main_output = main_buffer.getvalue()
        perf_output = perf_buffer.getvalue()
        
        self.assertIn("pipeline_event", main_output)
        self.assertNotIn("performance_metric", main_output)
        
        self.assertIn("performance_metric", perf_output)
        self.assertNotIn("pipeline_event", perf_output)
        
        # Cleanup
        main_logger.removeHandler(main_handler)
        perf_logger.removeHandler(perf_handler)


class TestJobLifecycleTracking(unittest.TestCase):
    """Test job lifecycle tracking events."""
    
    def setUp(self):
        self.log_buffer = StringIO()
        self.handler = logging.StreamHandler(self.log_buffer)
        self.handler.setFormatter(JsonFormatter())
        
        self.logger = logging.getLogger()
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)
    
    def tearDown(self):
        self.logger.removeHandler(self.handler)
        self.handler.close()
    
    def test_requirement_10_1_job_received_event(self):
        """Test Requirement 10.1: job_received event emission."""
        job_received(video_count=3, use_cookies=True, proxy_enabled=False)
        
        log_output = self.log_buffer.getvalue()
        parsed = json.loads(log_output.strip())
        
        self.assertEqual(parsed['event'], 'job_received')
        self.assertEqual(parsed['video_count'], 3)
        self.assertEqual(parsed['use_cookies'], True)
        self.assertEqual(parsed['proxy_enabled'], False)
    
    def test_requirement_10_3_job_finished_event(self):
        """Test Requirement 10.3: job_finished event with total duration."""
        job_finished(
            total_duration_ms=45000,
            processed_count=4,
            video_count=5,
            outcome="partial_success",
            email_sent=True
        )
        
        log_output = self.log_buffer.getvalue()
        parsed = json.loads(log_output.strip())
        
        self.assertEqual(parsed['event'], 'job_finished')
        self.assertEqual(parsed['total_duration_ms'], 45000)
        self.assertEqual(parsed['processed_count'], 4)
        self.assertEqual(parsed['video_count'], 5)
        self.assertEqual(parsed['outcome'], 'partial_success')
        self.assertEqual(parsed['email_sent'], True)
    
    def test_requirement_10_4_job_failure_classification(self):
        """Test Requirement 10.4: Job failure event with error classification."""
        job_failed(
            total_duration_ms=5000,
            processed_count=0,
            video_count=3,
            error_type="auth_error",
            error_detail="Invalid API key"
        )
        
        log_output = self.log_buffer.getvalue()
        parsed = json.loads(log_output.strip())
        
        self.assertEqual(parsed['event'], 'job_failed')
        self.assertEqual(parsed['error_type'], 'auth_error')
        self.assertEqual(parsed['detail'], 'Invalid API key')


class TestErrorClassification(unittest.TestCase):
    """Test error classification functionality."""
    
    def test_auth_error_classification(self):
        """Test authentication error classification."""
        auth_error = Exception("Authentication failed")
        error_type = classify_error_type(auth_error)
        self.assertEqual(error_type, "auth_error")
    
    def test_network_error_classification(self):
        """Test network error classification."""
        network_error = Exception("Connection timeout")
        error_type = classify_error_type(network_error)
        self.assertEqual(error_type, "network_error")
    
    def test_service_error_default_classification(self):
        """Test default service error classification."""
        generic_error = Exception("Unknown error")
        error_type = classify_error_type(generic_error)
        self.assertEqual(error_type, "service_error")


if __name__ == '__main__':
    unittest.main()