#!/usr/bin/env python3
"""
Integration tests for backward compatibility layer.

Tests that the backward compatibility layer works with actual application code.
"""

import os
import sys
import logging
import unittest
from unittest.mock import patch
from io import StringIO

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestBackwardCompatibilityIntegration(unittest.TestCase):
    """Integration tests for backward compatibility."""
    
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
    
    def test_app_initialization_with_minimal_logging(self):
        """Test that app.py initialization works with minimal logging."""
        with patch.dict(os.environ, {'USE_MINIMAL_LOGGING': 'true'}, clear=False):
            # Clear module cache
            modules_to_clear = [
                'structured_logging', 'logging_setup', 'log_events'
            ]
            for module in modules_to_clear:
                if module in sys.modules:
                    del sys.modules[module]
            
            try:
                # Import structured logging (simulating app.py import)
                from structured_logging import setup_structured_logging
                
                # Should initialize without error
                setup_structured_logging()
                
                # Test basic logging
                logger = logging.getLogger("test_app")
                logger.info("Application started")
                
                self.assertTrue(True)  # Completed without error
                
            except Exception as e:
                self.fail(f"App initialization failed with minimal logging: {e}")
    
    def test_app_initialization_with_legacy_logging(self):
        """Test that app.py initialization works with legacy logging."""
        with patch.dict(os.environ, {'USE_MINIMAL_LOGGING': 'false'}, clear=False):
            # Clear module cache
            modules_to_clear = [
                'structured_logging', 'logging_setup', 'log_events'
            ]
            for module in modules_to_clear:
                if module in sys.modules:
                    del sys.modules[module]
            
            try:
                # Import structured logging (simulating app.py import)
                from structured_logging import setup_structured_logging
                
                # Should initialize without error
                setup_structured_logging()
                
                # Test basic logging
                logger = logging.getLogger("test_app")
                logger.info("Application started")
                
                self.assertTrue(True)  # Completed without error
                
            except Exception as e:
                self.fail(f"App initialization failed with legacy logging: {e}")
    
    def test_transcript_service_compatibility(self):
        """Test that transcript service imports work with both modes."""
        test_modes = [
            {'USE_MINIMAL_LOGGING': 'false'},
            {'USE_MINIMAL_LOGGING': 'true'}
        ]
        
        for env_vars in test_modes:
            with self.subTest(env_vars=env_vars):
                with patch.dict(os.environ, env_vars, clear=False):
                    # Clear module cache
                    modules_to_clear = [
                        'structured_logging', 'logging_setup', 'log_events'
                    ]
                    for module in modules_to_clear:
                        if module in sys.modules:
                            del sys.modules[module]
                    
                    try:
                        # Import the functions used by transcript_service.py
                        from structured_logging import get_contextual_logger, log_context, log_performance
                        
                        # Test contextual logger
                        logger = get_contextual_logger("transcript_service")
                        logger.info("Test message")
                        
                        # Test log context
                        with log_context(video_id="test123", job_id="job456"):
                            logger.info("Context message")
                        
                        # Test log performance
                        with log_performance("test_operation", video_id="test123"):
                            pass
                        
                        self.assertTrue(True)  # Completed without error
                        
                    except Exception as e:
                        self.fail(f"Transcript service compatibility failed in mode {env_vars}: {e}")
    
    def test_performance_logger_compatibility(self):
        """Test that performance logger works with both modes."""
        test_modes = [
            {'USE_MINIMAL_LOGGING': 'false'},
            {'USE_MINIMAL_LOGGING': 'true'}
        ]
        
        for env_vars in test_modes:
            with self.subTest(env_vars=env_vars):
                with patch.dict(os.environ, env_vars, clear=False):
                    # Clear module cache
                    modules_to_clear = [
                        'structured_logging', 'logging_setup', 'log_events'
                    ]
                    for module in modules_to_clear:
                        if module in sys.modules:
                            del sys.modules[module]
                    
                    try:
                        # Import performance logger
                        from structured_logging import performance_logger
                        
                        # Test stage performance logging
                        performance_logger.log_stage_performance(
                            stage="test_stage",
                            duration_ms=1000.0,
                            success=True,
                            video_id="test123"
                        )
                        
                        # Test circuit breaker logging
                        performance_logger.log_circuit_breaker_event(
                            event_type="state_change",
                            state="open"
                        )
                        
                        # Test browser context logging
                        performance_logger.log_browser_context_metrics(
                            action="create",
                            profile="mobile"
                        )
                        
                        # Test proxy health logging
                        performance_logger.log_proxy_health_metrics(
                            healthy=True
                        )
                        
                        self.assertTrue(True)  # Completed without error
                        
                    except Exception as e:
                        self.fail(f"Performance logger compatibility failed in mode {env_vars}: {e}")
    
    def test_environment_variable_migration(self):
        """Test migration from ENABLE_STRUCTURED_LOGGING to USE_MINIMAL_LOGGING."""
        # Test old environment variable still works
        with patch.dict(os.environ, {'ENABLE_STRUCTURED_LOGGING': '1'}, clear=False):
            # Clear module cache
            modules_to_clear = [
                'structured_logging', 'logging_setup', 'log_events'
            ]
            for module in modules_to_clear:
                if module in sys.modules:
                    del sys.modules[module]
            
            try:
                # Should still initialize (backward compatibility)
                import structured_logging
                self.assertTrue(True)  # Import succeeded
                
            except Exception as e:
                self.fail(f"Legacy environment variable support failed: {e}")
        
        # Test new environment variable
        with patch.dict(os.environ, {'USE_MINIMAL_LOGGING': 'true'}, clear=False):
            # Clear module cache
            modules_to_clear = [
                'structured_logging', 'logging_setup', 'log_events'
            ]
            for module in modules_to_clear:
                if module in sys.modules:
                    del sys.modules[module]
            
            try:
                # Should initialize with minimal logging
                import structured_logging
                if structured_logging._MINIMAL_LOGGING_AVAILABLE:
                    self.assertTrue(structured_logging.USE_MINIMAL_LOGGING)
                
            except Exception as e:
                self.fail(f"New environment variable support failed: {e}")
    
    def test_graceful_degradation(self):
        """Test graceful degradation when minimal logging is not available."""
        with patch.dict(os.environ, {'USE_MINIMAL_LOGGING': 'true'}, clear=False):
            # Clear module cache first
            modules_to_clear = [
                'structured_logging', 'logging_setup', 'log_events'
            ]
            for module in modules_to_clear:
                if module in sys.modules:
                    del sys.modules[module]
            
            # Mock import failure for minimal logging modules
            with patch.dict('sys.modules', {'logging_setup': None, 'log_events': None}):
                try:
                    # Should fall back to legacy logging
                    import structured_logging
                    
                    # Should still work with legacy functionality
                    with structured_logging.log_context(video_id="test123"):
                        pass
                    
                    self.assertTrue(True)  # Fallback worked
                    
                except Exception as e:
                    self.fail(f"Graceful degradation failed: {e}")


if __name__ == '__main__':
    unittest.main()