#!/usr/bin/env python3
"""
Simple test for proxy session configuration fix.
Tests the core functionality without complex mocking.
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

class TestProxySessionSimple(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment"""
        # Clear any existing environment variables
        if 'ENFORCE_PROXY_ALL' in os.environ:
            del os.environ['ENFORCE_PROXY_ALL']
    
    def test_ensure_proxy_session_disabled(self):
        """Test that ensure_proxy_session returns None when ENFORCE_PROXY_ALL is false"""
        os.environ['ENFORCE_PROXY_ALL'] = 'false'
        
        from proxy_manager import ensure_proxy_session
        
        result = ensure_proxy_session("test_job", "test_video")
        self.assertIsNone(result, "Should return None when ENFORCE_PROXY_ALL is false")
    
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
