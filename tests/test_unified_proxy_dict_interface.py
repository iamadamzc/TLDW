#!/usr/bin/env python3
"""
Test script for Task 15: Unified Proxy Dictionary Interface

This script tests the enhanced proxy_dict_for method with error logging
and appropriate fallbacks for wrong formats.

Requirements tested:
- 15.1: proxy_dict_for("requests") returning {"http":..., "https":...}
- 15.2: proxy_dict_for("playwright") returning {"server":..., "username":..., "password":...}
- 15.3: Use current ProxySecret and session token generator
- 15.4: Add error logging for wrong formats
- 15.5: Add appropriate fallback for wrong formats
"""

import os
import sys
import logging
import json
from unittest.mock import Mock, patch

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from proxy_manager import ProxyManager, ProxySecret

def setup_logging():
    """Setup logging to capture log messages"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def create_test_proxy_manager():
    """Create a ProxyManager with test configuration"""
    test_secret = {
        "provider": "oxylabs",
        "host": "pr.oxylabs.io",
        "port": 10000,
        "username": "testuser",
        "password": "testpass123",
        "session_ttl_minutes": 10
    }
    
    logger = setup_logging()
    return ProxyManager(secret_dict=test_secret, logger=logger)

def test_requests_format():
    """Test 15.1: proxy_dict_for('requests') returns correct format"""
    print("🧪 Testing requests format...")
    
    pm = create_test_proxy_manager()
    result = pm.proxy_dict_for("requests")
    
    assert result is not None, "Should return proxy dict for requests"
    assert "http" in result, "Should contain http key"
    assert "https" in result, "Should contain https key"
    assert result["http"] == result["https"], "HTTP and HTTPS should be same URL"
    assert "testuser" in result["http"], "Should contain username"
    assert "testpass123" in result["http"], "Should contain password"
    
    print("✅ Requests format test passed")
    return result

def test_playwright_format():
    """Test 15.2: proxy_dict_for('playwright') returns correct format"""
    print("🧪 Testing playwright format...")
    
    pm = create_test_proxy_manager()
    result = pm.proxy_dict_for("playwright")
    
    assert result is not None, "Should return proxy dict for playwright"
    assert "server" in result, "Should contain server key"
    assert "username" in result, "Should contain username key"
    assert "password" in result, "Should contain password key"
    assert result["server"].startswith("http://"), "Server should be HTTP URL"
    assert "pr.oxylabs.io:10000" in result["server"], "Should contain host and port"
    assert "testuser" in result["username"], "Should contain session username"
    assert result["password"] == "testpass123", "Should contain raw password"
    
    print("✅ Playwright format test passed")
    return result

def test_unsupported_client_error_logging():
    """Test 15.4: Error logging for wrong formats"""
    print("🧪 Testing error logging for unsupported client...")
    
    # Capture log messages
    with patch('logging.Logger.log') as mock_log:
        pm = create_test_proxy_manager()
        result = pm.proxy_dict_for("unsupported_client")
        
        # Should fallback to requests format
        assert result is not None, "Should return fallback result"
        assert "http" in result, "Should fallback to requests format"
        
        # Check that error was logged
        error_logged = False
        fallback_logged = False
        for call in mock_log.call_args_list:
            args, kwargs = call
            if len(args) >= 2 and "Unsupported proxy client type" in str(args[1]):
                error_logged = True
            if len(args) >= 2 and "Falling back to requests format" in str(args[1]):
                fallback_logged = True
        
        assert error_logged, "Should log error for unsupported client type"
        assert fallback_logged, "Should log fallback action"
    
    print("✅ Error logging test passed")

def test_no_proxy_available():
    """Test behavior when no proxy is available"""
    print("🧪 Testing no proxy available scenario...")
    
    # Create ProxyManager without secret
    logger = setup_logging()
    pm = ProxyManager(secret_dict={}, logger=logger)
    
    result_requests = pm.proxy_dict_for("requests")
    result_playwright = pm.proxy_dict_for("playwright")
    
    assert result_requests is None, "Should return None when no proxy available for requests"
    assert result_playwright is None, "Should return None when no proxy available for playwright"
    
    print("✅ No proxy available test passed")

def test_proxy_url_parsing_error():
    """Test 15.5: Appropriate fallback for parsing errors"""
    print("🧪 Testing proxy URL parsing error handling...")
    
    pm = create_test_proxy_manager()
    
    # Mock proxy_url to return None (simulating URL generation failure)
    with patch.object(pm, 'proxy_url', return_value=None):
        result = pm.proxy_dict_for("playwright")
        # Should return None when proxy_url returns None
        assert result is None, "Should return None when proxy URL is None"
    
    # Test with malformed URL that causes urlparse to fail
    with patch.object(pm, 'proxy_url', return_value="not-a-url"):
        # Mock urlparse to raise an exception
        with patch('urllib.parse.urlparse', side_effect=Exception("Parse error")):
            result = pm.proxy_dict_for("playwright")
            # Should return None for playwright parsing errors
            assert result is None, "Should return None for playwright parsing errors"
    
    print("✅ Parsing error handling test passed")

def test_session_token_generation():
    """Test 15.3: Uses current ProxySecret and session token generator"""
    print("🧪 Testing session token generation...")
    
    pm = create_test_proxy_manager()
    
    # Get multiple proxy dicts to verify session tokens are generated
    result1 = pm.proxy_dict_for("requests")
    result2 = pm.proxy_dict_for("requests")
    
    # URLs should be different due to different session tokens
    assert result1["http"] != result2["http"], "Should generate different session tokens"
    
    # Both should contain session identifiers
    assert "-sessid-" in result1["http"], "Should contain session identifier"
    assert "-sessid-" in result2["http"], "Should contain session identifier"
    
    print("✅ Session token generation test passed")

def test_sticky_session_parameter():
    """Test sticky session parameter functionality"""
    print("🧪 Testing sticky session parameter...")
    
    pm = create_test_proxy_manager()
    
    # Test with sticky=True (default)
    result_sticky = pm.proxy_dict_for("requests", sticky=True)
    
    # Test with sticky=False
    result_non_sticky = pm.proxy_dict_for("requests", sticky=False)
    
    # Both should work (implementation detail may vary)
    assert result_sticky is not None, "Sticky session should work"
    assert result_non_sticky is not None, "Non-sticky session should work"
    
    print("✅ Sticky session parameter test passed")

def main():
    """Run all tests"""
    print("🚀 Starting Task 15: Unified Proxy Dictionary Interface Tests")
    print("=" * 60)
    
    try:
        # Test core functionality
        test_requests_format()
        test_playwright_format()
        
        # Test error handling and fallbacks
        test_unsupported_client_error_logging()
        test_no_proxy_available()
        test_proxy_url_parsing_error()
        
        # Test ProxySecret and session token usage
        test_session_token_generation()
        test_sticky_session_parameter()
        
        print("=" * 60)
        print("✅ All Task 15 tests passed!")
        print("\nRequirements verified:")
        print("✅ 15.1: proxy_dict_for('requests') returns {'http':..., 'https':...}")
        print("✅ 15.2: proxy_dict_for('playwright') returns {'server':..., 'username':..., 'password':...}")
        print("✅ 15.3: Uses current ProxySecret and session token generator")
        print("✅ 15.4: Adds error logging for wrong formats")
        print("✅ 15.5: Adds appropriate fallback for wrong formats")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)