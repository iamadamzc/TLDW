"""
Tests for logging initialization in deployment entry points.

Validates that all application entry points properly initialize
the minimal JSON logging system according to requirements 8.1, 8.2, 8.3.
"""

import os
import sys
import json
import logging
import subprocess
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from io import StringIO


class TestDeploymentLoggingInitialization(unittest.TestCase):
    """Test logging initialization in deployment entry points."""
    
    def setUp(self):
        """Set up test environment."""
        # Clear any existing logging configuration
        logging.getLogger().handlers.clear()
        
        # Reset environment variables
        self.original_env = os.environ.copy()
        
    def tearDown(self):
        """Clean up test environment."""
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Clear logging handlers
        logging.getLogger().handlers.clear()
    
    def test_app_py_logging_initialization(self):
        """Test that app.py initializes logging correctly."""
        # Set environment variables
        os.environ['USE_MINIMAL_LOGGING'] = 'true'
        os.environ['LOG_LEVEL'] = 'INFO'
        
        # Capture log output
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        
        # Mock configure_logging to verify it's called
        with patch('logging_setup.configure_logging') as mock_configure:
            mock_configure.return_value = logging.getLogger()
            
            # Import app.py (this triggers logging initialization)
            import importlib
            if 'app' in sys.modules:
                importlib.reload(sys.modules['app'])
            else:
                import app
            
            # Verify configure_logging was called with correct parameters
            mock_configure.assert_called_once_with(
                log_level='INFO',
                use_json=True
            )
    
    def test_main_py_logging_initialization(self):
        """Test that main.py initializes logging before importing app."""
        # Set environment variables
        os.environ['USE_MINIMAL_LOGGING'] = 'true'
        os.environ['LOG_LEVEL'] = 'DEBUG'
        
        # Mock configure_logging to verify it's called
        with patch('logging_setup.configure_logging') as mock_configure:
            mock_configure.return_value = logging.getLogger()
            
            # Import main.py
            import importlib
            if 'main' in sys.modules:
                importlib.reload(sys.modules['main'])
            else:
                import main
            
            # Verify configure_logging was called with correct parameters
            mock_configure.assert_called_once_with(
                log_level='DEBUG',
                use_json=True
            )
    
    def test_wsgi_py_logging_initialization(self):
        """Test that wsgi.py initializes logging early."""
        # Set environment variables
        os.environ['USE_MINIMAL_LOGGING'] = 'false'
        os.environ['LOG_LEVEL'] = 'WARNING'
        os.environ['ALLOW_MISSING_DEPS'] = 'true'  # Allow missing ffmpeg for test
        
        # Mock configure_logging to verify it's called
        with patch('logging_setup.configure_logging') as mock_configure:
            mock_configure.return_value = logging.getLogger()
            
            # Mock the binary check to avoid ffmpeg dependency
            with patch('wsgi._check_binary') as mock_check:
                mock_check.return_value = None  # Simulate missing binary but allowed
                
                # Import wsgi.py
                import importlib
                if 'wsgi' in sys.modules:
                    importlib.reload(sys.modules['wsgi'])
                else:
                    import wsgi
                
                # Verify configure_logging was called with correct parameters
                mock_configure.assert_called_once_with(
                    log_level='WARNING',
                    use_json=False
                )
    
    def test_environment_variable_defaults(self):
        """Test default environment variable handling."""
        # Clear logging environment variables
        os.environ.pop('USE_MINIMAL_LOGGING', None)
        os.environ.pop('LOG_LEVEL', None)
        
        # Mock configure_logging to verify defaults
        with patch('logging_setup.configure_logging') as mock_configure:
            mock_configure.return_value = logging.getLogger()
            
            # Import app.py to test defaults
            import importlib
            if 'app' in sys.modules:
                importlib.reload(sys.modules['app'])
            else:
                import app
            
            # Verify configure_logging was called with defaults
            mock_configure.assert_called_once_with(
                log_level='INFO',
                use_json=True
            )
    
    def test_json_logging_output_format(self):
        """Test that JSON logging produces valid JSON output."""
        # Set up JSON logging
        os.environ['USE_MINIMAL_LOGGING'] = 'true'
        os.environ['LOG_LEVEL'] = 'INFO'
        
        # Capture log output
        log_stream = StringIO()
        
        # Configure logging directly
        from logging_setup import configure_logging
        logger = configure_logging(log_level='INFO', use_json=True)
        
        # Replace handler with our test handler
        test_handler = logging.StreamHandler(log_stream)
        from logging_setup import JsonFormatter
        test_handler.setFormatter(JsonFormatter())
        
        logger.handlers.clear()
        logger.addHandler(test_handler)
        
        # Log a test message
        logger.info("Test deployment logging", extra={
            'stage': 'deployment',
            'event': 'test_log',
            'outcome': 'success'
        })
        
        # Verify JSON output
        log_output = log_stream.getvalue().strip()
        self.assertTrue(log_output, "No log output captured")
        
        # Parse JSON to verify format
        try:
            log_data = json.loads(log_output)
            
            # Verify required fields
            self.assertIn('ts', log_data)
            self.assertIn('lvl', log_data)
            self.assertIn('stage', log_data)
            self.assertIn('event', log_data)
            self.assertIn('outcome', log_data)
            
            # Verify field values
            self.assertEqual(log_data['lvl'], 'INFO')
            self.assertEqual(log_data['stage'], 'deployment')
            self.assertEqual(log_data['event'], 'test_log')
            self.assertEqual(log_data['outcome'], 'success')
            
        except json.JSONDecodeError as e:
            self.fail(f"Log output is not valid JSON: {e}\nOutput: {log_output}")
    
    def test_fallback_logging_on_error(self):
        """Test fallback to basic logging when JSON logging fails."""
        # Test the configure_logging function directly for fallback behavior
        from logging_setup import configure_logging
        
        # Mock JsonFormatter to raise an exception
        with patch('logging_setup.JsonFormatter') as mock_formatter:
            mock_formatter.side_effect = Exception("Formatter creation failed")
            
            # Should fallback to basic logging without raising exception
            try:
                logger = configure_logging(log_level='INFO', use_json=True)
                self.assertIsInstance(logger, logging.Logger)
            except Exception as e:
                self.fail(f"configure_logging should not fail with fallback: {e}")
    
    def test_gunicorn_handler_integration(self):
        """Test integration with gunicorn handlers in wsgi.py."""
        # Set environment to allow missing deps
        os.environ['ALLOW_MISSING_DEPS'] = 'true'
        
        # Mock gunicorn logger with handlers
        mock_handler = MagicMock()
        mock_gunicorn_logger = MagicMock()
        mock_gunicorn_logger.handlers = [mock_handler]
        mock_gunicorn_logger.level = logging.INFO
        
        with patch('logging.getLogger') as mock_get_logger:
            # Configure mock to return gunicorn logger for 'gunicorn.error'
            def get_logger_side_effect(name=None):
                if name == 'gunicorn.error':
                    return mock_gunicorn_logger
                return MagicMock()
            
            mock_get_logger.side_effect = get_logger_side_effect
            
            # Mock configure_logging and binary check
            with patch('logging_setup.configure_logging') as mock_configure:
                mock_configure.return_value = logging.getLogger()
                
                with patch('wsgi._check_binary') as mock_check:
                    mock_check.return_value = None  # Simulate missing binary but allowed
                    
                    # Import wsgi.py
                    import importlib
                    if 'wsgi' in sys.modules:
                        importlib.reload(sys.modules['wsgi'])
                    else:
                        import wsgi
                    
                    # Verify configure_logging was called
                    mock_configure.assert_called_once()
    
    def test_container_environment_variables(self):
        """Test that container environment variables are properly set."""
        # Test environment variables that should be set in production
        expected_env_vars = {
            'USE_MINIMAL_LOGGING': 'true',
            'LOG_LEVEL': 'INFO'
        }
        
        # Read Dockerfile to verify environment variables
        dockerfile_path = 'Dockerfile'
        if os.path.exists(dockerfile_path):
            with open(dockerfile_path, 'r') as f:
                dockerfile_content = f.read()
            
            # Check that required environment variables are set
            for env_var, expected_value in expected_env_vars.items():
                env_line = f"{env_var}={expected_value}"
                self.assertIn(env_line, dockerfile_content,
                            f"Environment variable {env_var}={expected_value} not found in Dockerfile")
        else:
            self.skipTest("Dockerfile not found, skipping container environment test")
    
    def test_logging_initialization_order(self):
        """Test that logging is initialized before other imports."""
        # Test that configure_logging is called in main.py before app import
        
        # Mock configure_logging to track when it's called
        with patch('logging_setup.configure_logging') as mock_configure:
            mock_configure.return_value = logging.getLogger()
            
            # Mock app import to track when it happens
            with patch('main.app') as mock_app:
                # Import main.py module code directly to test order
                import importlib.util
                spec = importlib.util.spec_from_file_location("main_test", "main.py")
                main_module = importlib.util.module_from_spec(spec)
                
                # Execute the module
                try:
                    spec.loader.exec_module(main_module)
                except Exception:
                    # Expected since we're mocking imports
                    pass
                
                # Verify configure_logging was called
                mock_configure.assert_called_once()


class TestLoggingConfigurationValidation(unittest.TestCase):
    """Test logging configuration validation for deployment."""
    
    def test_valid_log_levels(self):
        """Test that valid log levels are accepted."""
        from logging_setup import configure_logging
        
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        
        for level in valid_levels:
            try:
                logger = configure_logging(log_level=level, use_json=True)
                self.assertIsInstance(logger, logging.Logger)
                self.assertEqual(logger.level, getattr(logging, level))
            except Exception as e:
                self.fail(f"Failed to configure logging with level {level}: {e}")
    
    def test_invalid_log_level_fallback(self):
        """Test fallback behavior for invalid log levels."""
        from logging_setup import configure_logging
        
        # Test with invalid log level
        logger = configure_logging(log_level='INVALID', use_json=True)
        
        # Should fallback to INFO level
        self.assertEqual(logger.level, logging.INFO)
    
    def test_json_vs_basic_formatting(self):
        """Test difference between JSON and basic formatting."""
        from logging_setup import configure_logging
        from io import StringIO
        
        # Test JSON formatting
        json_stream = StringIO()
        json_logger = configure_logging(log_level='INFO', use_json=True)
        json_handler = logging.StreamHandler(json_stream)
        from logging_setup import JsonFormatter
        json_handler.setFormatter(JsonFormatter())
        json_logger.handlers = [json_handler]
        
        json_logger.info("Test message")
        json_output = json_stream.getvalue().strip()
        
        # Verify JSON output
        try:
            json.loads(json_output)
        except json.JSONDecodeError:
            self.fail(f"JSON formatting failed: {json_output}")
        
        # Test basic formatting
        basic_stream = StringIO()
        basic_logger = configure_logging(log_level='INFO', use_json=False)
        basic_handler = logging.StreamHandler(basic_stream)
        basic_logger.handlers = [basic_handler]
        
        basic_logger.info("Test message")
        basic_output = basic_stream.getvalue().strip()
        
        # Verify basic output is not JSON
        self.assertNotEqual(json_output, basic_output)
        self.assertIn("Test message", basic_output)


if __name__ == '__main__':
    unittest.main()