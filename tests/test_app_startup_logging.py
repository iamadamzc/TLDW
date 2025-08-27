"""
Test application startup with new logging configuration.
"""

import os
import unittest
from unittest.mock import patch


class TestAppStartupLogging(unittest.TestCase):
    """Test application startup with logging."""
    
    def setUp(self):
        """Set up test environment."""
        self.original_env = os.environ.copy()
        os.environ['USE_MINIMAL_LOGGING'] = 'true'
        os.environ['LOG_LEVEL'] = 'INFO'
        os.environ['ALLOW_MISSING_DEPS'] = 'true'
        
    def tearDown(self):
        """Clean up test environment."""
        os.environ.clear()
        os.environ.update(self.original_env)
    
    def test_app_startup_with_logging(self):
        """Test that app starts successfully with new logging."""
        # Mock configure_logging to verify it's called
        with patch('logging_setup.configure_logging') as mock_configure:
            mock_configure.return_value = __import__('logging').getLogger()
            
            # Import should succeed
            try:
                import app
                self.assertTrue(hasattr(app, 'app'))
                mock_configure.assert_called_once()
            except Exception as e:
                self.fail(f"App startup failed: {e}")


if __name__ == '__main__':
    unittest.main()