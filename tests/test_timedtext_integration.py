#!/usr/bin/env python3
"""
Integration test for enhanced timed-text cookie functionality.
Tests the complete pipeline from TranscriptService down to timed-text methods.
"""

import logging
import sys
from unittest.mock import patch, MagicMock

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def test_transcript_service_user_cookies():
    """Test that TranscriptService properly threads user cookies to timed-text methods."""
    print("Testing TranscriptService user cookie integration...")
    
    try:
        from transcript_service import TranscriptService
        
        # Create a transcript service instance
        service = TranscriptService()
        
        # Mock the cache to avoid cache hits and the timed-text function to capture cookies
        with patch.object(service.cache, 'get', return_value=None), \
             patch('transcript_service.get_captions_via_timedtext') as mock_timedtext, \
             patch('transcript_service.get_transcript') as mock_yt_api:
            
            # Make YT API fail so it falls back to timedtext
            mock_yt_api.side_effect = Exception("YT API failed")
            mock_timedtext.return_value = "Test transcript from timedtext"
            
            # Test with user cookies
            user_cookies = {"session_token": "user123", "consent": "accepted"}
            result = service.get_transcript(
                "test_video_id", 
                language_codes=["en"], 
                user_cookies=user_cookies
            )
            
            # Verify that get_captions_via_timedtext was called with user_cookies
            mock_timedtext.assert_called()
            call_args = mock_timedtext.call_args
            
            # Check that user_cookies was passed through
            assert 'user_cookies' in call_args.kwargs
            assert call_args.kwargs['user_cookies'] == user_cookies
            
            print("✓ User cookies properly threaded through TranscriptService")
            return True
            
    except Exception as e:
        print(f"✗ TranscriptService integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cookie_preference_order():
    """Test that user cookies take precedence over environment cookies."""
    print("Testing cookie preference order...")
    
    try:
        from transcript_service import get_captions_via_timedtext
        
        # Mock environment cookies
        with patch('transcript_service._cookie_header_from_env_or_file') as mock_env, \
             patch('transcript_service._fetch_timedtext_json3') as mock_json3, \
             patch('transcript_service._fetch_timedtext_xml') as mock_xml:
            
            mock_env.return_value = "env_cookie=env_value; other=test"
            mock_json3.return_value = "Test transcript"
            mock_xml.return_value = ""
            
            # Test 1: User cookies should override environment cookies
            user_cookies = {"user_cookie": "user_value"}
            result = get_captions_via_timedtext(
                "test_video",
                user_cookies=user_cookies
            )
            
            # Verify user cookies were passed to json3
            json3_call = mock_json3.call_args
            assert json3_call.kwargs['cookies'] == user_cookies
            
            print("✓ User cookies take precedence over environment cookies")
            
            # Test 2: Environment cookies used when no user cookies
            mock_json3.reset_mock()
            result = get_captions_via_timedtext("test_video")
            
            # Verify no user cookies were passed (should use env cookies internally)
            json3_call = mock_json3.call_args
            assert json3_call.kwargs['cookies'] is None  # No user cookies passed
            
            print("✓ Environment cookies used as fallback")
            return True
            
    except Exception as e:
        print(f"✗ Cookie preference test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cookie_format_handling():
    """Test that both string and dict cookie formats are handled correctly."""
    print("Testing cookie format handling...")
    
    try:
        from transcript_service import _fetch_timedtext_json3, _fetch_timedtext_xml
        
        with patch('transcript_service.HTTP') as mock_http:
            mock_response = MagicMock()
            mock_response.status_code = 404  # No transcript found, but we can check headers
            mock_http.get.return_value = mock_response
            
            # Test string format in json3
            _fetch_timedtext_json3("test", cookies="cookie1=value1; cookie2=value2")
            call_args = mock_http.get.call_args
            headers = call_args.kwargs['headers']
            assert headers['Cookie'] == "cookie1=value1; cookie2=value2"
            
            # Test dict format in json3
            mock_http.reset_mock()
            cookie_dict = {"cookie1": "value1", "cookie2": "value2"}
            _fetch_timedtext_json3("test", cookies=cookie_dict)
            call_args = mock_http.get.call_args
            headers = call_args.kwargs['headers']
            # Should contain both cookies (order may vary)
            assert "cookie1=value1" in headers['Cookie']
            assert "cookie2=value2" in headers['Cookie']
            
            # Test string format in xml (should convert to dict)
            mock_http.reset_mock()
            _fetch_timedtext_xml("test", "en", cookies="cookie1=value1; cookie2=value2")
            call_args = mock_http.get.call_args
            cookies = call_args.kwargs['cookies']
            assert isinstance(cookies, dict)
            assert cookies['cookie1'] == 'value1'
            assert cookies['cookie2'] == 'value2'
            
            # Test dict format in xml (should pass through)
            mock_http.reset_mock()
            _fetch_timedtext_xml("test", "en", cookies=cookie_dict)
            call_args = mock_http.get.call_args
            cookies = call_args.kwargs['cookies']
            assert cookies == cookie_dict
            
            print("✓ Both string and dict cookie formats handled correctly")
            return True
            
    except Exception as e:
        print(f"✗ Cookie format handling test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all integration tests."""
    print("=" * 60)
    print("TIMED-TEXT COOKIE INTEGRATION TESTS")
    print("=" * 60)
    
    tests = [
        test_transcript_service_user_cookies,
        test_cookie_preference_order,
        test_cookie_format_handling,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        print(f"\n{test.__name__}:")
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} failed with exception: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("✓ All timed-text cookie integration tests passed!")
        return True
    else:
        print("✗ Some tests failed")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)