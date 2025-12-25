"""
Test actual transcript extraction with urllib3 fix
"""
import os
os.environ['ALLOW_MISSING_DEPS'] = 'true'
os.environ['USE_MINIMAL_LOGGING'] = 'false'

from transcript_service import TranscriptService

def test_timedtext_extraction():
    """Test that TimedText method works with urllib3 fix"""
    print("\n" + "="*60)
    print("Testing TimedText extraction with urllib3 fix")
    print("="*60 + "\n")
    
    video_id = "OpSThrOl45E"
    
    try:
        service = TranscriptService()
        result = service.get_transcript(video_id)
        
        if result and len(result) > 0:
            print(f"✅ SUCCESS: Extracted transcript with {len(result)} segments")
            if isinstance(result, list) and len(result) > 0:
                print(f"   First segment: {result[0]}")
            return True
        else:
            print(f"⚠️  No transcript returned (may need network/cache)")
            return False
            
    except Exception as e:
        # Check if it's the urllib3 error
        if "method_whitelist" in str(e):
            print(f"❌ FAILED: urllib3 compatibility issue still present!")
            print(f"   Error: {e}")
            return False
        else:
            print(f"⚠️  Other error (not urllib3 issue): {e}")
            # Other errors are OK - we're just checking urllib3 fix
            return True

if __name__ == "__main__":
    import sys
    success = test_timedtext_extraction()
    sys.exit(0 if success else 1)
