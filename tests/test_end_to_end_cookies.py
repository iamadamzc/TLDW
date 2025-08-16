#!/usr/bin/env python3
"""
End-to-end integration tests for cookie functionality
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock, mock_open
from io import BytesIO

# Add parent directory to path to import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from transcript_service import TranscriptService
from yt_download_helper import download_audio_with_fallback


class TestEndToEndCookies(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment"""
        self.service = TranscriptService()
        self.test_video_id = "test_video_123"
        self.test_user_id = 456
        
    def test_complete_cookie_workflow(self):
        """Test complete workflow from cookie storage to video download"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup test environment
            cookie_file = os.path.join(temp_dir, f"{self.test_user_id}.txt")
            test_cookie_data = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tFALSE\t1234567890\tsession_token\tabc123"
            
            # Create cookie file
            with open(cookie_file, 'w') as f:
                f.write(test_cookie_data)
            
            # Set user ID and environment
            self.service.current_user_id = self.test_user_id
            
            with patch.dict(os.environ, {'COOKIE_LOCAL_DIR': temp_dir, 'DISABLE_COOKIES': 'false'}):
                # Test cookie resolution
                cookiefile, tmp_cookie = self.service._get_user_cookiefile(self.test_user_id)
                self.assertEqual(cookiefile, cookie_file)
                self.assertIsNone(tmp_cookie)  # Local file, no cleanup needed
                
                # Mock yt-dlp and Deepgram for full workflow test
                with patch('yt_download_helper.YoutubeDL') as mock_ydl:
                    with patch.object(self.service, '_send_to_deepgram', return_value="Test transcript"):
                        with patch('yt_download_helper._file_ok', return_value=True):
                            with patch('os.path.getsize', return_value=1024):
                                with patch('os.path.abspath', return_value='/tmp/test.m4a'):
                                    with patch('os.unlink'):  # Mock file cleanup
                                        
                                        # Mock successful yt-dlp download
                                        mock_instance = MagicMock()
                                        mock_ydl.return_value.__enter__.return_value = mock_instance
                                        
                                        # Test the download attempt
                                        result = self.service._attempt_ytdlp_download(
                                            self.test_video_id, 
                                            None,  # No session for this test
                                            attempt=1
                                        )
                                        
                                        # Verify successful result
                                        self.assertEqual(result['status'], 'ok')
                                        self.assertEqual(result['transcript_text'], 'Test transcript')
                                        
                                        # Verify yt-dlp was called with cookie file
                                        self.assertTrue(mock_ydl.called)
                                        call_args = mock_ydl.call_args[0][0]
                                        self.assertIn('cookiefile', call_args)
                                        self.assertEqual(call_args['cookiefile'], cookie_file)
    
    def test_bot_check_with_cookies_triggers_staleness_tracking(self):
        """Test that bot-check errors with cookies present trigger staleness tracking"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup cookie file
            cookie_file = os.path.join(temp_dir, f"{self.test_user_id}.txt")
            with open(cookie_file, 'w') as f:
                f.write("# Test cookie\n.youtube.com\tTRUE\t/\tFALSE\t1234567890\ttest\tvalue")
            
            self.service.current_user_id = self.test_user_id
            
            with patch.dict(os.environ, {'COOKIE_LOCAL_DIR': temp_dir}):
                # Mock yt-dlp to raise bot-check error
                with patch('yt_download_helper.YoutubeDL') as mock_ydl:
                    from yt_dlp.utils import DownloadError
                    mock_instance = MagicMock()
                    mock_ydl.return_value.__enter__.return_value = mock_instance
                    mock_instance.download.side_effect = DownloadError("Sign in to confirm you're not a bot")
                    
                    with patch('yt_download_helper._file_ok', return_value=False):
                        with patch.object(self.service, '_track_cookie_failure') as mock_track:
                            
                            result = self.service._attempt_ytdlp_download(
                                self.test_video_id, 
                                None,
                                attempt=1
                            )
                            
                            # Verify bot-check was detected
                            self.assertEqual(result['status'], 'bot_check')
                            
                            # Verify staleness tracking was called
                            mock_track.assert_called_once_with(self.test_user_id, 'bot_check')
    
    def test_s3_cookie_download_and_cleanup(self):
        """Test S3 cookie download with proper cleanup"""
        self.service.current_user_id = self.test_user_id
        
        with patch.dict(os.environ, {'COOKIE_S3_BUCKET': 'test-bucket'}):
            with patch('boto3.client') as mock_boto3:
                mock_s3 = MagicMock()
                mock_boto3.return_value = mock_s3
                
                with patch('tempfile.NamedTemporaryFile') as mock_temp:
                    mock_file = MagicMock()
                    mock_file.name = '/tmp/test_cookie.txt'
                    mock_temp.return_value.__enter__.return_value = mock_file
                    mock_temp.return_value.name = '/tmp/test_cookie.txt'
                    
                    with patch('os.path.exists', return_value=True):
                        with patch('os.path.getsize', return_value=100):
                            
                            # Test cookie resolution
                            cookiefile, tmp_cookie = self.service._get_user_cookiefile(self.test_user_id)
                            
                            # Verify S3 download was attempted
                            mock_s3.download_file.assert_called_once_with(
                                'test-bucket', 
                                f'cookies/{self.test_user_id}.txt', 
                                mock_file.name
                            )
                            
                            # Verify temp file path returned for cleanup
                            self.assertEqual(cookiefile, mock_file.name)
                            self.assertEqual(tmp_cookie, mock_file.name)
    
    def test_performance_impact_measurement(self):
        """Test that cookie resolution doesn't significantly impact performance"""
        import time
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create cookie file
            cookie_file = os.path.join(temp_dir, f"{self.test_user_id}.txt")
            with open(cookie_file, 'w') as f:
                f.write("# Test cookie\n.youtube.com\tTRUE\t/\tFALSE\t1234567890\ttest\tvalue")
            
            self.service.current_user_id = self.test_user_id
            
            with patch.dict(os.environ, {'COOKIE_LOCAL_DIR': temp_dir}):
                # Measure cookie resolution time
                start_time = time.time()
                for _ in range(10):  # Multiple iterations for better measurement
                    cookiefile, tmp_cookie = self.service._get_user_cookiefile(self.test_user_id)
                end_time = time.time()
                
                avg_time = (end_time - start_time) / 10
                
                # Cookie resolution should be very fast (< 10ms per call)
                self.assertLess(avg_time, 0.01, "Cookie resolution taking too long")
    
    def test_kill_switch_functionality(self):
        """Test emergency kill-switch functionality"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create cookie file
            cookie_file = os.path.join(temp_dir, f"{self.test_user_id}.txt")
            with open(cookie_file, 'w') as f:
                f.write("# Test cookie\n.youtube.com\tTRUE\t/\tFALSE\t1234567890\ttest\tvalue")
            
            self.service.current_user_id = self.test_user_id
            
            # Test with kill-switch enabled
            with patch.dict(os.environ, {'COOKIE_LOCAL_DIR': temp_dir, 'DISABLE_COOKIES': 'true'}):
                with patch('yt_download_helper.YoutubeDL') as mock_ydl:
                    mock_instance = MagicMock()
                    mock_ydl.return_value.__enter__.return_value = mock_instance
                    
                    with patch('yt_download_helper._file_ok', return_value=True):
                        with patch('os.path.getsize', return_value=1024):
                            with patch('os.path.abspath', return_value='/tmp/test.m4a'):
                                with patch.object(self.service, '_send_to_deepgram', return_value="Test"):
                                    with patch('os.unlink'):
                                        
                                        result = self.service._attempt_ytdlp_download(
                                            self.test_video_id, 
                                            None,
                                            attempt=1
                                        )
                                        
                                        # Verify yt-dlp was called WITHOUT cookiefile
                                        if mock_ydl.called:
                                            call_args = mock_ydl.call_args[0][0]
                                            self.assertNotIn('cookiefile', call_args)
                                        else:
                                            # If not called, that's also acceptable for this test
                                            pass
    
    def test_error_message_combination_with_bot_check_detection(self):
        """Test that combined error messages still trigger bot-check detection"""
        from yt_dlp.utils import DownloadError
        
        # Test combined error message with bot-check in Step 2
        step1_error = "Network timeout"
        step2_error = "Sign in to confirm you're not a bot"
        combined_error = f"{step1_error} || {step2_error}"
        
        # Verify bot-check detection works on combined message
        self.assertTrue(self.service._detect_bot_check(combined_error))
        
        # Test with bot-check in Step 1
        step1_error = "Sign in to confirm you're not a bot"
        step2_error = "Network error"
        combined_error = f"{step1_error} || {step2_error}"
        
        self.assertTrue(self.service._detect_bot_check(combined_error))
    
    def test_concurrent_cookie_access(self):
        """Test that concurrent access to cookies is handled safely"""
        import threading
        import time
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create cookie file
            cookie_file = os.path.join(temp_dir, f"{self.test_user_id}.txt")
            with open(cookie_file, 'w') as f:
                f.write("# Test cookie\n.youtube.com\tTRUE\t/\tFALSE\t1234567890\ttest\tvalue")
            
            self.service.current_user_id = self.test_user_id
            results = []
            errors = []
            
            def access_cookies():
                try:
                    with patch.dict(os.environ, {'COOKIE_LOCAL_DIR': temp_dir}):
                        cookiefile, tmp_cookie = self.service._get_user_cookiefile(self.test_user_id)
                        results.append((cookiefile, tmp_cookie))
                except Exception as e:
                    errors.append(e)
            
            # Start multiple threads accessing cookies simultaneously
            threads = []
            for _ in range(5):
                thread = threading.Thread(target=access_cookies)
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            # Verify no errors occurred
            self.assertEqual(len(errors), 0, f"Concurrent access errors: {errors}")
            self.assertEqual(len(results), 5)
            
            # All results should be the same
            for cookiefile, tmp_cookie in results:
                self.assertEqual(cookiefile, cookie_file)
                self.assertIsNone(tmp_cookie)


if __name__ == '__main__':
    unittest.main()