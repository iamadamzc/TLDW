#!/usr/bin/env python3
"""
Unit tests for cookie upload routes
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from io import BytesIO

# Add parent directory to path to import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from cookies_routes import _looks_like_netscape_format, _store_local, _store_s3_if_configured


class TestCookieRoutes(unittest.TestCase):
    
    def test_netscape_format_validation(self):
        """Test Netscape format validation"""
        # Valid Netscape format
        valid_cookie = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tFALSE\t1234567890\ttest\tvalue"
        self.assertTrue(_looks_like_netscape_format(valid_cookie))
        
        # Another valid format
        valid_cookie2 = "# Mozilla cookies file\n.youtube.com\tTRUE\t/\tFALSE\t1234567890\ttest\tvalue"
        self.assertTrue(_looks_like_netscape_format(valid_cookie2))
        
        # Invalid format (no tabs)
        invalid_cookie = "# Some header\nthis is not a cookie file"
        self.assertFalse(_looks_like_netscape_format(invalid_cookie))
        
        # Invalid format (no header)
        invalid_cookie2 = "just some text without proper format"
        self.assertFalse(_looks_like_netscape_format(invalid_cookie2))
    
    def test_local_storage(self):
        """Test local cookie storage"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {'COOKIE_LOCAL_DIR': temp_dir}):
                test_data = b"# Test cookie file\n.youtube.com\tTRUE\t/\tFALSE\t1234567890\ttest\tvalue"
                
                # Store cookie
                path = _store_local(123, test_data)
                
                # Verify file was created
                self.assertTrue(os.path.exists(path))
                
                # Verify content
                with open(path, 'rb') as f:
                    stored_data = f.read()
                self.assertEqual(stored_data, test_data)
                
                # Verify path format
                expected_path = os.path.join(temp_dir, "123.txt")
                self.assertEqual(path, expected_path)
    
    def test_s3_storage_no_bucket(self):
        """Test S3 storage when no bucket is configured"""
        with patch.dict(os.environ, {}, clear=True):
            result = _store_s3_if_configured(123, b"test data")
            self.assertIsNone(result)
    
    def test_s3_storage_with_bucket(self):
        """Test S3 storage when bucket is configured"""
        test_data = b"# Test cookie file\n.youtube.com\tTRUE\t/\tFALSE\t1234567890\ttest\tvalue"
        
        with patch.dict(os.environ, {'COOKIE_S3_BUCKET': 'test-bucket'}):
            with patch('boto3.client') as mock_boto3:
                mock_s3 = MagicMock()
                mock_boto3.return_value = mock_s3
                
                with patch('tempfile.NamedTemporaryFile') as mock_temp:
                    mock_file = MagicMock()
                    mock_file.name = '/tmp/test_cookie.txt'
                    mock_temp.return_value.__enter__.return_value = mock_file
                    mock_temp.return_value.name = '/tmp/test_cookie.txt'
                    
                    with patch('os.unlink') as mock_unlink:
                        result = _store_s3_if_configured(123, test_data)
                        
                        # Verify S3 upload was called with correct parameters
                        mock_s3.upload_file.assert_called_once()
                        call_args = mock_s3.upload_file.call_args
                        
                        # Check that ServerSideEncryption was specified
                        extra_args = call_args[1]['ExtraArgs']
                        self.assertEqual(extra_args['ServerSideEncryption'], 'aws:kms')
                        
                        # Verify return value
                        self.assertEqual(result, 's3://test-bucket/cookies/123.txt')
                        
                        # Verify temp file cleanup
                        mock_unlink.assert_called_once_with('/tmp/test_cookie.txt')
    
    def test_s3_storage_failure(self):
        """Test S3 storage failure handling"""
        test_data = b"test data"
        
        with patch.dict(os.environ, {'COOKIE_S3_BUCKET': 'test-bucket'}):
            with patch('boto3.client', side_effect=Exception("S3 error")):
                result = _store_s3_if_configured(123, test_data)
                self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()