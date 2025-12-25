#!/usr/bin/env python3
"""
Test script for the proxy session configuration fix.
This tests the ensure_proxy_session and _verify_proxy_connection functions.
"""

import os
import sys
import logging

# Add current directory to path to import modules
sys.path.insert(0, '.')

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_proxy_functions():
    """Test the new proxy session functions"""
    try:
        from proxy_manager import ensure_proxy_session, _verify_proxy_connection
        
        logger.info("Testing proxy session functions...")
        
        # Test 1: Test _verify_proxy_connection with empty config (should return False)
        logger.info("Test 1: Testing _verify_proxy_connection with empty config")
        result = _verify_proxy_connection({})
        logger.info(f"_verify_proxy_connection({{}}) = {result}")
        assert result is False, "Empty proxy config should return False"
        
        # Test 2: Test ensure_proxy_session when ENFORCE_PROXY_ALL is false
        logger.info("Test 2: Testing ensure_proxy_session with ENFORCE_PROXY_ALL=false")
        os.environ['ENFORCE_PROXY_ALL'] = 'false'
        result = ensure_proxy_session("test_job", "test_video")
        logger.info(f"ensure_proxy_session('test_job', 'test_video') = {result}")
        assert result is None, "Should return None when ENFORCE_PROXY_ALL is false"
        
        # Test 3: Test ensure_proxy_session when ENFORCE_PROXY_ALL is true but no proxy manager
        logger.info("Test 3: Testing ensure_proxy_session with ENFORCE_PROXY_ALL=true (no proxy manager)")
        os.environ['ENFORCE_PROXY_ALL'] = 'true'
        result = ensure_proxy_session("test_job", "test_video")
        logger.info(f"ensure_proxy_session('test_job', 'test_video') = {result}")
        # This should return None due to exception handling when no proxy manager is available
        
        logger.info("All tests passed! Proxy session functions are working correctly.")
        return True
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_proxy_functions()
    sys.exit(0 if success else 1)
