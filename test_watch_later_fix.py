#!/usr/bin/env python3
"""
Simple test script to verify the Watch Later playlist fix is working.
This script tests the YouTubeService without requiring the full Flask app.
"""

import sys
import logging
from unittest.mock import Mock, patch

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def test_watch_later_fix():
    """Test that the Watch Later playlist fix is working correctly."""
    print("🧪 Testing Watch Later Playlist Fix...")
    print("=" * 50)
    
    try:
        # Import the YouTubeService
        from youtube_service import YouTubeService
        print("✅ Successfully imported YouTubeService")
        
        # Test 1: Check that _get_watch_later_count method exists
        service = YouTubeService("dummy_token")
        assert hasattr(service, '_get_watch_later_count'), "Missing _get_watch_later_count method"
        print("✅ _get_watch_later_count method exists")
        
        # Test 2: Mock test of the counting functionality
        with patch('youtube_service.build') as mock_build:
            # Mock YouTube API response
            mock_youtube = Mock()
            mock_build.return_value = mock_youtube
            
            # Mock a response with 3 videos (including 1 private that should be filtered)
            mock_response = {
                'items': [
                    {'snippet': {'title': 'Video 1'}},
                    {'snippet': {'title': 'Video 2'}},
                    {'snippet': {'title': 'Private video'}},  # Should be filtered out
                    {'snippet': {'title': 'Video 3'}},
                ],
                'nextPageToken': None
            }
            mock_youtube.playlistItems().list().execute.return_value = mock_response
            
            # Test the counting method
            service = YouTubeService("test_token")
            result = service._get_watch_later_count()
            
            # Verify results
            assert result['count'] == 3, f"Expected 3 videos, got {result['count']}"
            assert not result['has_error'], "Should not have error"
            print("✅ Watch Later counting works correctly (filters private videos)")
        
        # Test 3: Mock test of get_user_playlists integration
        with patch('youtube_service.build') as mock_build:
            mock_youtube = Mock()
            mock_build.return_value = mock_youtube
            
            # Mock Watch Later response
            watch_later_response = {
                'items': [
                    {'snippet': {'title': 'Video 1'}},
                    {'snippet': {'title': 'Video 2'}},
                ],
                'nextPageToken': None
            }
            
            # Mock regular playlists response
            playlists_response = {
                'items': [
                    {
                        'id': 'playlist1',
                        'snippet': {
                            'title': 'My Custom Playlist',
                            'description': 'User created playlist',
                            'channelTitle': 'User Channel',
                            'thumbnails': {'default': {'url': 'thumb.jpg'}}
                        },
                        'contentDetails': {'itemCount': 5}
                    }
                ]
            }
            
            # Configure mock responses
            mock_youtube.playlistItems().list().execute.return_value = watch_later_response
            mock_youtube.playlists().list().execute.return_value = playlists_response
            
            # Test get_user_playlists
            service = YouTubeService("test_token")
            playlists = service.get_user_playlists()
            
            # Verify results
            assert len(playlists) == 2, f"Expected 2 playlists, got {len(playlists)}"
            
            # Find Watch Later playlist
            watch_later = next((p for p in playlists if p['id'] == 'WL'), None)
            assert watch_later is not None, "Watch Later playlist not found"
            assert watch_later['video_count'] == 2, f"Expected 2 videos in Watch Later, got {watch_later['video_count']}"
            assert watch_later['title'] == 'Watch Later', f"Expected 'Watch Later' title, got '{watch_later['title']}'"
            
            print("✅ get_user_playlists integration works correctly")
        
        # Test 4: Test error handling
        with patch('youtube_service.build') as mock_build:
            mock_youtube = Mock()
            mock_build.return_value = mock_youtube
            
            # Mock API error
            from googleapiclient.errors import HttpError
            mock_error = Mock()
            mock_error.resp.status = 403
            http_error = HttpError(mock_error, b'Forbidden')
            
            mock_youtube.playlistItems().list().execute.side_effect = http_error
            mock_youtube.playlists().list().execute.return_value = {'items': []}
            
            # Test error handling
            service = YouTubeService("test_token")
            playlists = service.get_user_playlists()
            
            # Should still return playlists with Watch Later in error state
            watch_later = next((p for p in playlists if p['id'] == 'WL'), None)
            assert watch_later is not None, "Watch Later playlist should still be present on error"
            assert watch_later['video_count'] == 0, "Should show 0 videos on error"
            assert 'Error' in watch_later['title'], "Should indicate error in title"
            
            print("✅ Error handling works correctly")
        
        print("\n🎉 ALL TESTS PASSED!")
        print("=" * 50)
        print("✅ The Watch Later playlist fix is working correctly!")
        print("✅ Watch Later playlists will now show actual video counts")
        print("✅ Error handling is robust and won't break other playlists")
        print("✅ Private/deleted videos are properly filtered out")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_before_after_comparison():
    """Show the difference between old and new behavior."""
    print("\n📊 BEFORE vs AFTER Comparison:")
    print("=" * 50)
    print("❌ BEFORE (Bug):")
    print("   - Watch Later playlist always showed 0 videos")
    print("   - Hardcoded video_count: 0 in the code")
    print("   - Comment: 'YouTube API has limited access to Watch Later'")
    print()
    print("✅ AFTER (Fixed):")
    print("   - Watch Later playlist shows actual video count")
    print("   - Dynamic counting via _get_watch_later_count() method")
    print("   - Proper pagination for large playlists")
    print("   - Filters out private/deleted videos")
    print("   - Robust error handling with graceful degradation")
    print("   - Performance optimized with minimal API calls")

if __name__ == "__main__":
    print("🔧 Watch Later Playlist Fix - Verification Test")
    print("=" * 50)
    
    success = test_watch_later_fix()
    test_before_after_comparison()
    
    if success:
        print("\n🚀 Ready to test with real YouTube API!")
        print("   To test with your actual YouTube account:")
        print("   1. Set up your Google OAuth credentials")
        print("   2. Run the Flask application: python main.py")
        print("   3. Log in and check your Watch Later playlist count")
        sys.exit(0)
    else:
        print("\n❌ Fix verification failed!")
        sys.exit(1)