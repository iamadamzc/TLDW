#!/usr/bin/env python3
"""
Simple test for YouTube Transcript API functionality
"""
import os
import sys
import logging

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from transcript_service import TranscriptService

def test_hierarchical_fallback():
    """Test the full hierarchical fallback system"""
    logging.basicConfig(level=logging.INFO)
    
    # Test with a TED talk that should have captions
    test_video_id = "ZQUxL4Jm1Lo"  # TED talk with reliable captions
    
    service = TranscriptService()
    
    print(f"Testing hierarchical fallback with video: {test_video_id}")
    
    # Test the full get_transcript method which uses hierarchical fallback
    transcript = service.get_transcript(test_video_id, language="en")
    
    if transcript:
        print(f"✅ Hierarchical fallback successful")
        print(f"Transcript length: {len(transcript)} characters")
        print(f"First 200 characters: {transcript[:200]}...")
        return True
    else:
        print("❌ Hierarchical fallback failed - no transcript returned")
        return False

def test_youtube_api_direct():
    """Test YouTube Transcript API directly without our wrapper"""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        
        test_video_id = "ZQUxL4Jm1Lo"
        print(f"Testing direct YouTube API with video: {test_video_id}")
        
        transcript = YouTubeTranscriptApi.get_transcript(test_video_id, languages=["en", "en-US"])
        
        if transcript:
            text = "\n".join([segment["text"] for segment in transcript[:5]])  # First 5 segments
            print(f"✅ Direct YouTube API successful")
            print(f"First 5 segments: {text}")
            return True
        else:
            print("❌ Direct YouTube API failed")
            return False
            
    except Exception as e:
        print(f"❌ Direct YouTube API error: {e}")
        return False

def test_feature_flags():
    """Test that feature flags are properly configured"""
    from transcript_service import ENABLE_YT_API, ENABLE_TIMEDTEXT, ENABLE_YOUTUBEI, ENABLE_ASR_FALLBACK
    
    print("\n=== Feature Flag Status ===")
    print(f"ENABLE_YT_API: {ENABLE_YT_API}")
    print(f"ENABLE_TIMEDTEXT: {ENABLE_TIMEDTEXT}")
    print(f"ENABLE_YOUTUBEI: {ENABLE_YOUTUBEI}")
    print(f"ENABLE_ASR_FALLBACK: {ENABLE_ASR_FALLBACK}")
    
    # Verify Phase 1 flags are enabled
    if ENABLE_YT_API and ENABLE_TIMEDTEXT:
        print("✅ Phase 1 flags properly configured")
        return True
    else:
        print("❌ Phase 1 flags not properly configured")
        return False

if __name__ == "__main__":
    print("=== YouTube Transcript API Test ===")
    
    direct_success = test_youtube_api_direct()
    fallback_success = test_hierarchical_fallback()
    flags_success = test_feature_flags()
    
    if direct_success and fallback_success and flags_success:
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)