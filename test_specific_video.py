"""
Quick test script to debug transcript extraction for specific video
"""
import os
import sys
import logging

# Set up basic logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Set required env vars for testing
os.environ['ALLOW_MISSING_DEPS'] = 'true'
os.environ['USE_MINIMAL_LOGGING'] = 'false'

from transcript_service import TranscriptService

def test_video(video_id: str):
    """Test transcript extraction for specific video"""
    print(f"\n{'='*60}")
    print(f"Testing transcript extraction for video: {video_id}")
    print(f"{'='*60}\n")
    
    service = TranscriptService()
    
    try:
        transcript = service.get_transcript(video_id)
        
        if transcript:
            if isinstance(transcript, list):
                # Convert list to text
                text = " ".join(segment.get('text', '') for segment in transcript if isinstance(segment, dict))
                print(f"\n✅ SUCCESS: Got transcript list with {len(transcript)} segments")
                print(f"Text length: {len(text)} characters")
                print(f"\nFirst 500 characters:\n{text[:500]}...")
            elif isinstance(transcript, str):
                print(f"\n✅ SUCCESS: Got transcript string ({len(transcript)} characters)")
                print(f"\nFirst 500 characters:\n{transcript[:500]}...")
            else:
                print(f"\n⚠️  UNEXPECTED: Got type {type(transcript)}")
        else:
            print(f"\n❌ FAILED: No transcript returned (empty or None)")
            
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    video_id = "OpSThrOl45E"
    test_video(video_id)
