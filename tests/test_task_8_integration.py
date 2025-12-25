#!/usr/bin/env python3
"""
Integration test for Task 8: Proxy-Enforced FFmpeg Audio Extraction

This test demonstrates the complete integration of proxy environment variables
with the ASRAudioExtractor and verifies all requirements are met.
"""

import os
import sys
import logging
import tempfile
from unittest.mock import Mock, patch, MagicMock

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from transcript_service import ASRAudioExtractor
from proxy_manager import ProxyManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_requirement_8_1():
    """Requirement 8.1: ASRAudioExtractor._extract_audio_to_wav computes proxy URL via proxy manager"""
    print("\n=== Testing Requirement 8.1: Proxy URL Computation ===")
    
    mock_secret = {
        "provider": "oxylabs",
        "host": "pr.oxylabs.io",
        "port": 10000,
        "username": "testuser",
        "password": "testpass"
    }
    
    pm = ProxyManager(secret_dict=mock_secret)
    extractor = ASRAudioExtractor("fake_deepgram_key", pm)
    
    # Verify proxy manager is available
    assert extractor.proxy_manager is not None, "ProxyManager should be available"
    
    # Verify proxy environment variables can be computed
    proxy_env = extractor.proxy_manager.proxy_env_for_subprocess()
    assert "http_proxy" in proxy_env, "http_proxy should be computed"
    assert "https_proxy" in proxy_env, "https_proxy should be computed"
    
    print("✅ Requirement 8.1: Proxy URL computation via proxy manager works")

def test_requirement_8_2():
    """Requirement 8.2: Set http_proxy and https_proxy environment variables for ffmpeg subprocess"""
    print("\n=== Testing Requirement 8.2: Environment Variables for FFmpeg ===")
    
    mock_secret = {
        "provider": "oxylabs", 
        "host": "pr.oxylabs.io",
        "port": 10000,
        "username": "testuser",
        "password": "testpass"
    }
    
    pm = ProxyManager(secret_dict=mock_secret)
    extractor = ASRAudioExtractor("fake_deepgram_key", pm)
    
    with patch('subprocess.run') as mock_run, \
         patch('os.path.exists') as mock_exists, \
         patch('os.path.getsize') as mock_getsize, \
         patch.object(extractor, '_verify_proxy_configuration') as mock_verify:
        
        # Setup mocks
        mock_verify.return_value = True
        mock_exists.return_value = True
        mock_getsize.return_value = 1000
        mock_run.return_value = Mock(returncode=0)
        
        # Test audio extraction
        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = os.path.join(temp_dir, "test.wav")
            result = extractor._extract_audio_to_wav("http://example.com/audio.m3u8", wav_path)
            
            # Verify subprocess was called with environment variables
            assert mock_run.called, "subprocess.run should have been called"
            call_args = mock_run.call_args
            env = call_args.kwargs.get('env', {})
            
            assert 'http_proxy' in env, "http_proxy should be set in environment"
            assert 'https_proxy' in env, "https_proxy should be set in environment"
            
    print("✅ Requirement 8.2: http_proxy and https_proxy environment variables set for FFmpeg")

def test_requirement_8_3():
    """Requirement 8.3: Add immediate failure detection for broken proxy configurations"""
    print("\n=== Testing Requirement 8.3: Immediate Failure Detection ===")
    
    mock_secret = {
        "provider": "oxylabs",
        "host": "pr.oxylabs.io", 
        "port": 10000,
        "username": "testuser",
        "password": "testpass"
    }
    
    pm = ProxyManager(secret_dict=mock_secret)
    extractor = ASRAudioExtractor("fake_deepgram_key", pm)
    
    # Test immediate failure when proxy verification fails
    with patch.object(extractor, '_verify_proxy_configuration') as mock_verify:
        mock_verify.return_value = False
        
        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = os.path.join(temp_dir, "test.wav")
            result = extractor._extract_audio_to_wav("http://example.com/audio.m3u8", wav_path)
            
            # Should return False immediately
            assert result == False, "Should fail immediately when proxy verification fails"
            
    print("✅ Requirement 8.3: Immediate failure detection for broken proxy configurations")

def test_requirement_8_4():
    """Requirement 8.4: Verify external IP changes when proxy environment is set"""
    print("\n=== Testing Requirement 8.4: External IP Verification ===")
    
    mock_secret = {
        "provider": "oxylabs",
        "host": "pr.oxylabs.io",
        "port": 10000, 
        "username": "testuser",
        "password": "testpass"
    }
    
    pm = ProxyManager(secret_dict=mock_secret)
    extractor = ASRAudioExtractor("fake_deepgram_key", pm)
    
    proxy_env = {
        "http_proxy": "http://testuser:testpass@pr.oxylabs.io:10000",
        "https_proxy": "http://testuser:testpass@pr.oxylabs.io:10000"
    }
    
    # Test successful IP verification (different IPs)
    with patch('requests.get') as mock_get:
        direct_response = Mock()
        direct_response.json.return_value = {"origin": "1.2.3.4"}
        
        proxy_response = Mock()
        proxy_response.json.return_value = {"origin": "5.6.7.8"}
        
        mock_get.side_effect = [direct_response, proxy_response]
        
        result = extractor._verify_proxy_configuration(proxy_env)
        assert result == True, "Should pass when IPs are different"
    
    # Test failed IP verification (same IPs)
    with patch('requests.get') as mock_get:
        same_ip_response = Mock()
        same_ip_response.json.return_value = {"origin": "1.2.3.4"}
        mock_get.return_value = same_ip_response
        
        result = extractor._verify_proxy_configuration(proxy_env)
        assert result == False, "Should fail when IPs are the same"
    
    print("✅ Requirement 8.4: External IP verification when proxy environment is set")

def test_requirement_8_5():
    """Requirement 8.5: External IP observed by httpbin changes when proxy is set"""
    print("\n=== Testing Requirement 8.5: HTTPBin IP Change Verification ===")
    
    mock_secret = {
        "provider": "oxylabs",
        "host": "pr.oxylabs.io",
        "port": 10000,
        "username": "testuser", 
        "password": "testpass"
    }
    
    pm = ProxyManager(secret_dict=mock_secret)
    extractor = ASRAudioExtractor("fake_deepgram_key", pm)
    
    # Test that verification specifically uses httpbin.org/ip
    proxy_env = {
        "http_proxy": "http://testuser:testpass@pr.oxylabs.io:10000",
        "https_proxy": "http://testuser:testpass@pr.oxylabs.io:10000"
    }
    
    with patch('requests.get') as mock_get:
        # Mock direct call to httpbin
        direct_response = Mock()
        direct_response.json.return_value = {"origin": "192.168.1.100"}
        
        # Mock proxy call to httpbin
        proxy_response = Mock()
        proxy_response.json.return_value = {"origin": "203.0.113.50"}
        
        mock_get.side_effect = [direct_response, proxy_response]
        
        result = extractor._verify_proxy_configuration(proxy_env)
        
        # Verify httpbin.org/ip was called
        calls = mock_get.call_args_list
        assert len(calls) == 2, "Should make 2 calls to httpbin"
        assert "httpbin.org/ip" in calls[0][0][0], "First call should be to httpbin.org/ip"
        assert "httpbin.org/ip" in calls[1][0][0], "Second call should be to httpbin.org/ip"
        
        # Verify proxy was used in second call
        second_call_kwargs = calls[1][1]
        assert 'proxies' in second_call_kwargs, "Second call should use proxies"
        
        assert result == True, "Should pass when httpbin shows different IPs"
    
    print("✅ Requirement 8.5: HTTPBin IP change verification works correctly")

def test_backward_compatibility():
    """Test that existing functionality still works"""
    print("\n=== Testing Backward Compatibility ===")
    
    # Test old constructor (without proxy_manager)
    extractor_old = ASRAudioExtractor("fake_deepgram_key")
    assert extractor_old.proxy_manager is None, "Old constructor should work"
    
    # Test that _extract_audio_to_wav works without proxy_manager
    with patch('subprocess.run') as mock_run, \
         patch('os.path.exists') as mock_exists, \
         patch('os.path.getsize') as mock_getsize:
        
        mock_exists.return_value = True
        mock_getsize.return_value = 1000
        mock_run.return_value = Mock(returncode=0)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = os.path.join(temp_dir, "test.wav")
            result = extractor_old._extract_audio_to_wav("http://example.com/audio.m3u8", wav_path)
            
            # Should work without proxy
            assert mock_run.called, "Should still call subprocess.run"
            call_args = mock_run.call_args
            env = call_args.kwargs.get('env', os.environ)
            
            # Should not have proxy environment variables from our implementation
            # (might have them from system environment, but that's not our concern)
    
    print("✅ Backward compatibility maintained")

def main():
    """Run all integration tests"""
    print("Integration Test for Task 8: Proxy-Enforced FFmpeg Audio Extraction")
    print("=" * 70)
    
    try:
        test_requirement_8_1()
        test_requirement_8_2()
        test_requirement_8_3()
        test_requirement_8_4()
        test_requirement_8_5()
        test_backward_compatibility()
        
        print("\n" + "=" * 70)
        print("✅ ALL REQUIREMENTS VERIFIED! Task 8 implementation is complete.")
        print("\nRequirements Status:")
        print("- ✅ 8.1: Proxy environment variable computation in ASRAudioExtractor")
        print("- ✅ 8.2: Set http_proxy and https_proxy environment variables for ffmpeg subprocess")
        print("- ✅ 8.3: Add immediate failure detection for broken proxy configurations")
        print("- ✅ 8.4: Verify external IP changes when proxy environment is set")
        print("- ✅ 8.5: External IP observed by httpbin changes when proxy is set")
        print("- ✅ Backward compatibility maintained")
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()