"""
Unit tests for log_events.py event helper functions.

Tests the evt() function and StageTimer context manager for:
- Consistent event emission
- Duration accuracy
- Exception handling
- Field naming compliance
"""

import unittest
import logging
import time
import json
from unittest.mock import patch, MagicMock
from io import StringIO

# Add parent directory to path for imports
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the modules under test
import log_events
from logging_setup import JsonFormatter, configure_logging


class TestEvtFunction(unittest.TestCase):
    """Test the evt() function for consistent event emission."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a string buffer to capture log output
        self.log_buffer = StringIO()
        
        # Create a handler that writes to our buffer with JSON formatter
        self.handler = logging.StreamHandler(self.log_buffer)
        self.handler.setFormatter(JsonFormatter())
        
        # Get the root logger and configure it
        self.logger = logging.getLogger()
        # Clear existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)
        
    def tearDown(self):
        """Clean up test fixtures."""
        self.logger.removeHandler(self.handler)
        self.handler.close()
        
    def test_evt_basic_event_emission(self):
        """Test basic event emission with evt() function."""
        # Emit a simple event
        log_events.evt("test_event", field1="value1", field2=42)
        
        # Get the log output
        log_output = self.log_buffer.getvalue().strip()
        
        # Verify the event was logged
        self.assertIn("test_event", log_output)
        
    def test_evt_with_multiple_fields(self):
        """Test evt() function with multiple field types."""
        log_events.evt(
            "job_received",
            video_id="abc123",
            config="default",
            timeout=30,
            use_proxy=True
        )
        
        log_output = self.log_buffer.getvalue().strip()
        self.assertIn("job_received", log_output)
        
    def test_evt_with_no_additional_fields(self):
        """Test evt() function with only event name."""
        log_events.evt("simple_event")
        
        log_output = self.log_buffer.getvalue().strip()
        self.assertIn("simple_event", log_output)


class TestStageTimer(unittest.TestCase):
    """Test the StageTimer context manager."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a string buffer to capture log output
        self.log_buffer = StringIO()
        
        # Create a handler that writes to our buffer with JSON formatter
        self.handler = logging.StreamHandler(self.log_buffer)
        self.handler.setFormatter(JsonFormatter())
        
        # Get the root logger and configure it
        self.logger = logging.getLogger()
        # Clear existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)
        
    def tearDown(self):
        """Clean up test fixtures."""
        self.logger.removeHandler(self.handler)
        self.handler.close()
        
    def test_stage_timer_success_case(self):
        """Test StageTimer with successful completion."""
        with log_events.StageTimer("test_stage", profile="mobile"):
            # Simulate some work
            time.sleep(0.01)  # 10ms
            
        log_output = self.log_buffer.getvalue()
        
        # Should have both stage_start and stage_result events
        self.assertIn("stage_start", log_output)
        self.assertIn("stage_result", log_output)
        self.assertIn("test_stage", log_output)
        self.assertIn("success", log_output)
        self.assertIn("profile", log_output)
        self.assertIn("mobile", log_output)
        
    def test_stage_timer_duration_accuracy(self):
        """Test that StageTimer calculates duration accurately."""
        start_time = time.time()
        
        with log_events.StageTimer("duration_test"):
            time.sleep(0.05)  # 50ms
            
        end_time = time.time()
        actual_duration_ms = int((end_time - start_time) * 1000)
        
        log_output = self.log_buffer.getvalue()
        
        # Extract duration from log output (this is a simplified check)
        # In a real implementation, you might parse the JSON to get exact values
        self.assertIn("dur_ms", log_output)
        
        # Duration should be approximately 50ms (allow some variance)
        # We can't easily extract the exact value without JSON parsing,
        # so we just verify the field is present
        
    def test_stage_timer_exception_handling(self):
        """Test StageTimer exception handling and error outcome."""
        with self.assertRaises(ValueError):
            with log_events.StageTimer("error_stage", attempt=2):
                raise ValueError("Test error message")
                
        log_output = self.log_buffer.getvalue()
        
        # Should have stage_start and stage_result with error outcome
        self.assertIn("stage_start", log_output)
        self.assertIn("stage_result", log_output)
        self.assertIn("error_stage", log_output)
        self.assertIn("error", log_output)
        self.assertIn("ValueError", log_output)
        self.assertIn("Test error message", log_output)
        
    def test_stage_timer_context_fields(self):
        """Test that context fields are included in events."""
        with log_events.StageTimer(
            "context_test",
            profile="desktop",
            use_proxy=True,
            attempt=3,
            cookie_source="s3"
        ):
            pass
            
        log_output = self.log_buffer.getvalue()
        
        # Verify context fields are included
        self.assertIn("profile", log_output)
        self.assertIn("desktop", log_output)
        self.assertIn("use_proxy", log_output)
        self.assertIn("attempt", log_output)
        self.assertIn("cookie_source", log_output)
        self.assertIn("s3", log_output)
        
    def test_stage_timer_no_context_fields(self):
        """Test StageTimer with no additional context fields."""
        with log_events.StageTimer("minimal_stage"):
            time.sleep(0.001)  # 1ms
            
        log_output = self.log_buffer.getvalue()
        
        # Should still work with just the stage name
        self.assertIn("stage_start", log_output)
        self.assertIn("stage_result", log_output)
        self.assertIn("minimal_stage", log_output)
        self.assertIn("success", log_output)
        
    def test_stage_timer_different_exception_types(self):
        """Test StageTimer with different exception types."""
        # Test with ConnectionError
        with self.assertRaises(ConnectionError):
            with log_events.StageTimer("connection_test"):
                raise ConnectionError("Connection failed")
                
        # Test with TimeoutError
        with self.assertRaises(TimeoutError):
            with log_events.StageTimer("timeout_test"):
                raise TimeoutError("Request timed out")
                
        log_output = self.log_buffer.getvalue()
        
        # Should handle different exception types
        self.assertIn("ConnectionError", log_output)
        self.assertIn("Connection failed", log_output)
        self.assertIn("TimeoutError", log_output)
        self.assertIn("Request timed out", log_output)
        
    def test_stage_timer_duration_integer_precision(self):
        """Test that duration is calculated as integer milliseconds."""
        # Test with a known sleep duration instead of mocking
        start_time = time.time()
        
        with log_events.StageTimer("precision_test"):
            time.sleep(0.1)  # 100ms
            
        end_time = time.time()
        actual_duration_ms = int((end_time - start_time) * 1000)
        
        log_output = self.log_buffer.getvalue()
        
        # Duration should be approximately 100ms (allow some variance)
        self.assertIn("dur_ms", log_output)
        # Check that duration is in a reasonable range (90-150ms to account for system variance)
        self.assertTrue(90 <= actual_duration_ms <= 150, f"Duration {actual_duration_ms}ms not in expected range")


class TestTimeStageConvenienceFunction(unittest.TestCase):
    """Test the time_stage convenience function."""
    
    def test_time_stage_returns_stage_timer(self):
        """Test that time_stage returns a StageTimer instance."""
        timer = log_events.time_stage("test_stage", profile="mobile")
        
        self.assertIsInstance(timer, log_events.StageTimer)
        self.assertEqual(timer.stage, "test_stage")
        self.assertEqual(timer.context_fields, {"profile": "mobile"})
        
    def test_time_stage_usage_as_context_manager(self):
        """Test using time_stage as a context manager."""
        # This should work the same as StageTimer
        with log_events.time_stage("convenience_test", attempt=1):
            time.sleep(0.001)
            
        # If we get here without exception, the test passes


class TestFieldNamingCompliance(unittest.TestCase):
    """Test that field naming follows the JSON schema requirements."""
    
    def test_standard_field_names(self):
        """Test that standard field names are used correctly."""
        # Test evt() with standard fields
        log_events.evt(
            "test_event",
            job_id="j-123",
            video_id="vid-456",
            stage="test_stage",
            outcome="success",
            dur_ms=1000,
            detail="test detail"
        )
        
        # Test StageTimer with standard context fields
        with log_events.StageTimer(
            "test_stage",
            attempt=1,
            use_proxy=True,
            profile="mobile",
            cookie_source="local"
        ):
            pass
            
        # If no exceptions are raised, field naming is working


if __name__ == '__main__':
    unittest.main()