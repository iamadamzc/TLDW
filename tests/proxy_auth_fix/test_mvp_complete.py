#!/usr/bin/env python3
"""
Complete MVP test suite for Oxylabs proxy auth fix
Tests all critical components and validates secret hygiene
"""

import sys
import os
import json
import subprocess
from unittest.mock import patch, MagicMock

# Set up test environment with RAW secret format
os.environ["OXYLABS_PROXY_CONFIG"] = json.dumps({
    "provider": "oxylabs",
    "host": "pr.oxylabs.io", 
    "port": 7777,
    "username": "customer-test123",
    "password": "myRawPassword123!",
    "geo_enabled": False,
    "country": "us",
    "version": 1
})
os.environ["DEEPGRAM_API_KEY"] = "test_api_key"

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_secret_validation_rejects_malformed():
    """Test that secret validation rejects malformed secrets"""
    print("Testing secret validation rejects malformed secrets...")
    
    from proxy_manager import ProxySecret, ProxyValidationError
    
    # Test 1: Pre-encoded password
    malformed_secret = {
        "provider": "oxylabs",
        "host": "pr.oxylabs.io",
        "port": 7777,
        "username": "customer-test123",
        "password": "myRawPassword123%21",  # ! encoded as %21
        "geo_enabled": False
    }
    
    try:
        ProxySecret.from_dict(malformed_secret)
        print("❌ Pre-encoded password was accepted (should be rejected)")
        return False
    except ProxyValidationError as e:
        if "password_looks_urlencoded" in str(e):
            print("✅ Pre-encoded password correctly rejected")
        else:
            print(f"❌ Wrong error for pre-encoded password: {e}")
            return False
    
    # Test 2: Host with scheme
    malformed_secret["password"] = "myRawPassword123!"  # Fix password
    malformed_secret["host"] = "https://pr.oxylabs.io"  # Add scheme
    
    try:
        ProxySecret.from_dict(malformed_secret)
        print("❌ Host with scheme was accepted (should be rejected)")
        return False
    except ProxyValidationError as e:
        if "host_contains_scheme" in str(e):
            print("✅ Host with scheme correctly rejected")
        else:
            print(f"❌ Wrong error for host with scheme: {e}")
            return False
    
    # Test 3: Missing required field
    del malformed_secret["password"]
    malformed_secret["host"] = "pr.oxylabs.io"  # Fix host
    
    try:
        ProxySecret.from_dict(malformed_secret)
        print("❌ Missing password was accepted (should be rejected)")
        return False
    except ProxyValidationError as e:
        if "missing_password" in str(e):
            print("✅ Missing password correctly rejected")
        else:
            print(f"❌ Wrong error for missing password: {e}")
            return False
    
    return True

def test_preflight_fail_fast():
    """Test that preflight validation fails fast on auth errors"""
    print("\nTesting preflight fail-fast behavior...")
    
    from transcript_service import TranscriptService
    
    # Create service with fresh proxy manager
    service = TranscriptService()
    
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 407
        mock_get.return_value = mock_response
        
        with patch.object(service, 'cache') as mock_cache:
            mock_cache.get.return_value = None  # No cache hit
            
            # Mock ASR to ensure it's not called
            with patch.object(service, '_transcribe_audio_with_proxy') as mock_asr:
                mock_asr.return_value = None
                
                result = service.get_transcript("test_video_fail_fast", has_captions=True)
                
                # Should return error response, not call ASR
                if isinstance(result, tuple) and len(result) == 2:
                    response_body, status_code = result
                    if (status_code == 502 and 
                        response_body.get("code") == "PROXY_AUTH_FAILED"):
                        print("✅ Preflight fail-fast working - returns 502 immediately")
                        
                        # Verify ASR was NOT called
                        if not mock_asr.called:
                            print("✅ ASR not attempted after preflight failure")
                            return True
                        else:
                            print("❌ ASR was called despite preflight failure")
                            return False
                    else:
                        print(f"❌ Wrong error response: {result}")
                        return False
                else:
                    print(f"❌ Expected error response, got: {result}")
                    return False

def test_session_rotation():
    """Test that session rotation works correctly"""
    print("\nTesting session rotation...")
    
    from proxy_manager import ProxyManager
    import logging
    
    # Create proxy manager
    secret_data = json.loads(os.environ["OXYLABS_PROXY_CONFIG"])
    pm = ProxyManager(secret_data, logging.getLogger(__name__))
    
    # Generate initial session
    proxies1 = pm.proxies_for("test_video_rotation")
    session1 = proxies1["https"].split("-sessid-")[1].split(":")[0]
    
    # Rotate session
    pm.rotate_session(session1)
    
    # Generate new session
    proxies2 = pm.proxies_for("test_video_rotation")
    session2 = proxies2["https"].split("-sessid-")[1].split(":")[0]
    
    # Sessions should be different
    if session1 != session2:
        print(f"✅ Session rotation working: {session1[:8]}... → {session2[:8]}...")
        
        # Verify old session is blacklisted
        if session1 in pm.session_blacklist:
            print("✅ Old session correctly blacklisted")
            return True
        else:
            print("❌ Old session not blacklisted")
            return False
    else:
        print(f"❌ Session not rotated: {session1} == {session2}")
        return False

def test_health_endpoints():
    """Test health endpoints return correct status codes"""
    print("\nTesting health endpoints...")
    
    from app import app
    
    with app.test_client() as client:
        # Test /health/live
        response = client.get('/health/live')
        if response.status_code == 200:
            data = response.get_json()
            if data.get("status") == "ok":
                print("✅ /health/live endpoint working")
            else:
                print(f"❌ /health/live wrong response: {data}")
                return False
        else:
            print(f"❌ /health/live returned {response.status_code}")
            return False
        
        # Test /health/ready with mocked success
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 204
            mock_get.return_value = mock_response
            
            response = client.get('/health/ready')
            if response.status_code == 200:
                data = response.get_json()
                if data.get("proxy_healthy") is True:
                    print("✅ /health/ready endpoint working")
                    return True
                else:
                    print(f"❌ /health/ready wrong response: {data}")
                    return False
            else:
                print(f"❌ /health/ready returned {response.status_code}")
                return False

def test_structured_logging():
    """Test that structured logging doesn't crash with unknown fields"""
    print("\nTesting structured logging safety...")
    
    from proxy_manager import SafeStructuredLogger
    import logging
    
    # Create logger
    base_logger = logging.getLogger("test_logger")
    safe_logger = SafeStructuredLogger(base_logger)
    
    # Test with unknown fields
    try:
        safe_logger.log_event("info", "Test message", 
                            component="test", 
                            unknown_field="should_be_ignored",
                            password="should_be_stripped",
                            correlation_id="test-123")
        print("✅ Structured logging handles unknown fields safely")
        return True
    except Exception as e:
        print(f"❌ Structured logging crashed: {e}")
        return False

def test_error_response_format():
    """Test standardized error response format"""
    print("\nTesting error response format...")
    
    from proxy_manager import error_response
    
    # Test error response
    response_body, status_code = error_response("PROXY_AUTH_FAILED", "test-correlation-123")
    
    required_fields = ["code", "message", "correlation_id", "timestamp", "details"]
    if all(field in response_body for field in required_fields):
        if (status_code == 502 and 
            response_body["code"] == "PROXY_AUTH_FAILED" and
            response_body["correlation_id"] == "test-correlation-123"):
            print("✅ Error response format correct")
            return True
        else:
            print(f"❌ Error response content wrong: {response_body}, status: {status_code}")
            return False
    else:
        print(f"❌ Error response missing fields: {response_body}")
        return False

def run_all_mvp_tests():
    """Run all MVP tests"""
    print("🚀 Running complete MVP test suite for Oxylabs proxy auth fix...")
    print("=" * 60)
    
    tests = [
        ("Secret Validation", test_secret_validation_rejects_malformed),
        ("Preflight Fail-Fast", test_preflight_fail_fast),
        ("Session Rotation", test_session_rotation),
        ("Health Endpoints", test_health_endpoints),
        ("Structured Logging", test_structured_logging),
        ("Error Response Format", test_error_response_format),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 40)
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                failed += 1
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            failed += 1
            print(f"❌ {test_name} FAILED with exception: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 MVP Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 ALL MVP TESTS PASSED! Ready for deployment.")
        print("\n📋 MVP Features Validated:")
        print("  ✅ Strict RAW secret validation (rejects pre-encoded passwords)")
        print("  ✅ Preflight fail-fast (502 on auth failure, no transcript/yt-dlp attempts)")
        print("  ✅ Session rotation (never reuse failed sessions)")
        print("  ✅ Safe structured logging (never crashes pipeline)")
        print("  ✅ Health endpoints (/health/live and /health/ready)")
        print("  ✅ Standardized error responses with correlation IDs")
        print("\n🚀 The 'whack-a-mole' 407 errors should now be eliminated!")
        return True
    else:
        print("❌ Some MVP tests failed. Fix issues before deployment.")
        return False

if __name__ == "__main__":
    success = run_all_mvp_tests()
    sys.exit(0 if success else 1)