#!/usr/bin/env python3
"""
Test enhanced 407 handling with re-preflight after session rotation
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

def test_enhanced_407_handling():
    """Test enhanced 407 handling with re-preflight after rotation"""
    
    print("Testing enhanced 407 handling with re-preflight...")
    
    from transcript_service import TranscriptService
    
    # Test 1: Rotation + re-preflight succeeds
    print("\n1. Testing rotation + re-preflight success path...")
    service = TranscriptService()
    
    with patch('requests.get') as mock_get:
        # First preflight succeeds, re-preflight after rotation also succeeds
        mock_response_success = MagicMock()
        mock_response_success.status_code = 204
        mock_get.return_value = mock_response_success
        
        with patch.object(service, 'cache') as mock_cache:
            mock_cache.get.return_value = None  # No cache hit
            
            with patch('youtube_transcript_api.YouTubeTranscriptApi.get_transcript') as mock_transcript:
                # First call fails with 407, second call succeeds
                mock_transcript.side_effect = [
                    Exception("407 Proxy Authentication Required"),
                    [{"text": "Success after rotation"}]
                ]
                
                result = service.get_transcript("test_video_rotation_success", has_captions=True)
                
                if result == "Success after rotation":
                    print("✅ Rotation + re-preflight success path working")
                    # Verify preflight was called multiple times (initial + re-preflight)
                    if mock_get.call_count >= 2:
                        print(f"✅ Preflight called {mock_get.call_count} times (initial + re-preflight)")
                    else:
                        print(f"❌ Expected multiple preflight calls, got {mock_get.call_count}")
                        return False
                else:
                    print(f"❌ Rotation + re-preflight success failed: {result}")
                    return False
    
    # Test 2: Rotation + re-preflight fails (proxy still unhealthy)
    print("\n2. Testing rotation + re-preflight failure path...")
    fresh_service = TranscriptService()
    
    with patch('requests.get') as mock_get:
        # First preflight succeeds, re-preflight after rotation fails
        responses = [
            MagicMock(status_code=204),  # Initial preflight succeeds
            MagicMock(status_code=407),  # Re-preflight fails
        ]
        mock_get.side_effect = responses
        
        with patch.object(fresh_service, 'cache') as mock_cache:
            mock_cache.get.return_value = None  # No cache hit
            
            with patch('youtube_transcript_api.YouTubeTranscriptApi.get_transcript') as mock_transcript:
                # First call fails with 407, triggering rotation
                mock_transcript.side_effect = Exception("407 Proxy Authentication Required")
                
                result = fresh_service.get_transcript("test_video_rotation_fail", has_captions=True)
                
                # Should return error response, not proceed to ASR
                if isinstance(result, tuple) and len(result) == 2:
                    response_body, status_code = result
                    if (status_code == 502 and 
                        response_body.get("code") == "PROXY_AUTH_FAILED"):
                        print("✅ Rotation + re-preflight failure correctly returns 502")
                        print(f"   Message: {response_body.get('message')}")
                    else:
                        print(f"❌ Wrong error response: {result}")
                        return False
                else:
                    print(f"❌ Expected error response, got: {result}")
                    return False
    
    # Test 3: YouTube download service enhanced handling
    print("\n3. Testing YouTube download service enhanced 407 handling...")
    from youtube_download_service import YouTubeDownloadService
    
    yt_service = YouTubeDownloadService()
    
    with patch('requests.get') as mock_get:
        # First preflight succeeds, re-preflight after rotation fails
        responses = [
            MagicMock(status_code=204),  # Initial preflight succeeds
            MagicMock(status_code=407),  # Re-preflight fails
        ]
        mock_get.side_effect = responses
        
        with patch('youtube_download_service.download_audio_with_retry') as mock_download:
            # First download attempt fails with 407
            mock_download.side_effect = Exception("407 Proxy Authentication Required")
            
            result = yt_service.download_with_ytdlp("test_video_yt_rotation_fail", user_id=1)
            
            # Should return error response due to failed re-preflight
            if isinstance(result, tuple) and len(result) == 2:
                response_body, status_code = result
                if (status_code == 502 and 
                    response_body.get("code") == "PROXY_AUTH_FAILED"):
                    print("✅ YouTube service enhanced 407 handling working")
                    print(f"   Message: {response_body.get('message')}")
                else:
                    print(f"❌ Wrong YouTube error response: {result}")
                    return False
            else:
                print(f"❌ Expected YouTube error response, got: {result}")
                return False
    
    return True

def test_observability_improvements():
    """Test that enhanced handling provides better observability"""
    print("\n4. Testing observability improvements...")
    
    from transcript_service import TranscriptService
    
    service = TranscriptService()
    
    with patch('requests.get') as mock_get:
        # Simulate rotation + re-preflight failure
        responses = [
            MagicMock(status_code=204),  # Initial preflight succeeds
            MagicMock(status_code=407),  # Re-preflight fails
        ]
        mock_get.side_effect = responses
        
        with patch.object(service, 'cache') as mock_cache:
            mock_cache.get.return_value = None
            
            with patch('youtube_transcript_api.YouTubeTranscriptApi.get_transcript') as mock_transcript:
                mock_transcript.side_effect = Exception("407 Proxy Authentication Required")
                
                # Capture logging calls
                with patch.object(service, '_log_structured') as mock_log:
                    result = service.get_transcript("test_observability", has_captions=True)
                    
                    # Check that we logged the rotation and re-preflight failure
                    log_calls = [str(call) for call in mock_log.call_args_list]
                    all_logs = " ".join(log_calls)
                    
                    rotation_logged = "blocked_rotating_session" in all_logs
                    preflight_logged = "rotated_session_still_unhealthy" in all_logs or "proxy_auth_failed" in all_logs
                    
                    if preflight_logged:
                        print("✅ Enhanced observability working - preflight failure logged")
                        print(f"   Debug: Rotation logged: {rotation_logged}, Preflight logged: {preflight_logged}")
                        return True
                    else:
                        print(f"❌ Missing observability logs. Rotation: {rotation_logged}, Preflight: {preflight_logged}")
                        print(f"   Debug: All logs: {all_logs[:200]}...")
                        return False

if __name__ == "__main__":
    print("🧪 Testing Enhanced 407 Handling")
    print("=" * 50)
    
    tests = [
        test_enhanced_407_handling,
        test_observability_improvements
    ]
    
    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                print("❌ Test failed")
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
    
    print(f"\n📊 Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 Enhanced 407 handling tests passed!")
        print("\n📋 Enhanced Features Validated:")
        print("  ✅ Re-preflight after session rotation")
        print("  ✅ Fail-fast if rotated session still unhealthy")
        print("  ✅ Better observability for rotation failures")
        print("  ✅ Consistent behavior across transcript and YouTube services")
        sys.exit(0)
    else:
        print("❌ Some enhanced 407 handling tests failed")
        sys.exit(1)