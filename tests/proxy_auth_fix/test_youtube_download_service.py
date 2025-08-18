#!/usr/bin/env python3
"""
Test script for YouTubeDownloadService integration with new proxy validation
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
os.environ["DEEPGRAM_API_KEY"] = "test_api_key"

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_youtube_download_service():
    """Test YouTubeDownloadService integration with new proxy validation"""
    
    print("Testing YouTubeDownloadService integration...")
    
    # Test 1: YouTubeDownloadService initialization
    print("\n1. Testing YouTubeDownloadService initialization...")
    try:
        from youtube_download_service import YouTubeDownloadService
        service = YouTubeDownloadService()
        
        if service.proxy_manager is not None:
            print("✅ YouTubeDownloadService initialized with ProxyManager")
            print(f"   Proxy host: {service.proxy_manager.secret.host}:{service.proxy_manager.secret.port}")
        else:
            print("❌ YouTubeDownloadService failed to initialize ProxyManager")
            return False
    except Exception as e:
        print(f"❌ YouTubeDownloadService initialization failed: {e}")
        return False
    
    # Test 2: Preflight success path
    print("\n2. Testing preflight success path...")
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_get.return_value = mock_response
        
        with patch('youtube_download_service.download_audio_with_retry') as mock_download:
            mock_download.return_value = "/tmp/test_audio.wav"
            
            with patch('os.path.exists') as mock_exists:
                mock_exists.return_value = True
                
                result = service.download_with_ytdlp("test_video_123", user_id=1)
                
                if (isinstance(result, dict) and 
                    result.get("success") is True and
                    "correlation_id" in result):
                    print("✅ Preflight success path working")
                    print(f"   Result: {result}")
                else:
                    print(f"❌ Preflight success path failed: {result}")
                    return False
    
    # Test 3: Preflight auth failure path
    print("\n3. Testing preflight auth failure path...")
    # Create fresh service to avoid cached preflight results
    fresh_service = YouTubeDownloadService()
    
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 407
        mock_get.return_value = mock_response
        
        result = fresh_service.download_with_ytdlp("test_video_456", user_id=1)
        
        if isinstance(result, tuple) and len(result) == 2:
            response_body, status_code = result
            if (status_code == 502 and 
                response_body.get("code") == "PROXY_AUTH_FAILED" and
                "correlation_id" in response_body):
                print("✅ Preflight auth failure path working")
                print(f"   Response: {response_body}")
            else:
                print(f"❌ Preflight auth failure response incorrect: {result}")
                return False
        else:
            print(f"❌ Preflight auth failure path failed: {result}")
            return False
    
    # Test 4: Cookie validation
    print("\n4. Testing cookie validation...")
    
    # Test with no cookies
    cookies_valid = service._validate_cookiefile(None)
    if not cookies_valid:
        print("✅ No cookies correctly identified as invalid")
    else:
        print("❌ No cookies should be invalid")
        return False
    
    # Test with non-existent file
    cookies_valid = service._validate_cookiefile("/nonexistent/cookies.txt")
    if not cookies_valid:
        print("✅ Non-existent cookie file correctly identified as invalid")
    else:
        print("❌ Non-existent cookie file should be invalid")
        return False
    
    # Test with valid cookies (mocked)
    with patch('os.path.exists') as mock_exists:
        mock_exists.return_value = True
        with patch('os.path.getsize') as mock_size:
            mock_size.return_value = 2048  # >1KB
            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = "SID=test; SAPISID=test; HSID=test"
                
                cookies_valid = service._validate_cookiefile("/tmp/test_cookies.txt")
                if cookies_valid:
                    print("✅ Valid cookies correctly identified")
                else:
                    print("❌ Valid cookies should be identified as valid")
                    return False
    
    # Test 5: Session rotation on auth failure
    print("\n5. Testing session rotation on auth failure...")
    with patch('requests.get') as mock_get:
        # Preflight succeeds
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_get.return_value = mock_response
        
        with patch('youtube_download_service.download_audio_with_retry') as mock_download:
            # First call fails with 407, second call succeeds
            mock_download.side_effect = [
                Exception("407 Proxy Authentication Required"),
                "/tmp/test_audio_retry.wav"
            ]
            
            with patch('os.path.exists') as mock_exists:
                mock_exists.return_value = True
                
                result = service.download_with_ytdlp("test_video_rotation", user_id=1)
                
                if (isinstance(result, dict) and 
                    result.get("success") is True and
                    "correlation_id" in result):
                    print("✅ Session rotation and retry working")
                    print(f"   Result: {result}")
                    # Verify download was called twice (original + retry)
                    if mock_download.call_count == 2:
                        print("   ✅ Download attempted twice (original + retry)")
                    else:
                        print(f"   ❌ Expected 2 download attempts, got {mock_download.call_count}")
                        return False
                else:
                    print(f"❌ Session rotation path failed: {result}")
                    return False
    
    # Test 6: Cookie fast-fail (disabled cookies)
    print("\n6. Testing cookie fast-fail with disabled cookies...")
    os.environ["DISABLE_COOKIES"] = "true"
    
    try:
        cookiefile = service._get_valid_cookiefile(user_id=1)
        if cookiefile is None:
            print("✅ Cookies correctly disabled")
        else:
            print(f"❌ Cookies should be disabled, got: {cookiefile}")
            return False
    finally:
        del os.environ["DISABLE_COOKIES"]
    
    print("\n🎉 All YouTubeDownloadService integration tests passed!")
    return True

if __name__ == "__main__":
    success = test_youtube_download_service()
    sys.exit(0 if success else 1)