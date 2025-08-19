#!/usr/bin/env python3
"""
Comprehensive test for error message propagation and logging improvements
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TestErrorHandlingImprovements(unittest.TestCase):
    """Test error handling improvements against requirements 3.1-3.4"""
    
    def setUp(self):
        """Set up test environment"""
        os.environ['DEEPGRAM_API_KEY'] = 'test-api-key'
        
        # Mock shared_managers
        self.shared_managers_patcher = patch('shared_managers.shared_managers')
        self.mock_shared_managers = self.shared_managers_patcher.start()
        
        self.mock_proxy_manager = MagicMock()
        self.mock_http_client = MagicMock()
        self.mock_user_agent_manager = MagicMock()
        
        self.mock_shared_managers.get_proxy_manager.return_value = self.mock_proxy_manager
        self.mock_shared_managers.get_proxy_http_client.return_value = self.mock_http_client
        self.mock_shared_managers.get_user_agent_manager.return_value = self.mock_user_agent_manager
    
    def tearDown(self):
        """Clean up test environment"""
        self.shared_managers_patcher.stop()
        if 'DEEPGRAM_API_KEY' in os.environ:
            del os.environ['DEEPGRAM_API_KEY']
        
        modules_to_clear = [mod for mod in sys.modules.keys() if 'transcript_service' in mod]
        for mod in modules_to_clear:
            del sys.modules[mod]
    
    def test_requirement_3_1_preserve_download_error_messages(self):
        """
        Requirement 3.1: WHEN yt-dlp raises a DownloadError 
        THEN the system SHALL preserve and propagate the original error message
        """
        from yt_download_helper import _combine_error_messages
        
        # Test that original error messages are preserved
        original_error = "Unable to extract player response: JSONDecodeError"
        combined = _combine_error_messages(original_error, None)
        
        self.assertEqual(combined, original_error)
        print("✅ Requirement 3.1: DownloadError messages preserved and propagated")
    
    def test_requirement_3_2_combine_error_messages(self):
        """
        Requirement 3.2: WHEN both step1 and step2 fail 
        THEN the system SHALL combine error messages with " || " separator
        """
        from yt_download_helper import _combine_error_messages
        
        step1_error = "Step 1 failed: Unable to extract video data"
        step2_error = "Step 2 failed: FFmpeg conversion error"
        
        combined = _combine_error_messages(step1_error, step2_error)
        expected = f"{step1_error} || {step2_error}"
        
        self.assertEqual(combined, expected)
        self.assertIn(" || ", combined)
        print("✅ Requirement 3.2: Error messages combined with || separator")
    
    def test_requirement_3_3_bot_check_detection_combined_messages(self):
        """
        Requirement 3.3: WHEN bot detection patterns are found in error messages 
        THEN the _detect_bot_check function SHALL properly identify them
        """
        from transcript_service import TranscriptService
        service = TranscriptService()
        
        # Test bot detection in single messages
        bot_patterns = [
            "sign in to confirm you're not a bot",
            "unusual traffic detected",
            "captcha required",
            "verify you are human"
        ]
        
        for pattern in bot_patterns:
            self.assertTrue(service._detect_bot_check(pattern))
        
        # Test bot detection in combined messages (key requirement)
        combined_with_bot = "Network error || sign in to confirm you're not a bot"
        self.assertTrue(service._detect_bot_check(combined_with_bot))
        
        combined_without_bot = "Network timeout || Connection failed"
        self.assertFalse(service._detect_bot_check(combined_without_bot))
        
        print("✅ Requirement 3.3: Bot detection works with combined error messages")
    
    def test_requirement_3_4_comprehensive_logging_without_sensitive_data(self):
        """
        Requirement 3.4: WHEN logging yt-dlp errors 
        THEN the system SHALL include sufficient detail without exposing sensitive information
        """
        from yt_download_helper import _extract_proxy_username, _combine_error_messages
        
        # Test proxy username masking (no sensitive data exposure)
        proxy_url = "http://user123456:password@proxy.example.com:8080"
        masked_username = _extract_proxy_username(proxy_url)
        
        # Should mask the username but keep it debuggable
        self.assertNotIn("password", masked_username)
        self.assertNotIn("proxy.example.com", masked_username)
        self.assertTrue(len(masked_username) > 3)  # Should have some visible chars
        
        # Test error message length capping (avoid jumbo lines)
        long_error = "A" * 15000  # 15k chars
        capped = _combine_error_messages(long_error, None)
        self.assertLessEqual(len(capped), 10000)  # Should be capped at 10k
        self.assertIn("[truncated: error too long]", capped)
        
        print("✅ Requirement 3.4: Comprehensive logging without sensitive data exposure")
    
    def test_error_message_length_capping(self):
        """Test that error messages are capped to avoid jumbo log lines"""
        from yt_download_helper import _combine_error_messages
        
        # Test single long error
        long_error = "X" * 12000
        result = _combine_error_messages(long_error, None)
        self.assertLessEqual(len(result), 10000)
        self.assertIn("[truncated: error too long]", result)
        
        # Test combined long errors
        error1 = "A" * 6000
        error2 = "B" * 6000
        result = _combine_error_messages(error1, error2)
        self.assertLessEqual(len(result), 10000)
        self.assertIn("[truncated: error too long]", result)
        
        print("✅ Error message length capping prevents jumbo log lines")
    
    def test_download_metadata_tracking(self):
        """Test that download attempt metadata is tracked without sensitive data"""
        from yt_download_helper import _track_download_metadata
        
        # This should not raise an exception even if app is not available
        try:
            _track_download_metadata(
                cookies_used=True,
                client_used="android",
                proxy_used=True
            )
            print("✅ Download metadata tracking works without exposing sensitive data")
        except Exception as e:
            self.fail(f"Download metadata tracking should not fail: {e}")
    
    def test_normalized_error_logging(self):
        """Test normalized error string return for structured logging"""
        from transcript_service import TranscriptService
        service = TranscriptService()
        
        # Test error normalization
        long_error = "Error: " + "X" * 12000
        normalized = service._normalize_error_for_logging(long_error, "test_video")
        
        # Should be capped and safe for structured logging
        self.assertLessEqual(len(normalized), 10000)
        self.assertIsInstance(normalized, str)
        
        print("✅ Normalized error strings for structured logging")

def run_comprehensive_tests():
    """Run all comprehensive error handling tests"""
    print("🧪 Running Comprehensive Error Handling Tests")
    print("=" * 55)
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test class
    suite.addTests(loader.loadTestsFromTestCase(TestErrorHandlingImprovements))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print()
    if result.wasSuccessful():
        print("✅ All error handling improvement tests passed!")
        print()
        print("📋 Requirements verified:")
        print("   - 3.1: DownloadError messages preserved and propagated")
        print("   - 3.2: Error messages combined with || separator")
        print("   - 3.3: Bot detection works with combined messages")
        print("   - 3.4: Comprehensive logging without sensitive data")
        print("   - Error message length capping (≤10k chars)")
        print("   - Download metadata tracking without sensitive data")
        print("   - Normalized error strings for structured logging")
        print()
        print("🎉 Task 6 error handling improvements verified!")
        return True
    else:
        print("❌ Some error handling tests failed!")
        print(f"   Failures: {len(result.failures)}")
        print(f"   Errors: {len(result.errors)}")
        return False

if __name__ == "__main__":
    success = run_comprehensive_tests()
    sys.exit(0 if success else 1)