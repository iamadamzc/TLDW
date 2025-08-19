#!/usr/bin/env python3
"""
Test ProxyManager resilience with missing or malformed secrets
"""

import logging
import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from proxy_manager import ProxyManager, ProxyValidationError

def test_missing_provider_field():
    """Test ProxyManager handles missing provider field gracefully"""
    print("Testing missing provider field...")
    
    # Secret missing provider field (the main issue from logs)
    malformed_secret = {
        "host": "proxy.example.com",
        "port": 8080,
        "username": "testuser",
        "password": "testpass",
        "protocol": "http"
        # Missing "provider" field
    }
    
    # Should not crash, should gracefully degrade
    try:
        proxy_manager = ProxyManager(malformed_secret, logging.getLogger(__name__))
        
        # Should be in degraded state
        assert not proxy_manager.in_use, "ProxyManager should not be in use with invalid secret"
        assert proxy_manager.secret is None, "Secret should be None with invalid schema"
        
        # Should return empty proxy config
        proxies = proxy_manager.proxies_for("test_video")
        assert proxies == {}, "Should return empty proxy config when not in use"
        
        print("✅ Missing provider field handled gracefully")
        return True
        
    except Exception as e:
        print(f"❌ ProxyManager crashed with missing provider: {e}")
        return False

def test_completely_empty_secret():
    """Test ProxyManager handles completely empty secret"""
    print("Testing completely empty secret...")
    
    try:
        proxy_manager = ProxyManager({}, logging.getLogger(__name__))
        
        assert not proxy_manager.in_use, "ProxyManager should not be in use with empty secret"
        assert proxy_manager.secret is None, "Secret should be None with empty dict"
        
        print("✅ Empty secret handled gracefully")
        return True
        
    except Exception as e:
        print(f"❌ ProxyManager crashed with empty secret: {e}")
        return False

def test_none_secret():
    """Test ProxyManager handles None secret"""
    print("Testing None secret...")
    
    try:
        proxy_manager = ProxyManager(None, logging.getLogger(__name__))
        
        assert not proxy_manager.in_use, "ProxyManager should not be in use with None secret"
        assert proxy_manager.secret is None, "Secret should be None"
        
        print("✅ None secret handled gracefully")
        return True
        
    except Exception as e:
        print(f"❌ ProxyManager crashed with None secret: {e}")
        return False

def test_valid_secret():
    """Test ProxyManager works correctly with valid secret"""
    print("Testing valid secret...")
    
    valid_secret = {
        "provider": "oxylabs",
        "host": "proxy.example.com", 
        "port": 8080,
        "username": "testuser",
        "password": "testpass",
        "protocol": "http"
    }
    
    try:
        proxy_manager = ProxyManager(valid_secret, logging.getLogger(__name__))
        
        assert proxy_manager.in_use, "ProxyManager should be in use with valid secret"
        assert proxy_manager.secret is not None, "Secret should not be None with valid schema"
        assert proxy_manager.secret.provider == "oxylabs", "Provider should be set correctly"
        
        # Should return proxy config
        proxies = proxy_manager.proxies_for("test_video")
        assert "http" in proxies, "Should return http proxy config"
        assert "https" in proxies, "Should return https proxy config"
        
        print("✅ Valid secret handled correctly")
        return True
        
    except Exception as e:
        print(f"❌ ProxyManager failed with valid secret: {e}")
        return False

def test_empty_field_values():
    """Test ProxyManager handles empty field values"""
    print("Testing empty field values...")
    
    secret_with_empty_values = {
        "provider": "",  # Empty provider
        "host": "proxy.example.com",
        "port": 8080,
        "username": "testuser", 
        "password": "testpass",
        "protocol": "http"
    }
    
    try:
        proxy_manager = ProxyManager(secret_with_empty_values, logging.getLogger(__name__))
        
        assert not proxy_manager.in_use, "ProxyManager should not be in use with empty field values"
        assert proxy_manager.secret is None, "Secret should be None with empty fields"
        
        print("✅ Empty field values handled gracefully")
        return True
        
    except Exception as e:
        print(f"❌ ProxyManager crashed with empty field values: {e}")
        return False

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    print("🧪 Testing ProxyManager resilience...")
    print()
    
    tests = [
        test_missing_provider_field,
        test_completely_empty_secret,
        test_none_secret,
        test_valid_secret,
        test_empty_field_values
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! ProxyManager is resilient to malformed secrets.")
        sys.exit(0)
    else:
        print("💥 Some tests failed. ProxyManager needs fixes.")
        sys.exit(1)