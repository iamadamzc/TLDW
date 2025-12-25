"""
Unit tests for ytdlp_service with mocked yt-dlp.

All tests mock yt-dlp's extract_info() to avoid live network calls.
Tests cover: success cases, proxy integration, error handling with fail_class,
and format selection logic.
"""

import unittest
from unittest import mock
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestYtdlpService(unittest.TestCase):
    """Test ytdlp_service functionality with mocked yt-dlp"""
    
    def setUp(self):
        """Set up test environment"""
        # Clear environment variables
        os.environ.pop("DISABLE_YTDLP", None)
        os.environ.pop("ENFORCE_PROXY_ALL", None)
    
    @mock.patch('ytdlp_service.yt_dlp')
    def test_extract_best_audio_url_success(self, mock_ytdlp):
        """Test successful audio extraction"""
        from ytdlp_service import extract_best_audio_url
        
        # Mock yt-dlp extract_info return value
        mock_info = {
            'formats': [
                {
                    'url': 'https://example.com/audio1.m4a',
                    'ext': 'm4a',
                    'format_id': '140',
                    'abr': 128,
                    'acodec': 'm4a',
                    'vcodec': 'none'
                },
                {
                    'url': 'https://example.com/audio2.webm',
                    'ext': 'webm',
                    'format_id': '251',
                    'abr': 160,
                    'acodec': 'opus',
                    'vcodec': 'none'
                }
            ]
        }
        
        mock_ydl_instance = mock.MagicMock()
        mock_ydl_instance.extract_info.return_value = mock_info
        mock_ytdlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance
        
        # Call function
        result = extract_best_audio_url("dQw4w9WgXcQ")
        
        # Assertions
        self.assertTrue(result["success"])
        self.assertEqual(result["url"], "https://example.com/audio2.webm")  # Higher ABR
        self.assertEqual(result["ext"], "webm")
        self.assertEqual(result["format_id"], "251")
        self.assertEqual(result["abr"], 160)
        self.assertFalse(result["proxy_used"])
        
    @mock.patch('ytdlp_service.yt_dlp')
    def test_extract_with_proxy(self, mock_ytdlp):
        """Test audio extraction with proxy"""
        from ytdlp_service import extract_best_audio_url
        
        # Mock ProxyManager with correct API
        mock_proxy_manager = mock.MagicMock()
        mock_proxy_manager.proxy_dict_for_job.return_value = {
            "http": "http://user:pass@proxy.example.com:8080",
            "https": "https://user:pass@proxy.example.com:8080"
        }
        
        # Mock yt-dlp
        mock_info = {
            'formats': [{
                'url': 'https://example.com/audio.m4a',
                'ext': 'm4a',
                'format_id': '140',
                'abr': 128,
                'acodec': 'm4a',
                'vcodec': 'none'
            }]
        }
        
        mock_ydl_instance = mock.MagicMock()
        mock_ydl_instance.extract_info.return_value = mock_info
        mock_ytdlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance
        
        # Call function with proxy
        result = extract_best_audio_url(
            "dQw4w9WgXcQ",
            proxy_manager=mock_proxy_manager,
            job_id="test_job"
        )
        
        # Verify proxy_dict_for_job was called with correct arguments
        mock_proxy_manager.proxy_dict_for_job.assert_called_once_with("test_job", "requests")
        
        # Verify proxy was passed to yt-dlp (prefer https)
        call_args = mock_ytdlp.YoutubeDL.call_args[0][0]
        self.assertIn('proxy', call_args)
        self.assertEqual(call_args['proxy'], "https://user:pass@proxy.example.com:8080")
        
        # Verify result includes proxy info
        self.assertTrue(result["success"])
        self.assertTrue(result["proxy_used"])
        self.assertTrue(result["proxy_enabled"])
        self.assertIsNotNone(result["proxy_host"])
        self.assertIsNotNone(result["proxy_profile"])
        
    @mock.patch('ytdlp_service.yt_dlp')
    def test_error_classification(self, mock_ytdlp):
        """Test error handling with fail_class categorization"""
        from ytdlp_service import extract_best_audio_url
        
        # Test video_unavailable error
        mock_ydl_instance = mock.MagicMock()
        mock_ydl_instance.extract_info.side_effect = Exception("Video unavailable: This video is private")
        mock_ytdlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance
        
        result = extract_best_audio_url("private_video")
        
        self.assertFalse(result["success"])
        self.assertEqual(result["fail_class"], "video_unavailable")
        self.assertIn("Video unavailable", result["error"])
        
        # Test network_error
        mock_ydl_instance.extract_info.side_effect = Exception("Connection timeout")
        result = extract_best_audio_url("dQw4w9WgXcQ")
        
        self.assertFalse(result["success"])
        self.assertEqual(result["fail_class"], "network_error")
        
        # Test geo_blocked
        mock_ydl_instance.extract_info.side_effect = Exception("not available in your country")
        result = extract_best_audio_url("dQw4w9WgXcQ")
        
        self.assertFalse(result["success"])
        self.assertEqual(result["fail_class"], "geo_blocked")
        
    @mock.patch('ytdlp_service.yt_dlp')
    def test_format_selection_prefers_audio_only(self, mock_ytdlp):
        """Test that format selection prefers audio-only formats with highest ABR"""
        from ytdlp_service import extract_best_audio_url
        
        # Mock formats with mixed audio-only and video+audio
        mock_info = {
            'formats': [
                # Video with audio
                {
                    'url': 'https://example.com/video.mp4',
                    'ext': 'mp4',
                    'format_id': '18',
                    'abr': 96,
                    'acodec': 'mp4a',
                    'vcodec': 'avc1'
                },
                # Audio-only, lower quality
                {
                    'url': 'https://example.com/audio1.m4a',
                    'ext': 'm4a',
                    'format_id': '139',
                    'abr': 48,
                    'acodec': 'm4a',
                    'vcodec': 'none'
                },
                # Audio-only, higher quality - should be selected
                {
                    'url': 'https://example.com/audio2.m4a',
                    'ext': 'm4a',
                    'format_id': '140',
                    'abr': 128,
                    'acodec': 'm4a',
                    'vcodec': 'none'
                }
            ]
        }
        
        mock_ydl_instance = mock.MagicMock()
        mock_ydl_instance.extract_info.return_value = mock_info
        mock_ytdlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance
        
        result = extract_best_audio_url("dQw4w9WgXcQ")
        
        # Should select audio-only format with highest ABR (140, 128 kbps)
        self.assertTrue(result["success"])
        self.assertEqual(result["format_id"], "140")
        self.assertEqual(result["abr"], 128)
        self.assertEqual(result["ext"], "m4a")
        
    def test_disable_ytdlp_killswitch(self):
        """Test DISABLE_YTDLP=1 kill-switch"""
        from ytdlp_service import extract_best_audio_url
        
        # Set kill-switch
        os.environ["DISABLE_YTDLP"] = "1"
        
        result = extract_best_audio_url("dQw4w9WgXcQ")
        
        self.assertFalse(result["success"])
        self.assertEqual(result["fail_class"], "disabled")
        self.assertIn("kill-switch", result["error"])
        
    @mock.patch('ytdlp_service.yt_dlp')
    def test_enforce_proxy_all_safety(self, mock_ytdlp):
        """Test ENFORCE_PROXY_ALL=1 blocks execution when no proxy available"""
        from ytdlp_service import extract_best_audio_url
        
        # Set ENFORCE_PROXY_ALL
        os.environ["ENFORCE_PROXY_ALL"] = "1"
        
        # Mock ProxyManager that returns empty dict (no proxy)
        mock_proxy_manager = mock.MagicMock()
        mock_proxy_manager.proxy_dict_for_job.return_value = {}  # No proxy
        
        result = extract_best_audio_url(
            "dQw4w9WgXcQ",
            proxy_manager=mock_proxy_manager,
            job_id="test_job"
        )
        
        # Verify proxy_dict_for_job was called
        mock_proxy_manager.proxy_dict_for_job.assert_called_once_with("test_job", "requests")
        
        # Should fail with proxy_unavailable
        self.assertFalse(result["success"])
        self.assertEqual(result["fail_class"], "proxy_unavailable")
        self.assertIn("ENFORCE_PROXY_ALL", result["error"])
        self.assertFalse(result["proxy_used"])
        self.assertFalse(result["proxy_enabled"])
        
        # Verify yt-dlp was NOT called
        mock_ytdlp.YoutubeDL.assert_not_called()


if __name__ == "__main__":
    unittest.main()
