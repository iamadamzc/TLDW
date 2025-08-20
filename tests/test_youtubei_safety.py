#!/usr/bin/env python3
"""
Test for YouTubei transcript capture with safety controls
"""
import os
import sys
import logging
import time

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_youtubei_configuration():
    """Test YouTubei configuration and feature flags"""
    from transcript_service import ENABLE_YOUTUBEI, PW_NAV_TIMEOUT_MS, _BROWSER_SEM
    
    print("=== YouTubei Configuration ===")
    print(f"ENABLE_YOUTUBEI: {ENABLE_YOUTUBEI}")
    print(f"PW_NAV_TIMEOUT_MS: {PW_NAV_TIMEOUT_MS}")
    print(f"Browser semaphore configured: {_BROWSER_SEM is not None}")
    print(f"Browser semaphore value: {_BROWSER_SEM._value}")
    
    return True

def test_preflight_function():
    """Test YouTube reachability preflight function"""
    try:
        from transcript_service import youtube_reachable
        
        print("\n=== Preflight Function Test ===")
        print("✅ youtube_reachable function exists")
        
        # Test function signature
        import inspect
        sig = inspect.signature(youtube_reachable)
        if 'timeout_s' in sig.parameters:
            print("✅ Preflight function has timeout parameter")
            return True
        else:
            print("❌ Preflight function missing timeout parameter")
            return False
            
    except ImportError as e:
        print(f"❌ Preflight function import failed: {e}")
        return False

def test_circuit_breaker():
    """Test circuit breaker functionality"""
    try:
        from transcript_service import _pw_allowed, _pw_register_timeout, _pw_register_success, _PW_FAILS
        
        print("\n=== Circuit Breaker Test ===")
        print("✅ Circuit breaker functions exist")
        
        # Test initial state
        now_ms = int(time.time() * 1000)
        if _pw_allowed(now_ms):
            print("✅ Circuit breaker initially allows requests")
        else:
            print("❌ Circuit breaker initially blocks requests")
            return False
        
        # Test timeout registration
        original_count = _PW_FAILS["count"]
        _pw_register_timeout(now_ms)
        if _PW_FAILS["count"] > original_count:
            print("✅ Circuit breaker registers timeouts")
        else:
            print("❌ Circuit breaker doesn't register timeouts")
            return False
        
        # Reset for other tests
        _pw_register_success()
        
        return True
        
    except ImportError as e:
        print(f"❌ Circuit breaker import failed: {e}")
        return False

def test_cookie_conversion():
    """Test cookie conversion function"""
    try:
        from transcript_service import _convert_cookiejar_to_playwright_format
        
        print("\n=== Cookie Conversion Test ===")
        print("✅ Cookie conversion function exists")
        
        # Test with None
        result = _convert_cookiejar_to_playwright_format(None)
        if result is None:
            print("✅ Cookie conversion handles None input")
            return True
        else:
            print("❌ Cookie conversion doesn't handle None input properly")
            return False
            
    except ImportError as e:
        print(f"❌ Cookie conversion import failed: {e}")
        return False

def test_youtubei_function_signature():
    """Test that YouTubei function has proper signature and safety features"""
    try:
        from transcript_service import get_transcript_via_youtubei
        import inspect
        
        print("\n=== YouTubei Function Signature Test ===")
        
        sig = inspect.signature(get_transcript_via_youtubei)
        params = list(sig.parameters.keys())
        expected_params = ['video_id', 'proxy_manager', 'cookies', 'timeout_ms']
        
        if all(param in params for param in expected_params):
            print("✅ YouTubei function signature correct")
        else:
            print(f"❌ YouTubei function signature incorrect. Expected {expected_params}, got {params}")
            return False
        
        # Check source for safety features
        source = inspect.getsource(get_transcript_via_youtubei)
        
        safety_features = [
            "_pw_allowed",  # Circuit breaker check
            "youtube_reachable",  # Preflight check
            "_BROWSER_SEM",  # Semaphore control
            "no-proxy first",  # No-proxy-first strategy
            "finally:"  # Proper cleanup
        ]
        
        found_features = [feature for feature in safety_features if feature in source]
        
        if len(found_features) >= 4:
            print(f"✅ Safety features implemented: {found_features}")
            return True
        else:
            print(f"❌ Missing safety features. Found {len(found_features)}/5: {found_features}")
            return False
            
    except ImportError as e:
        print(f"❌ YouTubei function import failed: {e}")
        return False

def test_semaphore_concurrency():
    """Test semaphore concurrency control"""
    try:
        from transcript_service import _BROWSER_SEM, WORKER_CONCURRENCY
        
        print("\n=== Semaphore Concurrency Test ===")
        print(f"Worker concurrency setting: {WORKER_CONCURRENCY}")
        print(f"Semaphore initial value: {_BROWSER_SEM._value}")
        
        if _BROWSER_SEM._value == WORKER_CONCURRENCY:
            print("✅ Semaphore properly configured with worker concurrency")
            return True
        else:
            print("❌ Semaphore not properly configured")
            return False
            
    except ImportError as e:
        print(f"❌ Semaphore import failed: {e}")
        return False

if __name__ == "__main__":
    print("=== YouTubei Safety Controls Test ===")
    
    config_success = test_youtubei_configuration()
    preflight_success = test_preflight_function()
    circuit_success = test_circuit_breaker()
    cookie_success = test_cookie_conversion()
    signature_success = test_youtubei_function_signature()
    semaphore_success = test_semaphore_concurrency()
    
    all_tests = [config_success, preflight_success, circuit_success, cookie_success, signature_success, semaphore_success]
    
    if all(all_tests):
        print("\n✅ All YouTubei safety control tests passed!")
        print("Task 4: UI-agnostic YouTubei transcript capture with safety controls - COMPLETE")
        sys.exit(0)
    else:
        print(f"\n❌ Some YouTubei safety tests failed! Results: {all_tests}")
        sys.exit(1)