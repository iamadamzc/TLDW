#!/usr/bin/env python3
"""
Test script for Task 8: Proxy-Enforced FFmpeg Audio Extraction

This script tests the implementation of proxy environment variable computation
in ASRAudioExtractor and verifies that FFmpeg uses proxy connections.
"""

import os
import sys
import logging
import tempfile
import subprocess
from unittest.mock import Mock, patch, MagicMock

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from transcript_service import ASRAudioExtractor
from proxy_manager import ProxyManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_proxy_env_for_subprocess():
    """Test ProxyManager.proxy_env_for_subprocess method"""
    print("\n=== Testing ProxyManager.proxy_env_for_subprocess ===")
    
    # Test with no proxy configuration
    pm_no_proxy = ProxyManager(secret_dict={})
    env_vars = pm_no_proxy.proxy_env_for_subprocess()
    assert env_vars == {}, f"Expected empty dict for no proxy, got {env_vars}"
    print("✅ No proxy configuration returns empty dict")
    
    # Test with mock proxy configuration
    mock_secret = {
        "provider": "oxylabs",
        "host": "pr.oxylabs.io",
        "port": 10000,
        "username": "testuser",
        "password": "testpass",
        "session_ttl_minutes": 10
    }
    
    pm_with_proxy = ProxyManager(secret_dict=mock_secret)
    env_vars = pm_with_proxy.proxy_env_for_subprocess()
    
    assert "http_proxy" in env_vars, "http_proxy not in environment variables"
    assert "https_proxy" in env_vars, "https_proxy not in environment variables"
    assert env_vars["http_proxy"] == env_vars["https_proxy"], "http_proxy and https_proxy should be the same"
    assert "testuser" in env_vars["http_proxy"], "Username not in proxy URL"
    assert "testpass" in env_vars["http_proxy"], "Password not in proxy URL"
    assert "pr.oxylabs.io:10000" in env_vars["http_proxy"], "Host and port not in proxy URL"
    
    print(f"✅ Proxy environment variables generated correctly")
    print(f"   http_proxy: {env_vars['http_proxy'][:50]}...")
    print(f"   https_proxy: {env_vars['https_proxy'][:50]}...")

def test_asr_extractor_with_proxy_manager():
    """Test ASRAudioExtractor initialization with proxy_manager"""
    print("\n=== Testing ASRAudioExtractor with ProxyManager ===")
    
    # Test without proxy manager
    extractor_no_proxy = ASRAudioExtractor("fake_deepgram_key")
    assert extractor_no_proxy.proxy_manager is None, "proxy_manager should be None when not provided"
    print("✅ ASRAudioExtractor initializes without proxy_manager")
    
    # Test with proxy manager
    mock_secret = {
        "provider": "oxylabs",
        "host": "pr.oxylabs.io", 
        "port": 10000,
        "username": "testuser",
        "password": "testpass"
    }
    pm = ProxyManager(secret_dict=mock_secret)
    
    extractor_with_proxy = ASRAudioExtractor("fake_deepgram_key", pm)
    assert extractor_with_proxy.proxy_manager is not None, "proxy_manager should not be None when provided"
    assert extractor_with_proxy.proxy_manager == pm, "proxy_manager should be the same instance"
    print("✅ ASRAudioExtractor initializes with proxy_manager")

def test_proxy_verification():
    """Test proxy configuration verification"""
    print("\n=== Testing Proxy Configuration Verification ===")
    
    mock_secret = {
        "provider": "oxylabs",
        "host": "pr.oxylabs.io",
        "port": 10000,
        "username": "testuser", 
        "password": "testpass"
    }
    pm = ProxyManager(secret_dict=mock_secret)
    extractor = ASRAudioExtractor("fake_deepgram_key", pm)
    
    # Test with empty proxy environment
    result = extractor._verify_proxy_configuration({})
    assert result == True, "Empty proxy environment should return True"
    print("✅ Empty proxy environment verification passes")
    
    # Test with mock proxy environment (we'll mock the requests)
    proxy_env = {
        "http_proxy": "http://testuser:testpass@pr.oxylabs.io:10000",
        "https_proxy": "http://testuser:testpass@pr.oxylabs.io:10000"
    }
    
    # Mock requests to simulate different IPs
    with patch('requests.get') as mock_get:
        # Mock direct IP response
        direct_response = Mock()
        direct_response.json.return_value = {"origin": "1.2.3.4"}
        
        # Mock proxy IP response  
        proxy_response = Mock()
        proxy_response.json.return_value = {"origin": "5.6.7.8"}
        
        # Configure mock to return different responses based on call
        mock_get.side_effect = [direct_response, proxy_response]
        
        result = extractor._verify_proxy_configuration(proxy_env)
        assert result == True, "Proxy verification should pass when IPs are different"
        print("✅ Proxy verification passes when IPs are different")
    
    # Test proxy verification failure (same IP)
    with patch('requests.get') as mock_get:
        # Mock both responses to return same IP
        same_ip_response = Mock()
        same_ip_response.json.return_value = {"origin": "1.2.3.4"}
        mock_get.return_value = same_ip_response
        
        result = extractor._verify_proxy_configuration(proxy_env)
        assert result == False, "Proxy verification should fail when IPs are the same"
        print("✅ Proxy verification fails when IPs are the same")

def test_ffmpeg_command_with_proxy():
    """Test that FFmpeg command includes proxy environment variables"""
    print("\n=== Testing FFmpeg Command with Proxy Environment ===")
    
    mock_secret = {
        "provider": "oxylabs",
        "host": "pr.oxylabs.io",
        "port": 10000,
        "username": "testuser",
        "password": "testpass"
    }
    pm = ProxyManager(secret_dict=mock_secret)
    extractor = ASRAudioExtractor("fake_deepgram_key", pm)
    
    # Mock the subprocess.run call to capture environment variables
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
            
            # Verify subprocess was called with proxy environment
            assert mock_run.called, "subprocess.run should have been called"
            call_args = mock_run.call_args
            
            # Check that env parameter was passed
            assert 'env' in call_args.kwargs, "env parameter should be passed to subprocess.run"
            env = call_args.kwargs['env']
            
            # Verify proxy environment variables are present
            assert 'http_proxy' in env, "http_proxy should be in environment"
            assert 'https_proxy' in env, "https_proxy should be in environment"
            assert 'testuser' in env['http_proxy'], "Username should be in proxy URL"
            
            print("✅ FFmpeg subprocess called with proxy environment variables")
            print(f"   http_proxy present: {'http_proxy' in env}")
            print(f"   https_proxy present: {'https_proxy' in env}")

def test_immediate_failure_detection():
    """Test immediate failure detection for broken proxy configurations"""
    print("\n=== Testing Immediate Failure Detection ===")
    
    mock_secret = {
        "provider": "oxylabs",
        "host": "pr.oxylabs.io",
        "port": 10000,
        "username": "testuser",
        "password": "testpass"
    }
    pm = ProxyManager(secret_dict=mock_secret)
    extractor = ASRAudioExtractor("fake_deepgram_key", pm)
    
    # Mock proxy verification to fail
    with patch.object(extractor, '_verify_proxy_configuration') as mock_verify:
        mock_verify.return_value = False
        
        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = os.path.join(temp_dir, "test.wav")
            result = extractor._extract_audio_to_wav("http://example.com/audio.m3u8", wav_path)
            
            # Should return False immediately when proxy verification fails
            assert result == False, "Should return False when proxy verification fails"
            print("✅ Immediate failure detection works for broken proxy configurations")

def main():
    """Run all tests"""
    print("Testing Task 8: Proxy-Enforced FFmpeg Audio Extraction")
    print("=" * 60)
    
    try:
        test_proxy_env_for_subprocess()
        test_asr_extractor_with_proxy_manager()
        test_proxy_verification()
        test_ffmpeg_command_with_proxy()
        test_immediate_failure_detection()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed! Task 8 implementation is working correctly.")
        print("\nImplemented features:")
        print("- ✅ ProxyManager.proxy_env_for_subprocess() method")
        print("- ✅ ASRAudioExtractor accepts proxy_manager parameter")
        print("- ✅ FFmpeg subprocess uses proxy environment variables")
        print("- ✅ Immediate failure detection for broken proxy configurations")
        print("- ✅ External IP verification when proxy environment is set")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()