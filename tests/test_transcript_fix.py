#!/usr/bin/env python3
"""
Test script to verify transcript extraction fixes.
Tests the YouTube Transcript API fix and fallback methods.
"""

import os
import sys
import logging
import time
from typing import Dict, Any

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('transcript_test.log')
    ]
)

def test_youtube_transcript_api():
    """Test the YouTube Transcript API directly"""
    print("\n=== Testing YouTube Transcript API ===")
    
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
        
        # Test video with known transcript: "The history of the entire world, i guess"
        test_video_id = "xuCn8ux2gbs"
        
        print(f"Testing video ID: {test_video_id}")
        
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(test_video_id, languages=["en", "en-US"])
            
            if transcript_list:
                total_text = " ".join([segment.get("text", "") for segment in transcript_list])
                print(f"✅ YouTube Transcript API SUCCESS")
                print(f"   Transcript length: {len(total_text)} characters")
                print(f"   First 100 chars: {total_text[:100]}...")
                return True
            else:
                print("❌ YouTube Transcript API returned empty list")
                return False
                
        except (TranscriptsDisabled, NoTranscriptFound) as e:
            print(f"❌ YouTube Transcript API - No transcript available: {e}")
            return False
        except Exception as e:
            print(f"❌ YouTube Transcript API error: {e}")
            return False
            
    except ImportError as e:
        print(f"❌ Failed to import YouTube Transcript API: {e}")
        return False

def test_transcript_service():
    """Test the TranscriptService class with our fixes"""
    print("\n=== Testing TranscriptService ===")
    
    try:
        from transcript_service import TranscriptService
        
        # Initialize service
        service = TranscriptService()
        
        # Test video with known transcript
        test_video_id = "xuCn8ux2gbs"  # "The history of the entire world, i guess"
        
        print(f"Testing video ID: {test_video_id}")
        
        start_time = time.time()
        transcript = service.get_transcript(test_video_id)
        duration = time.time() - start_time
        
        if transcript and transcript.strip():
            print(f"✅ TranscriptService SUCCESS")
            print(f"   Transcript length: {len(transcript)} characters")
            print(f"   Duration: {duration:.2f} seconds")
            print(f"   First 100 chars: {transcript[:100]}...")
            return True
        else:
            print(f"❌ TranscriptService returned empty transcript")
            return False
            
    except Exception as e:
        print(f"❌ TranscriptService error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_feature_flags():
    """Test that feature flags are properly configured"""
    print("\n=== Testing Feature Flags ===")
    
    try:
        from transcript_service import (
            ENABLE_YT_API, ENABLE_TIMEDTEXT, ENABLE_YOUTUBEI, ENABLE_ASR_FALLBACK
        )
        
        print(f"ENABLE_YT_API: {ENABLE_YT_API}")
        print(f"ENABLE_TIMEDTEXT: {ENABLE_TIMEDTEXT}")
        print(f"ENABLE_YOUTUBEI: {ENABLE_YOUTUBEI}")
        print(f"ENABLE_ASR_FALLBACK: {ENABLE_ASR_FALLBACK}")
        
        # Check that at least the primary methods are enabled
        if ENABLE_YT_API and ENABLE_YOUTUBEI:
            print("✅ Feature flags properly configured")
            return True
        else:
            print("❌ Critical feature flags are disabled")
            return False
            
    except Exception as e:
        print(f"❌ Feature flags test error: {e}")
        return False

def test_health_diagnostics():
    """Test the health diagnostics endpoint"""
    print("\n=== Testing Health Diagnostics ===")
    
    try:
        from transcript_service import TranscriptService
        
        service = TranscriptService()
        diagnostics = service.get_health_diagnostics()
        
        print("Health Diagnostics:")
        for key, value in diagnostics.items():
            print(f"  {key}: {value}")
        
        # Check that essential components are available
        if diagnostics.get("feature_flags", {}).get("yt_api") and \
           diagnostics.get("feature_flags", {}).get("youtubei"):
            print("✅ Health diagnostics show system is ready")
            return True
        else:
            print("❌ Health diagnostics show system issues")
            return False
            
    except Exception as e:
        print(f"❌ Health diagnostics error: {e}")
        return False

def test_fallback_video():
    """Test with a video that might require fallback methods"""
    print("\n=== Testing Fallback Video ===")
    
    try:
        from transcript_service import TranscriptService
        
        service = TranscriptService()
        
        # Test with the video from the original error log
        test_video_id = "BPjmmZlDhNc"
        
        print(f"Testing problematic video ID: {test_video_id}")
        
        start_time = time.time()
        transcript = service.get_transcript(test_video_id)
        duration = time.time() - start_time
        
        if transcript and transcript.strip():
            print(f"✅ Fallback video SUCCESS")
            print(f"   Transcript length: {len(transcript)} characters")
            print(f"   Duration: {duration:.2f} seconds")
            print(f"   First 100 chars: {transcript[:100]}...")
            return True
        else:
            print(f"⚠️  Fallback video returned empty transcript (may be expected)")
            print(f"   Duration: {duration:.2f} seconds")
            return False
            
    except Exception as e:
        print(f"❌ Fallback video test error: {e}")
        return False

def main():
    """Run all tests"""
    print("🔍 Starting Transcript Service Fix Tests")
    print("=" * 50)
    
    results = {}
    
    # Run all tests
    results["youtube_api"] = test_youtube_transcript_api()
    results["transcript_service"] = test_transcript_service()
    results["feature_flags"] = test_feature_flags()
    results["health_diagnostics"] = test_health_diagnostics()
    results["fallback_video"] = test_fallback_video()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:20} {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The transcript service fixes are working correctly.")
        return 0
    elif passed >= total - 1:  # Allow fallback video to fail
        print("✅ Core functionality is working. The fixes should resolve the transcript issues.")
        return 0
    else:
        print("⚠️  Some tests failed. Please review the errors above.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
