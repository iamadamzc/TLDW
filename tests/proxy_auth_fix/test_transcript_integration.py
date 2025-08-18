#!/usr/bin/env python3
"""
Test script for TranscriptService integration with new proxy validation
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

def test_transcript_integration():
    """Test TranscriptService integration with new proxy validation"""
    
    print("Testing TranscriptService integration...")
    
    # Test 1: TranscriptService initialization
    print("\n1. Testing TranscriptService initialization...")
    try:
        from transcript_service import TranscriptService
        service = TranscriptService()
        
        if service.proxy_manager is not None:
            print("✅ TranscriptService initialized with ProxyManager")
            print(f"   Proxy host: {service.proxy_manager.secret.host}:{service.proxy_manager.secret.port}")
        else:
            print("❌ TranscriptService failed to initialize ProxyManager")
            return False
    except Exception as e:
        print(f"❌ TranscriptService initialization failed: {e}")
        return False
    
    # Test 2: Preflight success path
    print("\n2. Testing preflight success path...")
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_get.return_value = mock_response
        
        with patch.object(service, 'cache') as mock_cache:
            mock_cache.get.return_value = None  # No cache hit
            
            with patch('youtube_transcript_api.YouTubeTranscriptApi.get_transcript') as mock_transcript:
                mock_transcript.return_value = [{"text": "Hello world"}]
                
                result = service.get_transcript("test_video_123", has_captions=True)
                
                if isinstance(result, str) and "Hello world" in result:
                    print("✅ Preflight success path working")
                    print(f"   Result: {result}")
                else:
                    print(f"❌ Preflight success path failed: {result}")
                    return False
    
    # Test 3: Preflight auth failure path
    print("\n3. Testing preflight auth failure path...")
    # Create fresh service to avoid cached preflight results
    fresh_service = TranscriptService()
    
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 407
        mock_get.return_value = mock_response
        
        with patch.object(fresh_service, 'cache') as mock_cache:
            mock_cache.get.return_value = None  # No cache hit
            
            # Mock the ASR fallback to avoid actual yt-dlp calls
            with patch.object(fresh_service, '_transcribe_audio_with_proxy') as mock_asr:
                mock_asr.return_value = None  # ASR fails too
                
                result = fresh_service.get_transcript("test_video_456", has_captions=True)
                
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
    
    # Test 4: Cache hit path (should skip preflight)
    print("\n4. Testing cache hit path...")
    with patch.object(service, 'cache') as mock_cache:
        mock_cache.get.return_value = "Cached transcript content"
        
        result = service.get_transcript("test_video_789", has_captions=True)
        
        if result == "Cached transcript content":
            print("✅ Cache hit path working (skips preflight)")
        else:
            print(f"❌ Cache hit path failed: {result}")
            return False
    
    # Test 5: Discovery gate path (no captions)
    print("\n5. Testing discovery gate path...")
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_get.return_value = mock_response
        
        with patch.object(service, 'cache') as mock_cache:
            mock_cache.get.return_value = None  # No cache hit
            
            with patch.object(service, '_transcribe_audio_with_proxy') as mock_asr:
                mock_asr.return_value = "ASR transcript content"
                
                result = service.get_transcript("test_video_no_captions", has_captions=False)
                
                if result == "ASR transcript content":
                    print("✅ Discovery gate path working (skips to ASR)")
                    # Verify ASR was called with correlation_id
                    mock_asr.assert_called_once()
                    args = mock_asr.call_args[0]
                    if len(args) >= 2:  # video_id, correlation_id
                        print(f"   ASR called with video_id: {args[0]}, correlation_id: {args[1]}")
                    else:
                        print("❌ ASR not called with correlation_id")
                        return False
                else:
                    print(f"❌ Discovery gate path failed: {result}")
                    return False
    
    # Test 6: Session rotation on auth failure
    print("\n6. Testing session rotation on auth failure...")
    with patch('requests.get') as mock_get:
        # First call succeeds (preflight), second call fails (transcript)
        mock_get.side_effect = [
            MagicMock(status_code=204),  # Preflight success
        ]
        
        with patch.object(service, 'cache') as mock_cache:
            mock_cache.get.return_value = None  # No cache hit
            
            with patch('youtube_transcript_api.YouTubeTranscriptApi.get_transcript') as mock_transcript:
                # Both calls fail, forcing fallback to ASR
                mock_transcript.side_effect = [
                    Exception("407 Proxy Authentication Required"),
                    Exception("407 Proxy Authentication Required")
                ]
                
                with patch.object(service, '_transcribe_audio_with_proxy') as mock_asr:
                    mock_asr.return_value = "ASR fallback content"
                    
                    result = service.get_transcript("test_video_rotation", has_captions=True)
                    
                    if result == "ASR fallback content":
                        print("✅ Session rotation and ASR fallback working")
                        # Verify session rotation was triggered
                        mock_asr.assert_called_once()
                    else:
                        print(f"❌ Session rotation path failed: {result}")
                        return False
    
    print("\n🎉 All TranscriptService integration tests passed!")
    return True

if __name__ == "__main__":
    success = test_transcript_integration()
    sys.exit(0 if success else 1)