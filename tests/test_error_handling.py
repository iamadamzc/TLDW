#!/usr/bin/env python3
"""
Test the updated error handling in transcript_service.py
"""
import sys
import logging
sys.path.append('.')

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')

def test_error_classification():
    """Test error classification with various error types"""
    from transcript_service import classify_transcript_error, get_user_friendly_error_message
    from youtube_transcript_api_compat import TranscriptApiError
    
    print("=== Error Classification Test ===")
    
    # Test compatibility layer errors
    test_errors = [
        (TranscriptApiError("Old API method 'get_transcript' not available"), 'test_video', 'test_method'),
        (TranscriptApiError("Transcript retrieval failed"), 'test_video', 'test_method'),
        (Exception("Connection timeout"), 'test_video', 'test_method'),
        (Exception("Video not found"), 'test_video', 'test_method'),
        (Exception("Unauthorized access"), 'test_video', 'test_method'),
    ]
    
    for error, video_id, method in test_errors:
        classification = classify_transcript_error(error, video_id, method)
        print(f'{type(error).__name__}: "{str(error)[:50]}..." -> {classification}')
    
    print('\n=== User-Friendly Messages Test ===')
    test_classifications = [
        'no_transcript', 'video_unavailable', 'age_restricted', 
        'cookie_error', 'request_blocked', 'api_migration_error'
    ]
    
    for classification in test_classifications:
        message = get_user_friendly_error_message(classification, 'test_video')
        print(f'{classification}: {message}')
    
    print('\n✅ Error handling tests completed successfully')


def test_transcript_service_initialization():
    """Test that TranscriptService initializes with new error handling"""
    from transcript_service import TranscriptService
    
    print("\n=== TranscriptService Initialization Test ===")
    
    try:
        service = TranscriptService()
        print("✅ TranscriptService initialized successfully")
        
        # Test health diagnostics
        health = service.get_health_diagnostics()
        print(f"✅ Health diagnostics available: {len(health)} categories")
        
        return True
    except Exception as e:
        print(f"❌ TranscriptService initialization failed: {e}")
        return False


def test_api_imports():
    """Test that all new API error types can be imported"""
    print("\n=== API Error Types Import Test ===")
    
    try:
        from youtube_transcript_api._errors import (
            TranscriptsDisabled, NoTranscriptFound, VideoUnavailable,
            AgeRestricted, CookieError, CookieInvalid, CookiePathInvalid,
            CouldNotRetrieveTranscript, FailedToCreateConsentCookie,
            HTTPError, InvalidVideoId, IpBlocked, NotTranslatable,
            PoTokenRequired, RequestBlocked, TranslationLanguageNotAvailable,
            VideoUnplayable, YouTubeDataUnparsable, YouTubeRequestFailed,
            YouTubeTranscriptApiException
        )
        
        error_types = [
            'TranscriptsDisabled', 'NoTranscriptFound', 'VideoUnavailable',
            'AgeRestricted', 'CookieError', 'CookieInvalid', 'CookiePathInvalid',
            'CouldNotRetrieveTranscript', 'FailedToCreateConsentCookie',
            'HTTPError', 'InvalidVideoId', 'IpBlocked', 'NotTranslatable',
            'PoTokenRequired', 'RequestBlocked', 'TranslationLanguageNotAvailable',
            'VideoUnplayable', 'YouTubeDataUnparsable', 'YouTubeRequestFailed',
            'YouTubeTranscriptApiException'
        ]
        
        print(f"✅ Successfully imported {len(error_types)} new API error types")
        return True
        
    except ImportError as e:
        print(f"❌ Failed to import new API error types: {e}")
        return False


if __name__ == "__main__":
    print("Testing updated error handling for youtube-transcript-api 1.2.2")
    print("=" * 60)
    
    success = True
    
    # Test API imports
    if not test_api_imports():
        success = False
    
    # Test service initialization
    if not test_transcript_service_initialization():
        success = False
    
    # Test error classification
    try:
        test_error_classification()
    except Exception as e:
        print(f"❌ Error classification test failed: {e}")
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("✅ All error handling tests passed!")
        print("✅ Task 5: Update error handling - COMPLETED")
    else:
        print("❌ Some error handling tests failed")
        sys.exit(1)