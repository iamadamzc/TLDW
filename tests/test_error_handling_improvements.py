#!/usr/bin/env python3
"""
Test error handling improvements for yt-dlp and transcript service
"""

import os
import sys
from unittest.mock import patch, MagicMock

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_error_message_combination():
    """Test that error messages are combined correctly with || separator"""
    print("Testing error message combination...")
    
    try:
        from yt_download_helper import _combine_error_messages
        
        # Test both errors present
        step1_error = "Unable to extract video data"
        step2_error = "Re-encoding failed"
        combined = _combine_error_messages(step1_error, step2_error)
        
        expected = "Unable to extract video data || Re-encoding failed"
        if combined != expected:
            print(f"❌ Expected: {expected}")
            print(f"   Got: {combined}")
            return False
        
        # Test only step1 error
        combined_step1_only = _combine_error_messages(step1_error, None)
        if combined_step1_only != step1_error:
            print(f"❌ Step1 only failed: expected {step1_error}, got {combined_step1_only}")
            return False
        
        # Test only step2 error
        combined_step2_only = _combine_error_messages(None, step2_error)
        if combined_step2_only != step2_error:
            print(f"❌ Step2 only failed: expected {step2_error}, got {combined_step2_only}")
            return False
        
        # Test no errors
        combined_none = _combine_error_messages(None, None)
        if combined_none != "Unknown download error":
            print(f"❌ No errors failed: expected 'Unknown download error', got {combined_none}")
            return False
        
        print("✅ Error message combination works correctly")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test error combination: {e}")
        return False

def test_error_message_length_capping():
    """Test that error messages are capped at 10k characters"""
    print("Testing error message length capping...")
    
    try:
        from yt_download_helper import _combine_error_messages
        
        # Create a very long error message
        long_error = "A" * 15000  # 15k characters
        short_error = "Short error"
        
        combined = _combine_error_messages(long_error, short_error)
        
        # Should be capped at 10k characters
        if len(combined) > 10000:
            print(f"❌ Error message not capped: length {len(combined)}")
            return False
        
        # Should contain truncation message
        if "[truncated: error too long]" not in combined:
            print("❌ Missing truncation message")
            return False
        
        print(f"✅ Error message properly capped at {len(combined)} characters")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test error capping: {e}")
        return False

def test_bot_detection_with_combined_messages():
    """Test that bot detection works with combined error messages"""
    print("Testing bot detection with combined messages...")
    
    try:
        from transcript_service import TranscriptService
        
        service = TranscriptService()
        
        # Test individual bot detection patterns
        bot_patterns = [
            "sign in to confirm you're not a bot",
            "unusual traffic",
            "captcha required",
            "verify you are human"
        ]
        
        for pattern in bot_patterns:
            if not service._detect_bot_check(pattern):
                print(f"❌ Failed to detect bot pattern: {pattern}")
                return False
        
        # Test combined error messages with bot detection
        combined_with_bot = "Unable to extract video data || sign in to confirm you're not a bot"
        if not service._detect_bot_check(combined_with_bot):
            print("❌ Failed to detect bot pattern in combined message")
            return False
        
        # Test combined error without bot detection
        combined_without_bot = "Network timeout || Connection failed"
        if service._detect_bot_check(combined_without_bot):
            print("❌ False positive bot detection in combined message")
            return False
        
        print("✅ Bot detection works correctly with combined messages")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test bot detection: {e}")
        return False

def test_error_normalization_for_logging():
    """Test that errors are normalized for logging without sensitive data"""
    print("Testing error normalization for logging...")
    
    try:
        from transcript_service import TranscriptService
        
        service = TranscriptService()
        
        # Test error with sensitive information
        sensitive_error = (
            "Failed to download http://user:pass@proxy.example.com:8080 "
            "from https://www.youtube.com/watch?v=dQw4w9WgXcQ "
            "to /tmp/audio_file.m4a"
        )
        
        normalized = service._normalize_error_for_logging(sensitive_error, "test_video")
        
        # Should not contain sensitive information
        sensitive_patterns = ["user:pass", "proxy.example.com", "/tmp/audio_file.m4a"]
        
        for pattern in sensitive_patterns:
            if pattern in normalized:
                print(f"❌ Sensitive data not removed: {pattern}")
                return False
        
        # Should contain sanitized placeholders
        expected_placeholders = ["[proxy_url]", "[url]", "[audio_file]"]
        
        for placeholder in expected_placeholders:
            if placeholder not in normalized:
                print(f"❌ Missing sanitized placeholder: {placeholder}")
                return False
        
        print("✅ Error normalization removes sensitive data correctly")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test error normalization: {e}")
        return False

def test_download_metadata_tracking():
    """Test that download metadata is tracked correctly"""
    print("Testing download metadata tracking...")
    
    try:
        from yt_download_helper import _track_download_metadata
        
        # Mock the app module to avoid import issues
        mock_app = MagicMock()
        mock_update_function = MagicMock()
        mock_app.update_download_metadata = mock_update_function
        
        with patch.dict('sys.modules', {'app': mock_app}):
            # Test metadata tracking
            _track_download_metadata(
                cookies_used=True,
                client_used="android",
                proxy_used=True
            )
            
            # Should call update function with correct parameters
            mock_update_function.assert_called_once_with(
                used_cookies=True,
                client_used="android"
            )
        
        print("✅ Download metadata tracking works correctly")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test metadata tracking: {e}")
        return False

def test_error_propagation_preserves_original():
    """Test that original yt-dlp error messages are preserved"""
    print("Testing error propagation preserves original messages...")
    
    try:
        from yt_dlp.utils import DownloadError
        from yt_download_helper import _combine_error_messages
        
        # Simulate original yt-dlp errors
        original_error1 = "ERROR: [youtube] dQw4w9WgXcQ: Unable to extract player response"
        original_error2 = "ERROR: ffmpeg not found. Please install ffmpeg"
        
        # Combine the errors
        combined = _combine_error_messages(original_error1, original_error2)
        
        # Should contain both original messages
        if original_error1 not in combined:
            print(f"❌ Original error1 not preserved in combined message")
            return False
        
        if original_error2 not in combined:
            print(f"❌ Original error2 not preserved in combined message")
            return False
        
        # Should use correct separator
        if " || " not in combined:
            print("❌ Missing || separator in combined message")
            return False
        
        print("✅ Error propagation preserves original messages")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test error propagation: {e}")
        return False

def test_structured_logging_format():
    """Test that structured logging maintains proper format"""
    print("Testing structured logging format...")
    
    try:
        from transcript_service import TranscriptService
        
        service = TranscriptService()
        
        # Test error normalization with various inputs
        test_cases = [
            ("Simple error message", "Simple error message"),
            ("", "unknown_error"),
            (None, "unknown_error")
        ]
        
        for input_error, expected_start in test_cases:
            normalized = service._normalize_error_for_logging(input_error, "test_video")
            
            if not normalized.startswith(expected_start) and expected_start != "unknown_error":
                print(f"❌ Unexpected normalization: {input_error} -> {normalized}")
                return False
            
            if expected_start == "unknown_error" and normalized != expected_start:
                print(f"❌ Expected {expected_start}, got {normalized}")
                return False
        
        print("✅ Structured logging format is maintained")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test structured logging: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing error handling improvements...")
    print()
    
    tests = [
        test_error_message_combination,
        test_error_message_length_capping,
        test_bot_detection_with_combined_messages,
        test_error_normalization_for_logging,
        test_download_metadata_tracking,
        test_error_propagation_preserves_original,
        test_structured_logging_format
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
        print()
    
    print(f"📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Error handling improvements are working correctly.")
        print("📝 Key features verified:")
        print("   - Error message combination with || separator")
        print("   - 10k character cap to avoid jumbo App Runner logs")
        print("   - Bot detection works with combined error messages")
        print("   - Error normalization removes sensitive data")
        print("   - Download metadata tracking for health endpoints")
        print("   - Original yt-dlp error messages preserved")
        print("   - Structured logging format maintained")
        sys.exit(0)
    else:
        print("💥 Some tests failed. Error handling needs fixes.")
        sys.exit(1)