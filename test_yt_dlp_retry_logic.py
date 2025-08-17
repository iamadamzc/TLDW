#!/usr/bin/env python3
"""
Test script for yt-dlp retry logic and cookie handling enhancements.
Tests the new retry functionality without requiring actual YouTube downloads.
"""

import os
import sys
import tempfile
import time
import logging
from unittest.mock import Mock, patch, MagicMock

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from yt_download_helper import (
    _check_cookie_freshness,
    _detect_cookie_invalidation,
    _detect_extraction_failure,
    download_audio_with_retry
)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def test_cookie_freshness():
    """Test cookie freshness detection"""
    print("\n=== Testing Cookie Freshness Detection ===")
    
    # Test with no cookie file
    assert _check_cookie_freshness(None) == True
    assert _check_cookie_freshness("nonexistent.txt") == True
    print("✅ No cookie file: returns True")
    
    # Test with fresh cookie file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        tmp.write(b"# Netscape HTTP Cookie File\n")
        tmp_path = tmp.name
    
    try:
        # Fresh file (just created)
        assert _check_cookie_freshness(tmp_path) == True
        print("✅ Fresh cookie file: returns True")
        
        # Simulate old file by modifying mtime
        old_time = time.time() - (13 * 3600)  # 13 hours ago
        os.utime(tmp_path, (old_time, old_time))
        
        assert _check_cookie_freshness(tmp_path) == False
        print("✅ Stale cookie file (13h old): returns False with warning")
        
    finally:
        os.unlink(tmp_path)

def test_cookie_invalidation_detection():
    """Test cookie invalidation pattern detection"""
    print("\n=== Testing Cookie Invalidation Detection ===")
    
    # Test positive cases
    invalid_patterns = [
        "The provided YouTube account cookies are no longer valid",
        "cookies are no longer valid",
        "Cookie has expired",
        "Invalid cookies detected"
    ]
    
    for pattern in invalid_patterns:
        assert _detect_cookie_invalidation(pattern) == True
        print(f"✅ Detected: '{pattern[:50]}...'")
    
    # Test negative cases
    valid_patterns = [
        "Network error occurred",
        "Unable to connect to server",
        "Video is private",
        ""
    ]
    
    for pattern in valid_patterns:
        assert _detect_cookie_invalidation(pattern) == False
        print(f"✅ Not detected: '{pattern}'")

def test_extraction_failure_detection():
    """Test extraction failure pattern detection"""
    print("\n=== Testing Extraction Failure Detection ===")
    
    # Test positive cases
    extraction_patterns = [
        "Unable to extract player response",
        "Unable to extract video data",
        "Extraction failed for this video",
        "Video unavailable"
    ]
    
    for pattern in extraction_patterns:
        assert _detect_extraction_failure(pattern) == True
        print(f"✅ Detected: '{pattern}'")
    
    # Test negative cases
    non_extraction_patterns = [
        "Network timeout",
        "407 Proxy Authentication Required",
        "Connection refused",
        ""
    ]
    
    for pattern in non_extraction_patterns:
        assert _detect_extraction_failure(pattern) == False
        print(f"✅ Not detected: '{pattern}'")

def test_retry_logic_mock():
    """Test retry logic with mocked yt-dlp calls"""
    print("\n=== Testing Retry Logic (Mocked) ===")
    
    # Create a temporary cookie file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        tmp.write(b"# Netscape HTTP Cookie File\n")
        cookie_path = tmp.name
    
    try:
        # Test 1: Success on first attempt
        print("\n--- Test 1: Success on first attempt ---")
        with patch('yt_download_helper.download_audio_with_fallback') as mock_fallback:
            mock_fallback.return_value = "/tmp/audio.m4a"
            
            result = download_audio_with_retry(
                "https://www.youtube.com/watch?v=test",
                "Mozilla/5.0 Test",
                "http://proxy:8080",
                "/usr/bin",
                logger=print,
                cookiefile=cookie_path
            )
            
            assert result == "/tmp/audio.m4a"
            assert mock_fallback.call_count == 1
            print("✅ Success on first attempt with cookies")
        
        # Test 2: Cookie invalidation, retry without cookies
        print("\n--- Test 2: Cookie invalidation, retry without cookies ---")
        with patch('yt_download_helper.download_audio_with_fallback') as mock_fallback:
            # First call fails with cookie error, second succeeds
            mock_fallback.side_effect = [
                RuntimeError("The provided YouTube account cookies are no longer valid"),
                "/tmp/audio.m4a"
            ]
            
            result = download_audio_with_retry(
                "https://www.youtube.com/watch?v=test",
                "Mozilla/5.0 Test", 
                "http://proxy:8080",
                "/usr/bin",
                logger=print,
                cookiefile=cookie_path,
                user_id=123
            )
            
            assert result == "/tmp/audio.m4a"
            assert mock_fallback.call_count == 2
            
            # Verify first call used cookies, second didn't
            # call_args_list contains (args, kwargs) tuples
            first_call_args, first_call_kwargs = mock_fallback.call_args_list[0]
            second_call_args, second_call_kwargs = mock_fallback.call_args_list[1]
            
            # Check both positional args (index 5 = cookiefile) and kwargs
            first_call_cookies = (first_call_kwargs.get('cookiefile') or 
                                 (first_call_args[5] if len(first_call_args) > 5 else None))
            second_call_cookies = (second_call_kwargs.get('cookiefile') or 
                                  (second_call_args[5] if len(second_call_args) > 5 else None))
            
            assert first_call_cookies == cookie_path
            assert second_call_cookies is None
            print("✅ Cookie invalidation detected, retried without cookies")
        
        # Test 3: Extraction failure, retry without cookies
        print("\n--- Test 3: Extraction failure, retry without cookies ---")
        with patch('yt_download_helper.download_audio_with_fallback') as mock_fallback:
            # First call fails with extraction error, second succeeds
            mock_fallback.side_effect = [
                RuntimeError("Unable to extract player response"),
                "/tmp/audio.m4a"
            ]
            
            result = download_audio_with_retry(
                "https://www.youtube.com/watch?v=test",
                "Mozilla/5.0 Test",
                "http://proxy:8080", 
                "/usr/bin",
                logger=print,
                cookiefile=cookie_path
            )
            
            assert result == "/tmp/audio.m4a"
            assert mock_fallback.call_count == 2
            print("✅ Extraction failure detected, retried without cookies")
        
        # Test 4: Both attempts fail, proper error message
        print("\n--- Test 4: Both attempts fail ---")
        with patch('yt_download_helper.download_audio_with_fallback') as mock_fallback:
            mock_fallback.side_effect = [
                RuntimeError("The provided YouTube account cookies are no longer valid"),
                RuntimeError("Unable to extract player response")
            ]
            
            try:
                download_audio_with_retry(
                    "https://www.youtube.com/watch?v=test",
                    "Mozilla/5.0 Test",
                    "http://proxy:8080",
                    "/usr/bin", 
                    logger=print,
                    cookiefile=cookie_path
                )
                assert False, "Should have raised RuntimeError"
            except RuntimeError as e:
                error_msg = str(e)
                assert "Attempt 1:" in error_msg
                assert "Attempt 2:" in error_msg
                assert "consider updating yt-dlp" in error_msg
                print("✅ Both attempts failed with combined error message")
        
        # Test 5: Stale cookies skipped automatically
        print("\n--- Test 5: Stale cookies skipped automatically ---")
        
        # Make cookie file stale
        old_time = time.time() - (13 * 3600)  # 13 hours ago
        os.utime(cookie_path, (old_time, old_time))
        
        with patch('yt_download_helper.download_audio_with_fallback') as mock_fallback:
            mock_fallback.return_value = "/tmp/audio.m4a"
            
            result = download_audio_with_retry(
                "https://www.youtube.com/watch?v=test",
                "Mozilla/5.0 Test",
                "http://proxy:8080",
                "/usr/bin",
                logger=print,
                cookiefile=cookie_path
            )
            
            assert result == "/tmp/audio.m4a"
            assert mock_fallback.call_count == 1
            
            # Verify cookies were not used due to staleness
            call_cookies = mock_fallback.call_args_list[0][1].get('cookiefile')
            assert call_cookies is None
            print("✅ Stale cookies automatically skipped")
            
    finally:
        os.unlink(cookie_path)

def main():
    """Run all tests"""
    print("🧪 Testing yt-dlp Retry Logic and Cookie Handling")
    print("=" * 60)
    
    try:
        test_cookie_freshness()
        test_cookie_invalidation_detection()
        test_extraction_failure_detection()
        test_retry_logic_mock()
        
        print("\n" + "=" * 60)
        print("🎉 All tests passed! Retry logic implementation is working correctly.")
        print("\nKey features verified:")
        print("✅ Cookie freshness checking (12-hour threshold)")
        print("✅ Cookie invalidation detection from yt-dlp errors")
        print("✅ Extraction failure detection")
        print("✅ Automatic retry without cookies on failure")
        print("✅ Proper error logging and user feedback")
        print("✅ Stale cookie automatic skipping")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
