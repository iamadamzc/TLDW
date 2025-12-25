#!/usr/bin/env python
"""Test transcript extraction for video rNxC16mlO60"""

from transcript_service import TranscriptService
import json

def test_transcript_extraction():
    print("="*60)
    print("Testing Transcript Extraction Fixes")
    print("Video: rNxC16mlO60 (Rick Astley - Never Gonna Give You Up)")
    print("="*60)
    print()
    
    service = TranscriptService()
    
    try:
        result = service.get_transcript('rNxC16mlO60')
        
        if result:
            print(f"✅ SUCCESS: Got {len(result)} transcript segments")
            print()
            print("First segment:")
            print(json.dumps(result[0], indent=2))
            return True
        else:
            print("❌ FAILED: No transcript segments returned")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_transcript_extraction()
    exit(0 if success else 1)
