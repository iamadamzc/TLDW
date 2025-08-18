#!/usr/bin/env python3
"""
Test to verify ffmpeg path fix in YouTubeDownloadService
"""

import sys
import os
import json
from unittest.mock import patch, MagicMock

# Set up test environment
os.environ["OXYLABS_PROXY_CONFIG"] = json.dumps({
    "provider": "oxylabs",
    "host": "pr.oxylabs.io", 
    "port": 7777,
    "username": "customer-test123",
    "password": "myRawPassword123!",
    "geo_enabled": False,
    "country": "us",
    "version": 1
})

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_ffmpeg_path_fix():
    """Test that ffmpeg_path is correctly passed to download_audio_with_retry"""
    
    print("Testing ffmpeg path fix...")
    
    from youtube_download_service import YouTubeDownloadService
    
    service = YouTubeDownloadService()
    
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_get.return_value = mock_response
        
        with patch('youtube_download_service.download_audio_with_retry') as mock_download:
            mock_download.return_value = "/tmp/test_audio.wav"
            
            with patch('os.path.exists') as mock_exists:
                mock_exists.return_value = True
                
                # Test with default ffmpeg path
                result = service.download_with_ytdlp("test_video_ffmpeg", user_id=1)
                
                # Verify download_audio_with_retry was called with correct parameters
                mock_download.assert_called_once()
                call_args = mock_download.call_args
                
                # Check that ffmpeg_path (not ffmpeg_location) was passed
                if 'ffmpeg_path' in call_args.kwargs:
                    ffmpeg_path = call_args.kwargs['ffmpeg_path']
                    if ffmpeg_path == '/usr/bin/ffmpeg':
                        print("✅ Default ffmpeg_path correctly set to /usr/bin/ffmpeg")
                    else:
                        print(f"❌ Wrong default ffmpeg_path: {ffmpeg_path}")
                        return False
                else:
                    print("❌ ffmpeg_path not found in call arguments")
                    return False
                
                # Check that ua (not user_agent) was passed
                if 'ua' in call_args.kwargs:
                    ua = call_args.kwargs['ua']
                    if 'Mozilla' in ua:
                        print("✅ User agent correctly passed as 'ua' parameter")
                    else:
                        print(f"❌ Wrong user agent: {ua}")
                        return False
                else:
                    print("❌ ua parameter not found in call arguments")
                    return False
                
                # Check that max_retries was NOT passed (it's not supported)
                if 'max_retries' not in call_args.kwargs:
                    print("✅ max_retries correctly omitted (not supported by function)")
                else:
                    print("❌ max_retries should not be passed to download_audio_with_retry")
                    return False
    
    # Test with custom FFMPEG_LOCATION
    print("\nTesting custom FFMPEG_LOCATION...")
    with patch.dict(os.environ, {'FFMPEG_LOCATION': '/custom/path/ffmpeg'}):
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 204
            mock_get.return_value = mock_response
            
            with patch('youtube_download_service.download_audio_with_retry') as mock_download:
                mock_download.return_value = "/tmp/test_audio_custom.wav"
                
                with patch('os.path.exists') as mock_exists:
                    mock_exists.return_value = True
                    
                    result = service.download_with_ytdlp("test_video_custom_ffmpeg", user_id=1)
                    
                    call_args = mock_download.call_args
                    ffmpeg_path = call_args.kwargs.get('ffmpeg_path')
                    
                    if ffmpeg_path == '/custom/path/ffmpeg':
                        print("✅ Custom FFMPEG_LOCATION correctly used")
                        return True
                    else:
                        print(f"❌ Custom FFMPEG_LOCATION not used: {ffmpeg_path}")
                        return False

if __name__ == "__main__":
    print("🔧 Testing FFmpeg Path Fix")
    print("=" * 40)
    
    if test_ffmpeg_path_fix():
        print("\n🎉 FFmpeg path fix tests passed!")
        print("\n📋 Fixes Validated:")
        print("  ✅ ffmpeg_path parameter (not ffmpeg_location)")
        print("  ✅ ua parameter (not user_agent)")
        print("  ✅ max_retries parameter removed (not supported)")
        print("  ✅ Default path is /usr/bin/ffmpeg (binary, not directory)")
        print("  ✅ Custom FFMPEG_LOCATION environment variable respected")
        sys.exit(0)
    else:
        print("\n❌ FFmpeg path fix tests failed")
        sys.exit(1)