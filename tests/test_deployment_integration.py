"""
Integration test for deployment logging initialization.

Tests the complete deployment flow with logging initialization.
"""

import os
import json
import logging
import subprocess
import tempfile
import unittest
from io import StringIO


class TestDeploymentIntegration(unittest.TestCase):
    """Integration tests for deployment with logging."""
    
    def setUp(self):
        """Set up test environment."""
        self.original_env = os.environ.copy()
        
        # Set deployment environment variables
        os.environ['USE_MINIMAL_LOGGING'] = 'true'
        os.environ['LOG_LEVEL'] = 'INFO'
        os.environ['ALLOW_MISSING_DEPS'] = 'true'
        
    def tearDown(self):
        """Clean up test environment."""
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Clear logging handlers
        logging.getLogger().handlers.clear()
    
    def test_end_to_end_logging_flow(self):
        """Test complete logging flow from initialization to output."""
        # Capture log output
        log_stream = StringIO()
        
        # Configure logging
        from logging_setup import configure_logging, set_job_ctx, get_logger
        logger = configure_logging(log_level='INFO', use_json=True)
        
        # Replace handler with test handler
        test_handler = logging.StreamHandler(log_stream)
        from logging_setup import JsonFormatter, RateLimitFilter
        test_handler.setFormatter(JsonFormatter())
        test_handler.addFilter(RateLimitFilter())
        
        logger.handlers.clear()
        logger.addHandler(test_handler)
        
        # Test job context setting
        set_job_ctx(job_id='test-job-123', video_id='test-video-456')
        
        # Test various log events
        logger.info("Job started", extra={
            'stage': 'initialization',
            'event': 'job_received',
            'outcome': 'success'
        })
        
        logger.info("Stage completed", extra={
            'stage': 'transcript',
            'event': 'stage_result',
            'outcome': 'success',
            'dur_ms': 1500,
            'attempt': 1,
            'use_proxy': False
        })
        
        logger.error("Stage failed", extra={
            'stage': 'youtubei',
            'event': 'stage_result',
            'outcome': 'timeout',
            'dur_ms': 30000,
            'detail': 'Connection timeout after 30s'
        })
        
        # Get log output
        log_output = log_stream.getvalue().strip()
        log_lines = [line for line in log_output.split('\n') if line.strip()]
        
        # Verify we have the expected number of log entries
        self.assertEqual(len(log_lines), 3, f"Expected 3 log lines, got {len(log_lines)}")
        
        # Parse and verify each log entry
        for i, line in enumerate(log_lines):
            try:
                log_data = json.loads(line)
                
                # Verify common fields
                self.assertIn('ts', log_data)
                self.assertIn('lvl', log_data)
                self.assertIn('job_id', log_data)
                self.assertIn('video_id', log_data)
                self.assertIn('stage', log_data)
                self.assertIn('event', log_data)
                self.assertIn('outcome', log_data)
                
                # Verify context propagation
                self.assertEqual(log_data['job_id'], 'test-job-123')
                self.assertEqual(log_data['video_id'], 'test-video-456')
                
                # Verify specific entries
                if i == 0:  # Job started
                    self.assertEqual(log_data['lvl'], 'INFO')
                    self.assertEqual(log_data['stage'], 'initialization')
                    self.assertEqual(log_data['event'], 'job_received')
                    self.assertEqual(log_data['outcome'], 'success')
                elif i == 1:  # Stage completed
                    self.assertEqual(log_data['lvl'], 'INFO')
                    self.assertEqual(log_data['stage'], 'transcript')
                    self.assertEqual(log_data['event'], 'stage_result')
                    self.assertEqual(log_data['outcome'], 'success')
                    self.assertEqual(log_data['dur_ms'], 1500)
                    self.assertEqual(log_data['attempt'], 1)
                    self.assertEqual(log_data['use_proxy'], False)
                elif i == 2:  # Stage failed
                    self.assertEqual(log_data['lvl'], 'ERROR')
                    self.assertEqual(log_data['stage'], 'youtubei')
                    self.assertEqual(log_data['event'], 'stage_result')
                    self.assertEqual(log_data['outcome'], 'timeout')
                    self.assertEqual(log_data['dur_ms'], 30000)
                    self.assertEqual(log_data['detail'], 'Connection timeout after 30s')
                    
            except json.JSONDecodeError as e:
                self.fail(f"Log line {i} is not valid JSON: {e}\nLine: {line}")
    
    def test_performance_logger_separation(self):
        """Test that performance metrics use separate logger channel."""
        # Capture log output
        log_stream = StringIO()
        
        # Configure logging
        from logging_setup import configure_logging, get_perf_logger
        configure_logging(log_level='INFO', use_json=True)
        
        # Get performance logger
        perf_logger = get_perf_logger()
        
        # Replace handler with test handler
        test_handler = logging.StreamHandler(log_stream)
        from logging_setup import JsonFormatter
        test_handler.setFormatter(JsonFormatter())
        
        perf_logger.handlers.clear()
        perf_logger.addHandler(test_handler)
        
        # Log performance metric
        perf_logger.info("CPU usage", extra={
            'event': 'performance_metric',
            'metric_type': 'cpu_usage',
            'value': 45.2,
            'unit': 'percent'
        })
        
        # Get log output
        log_output = log_stream.getvalue().strip()
        
        # Verify performance log format
        try:
            log_data = json.loads(log_output)
            
            self.assertEqual(log_data['event'], 'performance_metric')
            self.assertEqual(log_data['metric_type'], 'cpu_usage')
            self.assertEqual(log_data['value'], 45.2)
            self.assertEqual(log_data['unit'], 'percent')
            
        except json.JSONDecodeError as e:
            self.fail(f"Performance log is not valid JSON: {e}\nOutput: {log_output}")
    
    def test_rate_limiting_behavior(self):
        """Test rate limiting prevents log spam."""
        # Capture log output
        log_stream = StringIO()
        
        # Configure logging with rate limiting
        from logging_setup import configure_logging
        logger = configure_logging(log_level='INFO', use_json=True)
        
        # Replace handler with test handler
        test_handler = logging.StreamHandler(log_stream)
        from logging_setup import JsonFormatter, RateLimitFilter
        test_handler.setFormatter(JsonFormatter())
        test_handler.addFilter(RateLimitFilter(per_key=3, window_sec=60))  # Lower limit for testing
        
        logger.handlers.clear()
        logger.addHandler(test_handler)
        
        # Send repeated messages
        for i in range(6):
            logger.warning("Repeated warning message")
        
        # Get log output
        log_output = log_stream.getvalue().strip()
        log_lines = [line for line in log_output.split('\n') if line.strip()]
        
        # Should have 3 regular messages + 1 suppression marker = 4 total
        self.assertEqual(len(log_lines), 4, f"Expected 4 log lines with rate limiting, got {len(log_lines)}")
        
        # Verify suppression marker
        last_line = log_lines[-1]
        log_data = json.loads(last_line)
        self.assertIn('[suppressed]', log_data['detail'])
    
    def test_library_noise_suppression(self):
        """Test that third-party library logging is suppressed."""
        from logging_setup import configure_logging
        
        # Configure logging
        configure_logging(log_level='INFO', use_json=True)
        
        # Check that library loggers are set to WARNING level
        suppressed_libraries = [
            'playwright', 'urllib3', 'botocore', 'boto3', 'asyncio', 'httpx', 'httpcore'
        ]
        
        for library in suppressed_libraries:
            library_logger = logging.getLogger(library)
            self.assertGreaterEqual(
                library_logger.level, 
                logging.WARNING,
                f"Library {library} should be suppressed to WARNING level or higher"
            )
    
    def test_deployment_environment_variables(self):
        """Test that deployment environment variables are properly configured."""
        # Test that the environment variables we set are correct
        self.assertEqual(os.environ.get('USE_MINIMAL_LOGGING'), 'true')
        self.assertEqual(os.environ.get('LOG_LEVEL'), 'INFO')
        self.assertEqual(os.environ.get('ALLOW_MISSING_DEPS'), 'true')
        
        # Test that configure_logging respects these variables
        from logging_setup import configure_logging
        
        # Should use JSON logging
        logger = configure_logging(
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            use_json=os.getenv("USE_MINIMAL_LOGGING", "true").lower() == "true"
        )
        
        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.level, logging.INFO)


if __name__ == '__main__':
    unittest.main()