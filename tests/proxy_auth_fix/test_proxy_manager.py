#!/usr/bin/env python3
"""
Test script for ProxyManager functionality
"""

import sys
import os
import logging
import threading
import time
from unittest.mock import patch, MagicMock
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from proxy_manager import ProxyManager, ProxyAuthError, ProxyConfigError, extract_session_from_proxies

def test_proxy_manager():
    """Test ProxyManager with preflight and session management"""
    
    print("Testing ProxyManager functionality...")
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Test secret
    valid_secret = {
        "provider": "oxylabs",
        "host": "pr.oxylabs.io",
        "port": 7777,
        "username": "customer-test123",
        "password": "myRawPassword123!",
        "geo_enabled": False,
        "country": "us",
        "version": 1
    }
    
    # Test 1: ProxyManager initialization
    print("\n1. Testing ProxyManager initialization...")
    try:
        pm = ProxyManager(valid_secret, logger)
        print(f"✅ ProxyManager initialized successfully")
        print(f"   Secret provider: {pm.secret.provider}")
        print(f"   Secret host: {pm.secret.host}:{pm.secret.port}")
    except Exception as e:
        print(f"❌ ProxyManager initialization failed: {e}")
        return False
    
    # Test 2: Session token generation
    print("\n2. Testing session token generation...")
    token1 = pm._generate_session_token("test_video_123")
    token2 = pm._generate_session_token("test_video_123")
    token3 = pm._generate_session_token("different_video")
    token4 = pm._generate_session_token(None)
    
    print(f"   Token 1 (test_video_123): {token1}")
    print(f"   Token 2 (test_video_123): {token2}")
    print(f"   Token 3 (different_video): {token3}")
    print(f"   Token 4 (None): {token4}")
    
    if len(token1) > 10 and token1 != token2:
        print("✅ Session tokens are unique and properly generated")
    else:
        print("❌ Session token generation failed")
        return False
    
    # Test 3: Proxy URL generation
    print("\n3. Testing proxy URL generation...")
    proxies = pm.proxies_for("test_video_456")
    
    if proxies.get("http") and proxies.get("https"):
        print("✅ Proxy URLs generated successfully")
        print(f"   HTTP proxy: {proxies['http'][:50]}...")
        print(f"   HTTPS proxy: {proxies['https'][:50]}...")
        
        # Test session extraction
        session_token = extract_session_from_proxies(proxies)
        if session_token:
            print(f"✅ Session token extracted: {session_token}")
        else:
            print("❌ Failed to extract session token")
            return False
    else:
        print("❌ Proxy URL generation failed")
        return False
    
    # Test 4: Session blacklisting
    print("\n4. Testing session blacklisting...")
    test_token = "test_token_123"
    
    # Initially not blacklisted
    if test_token not in pm.session_blacklist:
        print("✅ Token initially not blacklisted")
    else:
        print("❌ Token should not be initially blacklisted")
        return False
    
    # Blacklist the token
    pm.rotate_session(test_token)
    
    # Should now be blacklisted
    if test_token in pm.session_blacklist:
        print("✅ Token successfully blacklisted")
    else:
        print("❌ Token should be blacklisted after rotation")
        return False
    
    # Test 5: Preflight disabled mode
    print("\n5. Testing preflight disabled mode...")
    os.environ["OXY_PREFLIGHT_DISABLED"] = "true"
    pm_disabled = ProxyManager(valid_secret, logger)
    
    try:
        result = pm_disabled.preflight()
        if result is True:
            print("✅ Preflight disabled mode working")
        else:
            print("❌ Preflight disabled mode not working")
            return False
    except Exception as e:
        print(f"❌ Preflight disabled mode failed: {e}")
        return False
    finally:
        del os.environ["OXY_PREFLIGHT_DISABLED"]
    
    # Test 6: Mock preflight success
    print("\n6. Testing preflight with mocked success...")
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_get.return_value = mock_response
        
        try:
            result = pm.preflight(timeout=1.0)
            if result is True and pm.healthy is True:
                print("✅ Preflight success test passed")
            else:
                print(f"❌ Preflight success test failed: result={result}, healthy={pm.healthy}")
                return False
        except Exception as e:
            print(f"❌ Preflight success test failed: {e}")
            return False
    
    # Test 7: Mock preflight auth failure
    print("\n7. Testing preflight with mocked auth failure...")
    pm_auth_test = ProxyManager(valid_secret, logger)  # Fresh instance
    
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 407
        mock_get.return_value = mock_response
        
        try:
            result = pm_auth_test.preflight(timeout=1.0)
            print(f"❌ Preflight should have raised ProxyAuthError, got result: {result}")
            return False
        except ProxyAuthError as e:
            if pm_auth_test.healthy is False:
                print("✅ Preflight auth failure test passed")
            else:
                print(f"❌ Preflight auth failure test failed: healthy={pm_auth_test.healthy}")
                return False
        except Exception as e:
            print(f"❌ Preflight auth failure test failed with unexpected error: {e}")
            return False
    
    # Test 8: Rate limiting
    print("\n8. Testing preflight rate limiting...")
    os.environ["OXY_PREFLIGHT_MAX_PER_MINUTE"] = "2"
    pm_rate_test = ProxyManager(valid_secret, logger)
    
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_get.return_value = mock_response
        
        # First two calls should work
        pm_rate_test.preflight()
        pm_rate_test.preflight()
        
        # Third call should be rate limited (return cached result)
        call_count_before = mock_get.call_count
        pm_rate_test.preflight()
        call_count_after = mock_get.call_count
        
        if call_count_after == call_count_before:
            print("✅ Rate limiting working correctly")
        else:
            print("❌ Rate limiting not working")
            return False
    
    del os.environ["OXY_PREFLIGHT_MAX_PER_MINUTE"]
    
    # Test 9: Thread safety
    print("\n9. Testing thread safety...")
    pm_thread_test = ProxyManager(valid_secret, logger)
    results = []
    errors = []
    
    def worker():
        try:
            for i in range(5):
                token = pm_thread_test._generate_session_token(f"video_{threading.current_thread().ident}_{i}")
                results.append(token)
                time.sleep(0.01)  # Small delay
        except Exception as e:
            errors.append(e)
    
    # Start multiple threads
    threads = []
    for i in range(3):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()
    
    # Wait for all threads
    for t in threads:
        t.join()
    
    if not errors and len(set(results)) == len(results):
        print(f"✅ Thread safety test passed: {len(results)} unique tokens generated")
    else:
        print(f"❌ Thread safety test failed: {len(errors)} errors, {len(set(results))}/{len(results)} unique tokens")
        return False
    
    print("\n🎉 All ProxyManager tests passed!")
    return True

if __name__ == "__main__":
    success = test_proxy_manager()
    sys.exit(0 if success else 1)