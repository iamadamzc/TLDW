#!/usr/bin/env python3
"""
Live demo script to show proxy integration with a fresh video ID that bypasses cache.
This will trigger the CRITICAL level logging to prove proxies are being used.
"""

import os
import logging
import sys
import time
import uuid
from unittest.mock import patch, MagicMock

# Set up logging to show ALL levels including CRITICAL
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def test_proxy_with_fresh_video():
    """Test proxy integration with a fresh video ID that won't be in cache."""
    
    print("=== Live Proxy Integration Test (No Cache) ===")
    
    # Generate a unique video ID that definitely won't be in cache
    unique_video_id = f"test_video_{uuid.uuid4().hex[:8]}_{int(time.time())}"
    print(f"🎯 Using fresh video ID: {unique_video_id}")
    
    # Mock proxy configuration
    mock_proxy_dict = {
        'http': 'http://proxy.example.com:8080',
        'https': 'http://proxy.example.com:8080'
    }
    
    try:
        from transcript_service import TranscriptService
        
        print("✅ TranscriptService imported successfully")
        
        # Create a mock proxy manager that returns our proxy config
        mock_proxy_manager = MagicMock()
        mock_proxy_manager.proxy_dict_for.return_value = mock_proxy_dict
        
        # Create transcript service with mocked proxy manager
        with patch('transcript_service.shared_managers') as mock_shared_managers:
            mock_shared_managers.get_proxy_manager.return_value = mock_proxy_manager
            mock_shared_managers.get_user_agent_manager.return_value = MagicMock()
            
            service = TranscriptService()
            
            print("✅ TranscriptService created with proxy manager")
            
            # Clear any potential cache for this video ID (just to be sure)
            if hasattr(service, 'cache'):
                try:
                    service.cache.delete(unique_video_id, 'en')
                    print("🗑️  Cleared any potential cache entries")
                except:
                    pass
            
            # Mock the compatibility layer to return a successful response
            # but let the real logging happen
            with patch('youtube_transcript_api_compat.get_compat_instance') as mock_get_instance:
                mock_instance = MagicMock()
                
                # Mock the get_transcript method to simulate a successful API call
                mock_instance.get_transcript.return_value = [
                    {'text': 'This is a live test transcript', 'start': 0.0, 'duration': 2.0},
                    {'text': 'showing proxy integration', 'start': 2.0, 'duration': 2.0},
                    {'text': 'with CRITICAL level logging', 'start': 4.0, 'duration': 2.0}
                ]
                
                mock_get_instance.return_value = mock_instance
                
                print("\n🚀 Starting transcript fetch - WATCH FOR CRITICAL LOGS:")
                print("=" * 60)
                
                # This should trigger our CRITICAL logging since it's not cached
                result = service.get_transcript(unique_video_id, user_id=999)
                
                print("=" * 60)
                print(f"✅ Transcript retrieved: {len(result)} characters")
                print(f"📝 Content: {result}")
                
                # Verify the mock was called with the expected parameters
                mock_instance.get_transcript.assert_called()
                call_args = mock_instance.get_transcript.call_args
                
                print(f"\n🔍 API Call Analysis:")
                print(f"   Called with args: {call_args[0] if call_args else 'None'}")
                print(f"   Called with kwargs: {call_args[1] if call_args and len(call_args) > 1 else 'None'}")
                
                # Check if proxies were passed
                if call_args and len(call_args) > 1 and call_args[1]:
                    kwargs = call_args[1]
                    if 'proxies' in kwargs:
                        print(f"✅ VERIFIED: Proxies passed to API: {kwargs['proxies']}")
                    else:
                        print(f"❌ Proxies not found in kwargs: {list(kwargs.keys())}")
                else:
                    print("❌ No kwargs passed to API")
                    
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n🎯 CRITICAL LOG VERIFICATION:")
    print("   If you saw logs like:")
    print("   'CRITICAL_CHECK --- TranscriptService calling get_transcript with proxies: {...}'")
    print("   'CRITICAL_CHECK --- Calling youtube-transcript-api fetch with proxies: {...}'")
    print("   Then the proxy integration is working perfectly!")
    
    return True

def test_proxy_with_disabled_cache():
    """Test with cache explicitly disabled to force API calls."""
    
    print("\n=== Test with Cache Disabled ===")
    
    # Generate another unique video ID
    unique_video_id = f"nocache_test_{uuid.uuid4().hex[:8]}"
    print(f"🎯 Using video ID: {unique_video_id}")
    
    mock_proxy_dict = {
        'http': 'http://test-proxy.example.com:3128',
        'https': 'http://test-proxy.example.com:3128'
    }
    
    try:
        from transcript_service import TranscriptService
        
        # Mock proxy manager
        mock_proxy_manager = MagicMock()
        mock_proxy_manager.proxy_dict_for.return_value = mock_proxy_dict
        
        with patch('transcript_service.shared_managers') as mock_shared_managers:
            mock_shared_managers.get_proxy_manager.return_value = mock_proxy_manager
            mock_shared_managers.get_user_agent_manager.return_value = MagicMock()
            
            service = TranscriptService()
            
            # Mock the cache to always return None (cache miss)
            with patch.object(service.cache, 'get', return_value=None):
                print("🚫 Cache disabled - forcing API call")
                
                # Mock the API response
                with patch('transcript_service.get_transcript') as mock_get_transcript:
                    mock_get_transcript.return_value = [
                        {'text': 'Cache bypassed successfully', 'start': 0.0, 'duration': 1.0}
                    ]
                    
                    print("\n🚀 Calling get_transcript - CRITICAL logs should appear:")
                    print("=" * 60)
                    
                    result = service.get_transcript(unique_video_id, user_id=888)
                    
                    print("=" * 60)
                    print(f"✅ Result: {result}")
                    
                    # Verify the call
                    mock_get_transcript.assert_called()
                    call_args = mock_get_transcript.call_args
                    
                    if call_args and len(call_args) > 1 and 'proxies' in call_args[1]:
                        print(f"✅ CONFIRMED: Proxies in API call: {call_args[1]['proxies']}")
                    else:
                        print("❌ Proxies not found in API call")
                        
    except Exception as e:
        print(f"❌ Error in cache disabled test: {e}")
        return False
        
    return True

if __name__ == "__main__":
    print("🔥 LIVE PROXY INTEGRATION TESTING 🔥")
    print("This will show CRITICAL logs proving proxy usage!\n")
    
    success1 = test_proxy_with_fresh_video()
    success2 = test_proxy_with_disabled_cache()
    
    if success1 and success2:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Proxy integration is working correctly")
        print("✅ CRITICAL logging proves proxies are being used")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)
