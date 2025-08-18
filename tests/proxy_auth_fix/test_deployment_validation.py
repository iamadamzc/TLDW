#!/usr/bin/env python3
"""
Test deployment validation with various secret formats
"""

import sys
import os
import json
from unittest.mock import patch

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_malformed_secret_detection():
    """Test that deployment validation catches malformed secrets"""
    print("Testing deployment validation with malformed secrets...")
    
    from validate_deployment import validate_secret_format
    
    # Test 1: Pre-encoded password
    malformed_secret = {
        "provider": "oxylabs",
        "host": "pr.oxylabs.io",
        "port": 7777,
        "username": "customer-test123",
        "password": "myRawPassword123%21",  # ! encoded as %21
        "geo_enabled": False
    }
    
    valid, message = validate_secret_format(malformed_secret)
    if not valid and "URL-encoded" in message:
        print("✅ Pre-encoded password correctly detected")
    else:
        print(f"❌ Pre-encoded password not detected: {message}")
        return False
    
    # Test 2: Host with scheme
    malformed_secret["password"] = "myRawPassword123!"  # Fix password
    malformed_secret["host"] = "https://pr.oxylabs.io"  # Add scheme
    
    valid, message = validate_secret_format(malformed_secret)
    if not valid and "scheme" in message:
        print("✅ Host with scheme correctly detected")
    else:
        print(f"❌ Host with scheme not detected: {message}")
        return False
    
    # Test 3: Missing field
    del malformed_secret["password"]
    malformed_secret["host"] = "pr.oxylabs.io"  # Fix host
    
    valid, message = validate_secret_format(malformed_secret)
    if not valid and "Missing" in message:
        print("✅ Missing field correctly detected")
    else:
        print(f"❌ Missing field not detected: {message}")
        return False
    
    # Test 4: Valid secret
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
    
    valid, message = validate_secret_format(valid_secret)
    if valid:
        print("✅ Valid secret correctly accepted")
        return True
    else:
        print(f"❌ Valid secret rejected: {message}")
        return False

def test_deployment_validation_integration():
    """Test full deployment validation"""
    print("\nTesting full deployment validation...")
    
    # Test with malformed secret in environment
    malformed_config = json.dumps({
        "provider": "oxylabs",
        "host": "https://pr.oxylabs.io",  # Has scheme - should fail
        "port": 7777,
        "username": "customer-test123",
        "password": "myRawPassword123%21",  # Pre-encoded - should fail
        "geo_enabled": False
    })
    
    with patch.dict(os.environ, {'OXYLABS_PROXY_CONFIG': malformed_config}):
        # Import and run validation
        from validate_deployment import main
        
        # Capture the result
        result = main()
        
        if not result:  # Should fail validation
            print("✅ Deployment validation correctly failed for malformed secret")
            return True
        else:
            print("❌ Deployment validation should have failed")
            return False

if __name__ == "__main__":
    print("🧪 Testing Deployment Validation")
    print("=" * 50)
    
    tests = [
        test_malformed_secret_detection,
        test_deployment_validation_integration
    ]
    
    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                print("❌ Test failed")
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
    
    print(f"\n📊 Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All deployment validation tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed")
        sys.exit(1)