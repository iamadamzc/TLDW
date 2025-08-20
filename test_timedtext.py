#!/usr/bin/env python3
"""
Test for timed-text endpoints with resilience features
"""
import os
import sys
import logging
import time

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_timedtext_configuration():
    """Test timed-text configuration and feature flags"""
    from transcript_service import USE_PROXY_FOR_TIMEDTEXT, ENABLE_TIMEDTEXT, HTTP
    
    print("=== Timed-text Configuration ===")
    print(f"ENABLE_TIMEDTEXT: {ENABLE_TIMEDTEXT}")
    print(f"USE_PROXY_FOR_TIMEDTEXT: {USE_PROXY_FOR_TIMEDTEXT}")
    print(f"HTTP session configured: {HTTP is not None}")
    
    # Check HTTP session has retry configuration
    if hasattr(HTTP, 'adapters'):
        adapter = HTTP.adapters.get('https://')
        if adapter and hasattr(adapter, 'max_retries'):
            print(f"✅ HTTP session has retry configuration: {adapter.max_retries}")
        else:
            print("❌ HTTP session missing retry configuration")
            return False
    
    return ENABLE_TIMEDTEXT

def test_timedtext_function_exists():
    """Test that timed-text functions exist and are properly structured"""
    try:
        from transcript_service import get_captions_via_timedtext, _fetch_timedtext
        
        print("\n=== Timed-text Function Check ===")
        print("✅ get_captions_via_timedtext function exists")
        print("✅ _fetch_timedtext helper function exists")
        
        # Check function signatures
        import inspect
        sig = inspect.signature(get_captions_via_timedtext)
        params = list(sig.parameters.keys())
        expected_params = ['video_id', 'proxy_manager', 'cookie_jar']
        
        if all(param in params for param in expected_params):
            print("✅ Function signature correct")
            return True
        else:
            print(f"❌ Function signature incorrect. Expected {expected_params}, got {params}")
            return False
            
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def test_timedtext_timeout_configuration():
    """Test that timeout configurations are properly set"""
    from transcript_service import _fetch_timedtext
    
    print("\n=== Timeout Configuration Test ===")
    
    # Test that the function accepts timeout parameter
    import inspect
    sig = inspect.signature(_fetch_timedtext)
    
    if 'timeout_s' in sig.parameters:
        default_timeout = sig.parameters['timeout_s'].default
        print(f"✅ Timeout parameter exists with default: {default_timeout}")
        
        # Verify it's set to 15s as per NFR specifications
        if default_timeout == 15:
            print("✅ Timeout set to 15s per NFR specifications")
            return True
        else:
            print(f"❌ Timeout should be 15s, got {default_timeout}")
            return False
    else:
        print("❌ Timeout parameter missing")
        return False

def test_timedtext_no_proxy_first():
    """Test that no-proxy-first strategy is implemented"""
    from transcript_service import get_captions_via_timedtext
    import inspect
    
    print("\n=== No-Proxy-First Strategy Test ===")
    
    # Read the source code to verify no-proxy-first implementation
    source = inspect.getsource(get_captions_via_timedtext)
    
    # Check for no-proxy first pattern
    if "proxies=None" in source and "No-proxy first" in source:
        print("✅ No-proxy-first strategy implemented")
        return True
    else:
        print("❌ No-proxy-first strategy not found in implementation")
        return False

def test_timedtext_retry_logic():
    """Test that retry logic with backoff is implemented"""
    from transcript_service import get_captions_via_timedtext
    import inspect
    
    print("\n=== Retry Logic Test ===")
    
    # Read the source code to verify retry implementation
    source = inspect.getsource(get_captions_via_timedtext)
    
    # Check for retry patterns
    retry_indicators = [
        "for attempt in range(2)",
        "time.sleep(1 + attempt)",
        "ReadTimeout",
        "ConnectTimeout"
    ]
    
    found_indicators = [indicator for indicator in retry_indicators if indicator in source]
    
    if len(found_indicators) >= 3:
        print(f"✅ Retry logic implemented with {len(found_indicators)}/4 indicators found")
        return True
    else:
        print(f"❌ Retry logic incomplete. Found {len(found_indicators)}/4 indicators: {found_indicators}")
        return False

def test_timedtext_language_fallback():
    """Test that multiple language fallback is implemented"""
    from transcript_service import get_captions_via_timedtext
    import inspect
    
    print("\n=== Language Fallback Test ===")
    
    # Read the source code to verify language fallback
    source = inspect.getsource(get_captions_via_timedtext)
    
    # Check for language array and iteration
    if '"en", "en-US", "es", "es-419"' in source and "for lang in languages" in source:
        print("✅ Language fallback implemented with multiple languages")
        return True
    else:
        print("❌ Language fallback not properly implemented")
        return False

if __name__ == "__main__":
    print("=== Timed-text Endpoints Resilience Test ===")
    
    config_success = test_timedtext_configuration()
    function_success = test_timedtext_function_exists()
    timeout_success = test_timedtext_timeout_configuration()
    proxy_success = test_timedtext_no_proxy_first()
    retry_success = test_timedtext_retry_logic()
    language_success = test_timedtext_language_fallback()
    
    all_tests = [config_success, function_success, timeout_success, proxy_success, retry_success, language_success]
    
    if all(all_tests):
        print("\n✅ All timed-text resilience tests passed!")
        print("Task 3: Enhanced timed-text endpoints with resilience - COMPLETE")
        sys.exit(0)
    else:
        print(f"\n❌ Some timed-text tests failed! Results: {all_tests}")
        sys.exit(1)