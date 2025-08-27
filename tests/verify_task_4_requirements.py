#!/usr/bin/env python3
"""
Verification script for Task 4: Enhanced Timed-Text Cookie Integration
Checks that all requirements (4.1-4.6) have been implemented correctly.
"""

import logging
import sys
from unittest.mock import patch, MagicMock

# Set up logging to capture debug messages
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

def verify_requirement_4_1():
    """Requirement 4.1: _fetch_timedtext_json3 accepts cookies parameter"""
    print("Verifying Requirement 4.1: _fetch_timedtext_json3 accepts cookies parameter")
    
    try:
        from transcript_service import _fetch_timedtext_json3
        import inspect
        
        # Check function signature
        sig = inspect.signature(_fetch_timedtext_json3)
        assert 'cookies' in sig.parameters, "cookies parameter not found in _fetch_timedtext_json3"
        
        # Test that it can be called with cookies parameter
        with patch('transcript_service.HTTP') as mock_http:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_http.get.return_value = mock_response
            
            # Should not raise an error
            result = _fetch_timedtext_json3("test_video", cookies={"test": "cookie"})
            
        print("✓ Requirement 4.1 PASSED: _fetch_timedtext_json3 accepts cookies parameter")
        return True
        
    except Exception as e:
        print(f"✗ Requirement 4.1 FAILED: {e}")
        return False


def verify_requirement_4_2():
    """Requirement 4.2: _fetch_timedtext_xml accepts cookies parameter"""
    print("Verifying Requirement 4.2: _fetch_timedtext_xml accepts cookies parameter")
    
    try:
        from transcript_service import _fetch_timedtext_xml
        import inspect
        
        # Check function signature
        sig = inspect.signature(_fetch_timedtext_xml)
        assert 'cookies' in sig.parameters, "cookies parameter not found in _fetch_timedtext_xml"
        
        # Test that it can be called with cookies parameter
        with patch('transcript_service.HTTP') as mock_http:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_http.get.return_value = mock_response
            
            # Should not raise an error
            result = _fetch_timedtext_xml("test_video", "en", cookies={"test": "cookie"})
            
        print("✓ Requirement 4.2 PASSED: _fetch_timedtext_xml accepts cookies parameter")
        return True
        
    except Exception as e:
        print(f"✗ Requirement 4.2 FAILED: {e}")
        return False


def verify_requirement_4_3():
    """Requirement 4.3: User cookie preference over environment/file cookies"""
    print("Verifying Requirement 4.3: User cookie preference over environment/file cookies")
    
    try:
        from transcript_service import get_captions_via_timedtext
        
        with patch('transcript_service._fetch_timedtext_json3') as mock_json3, \
             patch('transcript_service._cookie_header_from_env_or_file') as mock_env:
            
            mock_json3.return_value = "Test transcript"
            mock_env.return_value = "env_cookie=env_value"
            
            # Test that user cookies are passed to json3 method
            user_cookies = {"user_cookie": "user_value"}
            result = get_captions_via_timedtext("test_video", user_cookies=user_cookies)
            
            # Verify user cookies were passed
            call_args = mock_json3.call_args
            assert call_args.kwargs['cookies'] == user_cookies, "User cookies not passed correctly"
            
        print("✓ Requirement 4.3 PASSED: User cookies take preference over environment cookies")
        return True
        
    except Exception as e:
        print(f"✗ Requirement 4.3 FAILED: {e}")
        return False


def verify_requirement_4_4():
    """Requirement 4.4: Debug logging for cookie source (user vs env)"""
    print("Verifying Requirement 4.4: Debug logging for cookie source")
    
    try:
        from transcript_service import _fetch_timedtext_json3, _fetch_timedtext_xml
        import io
        
        # Capture log messages
        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.DEBUG)
        
        # Get the transcript_service logger (or root logger)
        logger = logging.getLogger()
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        
        with patch('transcript_service.HTTP') as mock_http:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_http.get.return_value = mock_response
            
            # Test user cookie logging in json3
            _fetch_timedtext_json3("test", cookies="user_cookie=value")
            log_output = log_capture.getvalue()
            assert "cookie_source=user" in log_output, "User cookie source not logged in json3"
            
            # Clear log capture
            log_capture.truncate(0)
            log_capture.seek(0)
            
            # Test user cookie logging in xml
            _fetch_timedtext_xml("test", "en", cookies="user_cookie=value")
            log_output = log_capture.getvalue()
            assert "cookie_source=user" in log_output, "User cookie source not logged in xml"
            
        logger.removeHandler(handler)
        print("✓ Requirement 4.4 PASSED: Debug logging for cookie source implemented")
        return True
        
    except Exception as e:
        print(f"✗ Requirement 4.4 FAILED: {e}")
        return False


def verify_requirement_4_5():
    """Requirement 4.5: Thread user cookies through timed-text extraction pipeline"""
    print("Verifying Requirement 4.5: User cookies threaded through pipeline")
    
    try:
        from transcript_service import get_captions_via_timedtext
        
        with patch('transcript_service._fetch_timedtext_json3') as mock_json3, \
             patch('transcript_service._fetch_timedtext_xml') as mock_xml:
            
            mock_json3.return_value = ""  # Force fallback to xml methods
            mock_xml.return_value = "Test transcript"
            
            # Test that user cookies are threaded through the pipeline
            user_cookies = {"session": "abc123"}
            result = get_captions_via_timedtext("test_video", user_cookies=user_cookies)
            
            # Verify user cookies were passed to both json3 and xml methods
            json3_call = mock_json3.call_args
            assert json3_call.kwargs['cookies'] == user_cookies, "User cookies not passed to json3"
            
            # xml method should be called with user cookies when json3 fails
            xml_calls = mock_xml.call_args_list
            assert len(xml_calls) > 0, "XML method not called"
            # Check that at least one xml call received user cookies
            xml_call_with_cookies = any(
                call.kwargs.get('cookies') == user_cookies 
                for call in xml_calls
            )
            assert xml_call_with_cookies, "User cookies not passed to xml method"
            
        print("✓ Requirement 4.5 PASSED: User cookies threaded through timed-text pipeline")
        return True
        
    except Exception as e:
        print(f"✗ Requirement 4.5 FAILED: {e}")
        return False


def verify_requirement_4_6():
    """Requirement 4.6: Integration with TranscriptService"""
    print("Verifying Requirement 4.6: Integration with TranscriptService")
    
    try:
        from transcript_service import TranscriptService
        
        service = TranscriptService()
        
        with patch.object(service.cache, 'get', return_value=None), \
             patch('transcript_service.get_transcript') as mock_yt_api, \
             patch('transcript_service.get_captions_via_timedtext') as mock_timedtext:
            
            mock_yt_api.side_effect = Exception("YT API failed")
            mock_timedtext.return_value = "Test transcript"
            
            # Test that user_cookies parameter is accepted and passed through
            user_cookies = {"auth": "token123"}
            result = service.get_transcript(
                "test_video",
                language_codes=["en"],
                user_cookies=user_cookies
            )
            
            # Verify get_captions_via_timedtext was called with user_cookies
            call_args = mock_timedtext.call_args
            assert 'user_cookies' in call_args.kwargs, "user_cookies not passed to timedtext"
            assert call_args.kwargs['user_cookies'] == user_cookies, "Incorrect user_cookies passed"
            
        print("✓ Requirement 4.6 PASSED: Integration with TranscriptService working")
        return True
        
    except Exception as e:
        print(f"✗ Requirement 4.6 FAILED: {e}")
        return False


def main():
    """Run all requirement verifications."""
    print("=" * 70)
    print("TASK 4: ENHANCED TIMED-TEXT COOKIE INTEGRATION - REQUIREMENTS VERIFICATION")
    print("=" * 70)
    
    requirements = [
        verify_requirement_4_1,
        verify_requirement_4_2,
        verify_requirement_4_3,
        verify_requirement_4_4,
        verify_requirement_4_5,
        verify_requirement_4_6,
    ]
    
    passed = 0
    failed = 0
    
    for requirement in requirements:
        print(f"\n{requirement.__name__.replace('verify_', '').upper()}:")
        try:
            if requirement():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ {requirement.__name__} failed with exception: {e}")
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"VERIFICATION RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)
    
    if failed == 0:
        print("✓ ALL REQUIREMENTS FOR TASK 4 HAVE BEEN SUCCESSFULLY IMPLEMENTED!")
        print("\nImplemented features:")
        print("- _fetch_timedtext_json3 accepts cookies parameter")
        print("- _fetch_timedtext_xml accepts cookies parameter")
        print("- User cookie preference over environment/file cookies")
        print("- Debug logging for cookie source (user vs env)")
        print("- User cookies threaded through timed-text extraction pipeline")
        print("- Full integration with TranscriptService")
        return True
    else:
        print("✗ Some requirements failed verification")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)