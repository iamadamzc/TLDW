#!/usr/bin/env python3
"""
Test network connectivity and YouTube API access
"""
import requests
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_basic_connectivity():
    """Test basic internet connectivity"""
    print("=== Testing Basic Connectivity ===")
    
    try:
        response = requests.get("https://httpbin.org/get", timeout=10)
        if response.status_code == 200:
            print("✓ Basic internet connectivity working")
            return True
        else:
            print(f"✗ Basic connectivity failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Basic connectivity failed: {e}")
        return False

def test_youtube_connectivity():
    """Test YouTube connectivity"""
    print("\n=== Testing YouTube Connectivity ===")
    
    try:
        # Test YouTube main page
        response = requests.get("https://www.youtube.com", timeout=10)
        if response.status_code == 200:
            print("✓ YouTube main page accessible")
        else:
            print(f"✗ YouTube main page failed: {response.status_code}")
            return False
            
        # Test YouTube API endpoint
        response = requests.get("https://www.youtube.com/api/timedtext?v=dQw4w9WgXcQ&lang=en", timeout=10)
        print(f"YouTube timedtext API response: {response.status_code}")
        if response.status_code == 200:
            print(f"Response length: {len(response.text)}")
            print(f"Response preview: {response.text[:200]}...")
        
        return True
        
    except Exception as e:
        print(f"✗ YouTube connectivity failed: {e}")
        return False

def test_youtube_transcript_api_raw():
    """Test YouTube Transcript API at a lower level"""
    print("\n=== Testing YouTube Transcript API Raw ===")
    
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._api import _TranscriptListFetcher
        
        video_id = "dQw4w9WgXcQ"
        
        # Try to get the raw transcript list
        print(f"Attempting to fetch transcript list for {video_id}...")
        
        # This is the internal method that might give us more info
        fetcher = _TranscriptListFetcher()
        try:
            transcript_list_data = fetcher.fetch(video_id)
            print(f"✓ Raw transcript list fetched: {len(transcript_list_data)} bytes")
            print(f"Preview: {transcript_list_data[:500]}...")
            
            # Try to parse it
            import json
            try:
                parsed = json.loads(transcript_list_data)
                print("✓ JSON parsing successful")
            except json.JSONDecodeError as je:
                print(f"✗ JSON parsing failed: {je}")
                # Maybe it's HTML or XML?
                if transcript_list_data.strip().startswith('<'):
                    print("Response appears to be HTML/XML")
                elif transcript_list_data.strip().startswith('{'):
                    print("Response appears to be JSON but malformed")
                else:
                    print("Response format unknown")
                    
        except Exception as fetch_error:
            print(f"✗ Raw transcript list fetch failed: {fetch_error}")
            
    except Exception as e:
        print(f"✗ YouTube Transcript API raw test failed: {e}")

def test_alternative_video():
    """Test with a different video that definitely has captions"""
    print("\n=== Testing Alternative Videos ===")
    
    # Test videos known to have captions
    test_videos = [
        "jNQXAC9IVRw",  # "Me at the zoo" - first YouTube video
        "9bZkp7q19f0",  # PSY - Gangnam Style
        "kJQP7kiw5Fk",  # Luis Fonsi - Despacito
    ]
    
    from youtube_transcript_api import YouTubeTranscriptApi
    
    for video_id in test_videos:
        print(f"\nTesting video {video_id}...")
        try:
            # Try the simplest possible call
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            print(f"✓ Success! Got {len(transcript)} segments")
            if transcript:
                print(f"First segment: {transcript[0]}")
            return True
        except Exception as e:
            print(f"✗ Failed: {e}")
            continue
    
    print("✗ All test videos failed")
    return False

if __name__ == "__main__":
    print("Network and API Connectivity Test")
    print("=" * 50)
    
    test_basic_connectivity()
    test_youtube_connectivity()
    test_youtube_transcript_api_raw()
    test_alternative_video()
    
    print("\n" + "=" * 50)
    print("Test complete!")
