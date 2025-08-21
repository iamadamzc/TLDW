#!/usr/bin/env python3
"""
Quick test to verify the YouTube Transcript API fix works.
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_api_fix():
    """Test the YouTube Transcript API fix with a known working video"""
    print("Testing YouTube Transcript API fix...")
    
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
        
        # Test with a popular TED talk that definitely has transcripts
        test_video_id = "ZQUxL4Jm1Lo"  # "Your body language may shape who you are" - Amy Cuddy TED talk
        
        print(f"Testing video: https://www.youtube.com/watch?v={test_video_id}")
        
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(test_video_id, languages=["en"])
            
            if transcript_list:
                # Join all text segments
                full_text = " ".join([segment.get("text", "") for segment in transcript_list])
                print(f"✅ SUCCESS! Retrieved transcript with {len(full_text)} characters")
                print(f"First 200 characters: {full_text[:200]}...")
                return True
            else:
                print("❌ API returned empty transcript list")
                return False
                
        except (TranscriptsDisabled, NoTranscriptFound) as e:
            print(f"❌ No transcript available: {e}")
            # Try another video
            test_video_id = "jNQXAC9IVRw"  # "Me at the zoo" - first YouTube video
            print(f"Trying backup video: https://www.youtube.com/watch?v={test_video_id}")
            
            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(test_video_id, languages=["en"])
                if transcript_list:
                    full_text = " ".join([segment.get("text", "") for segment in transcript_list])
                    print(f"✅ SUCCESS with backup video! Retrieved transcript with {len(full_text)} characters")
                    return True
                else:
                    print("❌ Backup video also returned empty transcript")
                    return False
            except Exception as e2:
                print(f"❌ Backup video also failed: {e2}")
                return False
                
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_transcript_service():
    """Test our TranscriptService with the fixes"""
    print("\nTesting TranscriptService...")
    
    try:
        from transcript_service import TranscriptService, ENABLE_YT_API, ENABLE_YOUTUBEI
        
        print(f"Feature flags - YT_API: {ENABLE_YT_API}, YOUTUBEI: {ENABLE_YOUTUBEI}")
        
        service = TranscriptService()
        
        # Test with TED talk
        test_video_id = "ZQUxL4Jm1Lo"
        
        transcript = service.get_transcript(test_video_id)
        
        if transcript and transcript.strip():
            print(f"✅ TranscriptService SUCCESS! Retrieved {len(transcript)} characters")
            print(f"First 200 characters: {transcript[:200]}...")
            return True
        else:
            print("❌ TranscriptService returned empty transcript")
            return False
            
    except Exception as e:
        print(f"❌ TranscriptService error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔍 Quick Transcript API Fix Test")
    print("=" * 40)
    
    api_result = test_api_fix()
    service_result = test_transcript_service()
    
    print("\n" + "=" * 40)
    print("RESULTS:")
    print(f"YouTube API Fix:     {'✅ PASS' if api_result else '❌ FAIL'}")
    print(f"TranscriptService:   {'✅ PASS' if service_result else '❌ FAIL'}")
    
    if api_result or service_result:
        print("\n🎉 The fixes are working! At least one method is successfully retrieving transcripts.")
    else:
        print("\n⚠️  Both tests failed. There may be network issues or the videos don't have transcripts.")
