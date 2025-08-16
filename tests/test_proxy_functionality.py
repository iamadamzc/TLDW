#!/usr/bin/env python3
"""
Test script to verify proxy functionality with yt-dlp operations
This tests the core proxy configuration without requiring web authentication
"""

import os
import sys
import json
import logging
from proxy_manager import ProxyManager
from yt_download_helper import download_audio_with_fallback

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_proxy_configuration():
    """Test that proxy configuration is loaded correctly"""
    print("=== Testing Proxy Configuration ===")
    
    try:
        proxy_manager = ProxyManager()
        
        # Test proxy config loading
        if proxy_manager.proxy_config:
            print("✅ Proxy configuration loaded successfully")
            print(f"   Source: {proxy_manager.config_source}")
            print(f"   Country: {proxy_manager.proxy_config.get('country', 'unknown')}")
            print(f"   Host: {proxy_manager.proxy_config.get('host', 'unknown')}")
            print(f"   Port: {proxy_manager.proxy_config.get('port', 'unknown')}")
            return True
        else:
            print("❌ Proxy configuration not loaded")
            return False
            
    except Exception as e:
        print(f"❌ Error loading proxy configuration: {e}")
        return False

def test_proxy_session():
    """Test that proxy sessions can be created"""
    print("\n=== Testing Proxy Session Creation ===")
    
    try:
        proxy_manager = ProxyManager()
        
        # Test session creation
        test_video_id = "dQw4w9WgXcQ"  # Rick Roll for testing
        session = proxy_manager.get_session_for_video(test_video_id)
        
        if session:
            print("✅ Proxy session created successfully")
            print(f"   Session type: {type(session).__name__}")
            
            # Test session has proxy configuration
            if hasattr(session, 'proxies') and session.proxies:
                print("✅ Session has proxy configuration")
                # Don't print actual proxy details for security
                print(f"   Proxy protocols configured: {list(session.proxies.keys())}")
                return True
            else:
                print("⚠️  Session created but no proxy configuration found")
                return False
        else:
            print("❌ Failed to create proxy session")
            return False
            
    except Exception as e:
        print(f"❌ Error creating proxy session: {e}")
        return False

def test_yt_dlp_with_proxy():
    """Test yt-dlp functionality with proxy (audio download only)"""
    print("\n=== Testing yt-dlp with Proxy ===")
    
    try:
        # Use a short, simple video for testing
        test_video_id = "dQw4w9WgXcQ"  # Rick Roll - short and reliable
        test_url = f"https://www.youtube.com/watch?v={test_video_id}"
        
        print(f"Testing with video: {test_url}")
        print("Attempting audio download with proxy...")
        
        # This will test the full proxy chain: ProxyManager -> yt-dlp -> proxy authentication
        result = download_audio_with_fallback(test_video_id, max_duration_minutes=1)
        
        if result and result.get('success'):
            print("✅ yt-dlp audio download successful with proxy")
            print(f"   Duration: {result.get('duration', 'unknown')} seconds")
            print(f"   File size: {result.get('file_size', 'unknown')} bytes")
            print(f"   Proxy used: {result.get('proxy_used', 'unknown')}")
            return True
        else:
            print("❌ yt-dlp audio download failed")
            if result:
                print(f"   Error: {result.get('error', 'unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing yt-dlp with proxy: {e}")
        return False

def main():
    """Run all proxy functionality tests"""
    print("🧪 Proxy Functionality Test Suite")
    print("=" * 50)
    
    # Test 1: Proxy Configuration
    config_ok = test_proxy_configuration()
    
    # Test 2: Proxy Session Creation
    session_ok = test_proxy_session()
    
    # Test 3: yt-dlp with Proxy (only if previous tests pass)
    ytdlp_ok = False
    if config_ok and session_ok:
        ytdlp_ok = test_yt_dlp_with_proxy()
    else:
        print("\n⏭️  Skipping yt-dlp test due to previous failures")
    
    # Summary
    print("\n" + "=" * 50)
    print("🏁 Test Results Summary:")
    print(f"   Proxy Configuration: {'✅ PASS' if config_ok else '❌ FAIL'}")
    print(f"   Proxy Session:       {'✅ PASS' if session_ok else '❌ FAIL'}")
    print(f"   yt-dlp with Proxy:   {'✅ PASS' if ytdlp_ok else '❌ FAIL'}")
    
    if config_ok and session_ok and ytdlp_ok:
        print("\n🎉 All proxy functionality tests PASSED!")
        print("   The proxy configuration is working correctly.")
        return 0
    else:
        print("\n⚠️  Some proxy functionality tests FAILED.")
        print("   Check the error messages above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())