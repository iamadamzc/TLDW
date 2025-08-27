#!/usr/bin/env python3
"""
Test script for enhanced timed-text cookie integration.
Verifies that user cookies are properly threaded through the timed-text pipeline.
"""

import logging
import sys
import os
from unittest.mock import patch, MagicMock

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

def test_fetch_timedtext_json3_with_user_cookies():
    """Test _fetch_timedtext_json3 with user cookies parameter."""
    print("Testing _fetch_timedtext_json3 with user cookies...")
    
    try:
        from transcript_service import _fetch_timedtext_json3
        
        # Test with string cookies
        with patch('transcript_service.HTTP') as mock_http:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = '{"events": [{"segs": [{"utf8": "Test transcript"}]}]}'
            mock_response.json.return_value = {"events": [{"segs": [{"utf8": "Test transcript"}]}]}
            mock_http.get.return_value = mock_response
            
            result = _fetch_timedtext_json3("test_video", cookies="session_token=abc123; user_pref=en")
            
            # Verify the request was made with user cookies
            mock_http.get.assert_called()
            call_args = mock_http.get.call_args
            headers = call_args[1]['headers']
            assert 'Cookie' in headers
            assert headers['Cookie'] == "session_token=abc123; user_pref=en"
            
            print("✓ String cookies properly set in headers")
        
        # Test with dict cookies
        with patch('transcript_service.HTTP') as mock_http:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = '{"events": [{"segs": [{"utf8": "Test transcript"}]}]}'
            mock_response.json.return_value = {"events": [{"segs": [{"utf8": "Test transcript"}]}]}
            mock_http.get.return_value = mock_response
            
            cookie_dict = {"session_token": "abc123", "user_pref": "en"}
            result = _fetch_timedtext_json3("test_video", cookies=cookie_dict)
            
            # Verify the request was made with converted cookies
            mock_http.get.assert_called()
            call_args = mock_http.get.call_args
            headers = call_args[1]['headers']
            assert 'Cookie' in headers
            # Should contain both cookies (order may vary)
            assert "session_token=abc123" in headers['Cookie']
            assert "user_pref=en" in headers['Cookie']
            
            print("✓ Dict cookies properly converted to header string")
        
        print("✓ _fetch_timedtext_json3 user cookie integration working")
        return True
        
    except Exception as e:
        print(f"✗ _fetch_timedtext_json3 test failed: {e}")
        return False


def test_fetch_timedtext_xml_with_user_cookies():
    """Test _fetch_timedtext_xml with user cookies parameter."""
    print("Testing _fetch_timedtext_xml with user cookies...")
    
    try:
        from transcript_service import _fetch_timedtext_xml
        
        # Test with string cookies
        with patch('transcript_service.HTTP') as mock_http:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = '<transcript><text>Test transcript</text></transcript>'
            mock_http.get.return_value = mock_response
            
            result = _fetch_timedtext_xml("test_video", "en", cookies="session_token=abc123; user_pref=en")
            
            # Verify the request was made with user cookies converted to dict
            mock_http.get.assert_called()
            call_args = mock_http.get.call_args
            cookies = call_args[1]['cookies']
            assert isinstance(cookies, dict)
            assert cookies.get('session_token') == 'abc123'
            assert cookies.get('user_pref') == 'en'
            
            print("✓ String cookies properly converted to dict for requests")
        
        # Test with dict cookies
        with patch('transcript_service.HTTP') as mock_http:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = '<transcript><text>Test transcript</text></transcript>'
            mock_http.get.return_value = mock_response
            
            cookie_dict = {"session_token": "abc123", "user_pref": "en"}
            result = _fetch_timedtext_xml("test_video", "en", cookies=cookie_dict)
            
            # Verify the request was made with dict cookies
            mock_http.get.assert_called()
            call_args = mock_http.get.call_args
            cookies = call_args[1]['cookies']
            assert cookies == cookie_dict
            
            print("✓ Dict cookies properly passed through")
        
        print("✓ _fetch_timedtext_xml user cookie integration working")
        return True
        
    except Exception as e:
        print(f"✗ _fetch_timedtext_xml test failed: {e}")
        return False


def test_get_captions_via_timedtext_cookie_priority():
    """Test get_captions_via_timedtext cookie priority logic."""
    print("Testing get_captions_via_timedtext cookie priority...")
    
    try:
        from transcript_service import get_captions_via_timedtext
        
        # Mock the internal functions
        with patch('transcript_service._fetch_timedtext_json3') as mock_json3, \
             patch('transcript_service._fetch_timedtext_xml') as mock_xml, \
             patch('transcript_service._cookie_header_from_env_or_file') as mock_env_cookies:
            
            mock_json3.return_value = "Test transcript from json3"
            mock_xml.return_value = ""
            mock_env_cookies.return_value = "env_cookie=env_value"
            
            # Test user cookies take priority over environment cookies
            user_cookies = {"user_cookie": "user_value"}
            result = get_captions_via_timedtext("test_video", user_cookies=user_cookies)
            
            # Verify user cookies were passed to json3 method
            mock_json3.assert_called_with("test_video", proxy_manager=None, cookies=user_cookies)
            
            print("✓ User cookies take priority over environment cookies")
        
        # Test fallback to environment cookies when no user cookies
        with patch('transcript_service._fetch_timedtext_json3') as mock_json3, \
             patch('transcript_service._fetch_timedtext_xml') as mock_xml, \
             patch('transcript_service._cookie_header_from_env_or_file') as mock_env_cookies:
            
            mock_json3.return_value = "Test transcript from json3"
            mock_xml.return_value = ""
            mock_env_cookies.return_value = "env_cookie=env_value"
            
            result = get_captions_via_timedtext("test_video")
            
            # Verify environment cookies were used (converted to None for json3, dict for xml)
            mock_json3.assert_called_with("test_video", proxy_manager=None, cookies=None)
            
            print("✓ Environment cookies used when no user cookies provided")
        
        print("✓ get_captions_via_timedtext cookie priority working")
        return True
        
    except Exception as e:
        print(f"✗ get_captions_via_timedtext test failed: {e}")
        return False


def test_cookie_source_logging():
    """Test that cookie source is properly logged."""
    print("Testing cookie source logging...")
    
    try:
        from transcript_service import _fetch_timedtext_json3, _fetch_timedtext_xml
        
        # Capture log messages
        import io
        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.DEBUG)
        logger = logging.getLogger('transcript_service')
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        
        with patch('transcript_service.HTTP') as mock_http:
            mock_response = MagicMock()
            mock_response.status_code = 404  # No transcript found
            mock_http.get.return_value = mock_response
            
            # Test user cookie logging
            _fetch_timedtext_json3("test_video", cookies="user_cookie=value")
            
            log_output = log_capture.getvalue()
            assert "cookie_source=user" in log_output
            
            print("✓ Cookie source logging working")
        
        return True
        
    except Exception as e:
        print(f"✗ Cookie source logging test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("ENHANCED TIMED-TEXT COOKIE INTEGRATION TESTS")
    print("=" * 60)
    
    tests = [
        test_fetch_timedtext_json3_with_user_cookies,
        test_fetch_timedtext_xml_with_user_cookies,
        test_get_captions_via_timedtext_cookie_priority,
        test_cookie_source_logging,
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
        print("✓ All enhanced timed-text cookie integration tests passed!")
        return True
    else:
        print("✗ Some tests failed")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)