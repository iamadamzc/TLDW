"""
Unit tests for logging_setup.py core logging infrastructure.

Tests JsonFormatter field order, timestamp format, context management,
rate limiting, and library noise suppression.
"""

import json
import logging
import threading
import time
import unittest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logging_setup import (
    JsonFormatter, RateLimitFilter, set_job_ctx, clear_job_ctx, get_job_ctx,
    configure_logging, get_logger, get_perf_logger
)


class TestJsonFormatter(unittest.TestCase):
    """Test JsonFormatter field order and timestamp format."""
    
    def setUp(self):
        self.formatter = JsonFormatter()
        clear_job_ctx()
    
    def test_field_order_consistency(self):
        """Test that JSON fields are in the expected order."""
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='test message', args=(), exc_info=None
        )
        
        # Add all possible fields
        record.stage = 'test_stage'
        record.event = 'test_event'
        record.outcome = 'success'
        record.dur_ms = 1500
        record.detail = 'test detail'
        record.attempt = 2
        record.use_proxy = True
        record.profile = 'mobile'
        record.cookie_source = 's3'
        
        formatted = self.formatter.format(record)
        parsed = json.loads(formatted)
        
        # Check that required fields are present
        self.assertIn('ts', parsed)
        self.assertIn('lvl', parsed)
        
        # Check field order by converting back to JSON and comparing key order
        expected_order = ['ts', 'lvl', 'stage', 'event', 'outcome', 'dur_ms', 'detail', 'attempt', 'use_proxy', 'profile', 'cookie_source']
        actual_keys = list(parsed.keys())
        
        # Filter expected order to only include keys that are present
        filtered_expected = [key for key in expected_order if key in actual_keys]
        
        self.assertEqual(actual_keys, filtered_expected)
    
    def test_timestamp_format(self):
        """Test ISO 8601 timestamp format with millisecond precision."""
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='test message', args=(), exc_info=None
        )
        
        formatted = self.formatter.format(record)
        parsed = json.loads(formatted)
        
        # Check timestamp format
        timestamp = parsed['ts']
        self.assertRegex(timestamp, r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$')
        
        # Verify it's a valid ISO 8601 timestamp
        parsed_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        self.assertEqual(parsed_time.tzinfo, timezone.utc)
    
    def test_context_injection(self):
        """Test automatic context injection from thread-local storage."""
        # Set context
        set_job_ctx(job_id='j-test-123', video_id='abc123')
        
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='test message', args=(), exc_info=None
        )
        
        formatted = self.formatter.format(record)
        parsed = json.loads(formatted)
        
        self.assertEqual(parsed['job_id'], 'j-test-123')
        self.assertEqual(parsed['video_id'], 'abc123')
    
    def test_null_value_omission(self):
        """Test that null/None values are omitted from JSON output."""
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='test message', args=(), exc_info=None
        )
        
        # Set some fields to None
        record.stage = None
        record.event = 'test_event'
        record.outcome = None
        
        formatted = self.formatter.format(record)
        parsed = json.loads(formatted)
        
        # None values should be omitted
        self.assertNotIn('stage', parsed)
        self.assertNotIn('outcome', parsed)
        # Non-None values should be present
        self.assertEqual(parsed['event'], 'test_event')
    
    def test_fallback_on_error(self):
        """Test fallback to basic JSON on formatting errors."""
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='test message', args=(), exc_info=None
        )
        
        # Create a problematic attribute that can't be JSON serialized
        record.problematic = object()
        
        with patch('json.dumps', side_effect=TypeError("Not serializable")):
            formatted = self.formatter.format(record)
            parsed = json.loads(formatted)
            
            # Should still produce valid JSON with basic fields
            self.assertIn('ts', parsed)
            self.assertIn('lvl', parsed)
            self.assertIn('detail', parsed)


class TestRateLimitFilter(unittest.TestCase):
    """Test RateLimitFilter rate limiting and suppression behavior."""
    
    def setUp(self):
        self.filter = RateLimitFilter(per_key=3, window_sec=1)  # Smaller limits for testing
    
    def test_allows_messages_within_limit(self):
        """Test that messages within rate limit are allowed."""
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='test message', args=(), exc_info=None
        )
        
        # First 3 messages should be allowed
        for i in range(3):
            self.assertTrue(self.filter.filter(record))
    
    def test_suppresses_messages_over_limit(self):
        """Test that messages over rate limit are suppressed."""
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='test message', args=(), exc_info=None
        )
        
        # First 3 messages allowed
        for i in range(3):
            self.assertTrue(self.filter.filter(record))
        
        # 4th message should be allowed with suppression marker
        result = self.filter.filter(record)
        self.assertTrue(result)
        self.assertIn('[suppressed]', record.getMessage())
        
        # 5th message should be suppressed
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='test message', args=(), exc_info=None
        )
        self.assertFalse(self.filter.filter(record))
    
    def test_window_reset(self):
        """Test that rate limit resets after window expires."""
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='test message', args=(), exc_info=None
        )
        
        # Fill up the limit
        for i in range(3):
            self.assertTrue(self.filter.filter(record))
        
        # Next message should trigger suppression
        self.assertTrue(self.filter.filter(record))
        
        # Wait for window to expire
        time.sleep(1.1)
        
        # Should allow messages again
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='test message', args=(), exc_info=None
        )
        self.assertTrue(self.filter.filter(record))
    
    def test_different_keys_separate_limits(self):
        """Test that different message keys have separate rate limits."""
        record1 = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='message type 1', args=(), exc_info=None
        )
        record2 = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='message type 2', args=(), exc_info=None
        )
        
        # Fill limit for first message type
        for i in range(3):
            self.assertTrue(self.filter.filter(record1))
        
        # Second message type should still be allowed
        self.assertTrue(self.filter.filter(record2))
    
    def test_thread_safety(self):
        """Test that rate limiting is thread-safe."""
        results = []
        
        def worker():
            for i in range(5):
                # Create a new record for each attempt to avoid shared state
                record = logging.LogRecord(
                    name='test', level=logging.INFO, pathname='', lineno=0,
                    msg='concurrent message', args=(), exc_info=None
                )
                result = self.filter.filter(record)
                results.append(result)
        
        # Start multiple threads
        threads = []
        for i in range(3):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # Should have some allowed and some suppressed messages
        # With 3 threads * 5 messages = 15 total, limit is 3 per key
        # So we should have at most 4 allowed (3 + 1 suppression marker)
        allowed_count = sum(1 for r in results if r)
        self.assertGreater(allowed_count, 0)
        self.assertLessEqual(allowed_count, 4)  # At most 3 regular + 1 suppression marker


class TestContextManagement(unittest.TestCase):
    """Test thread-local context management."""
    
    def setUp(self):
        clear_job_ctx()
    
    def test_set_and_get_context(self):
        """Test setting and getting job context."""
        set_job_ctx(job_id='j-123', video_id='vid-456')
        
        context = get_job_ctx()
        self.assertEqual(context['job_id'], 'j-123')
        self.assertEqual(context['video_id'], 'vid-456')
    
    def test_partial_context_setting(self):
        """Test setting only some context fields."""
        set_job_ctx(job_id='j-123')
        context = get_job_ctx()
        
        self.assertEqual(context['job_id'], 'j-123')
        self.assertNotIn('video_id', context)
        
        set_job_ctx(video_id='vid-456')
        context = get_job_ctx()
        
        self.assertEqual(context['job_id'], 'j-123')
        self.assertEqual(context['video_id'], 'vid-456')
    
    def test_context_clearing(self):
        """Test clearing job context."""
        set_job_ctx(job_id='j-123', video_id='vid-456')
        clear_job_ctx()
        
        context = get_job_ctx()
        self.assertEqual(context, {})
    
    def test_thread_isolation(self):
        """Test that context is isolated between threads."""
        results = {}
        
        def worker(thread_id):
            set_job_ctx(job_id=f'j-{thread_id}', video_id=f'vid-{thread_id}')
            time.sleep(0.1)  # Allow other threads to run
            context = get_job_ctx()
            results[thread_id] = context
        
        # Start multiple threads with different contexts
        threads = []
        for i in range(3):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # Each thread should have its own context
        for i in range(3):
            self.assertEqual(results[i]['job_id'], f'j-{i}')
            self.assertEqual(results[i]['video_id'], f'vid-{i}')


class TestLoggingConfiguration(unittest.TestCase):
    """Test logging configuration and library noise suppression."""
    
    def test_configure_logging_json(self):
        """Test JSON logging configuration."""
        logger = configure_logging(log_level='INFO', use_json=True)
        
        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.level, logging.INFO)
        
        # Should have one handler with JsonFormatter
        self.assertEqual(len(logger.handlers), 1)
        handler = logger.handlers[0]
        self.assertIsInstance(handler.formatter, JsonFormatter)
    
    def test_configure_logging_basic(self):
        """Test basic logging configuration fallback."""
        logger = configure_logging(log_level='DEBUG', use_json=False)
        
        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.level, logging.DEBUG)
        
        # Should have basic formatter
        handler = logger.handlers[0]
        self.assertNotIsInstance(handler.formatter, JsonFormatter)
    
    def test_library_noise_suppression(self):
        """Test that third-party library loggers are suppressed."""
        configure_logging()
        
        # Check that library loggers are set to WARNING level
        suppressed_libraries = ['playwright', 'urllib3', 'botocore', 'boto3', 'asyncio']
        
        for lib in suppressed_libraries:
            lib_logger = logging.getLogger(lib)
            self.assertGreaterEqual(lib_logger.level, logging.WARNING)
    
    def test_get_perf_logger(self):
        """Test performance logger separation."""
        perf_logger = get_perf_logger()
        
        self.assertEqual(perf_logger.name, 'perf')
        self.assertIsInstance(perf_logger, logging.Logger)


if __name__ == '__main__':
    unittest.main()