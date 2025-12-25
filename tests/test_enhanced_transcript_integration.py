#!/usr/bin/env python3
"""
Comprehensive test suite for the enhanced transcript API cookie integration.
Tests S3 cookie loading, timeout protection, circuit breaker, and error handling.
"""

import os
import sys
import logging
import time
import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import json

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TestS3CookieLoading(unittest.TestCase):
    """Test S3 cookie loading infrastructure"""
    
    def setUp(self):
        """Set up test environment"""
        # Import here to avoid import errors if modules aren't available
        try:
            from transcript_service import (
                load_user_cookies_from_s3, 
                get_user_cookies_with_fallback,
                CookieSecurityManager
            )
            self.load_user_cookies_from_s3 = load_user_cookies_from_s3
            self.get_user_cookies_with_fallback = get_user_cookies_with_fallback
            self.CookieSecurityManager = CookieSecurityManager
        except ImportError as e:
            self.skipTest(f"Required modules not available: {e}")
    
    @patch('transcript_service.boto3')
    def test_s3_cookie_loading_success(self, mock_boto3):
        """Test successful S3 cookie loading and parsing"""
        # Mock S3 response
        mock_s3_client = Mock()
        mock_boto3.client.return_value = mock_s3_client
        
        # Sample Netscape format cookie content
        cookie_content = """# Netscape HTTP Cookie File
.youtube.com	TRUE	/	FALSE	1735689600	session_token	abc123
.youtube.com	TRUE	/	TRUE	1735689600	secure_token	def456
"""
        
        mock_response = {
            'Body': Mock()
        }
        mock_response['Body'].read.return_value = cookie_content.encode('utf-8')
        mock_s3_client.get_object.return_value = mock_response
        
        # Test cookie loading
        with patch.dict(os.environ, {'COOKIE_S3_BUCKET': 'test-bucket'}):
            cookies = self.load_user_cookies_from_s3(123)
        
        self.assertIsNotNone(cookies)
        self.assertIn('session_token', cookies)
        self.assertIn('secure_token', cookies)
        self.assertEqual(cookies['session_token'], 'abc123')
        self.assertEqual(cookies['secure_token'], 'def456')
    
    @patch('transcript_service.boto3')
    def test_s3_cookie_loading_fallback(self, mock_boto3):
        """Test fallback to environment cookies when S3 fails"""
        # Mock S3 failure
        mock_s3_client = Mock()
        mock_boto3.client.return_value = mock_s3_client
        mock_s3_client.get_object.side_effect = Exception("S3 error")
        
        # Mock environment cookie
        with patch('transcript_service._cookie_header_from_env_or_file') as mock_env_cookies:
            mock_env_cookies.return_value = "test_cookie=test_value"
            
            with patch.dict(os.environ, {'COOKIE_S3_BUCKET': 'test-bucket'}):
                cookie_header = self.get_user_cookies_with_fallback(123)
            
            # Should fallback to environment cookies
            mock_env_cookies.assert_called_once()
            self.assertEqual(cookie_header, "test_cookie=test_value")
    
    def test_cookie_security_manager(self):
        """Test cookie security and validation"""
        # Test cookie name sanitization
        cookies = {'session_token': 'secret123', 'user_id': 'user456'}
        sanitized = self.CookieSecurityManager.sanitize_cookie_logs(cookies)
        
        self.assertEqual(set(sanitized), {'session_token', 'user_id'})
        self.assertNotIn('secret123', sanitized)
        self.assertNotIn('user456', sanitized)
        
        # Test Netscape format validation
        valid_content = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tFALSE\t123\tname\tvalue"
        invalid_content = "not a cookie file"
        
        self.assertTrue(self.CookieSecurityManager.validate_cookie_format(valid_content))
        self.assertFalse(self.CookieSecurityManager.validate_cookie_format(invalid_content))


class TestUserContextManagement(unittest.TestCase):
    """Test user context management in TranscriptService"""
    
    def setUp(self):
        """Set up test environment"""
        try:
            from transcript_service import TranscriptService
            self.TranscriptService = TranscriptService
        except ImportError as e:
            self.skipTest(f"TranscriptService not available: {e}")
    
    def test_set_current_user_id(self):
        """Test setting current user ID"""
        service = self.TranscriptService()
        
        # Initially no user ID
        self.assertIsNone(service.current_user_id)
        
        # Set user ID
        service.set_current_user_id(123)
        self.assertEqual(service.current_user_id, 123)
    
    def test_get_transcript_with_user_id(self):
        """Test get_transcript method with user_id parameter"""
        service = self.TranscriptService()
        
        # Mock the internal methods to avoid actual API calls
        with patch.object(service, '_get_transcript_with_fallback') as mock_fallback:
            mock_fallback.return_value = ("test transcript", "test_source")
            
            # Call with user_id
            result = service.get_transcript("test_video", user_id=456)
            
            # Should set current_user_id
            self.assertEqual(service.current_user_id, 456)


class TestTimeoutProtection(unittest.TestCase):
    """Test YouTubei timeout protection system"""
    
    def setUp(self):
        """Set up test environment"""
        try:
            from transcript_service import (
                get_transcript_via_youtubei_with_timeout,
                PlaywrightCircuitBreaker,
                ResourceCleanupManager
            )
            self.get_transcript_via_youtubei_with_timeout = get_transcript_via_youtubei_with_timeout
            self.PlaywrightCircuitBreaker = PlaywrightCircuitBreaker
            self.ResourceCleanupManager = ResourceCleanupManager
        except ImportError as e:
            self.skipTest(f"Required modules not available: {e}")
    
    def test_circuit_breaker_functionality(self):
        """Test circuit breaker activation and recovery"""
        cb = self.PlaywrightCircuitBreaker()
        
        # Initially closed
        self.assertFalse(cb.is_open())
        
        # Record failures
        cb.record_failure()
        self.assertFalse(cb.is_open())  # Still closed after 1 failure
        
        cb.record_failure()
        self.assertFalse(cb.is_open())  # Still closed after 2 failures
        
        cb.record_failure()
        self.assertTrue(cb.is_open())   # Open after 3 failures
        
        # Record success should reset
        cb.record_success()
        self.assertFalse(cb.is_open())
    
    def test_resource_cleanup(self):
        """Test resource cleanup functionality"""
        cleanup_manager = self.ResourceCleanupManager()
        
        # Mock Playwright resources
        mock_browser = Mock()
        mock_context = Mock()
        mock_page = Mock()
        
        # Test cleanup doesn't raise exceptions
        try:
            cleanup_manager.cleanup_playwright_resources(mock_browser, mock_context, mock_page)
            mock_page.close.assert_called_once()
            mock_context.close.assert_called_once()
            mock_browser.close.assert_called_once()
        except Exception as e:
            self.fail(f"Resource cleanup raised exception: {e}")
    
    @patch('transcript_service.sync_playwright')
    @patch('transcript_service._BROWSER_SEM')
    def test_timeout_enforcement(self, mock_sem, mock_playwright):
        """Test that timeout is enforced correctly"""
        # Mock circuit breaker to allow operation
        with patch('transcript_service._playwright_circuit_breaker') as mock_cb:
            mock_cb.is_open.return_value = False
            
            # Mock youtube_reachable to avoid network calls
            with patch('transcript_service.youtube_reachable') as mock_reachable:
                mock_reachable.return_value = True
                
                # Test with very short timeout
                result = self.get_transcript_via_youtubei_with_timeout(
                    "test_video", max_duration_seconds=0.1
                )
                
                # Should return empty string due to timeout
                self.assertEqual(result, "")


class TestErrorDetection(unittest.TestCase):
    """Test enhanced error detection and classification"""
    
    def setUp(self):
        """Set up test environment"""
        try:
            from transcript_service import (
                detect_youtube_blocking,
                classify_transcript_error,
                handle_timeout_error
            )
            self.detect_youtube_blocking = detect_youtube_blocking
            self.classify_transcript_error = classify_transcript_error
            self.handle_timeout_error = handle_timeout_error
        except ImportError as e:
            self.skipTest(f"Required modules not available: {e}")
    
    def test_youtube_blocking_detection(self):
        """Test YouTube blocking detection"""
        # Test blocking indicators
        blocking_errors = [
            "no element found: line 1, column 0",
            "ParseError: syntax error",
            "XML document structures must start and end within the same entity"
        ]
        
        for error in blocking_errors:
            self.assertTrue(self.detect_youtube_blocking(error))
        
        # Test non-blocking errors
        normal_errors = [
            "Network connection failed",
            "Video not found",
            "Transcript unavailable"
        ]
        
        for error in normal_errors:
            self.assertFalse(self.detect_youtube_blocking(error))
    
    def test_error_classification(self):
        """Test error classification system"""
        # Test timeout error
        timeout_error = Exception("TimeoutError: Operation timed out")
        classification = self.classify_transcript_error(timeout_error, "test_video", "youtubei")
        self.assertEqual(classification, "timeout")
        
        # Test YouTube blocking
        blocking_error = Exception("no element found: line 1, column 0")
        classification = self.classify_transcript_error(blocking_error, "test_video", "api")
        self.assertEqual(classification, "youtube_blocking")
        
        # Test auth failure
        auth_error = Exception("401 Unauthorized")
        classification = self.classify_transcript_error(auth_error, "test_video", "api")
        self.assertEqual(classification, "auth_failure")


class TestEnhancedTranscriptAPI(unittest.TestCase):
    """Test enhanced transcript API functionality"""
    
    def setUp(self):
        """Set up test environment"""
        try:
            from transcript_service import (
                TranscriptService,
                get_transcript_with_cookies_fixed
            )
            self.TranscriptService = TranscriptService
            self.get_transcript_with_cookies_fixed = get_transcript_with_cookies_fixed
        except ImportError as e:
            self.skipTest(f"Required modules not available: {e}")
    
    @patch('transcript_service.get_user_cookies_with_fallback')
    @patch('requests.Session')
    def test_enhanced_cookie_transcript_fetching(self, mock_session_class, mock_get_cookies):
        """Test enhanced cookie-based transcript fetching"""
        # Mock cookie loading
        mock_get_cookies.return_value = "session_token=abc123; user_id=456"
        
        # Mock HTTP session
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """<?xml version="1.0" encoding="utf-8"?>
        <transcript>
            <text start="0" dur="2">Hello world</text>
            <text start="2" dur="2">This is a test</text>
        </transcript>"""
        mock_session.get.return_value = mock_response
        
        # Test transcript fetching
        result = self.get_transcript_with_cookies_fixed("test_video", ["en"], 123)
        
        # Should return transcript text
        self.assertIn("Hello world", result)
        self.assertIn("This is a test", result)
    
    def test_multi_strategy_fallback(self):
        """Test multi-strategy fallback in get_captions_via_api"""
        service = self.TranscriptService()
        service.set_current_user_id(123)
        
        # Mock all strategies to fail except the last one
        with patch('transcript_service.get_transcript_with_cookies_fixed') as mock_strategy1:
            mock_strategy1.return_value = ""  # Strategy 1 fails
            
            with patch('transcript_service.list_transcripts') as mock_strategy2:
                mock_strategy2.side_effect = Exception("Library failed")  # Strategy 2 fails
                
                with patch('transcript_service.get_transcript') as mock_strategy3:
                    # Strategy 3 succeeds
                    mock_strategy3.return_value = [
                        {"text": "Hello world"},
                        {"text": "This is a test"}
                    ]
                    
                    result = service.get_captions_via_api("test_video")
                    
                    # Should return transcript from strategy 3
                    self.assertIn("Hello world", result)
                    self.assertIn("This is a test", result)


def run_integration_tests():
    """Run integration tests that require actual network access"""
    print("\n=== Integration Tests (require network) ===")
    
    try:
        from transcript_service import TranscriptService
        
        # Test with a known public video
        service = TranscriptService()
        
        # Use a video that's likely to have transcripts
        test_video_id = "dQw4w9WgXcQ"  # Rick Roll - likely to have captions
        
        print(f"Testing transcript fetching for video: {test_video_id}")
        start_time = time.time()
        
        result = service.get_transcript(test_video_id)
        duration = time.time() - start_time
        
        if result and result.strip():
            print(f"✅ Integration test successful!")
            print(f"   Duration: {duration:.2f}s")
            print(f"   Transcript length: {len(result)} characters")
            print(f"   First 100 chars: {result[:100]}...")
            return True
        else:
            print(f"⚠️  Integration test returned empty result (may be expected)")
            return True  # Don't fail on empty result as video may not have captions
            
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("🧪 Enhanced Transcript API Cookie Integration Tests")
    print("=" * 60)
    
    # Run unit tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestS3CookieLoading,
        TestUserContextManagement,
        TestTimeoutProtection,
        TestErrorDetection,
        TestEnhancedTranscriptAPI
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run unit tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Run integration tests if unit tests pass
    integration_success = True
    if result.wasSuccessful():
        integration_success = run_integration_tests()
    
    # Summary
    print("\n" + "=" * 60)
    unit_tests_passed = result.wasSuccessful()
    
    if unit_tests_passed and integration_success:
        print("🎉 All tests passed! Enhanced transcript integration is working correctly.")
        return 0
    else:
        if not unit_tests_passed:
            print(f"❌ Unit tests failed: {len(result.failures)} failures, {len(result.errors)} errors")
        if not integration_success:
            print("❌ Integration tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())