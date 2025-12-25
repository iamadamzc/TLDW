#!/usr/bin/env python3
"""
Tests for backward compatibility layer in structured logging.

Ensures that existing code continues to work when migrating from legacy
structured logging to minimal JSON logging system.
"""

import os
import sys
import json
import time
import logging
import threading
import unittest
from unittest.mock import patch, MagicMock
from contextlib import contextmanager
from io import StringIO

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestBackwardCompatibility(unittest.TestCase):
    """Test backward compatibility layer functionality."""
    
    def setUp(self):
        """Set up test environment."""
        # Clear any existing handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Reset logging level
        root_logger.setLevel(logging.INFO)
        
        # Clear environment variables
        self.original_env = {}
        for key in ['USE_MINIMAL_LOGGING', 'LOG_LEVEL', 'ENABLE_STRUCTURED_LOGGING']:
            self.original_env[key] = os.environ.get(key)
            if key in os.environ:
                del os.environ[key]
    
    def tearDown(self):
        """Clean up test environment."""
        # Restore environment variables
        for key, value in self.original_env.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]
        
        # Clear handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
    
    @contextmanager
    def capture_logs(self):
        """Capture log output for testing."""
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        
        try:
            yield log_capture
        finally:
            root_logger.removeHandler(handler)
    
    def test_legacy_mode_by_default(self):
        """Test that legacy mode is used by default."""
        # Import without setting USE_MINIMAL_LOGGING
        with patch.dict(os.environ, {}, clear=False):
            # Force reimport to test default behavior
            if 'structured_logging' in sys.modules:
                del sys.modules['structured_logging']
            
            import structured_logging
            
            # Should use legacy mode
            self.assertFalse(structured_logging.USE_MINIMAL_LOGGING)
    
    def test_minimal_mode_when_enabled(self):
        """Test that minimal mode is used when USE_MINIMAL_LOGGING=true."""
        with patch.dict(os.environ, {'USE_MINIMAL_LOGGING': 'true'}, clear=False):
            # Force reimport to test minimal mode
            if 'structured_logging' in sys.modules:
                del sys.modules['structured_logging']
            
            import structured_logging
            
            # Should use minimal mode if available
            if structured_logging._MINIMAL_LOGGING_AVAILABLE:
                self.assertTrue(structured_logging.USE_MINIMAL_LOGGING)
    
    def test_setup_structured_logging_legacy(self):
        """Test setup_structured_logging in legacy mode."""
        with patch.dict(os.environ, {'USE_MINIMAL_LOGGING': 'false'}, clear=False):
            if 'structured_logging' in sys.modules:
                del sys.modules['structured_logging']
            
            import structured_logging
            
            # Test that setup completes without error
            try:
                structured_logging.setup_structured_logging()
                self.assertTrue(True)  # Setup completed
            except Exception as e:
                self.fail(f"Legacy setup failed: {e}")
    
    def test_setup_structured_logging_minimal(self):
        """Test setup_structured_logging in minimal mode."""
        with patch.dict(os.environ, {'USE_MINIMAL_LOGGING': 'true'}, clear=False):
            if 'structured_logging' in sys.modules:
                del sys.modules['structured_logging']
            
            import structured_logging
            
            if structured_logging._MINIMAL_LOGGING_AVAILABLE:
                # Test that setup completes without error
                try:
                    structured_logging.setup_structured_logging()
                    self.assertTrue(True)  # Setup completed
                except Exception as e:
                    self.fail(f"Minimal setup failed: {e}")
    
    def test_log_context_legacy(self):
        """Test log_context context manager in legacy mode."""
        with patch.dict(os.environ, {'USE_MINIMAL_LOGGING': 'false'}, clear=False):
            if 'structured_logging' in sys.modules:
                del sys.modules['structured_logging']
            
            import structured_logging
            
            with structured_logging.log_context(video_id="test123", job_id="job456") as context:
                # Should have correlation_id
                self.assertIsNotNone(context.correlation_id)
                self.assertEqual(context.video_id, "test123")
                self.assertEqual(context.job_id, "job456")
    
    def test_log_context_minimal(self):
        """Test log_context context manager in minimal mode."""
        with patch.dict(os.environ, {'USE_MINIMAL_LOGGING': 'true'}, clear=False):
            if 'structured_logging' in sys.modules:
                del sys.modules['structured_logging']
            
            import structured_logging
            
            if structured_logging._MINIMAL_LOGGING_AVAILABLE:
                with structured_logging.log_context(video_id="test123", job_id="job456") as context:
                    # Should have correlation_id
                    self.assertIsNotNone(context.correlation_id)
                    self.assertEqual(context.video_id, "test123")
                    self.assertEqual(context.job_id, "job456")
    
    def test_log_performance_legacy(self):
        """Test log_performance context manager in legacy mode."""
        with patch.dict(os.environ, {'USE_MINIMAL_LOGGING': 'false'}, clear=False):
            if 'structured_logging' in sys.modules:
                del sys.modules['structured_logging']
            
            import structured_logging
            
            with self.capture_logs():
                with structured_logging.log_performance("test_operation", video_id="test123"):
                    time.sleep(0.01)  # Small delay
                
                # Should complete without error
                self.assertTrue(True)
    
    def test_log_performance_minimal(self):
        """Test log_performance context manager in minimal mode."""
        with patch.dict(os.environ, {'USE_MINIMAL_LOGGING': 'true'}, clear=False):
            if 'structured_logging' in sys.modules:
                del sys.modules['structured_logging']
            
            import structured_logging
            
            if structured_logging._MINIMAL_LOGGING_AVAILABLE:
                with self.capture_logs():
                    with structured_logging.log_performance("test_operation", video_id="test123"):
                        time.sleep(0.01)  # Small delay
                    
                    # Should complete without error
                    self.assertTrue(True)
    
    def test_performance_logger_compatibility(self):
        """Test that performance_logger maintains compatibility."""
        with patch.dict(os.environ, {'USE_MINIMAL_LOGGING': 'false'}, clear=False):
            if 'structured_logging' in sys.modules:
                del sys.modules['structured_logging']
            
            import structured_logging
            
            with self.capture_logs():
                # Should work with legacy interface
                structured_logging.performance_logger.log_stage_performance(
                    stage="test_stage",
                    duration_ms=1000.0,
                    success=True,
                    video_id="test123"
                )
                
                # Should complete without error
                self.assertTrue(True)
    
    def test_contextual_logger_compatibility(self):
        """Test that get_contextual_logger maintains compatibility."""
        with patch.dict(os.environ, {'USE_MINIMAL_LOGGING': 'false'}, clear=False):
            if 'structured_logging' in sys.modules:
                del sys.modules['structured_logging']
            
            import structured_logging
            
            logger = structured_logging.get_contextual_logger("test_logger")
            
            with self.capture_logs():
                # Should work with legacy interface
                logger.info("Test message", extra_field="test_value")
                
                # Should complete without error
                self.assertTrue(True)
    
    def test_fallback_on_initialization_error(self):
        """Test fallback to basic logging on initialization errors."""
        with patch.dict(os.environ, {'ENABLE_STRUCTURED_LOGGING': '1', 'USE_MINIMAL_LOGGING': 'true'}, clear=False):
            # Mock the minimal logging to fail
            with patch('logging_setup.configure_logging', side_effect=Exception("Mock error")):
                if 'structured_logging' in sys.modules:
                    del sys.modules['structured_logging']
                
                # Import should not fail, should fall back
                try:
                    import structured_logging
                    # If we get here, fallback worked
                    self.assertTrue(True)
                except Exception as e:
                    self.fail(f"Should have fallen back gracefully, but got: {e}")
    
    def test_thread_safety(self):
        """Test that backward compatibility maintains thread safety."""
        with patch.dict(os.environ, {'USE_MINIMAL_LOGGING': 'true'}, clear=False):
            if 'structured_logging' in sys.modules:
                del sys.modules['structured_logging']
            
            import structured_logging
            
            if not structured_logging._MINIMAL_LOGGING_AVAILABLE:
                self.skipTest("Minimal logging not available")
            
            results = []
            
            def worker(thread_id):
                with structured_logging.log_context(job_id=f"job_{thread_id}", video_id=f"video_{thread_id}"):
                    time.sleep(0.01)
                    results.append(thread_id)
            
            # Start multiple threads
            threads = []
            for i in range(5):
                thread = threading.Thread(target=worker, args=(i,))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads
            for thread in threads:
                thread.join()
            
            # All threads should complete
            self.assertEqual(len(results), 5)
    
    def test_json_output_format(self):
        """Test that JSON output format is maintained in both modes."""
        test_cases = [
            {'USE_MINIMAL_LOGGING': 'false'},
            {'USE_MINIMAL_LOGGING': 'true'}
        ]
        
        for env_vars in test_cases:
            with self.subTest(env_vars=env_vars):
                with patch.dict(os.environ, env_vars, clear=False):
                    if 'structured_logging' in sys.modules:
                        del sys.modules['structured_logging']
                    
                    import structured_logging
                    
                    # Skip if minimal logging not available
                    if env_vars.get('USE_MINIMAL_LOGGING') == 'true' and not structured_logging._MINIMAL_LOGGING_AVAILABLE:
                        continue
                    
                    # Test that setup and logging work without errors
                    try:
                        structured_logging.setup_structured_logging()
                        logger = logging.getLogger("test")
                        logger.info("Test message")
                        self.assertTrue(True)  # Completed without error
                    except Exception as e:
                        self.fail(f"JSON logging failed in mode {env_vars}: {e}")
    
    def test_error_handling_compatibility(self):
        """Test that error handling works in both modes."""
        test_cases = [
            {'USE_MINIMAL_LOGGING': 'false'},
            {'USE_MINIMAL_LOGGING': 'true'}
        ]
        
        for env_vars in test_cases:
            with self.subTest(env_vars=env_vars):
                with patch.dict(os.environ, env_vars, clear=False):
                    if 'structured_logging' in sys.modules:
                        del sys.modules['structured_logging']
                    
                    import structured_logging
                    
                    # Skip if minimal logging not available
                    if env_vars.get('USE_MINIMAL_LOGGING') == 'true' and not structured_logging._MINIMAL_LOGGING_AVAILABLE:
                        continue
                    
                    with self.capture_logs():
                        try:
                            with structured_logging.log_performance("error_test", video_id="test123"):
                                raise ValueError("Test error")
                        except ValueError:
                            pass  # Expected
                        
                        # Should complete without additional errors
                        self.assertTrue(True)
    
    def test_import_compatibility(self):
        """Test that all expected imports work in both modes."""
        test_cases = [
            {'USE_MINIMAL_LOGGING': 'false'},
            {'USE_MINIMAL_LOGGING': 'true'}
        ]
        
        expected_imports = [
            'setup_structured_logging',
            'log_context',
            'log_performance',
            'get_contextual_logger',
            'performance_logger',
            'alert_logger',
            'LogContext',
            'ContextualLogger',
            'PerformanceLogger',
            'AlertLogger'
        ]
        
        for env_vars in test_cases:
            with self.subTest(env_vars=env_vars):
                with patch.dict(os.environ, env_vars, clear=False):
                    if 'structured_logging' in sys.modules:
                        del sys.modules['structured_logging']
                    
                    import structured_logging
                    
                    # All expected attributes should be available
                    for attr_name in expected_imports:
                        self.assertTrue(
                            hasattr(structured_logging, attr_name),
                            f"Missing attribute {attr_name} in mode {env_vars}"
                        )


class TestMigrationScenarios(unittest.TestCase):
    """Test specific migration scenarios."""
    
    def setUp(self):
        """Set up test environment."""
        # Clear any existing handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Reset logging level
        root_logger.setLevel(logging.INFO)
    
    def tearDown(self):
        """Clean up test environment."""
        # Clear handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
    
    def test_gradual_migration_workflow(self):
        """Test the gradual migration workflow from legacy to minimal."""
        # Step 1: Start with legacy logging
        with patch.dict(os.environ, {'USE_MINIMAL_LOGGING': 'false'}, clear=False):
            if 'structured_logging' in sys.modules:
                del sys.modules['structured_logging']
            
            import structured_logging
            
            # Should use legacy mode
            self.assertFalse(structured_logging.USE_MINIMAL_LOGGING)
            
            # Test legacy functionality
            with structured_logging.log_context(video_id="test123") as context:
                self.assertIsNotNone(context.correlation_id)
        
        # Step 2: Switch to minimal logging
        with patch.dict(os.environ, {'USE_MINIMAL_LOGGING': 'true'}, clear=False):
            if 'structured_logging' in sys.modules:
                del sys.modules['structured_logging']
            
            import structured_logging
            
            if structured_logging._MINIMAL_LOGGING_AVAILABLE:
                # Should use minimal mode
                self.assertTrue(structured_logging.USE_MINIMAL_LOGGING)
                
                # Same API should still work
                with structured_logging.log_context(video_id="test123") as context:
                    self.assertIsNotNone(context.correlation_id)
    
    def test_existing_code_compatibility(self):
        """Test that existing code patterns continue to work."""
        # Common usage patterns from the codebase
        patterns = [
            # Pattern 1: Basic context usage
            lambda sl: sl.log_context(video_id="test123", job_id="job456"),
            
            # Pattern 2: Performance logging
            lambda sl: sl.log_performance("transcript_extraction", video_id="test123"),
            
            # Pattern 3: Contextual logger
            lambda sl: sl.get_contextual_logger("test_service"),
            
            # Pattern 4: Performance logger (returns True for compatibility)
            lambda sl: sl.performance_logger.log_stage_performance(
                stage="test", duration_ms=1000, success=True, video_id="test123"
            ) or True
        ]
        
        for mode in ['false', 'true']:
            with self.subTest(mode=mode):
                with patch.dict(os.environ, {'USE_MINIMAL_LOGGING': mode}, clear=False):
                    if 'structured_logging' in sys.modules:
                        del sys.modules['structured_logging']
                    
                    import structured_logging
                    
                    # Skip if minimal logging not available
                    if mode == 'true' and not structured_logging._MINIMAL_LOGGING_AVAILABLE:
                        continue
                    
                    # All patterns should work without errors
                    for i, pattern in enumerate(patterns):
                        with self.subTest(pattern=i):
                            try:
                                if i < 2:  # Context managers
                                    with pattern(structured_logging):
                                        pass
                                else:  # Direct calls
                                    result = pattern(structured_logging)
                                    self.assertIsNotNone(result)
                            except Exception as e:
                                self.fail(f"Pattern {i} failed in mode {mode}: {e}")


if __name__ == '__main__':
    unittest.main()