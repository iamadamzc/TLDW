#!/usr/bin/env python3
"""
Comprehensive test for proxy session configuration fix.
Tests the ensure_proxy_session function with various scenarios.
"""

import os
import sys
import logging
import unittest
from unittest.mock import patch, MagicMock

# Add current directory to path to import modules
sys.path.insert(0, '.')

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TestProxySessionFix(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment"""
        # Clear any existing environment variables
        if 'ENFORCE_PROXY_ALL' in os.environ:
            del os.environ['ENFORCE_PROXY_ALL']
        if 'PROXY_SECRET_NAME' in os.environ:
            del os.environ['PROXY_SECRET_NAME']
    
    def test_ensure_proxy_session_disabled(self):
        """Test that ensure_proxy_session returns None when ENFORCE_PROXY_ALL is false"""
        os.environ['ENFORCE_PROXY_ALL'] = 'false'
        
        from proxy_manager import ensure_proxy_session
        
        result = ensure_proxy_session("test_job", "test_video")
        self.assertIsNone(result, "Should return None when ENFORCE_PROXY_ALL is false")
    
    def test_ensure_proxy_session_enabled_no_proxy(self):
        """Test ensure_proxy_session when ENFORCE_PROXY_ALL is true but no proxy manager available"""
        os.environ['ENFORCE_PROXY_ALL'] = 'true'
        
        # Mock the shared managers module import inside the function
        with patch('proxy_manager.shared_managers') as mock_shared_managers:
            # Mock the shared managers to return a proxy manager that's not in use
            mock_proxy_manager = MagicMock()
            mock_proxy_manager.in_use = False
            mock_shared_managers.get_proxy_manager.return_value = mock_proxy_manager
            
            from proxy_manager import ensure_proxy_session
            
            result = ensure_proxy_session("test_job", "test_video")
            self.assertIsNone(result, "Should return None when proxy manager is not in use")
    
    @patch('proxy_manager._verify_proxy_connection')
    def test_ensure_proxy_session_success(self, mock_verify):
        """Test ensure_proxy_session with successful proxy connection"""
        os.environ['ENFORCE_PROXY_ALL'] = 'true'
        
        # Mock the shared managers module import inside the function
        with patch('proxy_manager.shared_managers') as mock_shared_managers:
            # Mock the shared managers and proxy manager
            mock_proxy_manager = MagicMock()
            mock_proxy_manager.in_use = True
            mock_proxy_manager.for_job.return_value = {"http": "http://proxy:8080", "https": "http://proxy:8080"}
            mock_shared_managers.get_proxy_manager.return_value = mock_proxy_manager
            
            # Mock the verification to return True
            mock_verify.return_value = True
            
            from proxy_manager import ensure_proxy_session
            
            result = ensure_proxy_session("test_job", "test_video")
            self.assertIsNotNone(result, "Should return proxy config when successful")
            self.assertEqual(result, {"http": "http://proxy:8080", "https": "http://proxy:8080"})
            
            # Verify methods were called
            mock_proxy_manager.for_job.assert_called_once_with("yt_test_job_test_video")
            mock_verify.assert_called_once_with({"http": "http://proxy:8080", "https": "http://proxy:8080"})
    
    @patch('proxy_manager._verify_proxy_connection')
    def test_ensure_proxy_session_rotation(self, mock_verify):
        """Test ensure_proxy_session with proxy rotation when connection fails"""
        os.environ['ENFORCE_PROXY_ALL'] = 'true'
        
        # Mock the shared managers module import inside the function
        with patch('proxy_manager.shared_managers') as mock_shared_managers:
            # Mock the shared managers and proxy manager
            mock_proxy_manager = MagicMock()
            mock_proxy_manager.in_use = True
            # First call returns one config, second call returns a different one after rotation
            mock_proxy_manager.for_job.side_effect = [
                {"http": "http://proxy1:8080", "https": "http://proxy1:8080"},
                {"http": "http://proxy2:8080", "https": "http://proxy2:8080"}
            ]
            mock_shared_managers.get_proxy_manager.return_value = mock_proxy_manager
            
            # Mock the verification to return False first time, then True
            mock_verify.side_effect = [False, True]
            
            from proxy_manager import ensure_proxy_session
            
            result = ensure_proxy_session("test_job", "test_video")
            self.assertIsNotNone(result, "Should return proxy config after rotation")
            self.assertEqual(result, {"http": "http://proxy2:8080", "https": "http://proxy2:8080"})
            
            # Verify methods were called
            self.assertEqual(mock_proxy_manager.for_job.call_count, 2)
            mock_proxy_manager.rotate_session.assert_called_once_with("yt_test_job_test_video")
            self.assertEqual(mock_verify.call_count, 2)
    
    def test_verify_proxy_connection_empty_config(self):
        """Test _verify_proxy_connection with empty config"""
        from proxy_manager import _verify_proxy_connection
        
        result = _verify_proxy_connection({})
        self.assertFalse(result, "Should return False for empty proxy config")
        
        result = _verify_proxy_connection({"http": "", "https": ""})
        self.assertFalse(result, "Should return False for empty proxy URLs")
    
    @patch('proxy_manager.requests.get')
    def test_verify_proxy_connection_success(self, mock_get):
        """Test _verify_proxy_connection with successful connection"""
        from proxy_manager import _verify_proxy_connection
        
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_get.return_value = mock_response
        
        proxy_config = {"http": "http://proxy:8080", "https": "http://proxy:8080"}
        result = _verify_proxy_connection(proxy_config)
        
        self.assertTrue(result, "Should return True for successful connection")
        mock_get.assert_called_once_with(
            "https://www.youtube.com/generate_204",
            proxies=proxy_config,
            timeout=10
        )
    
    @patch('proxy_manager.requests.get')
    def test_verify_proxy_connection_failure(self, mock_get):
        """Test _verify_proxy_connection with failed connection"""
        from proxy_manager import _verify_proxy_connection
        
        # Mock failed response (different status code)
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        proxy_config = {"http": "http://proxy:8080", "https": "http://proxy:8080"}
        result = _verify_proxy_connection(proxy_config)
        
        self.assertFalse(result, "Should return False for failed connection")
    
    @patch('proxy_manager.requests.get')
    def test_verify_proxy_connection_exception(self, mock_get):
        """Test _verify_proxy_connection with exception"""
        from proxy_manager import _verify_proxy_connection
        
        # Mock exception
        mock_get.side_effect = Exception("Connection failed")
        
        proxy_config = {"http": "http://proxy:8080", "https": "http://proxy:8080"}
        result = _verify_proxy_connection(proxy_config)
        
        self.assertFalse(result, "Should return False when exception occurs")

if __name__ == "__main__":
    unittest.main(verbosity=2)
