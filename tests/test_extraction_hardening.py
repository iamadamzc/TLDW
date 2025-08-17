"""
Unit tests for yt-dlp extraction hardening functionality.
Tests the enhanced failure detection patterns and mandatory A/B testing logic.
"""

import unittest
from unittest.mock import patch, MagicMock
import os
import tempfile
import time

# Import the functions we're testing
from yt_download_helper import (
    _detect_extraction_failure,
    _detect_cookie_invalidation,
    _check_cookie_freshness,
    download_audio_with_retry
)


class TestExtractionFailureDetection(unittest.TestCase):
    """Test the enhanced extraction failure detection patterns."""
    
    def test_existing_patterns_still_work(self):
        """Test that existing extraction failure patterns continue to work."""
        existing_patterns = [
            "unable to extract player response",
            "unable to extract video data", 
            "unable to extract initial player response",
            "video unavailable",
            "this video is not available",
            "extraction failed"
        ]
        
        for pattern in existing_patterns:
            with self.subTest(pattern=pattern):
                self.assertTrue(_detect_extraction_failure(pattern))
                # Test case insensitive
                self.assertTrue(_detect_extraction_failure(pattern.upper()))
                self.assertTrue(_detect_extraction_failure(pattern.capitalize()))
    
    def test_new_extraction_patterns(self):
        """Test the new YouTube extraction failure patterns."""
        new_patterns = [
            "unable to extract yt initial data",
            "failed to parse json",
            "unable to extract player version", 
            "failed to extract any player response"
        ]
        
        for pattern in new_patterns:
            with self.subTest(pattern=pattern):
                self.assertTrue(_detect_extraction_failure(pattern))
                # Test case insensitive
                self.assertTrue(_detect_extraction_failure(pattern.upper()))
                self.assertTrue(_detect_extraction_failure(pattern.capitalize()))
    
    def test_case_insensitive_matching(self):
        """Test that pattern matching is case insensitive."""
        test_cases = [
            "UNABLE TO EXTRACT YT INITIAL DATA",
            "Failed To Parse JSON",
            "Unable To Extract Player Version",
            "FAILED TO EXTRACT ANY PLAYER RESPONSE"
        ]
        
        for error_text in test_cases:
            with self.subTest(error_text=error_text):
                self.assertTrue(_detect_extraction_failure(error_text))
    
    def test_non_extraction_errors_not_detected(self):
        """Test that non-extraction errors are not detected as extraction failures."""
        non_extraction_errors = [
            "network timeout",
            "connection refused", 
            "proxy authentication required",
            "403 forbidden",
            "rate limited",
            "cookies are no longer valid",
            "some random error message"
        ]
        
        for error_text in non_extraction_errors:
            with self.subTest(error_text=error_text):
                self.assertFalse(_detect_extraction_failure(error_text))
    
    def test_http_throttling_detection(self):
        """Test HTTP throttling detection patterns."""
        from yt_download_helper import _detect_http_throttling
        
        throttling_patterns = [
            "HTTP Error 429: Too Many Requests",
            "HTTP 429 rate limited",
            " 429 ",
            "HTTP 403 Forbidden",
            "http 403 access denied",
            "forbidden by server"
        ]
        
        for pattern in throttling_patterns:
            with self.subTest(pattern=pattern):
                self.assertTrue(_detect_http_throttling(pattern))
        
        # Test non-throttling errors
        non_throttling = [
            "network timeout",
            "connection refused",
            "404 not found",
            "500 internal server error"
        ]
        
        for pattern in non_throttling:
            with self.subTest(pattern=pattern):
                self.assertFalse(_detect_http_throttling(pattern))
    
    def test_empty_or_none_input(self):
        """Test that empty or None input returns False."""
        self.assertFalse(_detect_extraction_failure(""))
        self.assertFalse(_detect_extraction_failure(None))
    
    def test_partial_matches_work(self):
        """Test that patterns work when embedded in longer error messages."""
        long_error = "ERROR: [youtube] abc123: unable to extract yt initial data; please report this issue"
        self.assertTrue(_detect_extraction_failure(long_error))
        
        another_error = "yt-dlp: error: failed to parse json response from YouTube API"
        self.assertTrue(_detect_extraction_failure(another_error))


class TestCookieFreshnessDetection(unittest.TestCase):
    """Test cookie freshness detection for stale cookie handling."""
    
    def setUp(self):
        """Set up temporary files for testing."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_fresh_cookie_file(self):
        """Test that a fresh cookie file is detected as fresh."""
        # Create a fresh cookie file
        cookie_file = os.path.join(self.temp_dir, "fresh_cookies.txt")
        with open(cookie_file, 'w') as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write(".youtube.com\tTRUE\t/\tFALSE\t1234567890\ttest\tvalue\n")
        
        self.assertTrue(_check_cookie_freshness(cookie_file))
    
    def test_stale_cookie_file(self):
        """Test that a stale cookie file (>12h) is detected as stale."""
        # Create a stale cookie file
        cookie_file = os.path.join(self.temp_dir, "stale_cookies.txt")
        with open(cookie_file, 'w') as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write(".youtube.com\tTRUE\t/\tFALSE\t1234567890\ttest\tvalue\n")
        
        # Set modification time to 13 hours ago
        thirteen_hours_ago = time.time() - (13 * 3600)
        os.utime(cookie_file, (thirteen_hours_ago, thirteen_hours_ago))
        
        self.assertFalse(_check_cookie_freshness(cookie_file))
    
    def test_nonexistent_cookie_file(self):
        """Test that nonexistent cookie file is treated as fresh (no error)."""
        nonexistent_file = os.path.join(self.temp_dir, "nonexistent.txt")
        self.assertTrue(_check_cookie_freshness(nonexistent_file))
    
    def test_none_cookie_file(self):
        """Test that None cookie file is treated as fresh."""
        self.assertTrue(_check_cookie_freshness(None))


class TestMandatoryABTesting(unittest.TestCase):
    """Test the mandatory A/B testing logic in download_audio_with_retry."""
    
    @patch('yt_download_helper.download_audio_with_fallback')
    @patch('yt_download_helper._check_cookie_freshness')
    def test_extraction_failure_triggers_retry_with_fresh_cookies(self, mock_freshness, mock_fallback):
        """Test that extraction failure triggers retry even with fresh cookies."""
        # Setup: fresh cookies, extraction failure on attempt 1, success on attempt 2
        mock_freshness.return_value = True
        mock_fallback.side_effect = [
            RuntimeError("unable to extract yt initial data"),  # Attempt 1 fails
            "/tmp/audio.m4a"  # Attempt 2 succeeds
        ]
        
        # Test
        result = download_audio_with_retry(
            "https://youtube.com/watch?v=test",
            "test-ua",
            "http://proxy:8080",
            cookiefile="/tmp/cookies.txt"
        )
        
        # Verify
        self.assertEqual(result, "/tmp/audio.m4a")
        self.assertEqual(mock_fallback.call_count, 2)
        
        # Verify call arguments - check how the function was called
        first_call = mock_fallback.call_args_list[0]
        second_call = mock_fallback.call_args_list[1]
        
        # The function should be called with cookiefile as keyword argument
        # First call should use cookies
        if 'cookiefile' in first_call.kwargs:
            self.assertEqual(first_call.kwargs['cookiefile'], "/tmp/cookies.txt")
        else:
            # If positional, cookiefile is the 6th parameter (index 5)
            self.assertEqual(first_call.args[5], "/tmp/cookies.txt")
        
        # Second call should not use cookies
        if 'cookiefile' in second_call.kwargs:
            self.assertIsNone(second_call.kwargs['cookiefile'])
        else:
            # If positional, check if there are enough args
            if len(second_call.args) > 5:
                self.assertIsNone(second_call.args[5])
            else:
                # cookiefile not passed, which means None (default)
                pass
    
    @patch('yt_download_helper.download_audio_with_fallback')
    @patch('yt_download_helper._check_cookie_freshness')
    def test_cookie_invalid_triggers_retry(self, mock_freshness, mock_fallback):
        """Test that cookie invalidation triggers retry."""
        # Setup: fresh cookies, cookie invalid on attempt 1, success on attempt 2
        mock_freshness.return_value = True
        mock_fallback.side_effect = [
            RuntimeError("cookies are no longer valid"),  # Attempt 1 fails
            "/tmp/audio.m4a"  # Attempt 2 succeeds
        ]
        
        # Test
        result = download_audio_with_retry(
            "https://youtube.com/watch?v=test",
            "test-ua", 
            "http://proxy:8080",
            cookiefile="/tmp/cookies.txt"
        )
        
        # Verify
        self.assertEqual(result, "/tmp/audio.m4a")
        self.assertEqual(mock_fallback.call_count, 2)
    
    @patch('yt_download_helper.download_audio_with_fallback')
    @patch('yt_download_helper._check_cookie_freshness')
    def test_stale_cookies_skip_attempt_1(self, mock_freshness, mock_fallback):
        """Test that stale cookies result in use_cookies=false for attempt 1."""
        # Setup: stale cookies, success on attempt 1 (without cookies)
        mock_freshness.return_value = False
        mock_fallback.return_value = "/tmp/audio.m4a"
        
        # Test
        result = download_audio_with_retry(
            "https://youtube.com/watch?v=test",
            "test-ua",
            "http://proxy:8080", 
            cookiefile="/tmp/stale_cookies.txt"
        )
        
        # Verify
        self.assertEqual(result, "/tmp/audio.m4a")
        self.assertEqual(mock_fallback.call_count, 1)
        
        # Should not use cookies due to staleness (cookiefile is 6th positional argument, index 5)
        call_args = mock_fallback.call_args_list[0]
        self.assertIsNone(call_args[0][5])  # cookiefile parameter
    
    @patch.dict(os.environ, {'DISABLE_COOKIES': 'true'})
    @patch('yt_download_helper.download_audio_with_fallback')
    @patch('yt_download_helper._check_cookie_freshness')
    def test_disable_cookies_environment_flag(self, mock_freshness, mock_fallback):
        """Test that DISABLE_COOKIES=true skips all cookie usage."""
        # Setup: fresh cookies but environment disabled, success on attempt 1
        mock_freshness.return_value = True
        mock_fallback.return_value = "/tmp/audio.m4a"
        
        # Test
        result = download_audio_with_retry(
            "https://youtube.com/watch?v=test",
            "test-ua",
            "http://proxy:8080",
            cookiefile="/tmp/cookies.txt"
        )
        
        # Verify
        self.assertEqual(result, "/tmp/audio.m4a")
        self.assertEqual(mock_fallback.call_count, 1)
        
        # Should not use cookies due to environment flag (cookiefile is 6th positional argument, index 5)
        call_args = mock_fallback.call_args_list[0]
        self.assertIsNone(call_args[0][5])  # cookiefile parameter
    
    @patch('yt_download_helper.download_audio_with_fallback')
    @patch('yt_download_helper._check_cookie_freshness')
    def test_both_attempts_fail_error_format(self, mock_freshness, mock_fallback):
        """Test that both attempts failing produces correct error format."""
        # Setup: both attempts fail
        mock_freshness.return_value = True
        mock_fallback.side_effect = [
            RuntimeError("failed to parse json"),  # Attempt 1 fails
            RuntimeError("video unavailable")      # Attempt 2 fails
        ]
        
        # Test
        with self.assertRaises(RuntimeError) as context:
            download_audio_with_retry(
                "https://youtube.com/watch?v=test",
                "test-ua",
                "http://proxy:8080",
                cookiefile="/tmp/cookies.txt"
            )
        
        # Verify error format
        error_msg = str(context.exception)
        self.assertIn("Attempt 1: failed to parse json", error_msg)
        self.assertIn("Attempt 2: video unavailable", error_msg)
        self.assertIn("consider updating yt-dlp", error_msg)
    
    @patch('yt_download_helper.download_audio_with_fallback')
    @patch('yt_download_helper._check_cookie_freshness')
    @patch('time.sleep')
    def test_backoff_sleep_between_attempts(self, mock_sleep, mock_freshness, mock_fallback):
        """Test that there's a sleep between attempt 1 and attempt 2."""
        # Setup: extraction failure triggers retry
        mock_freshness.return_value = True
        mock_fallback.side_effect = [
            RuntimeError("unable to extract player version"),  # Attempt 1 fails
            "/tmp/audio.m4a"  # Attempt 2 succeeds
        ]
        
        # Test
        download_audio_with_retry(
            "https://youtube.com/watch?v=test",
            "test-ua",
            "http://proxy:8080",
            cookiefile="/tmp/cookies.txt"
        )
        
        # Verify sleep was called
        mock_sleep.assert_called_once()
        # Verify sleep time is between 1-2 seconds
        sleep_time = mock_sleep.call_args[0][0]
        self.assertGreaterEqual(sleep_time, 1.0)
        self.assertLessEqual(sleep_time, 2.0)


if __name__ == '__main__':
    unittest.main()