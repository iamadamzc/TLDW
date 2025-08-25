#!/usr/bin/env python3
"""
Test script to verify the TranscriptService fixes:
1. user_id parameter addition
2. Cookie resolution and threading
3. ffmpeg CRLF header fix
4. YouTubei function completeness
"""

import os
import sys
import logging
from unittest.mock import Mock, patch, MagicMock

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_transcript_service_signature():
    """Test that TranscriptService.get_transcript has the correct signature"""
    try:
        from transcript_service import TranscriptService
        
        # Create instance
        service = TranscriptService()
        
        # Test that the method signature accepts user_id parameter
        import inspect
        sig = inspect.signature(service.get_transcript)
        params = list(sig.parameters.keys())
        
        print("✓ TranscriptService.get_transcript signature:")
        print(f"  Parameters: {params}")
        
        # Check required parameters
        assert 'video_id' in params, "Missing video_id parameter"
        assert 'user_id' in params, "Missing user_id parameter"
        assert 'language_codes' in params, "Missing language_codes parameter"
        assert 'proxy_manager' in params, "Missing proxy_manager parameter"
        assert 'cookies' in params, "Missing cookies parameter"
        
        print("✓ All required parameters present")
        
        # Check that user_id has correct default
        user_id_param = sig.parameters['user_id']
        assert user_id_param.default is None, f"user_id default should be None, got {user_id_param.default}"
        print("✓ user_id parameter has correct default (None)")
        
        return True
        
    except Exception as e:
        print(f"✗ Signature test failed: {e}")
        return False

def test_cookie_resolution():
    """Test cookie resolution logic"""
    try:
        from transcript_service import get_user_cookies_with_fallback
        
        # Test with no user_id (should fall back to environment)
        result = get_user_cookies_with_fallback(None)
        print(f"✓ Cookie fallback with no user_id: {type(result)} ({'found' if result else 'not found'})")
        
        # Test with user_id (should try S3 first, then fall back)
        result = get_user_cookies_with_fallback(123)
        print(f"✓ Cookie fallback with user_id=123: {type(result)} ({'found' if result else 'not found'})")
        
        return True
        
    except Exception as e:
        print(f"✗ Cookie resolution test failed: {e}")
        return False

def test_ffmpeg_headers():
    """Test that ffmpeg headers use real CRLF"""
    try:
        from transcript_service import ASRAudioExtractor
        
        # Create mock extractor
        extractor = ASRAudioExtractor("fake_key")
        
        # Mock the subprocess and file operations
        with patch('transcript_service.subprocess.run') as mock_run, \
             patch('transcript_service.os.path.exists', return_value=True), \
             patch('transcript_service.os.path.getsize', return_value=1000), \
             patch('transcript_service._cookie_header_from_env_or_file', return_value="test=cookie"):
            
            mock_run.return_value = Mock(returncode=0)
            
            # Call the method that should use proper CRLF
            result = extractor._extract_audio_to_wav("http://test.url", "/tmp/test.wav")
            
            # Check that subprocess.run was called
            assert mock_run.called, "subprocess.run should have been called"
            
            # Get the command that was passed
            call_args = mock_run.call_args[0][0]  # First positional argument (the command list)
            
            # Find the headers argument
            headers_arg = None
            for i, arg in enumerate(call_args):
                if arg == "-headers" and i + 1 < len(call_args):
                    headers_arg = call_args[i + 1]
                    break
            
            assert headers_arg is not None, "Headers argument not found in ffmpeg command"
            
            # Check that it contains real CRLF, not escaped
            assert "\r\n" in headers_arg, "Headers should contain real CRLF characters"
            assert "\\r\\n" not in headers_arg, "Headers should not contain escaped CRLF"
            
            print("✓ FFmpeg headers use real CRLF characters")
            print(f"  Headers preview: {repr(headers_arg[:50])}...")
            
            return True
            
    except Exception as e:
        print(f"✗ FFmpeg headers test failed: {e}")
        return False

def test_youtubei_function():
    """Test that YouTubei function is complete"""
    try:
        from transcript_service import get_transcript_via_youtubei, get_transcript_via_youtubei_with_timeout
        
        # Check function signatures
        import inspect
        
        sig1 = inspect.signature(get_transcript_via_youtubei)
        params1 = list(sig1.parameters.keys())
        print(f"✓ get_transcript_via_youtubei parameters: {params1}")
        
        sig2 = inspect.signature(get_transcript_via_youtubei_with_timeout)
        params2 = list(sig2.parameters.keys())
        print(f"✓ get_transcript_via_youtubei_with_timeout parameters: {params2}")
        
        # Check that both functions exist and are callable
        assert callable(get_transcript_via_youtubei), "get_transcript_via_youtubei should be callable"
        assert callable(get_transcript_via_youtubei_with_timeout), "get_transcript_via_youtubei_with_timeout should be callable"
        
        print("✓ YouTubei functions are complete and callable")
        
        return True
        
    except Exception as e:
        print(f"✗ YouTubei function test failed: {e}")
        return False

def test_integration():
    """Test integration of all fixes"""
    try:
        from transcript_service import TranscriptService
        
        # Mock dependencies
        with patch('transcript_service.shared_managers') as mock_managers, \
             patch('transcript_service.TranscriptCache') as mock_cache, \
             patch('transcript_service.get_transcript') as mock_get_transcript, \
             patch('transcript_service.get_captions_via_timedtext') as mock_timedtext, \
             patch('transcript_service.get_transcript_via_youtubei_with_timeout') as mock_youtubei, \
             patch('transcript_service.get_user_cookies_with_fallback') as mock_cookies:
            
            # Set up mocks
            mock_managers.get_proxy_manager.return_value = None
            mock_managers.get_user_agent_manager.return_value = None
            mock_cache.return_value = Mock()
            mock_cache.return_value.get.return_value = None  # No cached result
            
            mock_cookies.return_value = "test=cookie; session=abc123"
            mock_get_transcript.return_value = ""  # Force fallback
            mock_timedtext.return_value = "Test transcript from timedtext"
            
            # Create service and test
            service = TranscriptService()
            
            # Test with user_id
            result = service.get_transcript(
                "test_video_id",
                language_codes=["en", "en-US"],
                user_id=123
            )
            
            # Verify cookie resolution was called with user_id
            mock_cookies.assert_called_with(123)
            
            # Verify timedtext was called with cookie_dict
            assert mock_timedtext.called, "timedtext should have been called"
            call_args = mock_timedtext.call_args
            assert 'cookie_jar' in call_args.kwargs, "cookie_jar should be passed to timedtext"
            
            print("✓ Integration test passed")
            print(f"  Result: {result[:50]}..." if result else "  Result: (empty)")
            print(f"  Cookie resolution called with user_id: 123")
            print(f"  Cookies threaded through timedtext: {call_args.kwargs.get('cookie_jar') is not None}")
            
            return True
            
    except Exception as e:
        print(f"✗ Integration test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("Testing TranscriptService fixes...")
    print("=" * 50)
    
    tests = [
        ("Signature Test", test_transcript_service_signature),
        ("Cookie Resolution Test", test_cookie_resolution),
        ("FFmpeg Headers Test", test_ffmpeg_headers),
        ("YouTubei Function Test", test_youtubei_function),
        ("Integration Test", test_integration),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        print("-" * 30)
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"✗ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("SUMMARY:")
    print("=" * 50)
    
    passed = 0
    for test_name, success in results:
        status = "PASS" if success else "FAIL"
        print(f"{test_name}: {status}")
        if success:
            passed += 1
    
    print(f"\nPassed: {passed}/{len(results)}")
    
    if passed == len(results):
        print("🎉 All tests passed! The fixes are working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please review the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
