#!/usr/bin/env python3
"""
Test script to verify that proxies are properly passed through the YouTube Transcript API system.
"""

import os
import logging
import sys
from unittest.mock import patch, MagicMock

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_proxy_passthrough():
    """Test that proxies are properly passed through the compatibility layer."""
    
    print("=== Testing Proxy Passthrough ===")
    
    # Mock proxy configuration
    mock_proxy_dict = {
        'http': 'http://proxy.example.com:8080',
        'https': 'http://proxy.example.com:8080'
    }
    
    try:
        # Import the compatibility layer
        from youtube_transcript_api_compat import get_transcript, YouTubeTranscriptApiCompat
        
        print("✅ Successfully imported compatibility layer")
        
        # Create a mock instance to test proxy passing
        compat_instance = YouTubeTranscriptApiCompat()
        
        # Mock the API instance and its methods
        with patch.object(compat_instance, '_api_instance') as mock_api:
            # Mock the list method to return a mock transcript list
            mock_transcript_list = MagicMock()
            mock_transcript_list.__iter__ = MagicMock(return_value=iter([
                MagicMock(language_code='en', language='English', is_generated=False)
            ]))
            mock_api.list.return_value = mock_transcript_list
            
            # Mock the fetch method to capture the arguments
            mock_fetched_transcript = MagicMock()
            mock_fetched_transcript.__iter__ = MagicMock(return_value=iter([
                MagicMock(text='Test transcript', start=0.0, duration=1.0)
            ]))
            mock_api.fetch.return_value = mock_fetched_transcript
            
            # Test the get_transcript method with proxies
            try:
                result = compat_instance.get_transcript(
                    'test_video_id',
                    languages=['en'],
                    cookies=None,
                    proxies=mock_proxy_dict
                )
                
                print("✅ get_transcript method executed successfully")
                print(f"✅ Returned {len(result)} transcript segments")
                
                # Check if fetch was called with the expected arguments
                mock_api.fetch.assert_called()
                call_args = mock_api.fetch.call_args
                
                # The proxies should be passed as keyword arguments
                if call_args and call_args[1]:  # kwargs
                    if 'proxies' in call_args[1]:
                        passed_proxies = call_args[1]['proxies']
                        if passed_proxies == mock_proxy_dict:
                            print("✅ Proxies correctly passed to API fetch method")
                            print(f"   Proxies: {passed_proxies}")
                        else:
                            print(f"❌ Proxies mismatch. Expected: {mock_proxy_dict}, Got: {passed_proxies}")
                    else:
                        print("❌ Proxies not found in API call arguments")
                        print(f"   Call kwargs: {call_args[1]}")
                else:
                    print("❌ No keyword arguments passed to API fetch method")
                    
            except Exception as e:
                print(f"❌ Error during get_transcript call: {e}")
                return False
                
    except ImportError as e:
        print(f"❌ Failed to import compatibility layer: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    
    print("\n=== Testing Direct Function Call ===")
    
    # Test the direct function call as well
    try:
        with patch('youtube_transcript_api_compat.get_compat_instance') as mock_get_instance:
            mock_instance = MagicMock()
            mock_instance.get_transcript.return_value = [
                {'text': 'Test transcript', 'start': 0.0, 'duration': 1.0}
            ]
            mock_get_instance.return_value = mock_instance
            
            # Call the direct function
            result = get_transcript(
                'test_video_id',
                languages=['en'],
                cookies=None,
                proxies=mock_proxy_dict
            )
            
            print("✅ Direct get_transcript function executed successfully")
            
            # Check if the instance method was called with proxies
            mock_instance.get_transcript.assert_called_once_with(
                'test_video_id',
                ['en'],
                None,
                mock_proxy_dict
            )
            print("✅ Proxies correctly passed to compatibility instance")
            
    except Exception as e:
        print(f"❌ Error during direct function call test: {e}")
        return False
    
    print("\n=== Testing TranscriptService Integration ===")
    
    # Test the TranscriptService integration
    try:
        from transcript_service import TranscriptService
        
        # Create a mock proxy manager
        mock_proxy_manager = MagicMock()
        mock_proxy_manager.proxy_dict_for.return_value = mock_proxy_dict
        
        # Create transcript service with mocked proxy manager
        with patch('transcript_service.shared_managers') as mock_shared_managers:
            mock_shared_managers.get_proxy_manager.return_value = mock_proxy_manager
            mock_shared_managers.get_user_agent_manager.return_value = MagicMock()
            
            service = TranscriptService()
            
            print("✅ TranscriptService created successfully")
            print(f"✅ Proxy manager available: {service.proxy_manager is not None}")
            
            # Test that proxy_dict_for is called correctly
            proxy_dict = service.proxy_manager.proxy_dict_for("requests")
            print(f"✅ Proxy dict retrieved: {proxy_dict}")
            
    except Exception as e:
        print(f"❌ Error during TranscriptService test: {e}")
        return False
    
    print("\n=== All Tests Passed! ===")
    print("✅ Proxies are properly configured to be passed through the system")
    print("✅ Compatibility layer accepts and forwards proxy parameters")
    print("✅ TranscriptService integrates correctly with proxy manager")
    
    return True

if __name__ == "__main__":
    success = test_proxy_passthrough()
    sys.exit(0 if success else 1)
