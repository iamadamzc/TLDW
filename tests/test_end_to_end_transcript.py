#!/usr/bin/env python3
"""
End-to-end test of the updated transcript service with new API
"""
import logging
import os

# Set up logging to see what's happening
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_transcript_service_end_to_end():
    """Test the complete transcript service workflow"""
    try:
        from transcript_service import TranscriptService
        
        print("=== End-to-End Transcript Service Test ===")
        
        # Create service
        service = TranscriptService()
        print("✅ TranscriptService created successfully")
        
        # Test with a known video that has transcripts
        test_video_id = "dQw4w9WgXcQ"  # Rick Roll - definitely has captions
        
        print(f"\n--- Testing get_captions_via_api with {test_video_id} ---")
        
        try:
            # Call the main method
            result = service.get_captions_via_api(test_video_id, languages=("en", "en-US"))
            
            if result and result.strip():
                print(f"✅ SUCCESS: Got transcript with {len(result)} characters")
                print(f"First 100 characters: {result[:100]}...")
                
                # Check if it contains expected content
                if "strangers" in result.lower() or "love" in result.lower():
                    print("✅ Content validation passed (contains expected lyrics)")
                else:
                    print("⚠️  Content validation unclear (may be different transcript)")
                
                return True
            else:
                print("❌ FAILED: Got empty result")
                return False
                
        except Exception as e:
            print(f"❌ FAILED: Exception during transcript fetch: {e}")
            import traceback
            traceback.print_exc()
            return False
        
    except Exception as e:
        print(f"❌ FAILED: Service creation failed: {e}")
        return False

def test_compatibility_layer_direct():
    """Test the compatibility layer directly"""
    try:
        from youtube_transcript_api_compat import get_transcript, list_transcripts
        
        print("\n=== Direct Compatibility Layer Test ===")
        
        test_video_id = "dQw4w9WgXcQ"
        
        # Test list_transcripts
        print("Testing list_transcripts...")
        transcript_list = list_transcripts(test_video_id)
        print(f"✅ Got {len(transcript_list)} available transcripts")
        
        if transcript_list:
            print(f"First transcript: {transcript_list[0]}")
        
        # Test get_transcript
        print("Testing get_transcript...")
        transcript = get_transcript(test_video_id, languages=['en'])
        print(f"✅ Got transcript with {len(transcript)} segments")
        
        if transcript:
            print(f"First segment: {transcript[0]}")
            
            # Verify structure
            first_seg = transcript[0]
            if 'text' in first_seg and 'start' in first_seg and 'duration' in first_seg:
                print("✅ Transcript structure is correct")
            else:
                print(f"❌ Unexpected transcript structure: {first_seg}")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Direct compatibility test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_error_scenarios():
    """Test error handling scenarios"""
    try:
        from youtube_transcript_api_compat import get_transcript, TranscriptApiError
        
        print("\n=== Error Scenario Tests ===")
        
        # Test with invalid video ID
        try:
            result = get_transcript("invalid_video_id_12345", languages=['en'])
            print("❌ Should have failed with invalid video ID")
            return False
        except TranscriptApiError as e:
            print(f"✅ Correctly handled invalid video ID: {e}")
        except Exception as e:
            print(f"✅ Got expected error for invalid video: {type(e).__name__}: {e}")
        
        # Test with video that might not have transcripts
        try:
            result = get_transcript("xxxxxxxxxx", languages=['en'])
            print("❌ Should have failed with non-existent video")
            return False
        except (TranscriptApiError, Exception) as e:
            print(f"✅ Correctly handled non-existent video: {type(e).__name__}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error scenario test failed: {e}")
        return False

def main():
    """Run all end-to-end tests"""
    print("🧪 End-to-End Testing of Updated Transcript Service")
    print("=" * 60)
    
    tests = [
        ("Compatibility Layer Direct", test_compatibility_layer_direct),
        ("Transcript Service End-to-End", test_transcript_service_end_to_end),
        ("Error Scenarios", test_error_scenarios),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} PASSED\n")
            else:
                print(f"❌ {test_name} FAILED\n")
        except Exception as e:
            print(f"❌ {test_name} CRASHED: {e}\n")
    
    print("=" * 60)
    print(f"📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All end-to-end tests passed!")
        print("✅ The transcript service is working correctly with the new API")
        return True
    else:
        print("⚠️  Some tests failed")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)