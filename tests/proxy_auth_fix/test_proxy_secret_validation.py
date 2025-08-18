#!/usr/bin/env python3
"""
Test script for ProxySecret validation
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from proxy_manager import ProxySecret, ProxyValidationError, looks_preencoded

def test_secret_validation():
    """Test ProxySecret validation with various inputs"""
    
    print("Testing ProxySecret validation...")
    
    # Test 1: Valid RAW secret
    print("\n1. Testing valid RAW secret...")
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
    
    try:
        secret = ProxySecret.from_dict(valid_secret)
        print(f"✅ Valid secret accepted: {secret.provider}@{secret.host}:{secret.port}")
    except Exception as e:
        print(f"❌ Valid secret rejected: {e}")
        return False
    
    # Test 2: Pre-encoded password (should be rejected)
    print("\n2. Testing pre-encoded password...")
    preencoded_secret = valid_secret.copy()
    preencoded_secret["password"] = "myRawPassword123%21"  # ! encoded as %21
    
    try:
        secret = ProxySecret.from_dict(preencoded_secret)
        print(f"❌ Pre-encoded password accepted (should be rejected)")
        return False
    except ProxyValidationError as e:
        print(f"✅ Pre-encoded password correctly rejected: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    
    # Test 3: Host with scheme (should be rejected)
    print("\n3. Testing host with scheme...")
    scheme_secret = valid_secret.copy()
    scheme_secret["host"] = "https://pr.oxylabs.io"
    
    try:
        secret = ProxySecret.from_dict(scheme_secret)
        print(f"❌ Host with scheme accepted (should be rejected)")
        return False
    except ProxyValidationError as e:
        print(f"✅ Host with scheme correctly rejected: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    
    # Test 4: Missing required field
    print("\n4. Testing missing required field...")
    missing_secret = valid_secret.copy()
    del missing_secret["password"]
    
    try:
        secret = ProxySecret.from_dict(missing_secret)
        print(f"❌ Missing password accepted (should be rejected)")
        return False
    except ProxyValidationError as e:
        print(f"✅ Missing password correctly rejected: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    
    # Test 5: Test looks_preencoded function
    print("\n5. Testing looks_preencoded function...")
    test_cases = [
        ("rawPassword123!", False, "Raw password"),
        ("rawPassword123%21", True, "Password with encoded !"),
        ("user%40domain.com", True, "Password with encoded @"),
        ("simple", False, "Simple password"),
        ("", False, "Empty password"),
    ]
    
    for password, expected, description in test_cases:
        result = looks_preencoded(password)
        if result == expected:
            print(f"✅ {description}: {password} -> {result}")
        else:
            print(f"❌ {description}: {password} -> {result} (expected {expected})")
            return False
    
    # Test 6: Test proxy URL building
    print("\n6. Testing proxy URL building...")
    try:
        secret = ProxySecret.from_dict(valid_secret)
        
        # Test without session
        url_no_session = secret.build_proxy_url()
        expected_no_session = "http://customer-test123:myRawPassword123%21@pr.oxylabs.io:7777"
        if url_no_session == expected_no_session:
            print(f"✅ URL without session: {url_no_session}")
        else:
            print(f"❌ URL without session: {url_no_session} (expected {expected_no_session})")
            return False
        
        # Test with session
        url_with_session = secret.build_proxy_url("abc123")
        expected_with_session = "http://customer-test123-sessid-abc123:myRawPassword123%21@pr.oxylabs.io:7777"
        if url_with_session == expected_with_session:
            print(f"✅ URL with session: {url_with_session}")
        else:
            print(f"❌ URL with session: {url_with_session} (expected {expected_with_session})")
            return False
            
    except Exception as e:
        print(f"❌ URL building failed: {e}")
        return False
    
    print("\n🎉 All tests passed! Secret validation is working correctly.")
    return True

if __name__ == "__main__":
    success = test_secret_validation()
    sys.exit(0 if success else 1)