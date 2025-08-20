#!/usr/bin/env python3
"""
Test for enhanced VideoSummarizer with bullet-proof parameter validation
"""
import os
import sys
import logging

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_summarizer_initialization():
    """Test VideoSummarizer initialization and configuration"""
    print("=== VideoSummarizer Initialization Test ===")
    
    # Test without OpenAI API key
    original_key = os.environ.get("OPENAI_API_KEY")
    if "OPENAI_API_KEY" in os.environ:
        del os.environ["OPENAI_API_KEY"]
    
    try:
        from summarizer import VideoSummarizer
        summarizer = VideoSummarizer()
        print("❌ Should have failed without API key")
        return False
    except ValueError as e:
        if "OPENAI_API_KEY" in str(e):
            print("✅ Properly validates OpenAI API key requirement")
        else:
            print(f"❌ Wrong error message: {e}")
            return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    finally:
        # Restore original key
        if original_key:
            os.environ["OPENAI_API_KEY"] = original_key
    
    return True

def test_keyword_only_parameters():
    """Test that summarize_video uses keyword-only parameters"""
    print("\n=== Keyword-Only Parameters Test ===")
    
    # Set a dummy API key for testing
    os.environ["OPENAI_API_KEY"] = "test-key-for-validation"
    
    try:
        from summarizer import VideoSummarizer
        import inspect
        
        # Test method signature
        sig = inspect.signature(VideoSummarizer.summarize_video)
        params = sig.parameters
        
        # Check that transcript_text and video_id are keyword-only
        transcript_param = params.get('transcript_text')
        video_id_param = params.get('video_id')
        
        if not transcript_param or transcript_param.kind != inspect.Parameter.KEYWORD_ONLY:
            print("❌ transcript_text is not keyword-only")
            return False
        
        if not video_id_param or video_id_param.kind != inspect.Parameter.KEYWORD_ONLY:
            print("❌ video_id is not keyword-only")
            return False
        
        print("✅ Parameters are properly keyword-only")
        
        # Test type annotations
        if transcript_param.annotation != str:
            print("❌ transcript_text missing str annotation")
            return False
        
        if video_id_param.annotation != str:
            print("❌ video_id missing str annotation")
            return False
        
        print("✅ Parameters have proper type annotations")
        
        # Test return type annotation
        if sig.return_annotation != str:
            print("❌ Return type not annotated as str")
            return False
        
        print("✅ Return type properly annotated")
        
        return True
        
    except Exception as e:
        print(f"❌ Keyword-only parameters test failed: {e}")
        return False

def test_input_validation():
    """Test strict input validation"""
    print("\n=== Input Validation Test ===")
    
    os.environ["OPENAI_API_KEY"] = "test-key-for-validation"
    
    try:
        from summarizer import VideoSummarizer
        
        # Create summarizer instance (will fail on actual API call, but that's OK for validation testing)
        summarizer = VideoSummarizer()
        
        # Test empty transcript
        result = summarizer.summarize_video(transcript_text="", video_id="test123")
        if result == "No transcript available for this video.":
            print("✅ Empty transcript handled correctly")
        else:
            print(f"❌ Empty transcript not handled correctly: {result}")
            return False
        
        # Test whitespace-only transcript
        result = summarizer.summarize_video(transcript_text="   \n\t  ", video_id="test123")
        if result == "No transcript available for this video.":
            print("✅ Whitespace-only transcript handled correctly")
        else:
            print(f"❌ Whitespace-only transcript not handled correctly: {result}")
            return False
        
        # Test very short transcript
        result = summarizer.summarize_video(transcript_text="Hi", video_id="test123")
        if result == "No transcript available for this video.":
            print("✅ Very short transcript handled correctly")
        else:
            print(f"❌ Very short transcript not handled correctly: {result}")
            return False
        
        # Test non-string transcript_text
        result = summarizer.summarize_video(transcript_text=None, video_id="test123")
        if result == "No transcript available for this video.":
            print("✅ None transcript_text handled correctly")
        else:
            print(f"❌ None transcript_text not handled correctly: {result}")
            return False
        
        # Test non-string video_id (should be converted)
        result = summarizer.summarize_video(transcript_text="", video_id=123)
        if result == "No transcript available for this video.":
            print("✅ Non-string video_id handled correctly")
        else:
            print(f"❌ Non-string video_id not handled correctly: {result}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Input validation test failed: {e}")
        return False

def test_timestamp_conversion():
    """Test timestamp conversion robustness"""
    print("\n=== Timestamp Conversion Test ===")
    
    os.environ["OPENAI_API_KEY"] = "test-key-for-validation"
    
    try:
        from summarizer import VideoSummarizer
        
        summarizer = VideoSummarizer()
        
        # Test valid timestamps
        test_cases = [
            ("1:30", 90),
            ("10:45", 645),
            ("1:05:22", 3922),
            ("0:30", 30),
        ]
        
        for timestamp, expected_seconds in test_cases:
            result = summarizer._timestamp_to_seconds(timestamp)
            if result == expected_seconds:
                print(f"✅ Timestamp '{timestamp}' -> {result}s")
            else:
                print(f"❌ Timestamp '{timestamp}' -> {result}s (expected {expected_seconds}s)")
                return False
        
        # Test invalid timestamps
        invalid_cases = [
            None,
            "",
            "invalid",
            "1:2:3:4",
            "abc:def"
        ]
        
        for invalid_timestamp in invalid_cases:
            result = summarizer._timestamp_to_seconds(invalid_timestamp)
            if result == 0:
                print(f"✅ Invalid timestamp '{invalid_timestamp}' -> 0s")
            else:
                print(f"❌ Invalid timestamp '{invalid_timestamp}' -> {result}s (expected 0s)")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Timestamp conversion test failed: {e}")
        return False

def test_error_handling():
    """Test that error handling never crashes the pipeline"""
    print("\n=== Error Handling Test ===")
    
    os.environ["OPENAI_API_KEY"] = "test-key-for-validation"
    
    try:
        from summarizer import VideoSummarizer
        
        summarizer = VideoSummarizer()
        
        # Test timestamp link addition with invalid inputs
        test_cases = [
            (None, "test123"),
            ("valid text", None),
            (123, "test123"),
            ("valid text", 123),
        ]
        
        for summary_text, video_id in test_cases:
            try:
                result = summarizer._add_timestamp_links(summary_text, video_id)
                print(f"✅ Timestamp links handled invalid input gracefully")
            except Exception as e:
                print(f"❌ Timestamp links crashed on invalid input: {e}")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        return False

if __name__ == "__main__":
    print("=== Enhanced VideoSummarizer Test ===")
    
    init_success = test_summarizer_initialization()
    keyword_success = test_keyword_only_parameters()
    validation_success = test_input_validation()
    timestamp_success = test_timestamp_conversion()
    error_success = test_error_handling()
    
    all_tests = [init_success, keyword_success, validation_success, timestamp_success, error_success]
    
    if all(all_tests):
        print("\n✅ All VideoSummarizer enhancement tests passed!")
        print("Task 7: Enhance VideoSummarizer with bullet-proof parameter validation - COMPLETE")
        sys.exit(0)
    else:
        print(f"\n❌ Some VideoSummarizer tests failed! Results: {all_tests}")
        sys.exit(1)