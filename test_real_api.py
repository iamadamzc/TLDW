#!/usr/bin/env python3
"""
Real API test script to demonstrate the Watch Later playlist fix.
This script shows how the fix would work with actual YouTube API calls.

NOTE: This requires actual YouTube API credentials to run.
"""

import os
import logging
from youtube_service import YouTubeService

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def demonstrate_fix():
    """Demonstrate the Watch Later playlist fix."""
    print("🔧 Watch Later Playlist Fix - Real API Demo")
    print("=" * 60)
    
    # Check for API credentials
    if not os.environ.get('YOUTUBE_ACCESS_TOKEN'):
        print("⚠️  No YouTube access token found in environment variables.")
        print("   To test with real API:")
        print("   1. Set up Google OAuth and get an access token")
        print("   2. Set YOUTUBE_ACCESS_TOKEN environment variable")
        print("   3. Run this script again")
        print()
        print("📝 What the fix does:")
        print("   ✅ Before: Watch Later always showed 0 videos (hardcoded)")
        print("   ✅ After:  Watch Later shows actual video count from API")
        print("   ✅ Handles pagination for large playlists")
        print("   ✅ Filters out private/deleted videos")
        print("   ✅ Robust error handling")
        return
    
    try:
        # Create YouTube service with real token
        access_token = os.environ.get('YOUTUBE_ACCESS_TOKEN')
        service = YouTubeService(access_token)
        
        print("🔍 Testing Watch Later playlist counting...")
        
        # Test the counting method directly
        result = service._get_watch_later_count()
        
        if result['has_error']:
            print(f"❌ Error counting Watch Later videos: {result['error_message']}")
        else:
            print(f"✅ Found {result['count']} videos in Watch Later playlist")
        
        print("\n🔍 Testing full playlist integration...")
        
        # Test the full playlist method
        playlists = service.get_user_playlists()
        
        # Find Watch Later playlist
        watch_later = next((p for p in playlists if p['id'] == 'WL'), None)
        
        if watch_later:
            print(f"✅ Watch Later playlist found:")
            print(f"   Title: {watch_later['title']}")
            print(f"   Video Count: {watch_later['video_count']}")
            print(f"   Is Special: {watch_later['is_special']}")
            
            if 'Error' in watch_later['title']:
                print(f"   Error Details: {watch_later['description']}")
            else:
                print("   ✅ Successfully showing actual video count!")
        else:
            print("❌ Watch Later playlist not found in results")
        
        print(f"\n📊 Total playlists found: {len(playlists)}")
        
        # Show first few playlists
        print("\n📋 Playlist Summary:")
        for i, playlist in enumerate(playlists[:5]):
            special_indicator = " (Special)" if playlist.get('is_special') else ""
            print(f"   {i+1}. {playlist['title']}{special_indicator} - {playlist['video_count']} videos")
        
        if len(playlists) > 5:
            print(f"   ... and {len(playlists) - 5} more playlists")
            
    except Exception as e:
        print(f"❌ Error testing with real API: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    demonstrate_fix()