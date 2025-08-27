#!/usr/bin/env python3
"""
Integration test for Task 15: Unified Proxy Dictionary Interface

This script tests the integration of the enhanced proxy_dict_for method
with the transcript service and other components that use proxy configuration.
"""

import os
import sys
import logging
from unittest.mock import Mock, patch

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from proxy_manager import ProxyManager

def setup_logging():
    """Setup logging to capture integration test messages"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def test_transcript_service_integration():
    """Test integration with transcript service proxy usage patterns"""
    print("🧪 Testing transcript service integration...")
    
    # Create ProxyManager with test configuration
    test_secret = {
        "provider": "oxylabs",
        "host": "pr.oxylabs.io", 
        "port": 10000,
        "username": "testuser",
        "password": "testpass123"
    }
    
    logger = setup_logging()
    pm = ProxyManager(secret_dict=test_secret, logger=logger)
    
    # Test requests format for HTTP client usage
    requests_proxies = pm.proxy_dict_for("requests")
    assert requests_proxies is not None, "Should return requests proxy config"
    assert isinstance(requests_proxies, dict), "Should return dict"
    assert "http" in requests_proxies and "https" in requests_proxies, "Should have both protocols"
    
    # Test playwright format for browser automation
    playwright_proxies = pm.proxy_dict_for("playwright")
    assert playwright_proxies is not None, "Should return playwright proxy config"
    assert isinstance(playwright_proxies, dict), "Should return dict"
    assert all(k in playwright_proxies for k in ["server", "username", "password"]), "Should have all required keys"
    
    print("✅ Transcript service integration test passed")

def test_error_handling_integration():
    """Test error handling in realistic scenarios"""
    print("🧪 Testing error handling integration...")
    
    logger = setup_logging()
    
    # Test with invalid client type (common mistake)
    pm = ProxyManager(secret_dict={
        "provider": "oxylabs",
        "host": "pr.oxylabs.io",
        "port": 10000,
        "username": "testuser", 
        "password": "testpass123"
    }, logger=logger)
    
    # Test typo in client name - should fallback gracefully
    result = pm.proxy_dict_for("request")  # Missing 's'
    assert result is not None, "Should fallback for typo"
    assert "http" in result, "Should fallback to requests format"
    
    # Test completely wrong client name
    result = pm.proxy_dict_for("selenium")
    assert result is not None, "Should fallback for unknown client"
    assert "http" in result, "Should fallback to requests format"
    
    print("✅ Error handling integration test passed")

def test_backward_compatibility():
    """Test that existing code patterns still work"""
    print("🧪 Testing backward compatibility...")
    
    test_secret = {
        "provider": "oxylabs",
        "host": "pr.oxylabs.io",
        "port": 10000,
        "username": "testuser",
        "password": "testpass123"
    }
    
    logger = setup_logging()
    pm = ProxyManager(secret_dict=test_secret, logger=logger)
    
    # Test existing method calls still work
    requests_result = pm.proxy_dict_for("requests")
    playwright_result = pm.proxy_dict_for("playwright")
    
    # Test with sticky parameter (existing usage)
    sticky_result = pm.proxy_dict_for("requests", sticky=True)
    non_sticky_result = pm.proxy_dict_for("requests", sticky=False)
    
    assert all(r is not None for r in [requests_result, playwright_result, sticky_result, non_sticky_result]), \
        "All existing usage patterns should work"
    
    print("✅ Backward compatibility test passed")

def test_no_proxy_configuration():
    """Test behavior when no proxy is configured (common in development)"""
    print("🧪 Testing no proxy configuration...")
    
    logger = setup_logging()
    
    # Test with empty configuration
    pm = ProxyManager(secret_dict={}, logger=logger)
    
    requests_result = pm.proxy_dict_for("requests")
    playwright_result = pm.proxy_dict_for("playwright")
    
    assert requests_result is None, "Should return None when no proxy configured"
    assert playwright_result is None, "Should return None when no proxy configured"
    
    print("✅ No proxy configuration test passed")

def test_logging_output():
    """Test that appropriate logging messages are generated"""
    print("🧪 Testing logging output...")
    
    test_secret = {
        "provider": "oxylabs",
        "host": "pr.oxylabs.io",
        "port": 10000,
        "username": "testuser",
        "password": "testpass123"
    }
    
    # Capture log messages
    with patch('logging.Logger.log') as mock_log:
        logger = setup_logging()
        pm = ProxyManager(secret_dict=test_secret, logger=logger)
        
        # Test normal operation
        pm.proxy_dict_for("requests")
        pm.proxy_dict_for("playwright")
        
        # Test error case
        pm.proxy_dict_for("invalid_client")
        
        # Verify appropriate log messages were generated
        log_messages = [str(call) for call in mock_log.call_args_list]
        
        # Should have debug messages for successful operations
        debug_logged = any("Generated" in msg and "proxy dict" in msg for msg in log_messages)
        assert debug_logged, "Should log debug messages for successful operations"
        
        # Should have error message for invalid client
        error_logged = any("Unsupported proxy client type" in msg for msg in log_messages)
        assert error_logged, "Should log error for unsupported client type"
    
    print("✅ Logging output test passed")

def main():
    """Run all integration tests"""
    print("🚀 Starting Task 15 Integration Tests")
    print("=" * 50)
    
    try:
        test_transcript_service_integration()
        test_error_handling_integration()
        test_backward_compatibility()
        test_no_proxy_configuration()
        test_logging_output()
        
        print("=" * 50)
        print("✅ All Task 15 integration tests passed!")
        print("\nIntegration aspects verified:")
        print("✅ Works with transcript service usage patterns")
        print("✅ Handles errors gracefully in realistic scenarios")
        print("✅ Maintains backward compatibility")
        print("✅ Handles missing proxy configuration correctly")
        print("✅ Generates appropriate logging output")
        
        return True
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)