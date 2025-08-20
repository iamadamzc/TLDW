#!/usr/bin/env python3
"""
Test for security enhancements including cookie encryption and credential protection
"""
import os
import sys
import logging
import json
import tempfile
from datetime import datetime, timedelta

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_secure_cookie_manager():
    """Test SecureCookieManager functionality"""
    print("=== SecureCookieManager Test ===")
    
    try:
        from security_manager import SecureCookieManager
        
        # Create temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["SECURE_COOKIES_DIR"] = temp_dir
            
            manager = SecureCookieManager()
            
            # Test cookie storage
            test_cookies = {"session_id": "test123", "auth_token": "token456"}
            result = manager.store_cookies(1, test_cookies, "test")
            
            if result:
                print("✅ Cookie storage works")
            else:
                print("❌ Cookie storage failed")
                return False
            
            # Test cookie retrieval
            retrieved = manager.retrieve_cookies(1)
            
            if retrieved and retrieved.get("cookies") == test_cookies:
                print("✅ Cookie retrieval works")
            else:
                print(f"❌ Cookie retrieval failed: {retrieved}")
                return False
            
            # Test cookie status
            status = manager.get_cookie_status(1)
            
            if status.get("has_cookies") and status.get("status") == "active":
                print("✅ Cookie status works")
            else:
                print(f"❌ Cookie status failed: {status}")
                return False
            
            # Test cookie deletion
            delete_result = manager.delete_cookies(1)
            
            if delete_result:
                print("✅ Cookie deletion works")
            else:
                print("❌ Cookie deletion failed")
                return False
            
            # Verify deletion
            status_after_delete = manager.get_cookie_status(1)
            
            if not status_after_delete.get("has_cookies"):
                print("✅ Cookie deletion verified")
            else:
                print("❌ Cookie deletion not verified")
                return False
            
            return True
        
    except Exception as e:
        print(f"❌ SecureCookieManager test failed: {e}")
        return False

def test_cookie_encryption():
    """Test cookie encryption and decryption"""
    print("\n=== Cookie Encryption Test ===")
    
    try:
        from security_manager import SecureCookieManager
        
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["SECURE_COOKIES_DIR"] = temp_dir
            
            manager = SecureCookieManager()
            
            # Store sensitive cookie data
            sensitive_cookies = {
                "auth_token": "very-secret-token-12345",
                "session_data": {"user_id": 123, "permissions": ["read", "write"]}
            }
            
            # Store cookies
            manager.store_cookies(1, sensitive_cookies, "test")
            
            # Read raw storage file to verify encryption
            storage_path = manager._get_cookie_storage_path(1)
            with open(storage_path, 'r') as f:
                raw_data = json.load(f)
            
            # Verify sensitive data is not in plain text
            raw_content = json.dumps(raw_data)
            if "very-secret-token-12345" not in raw_content:
                print("✅ Cookie data is encrypted in storage")
            else:
                print("❌ Cookie data not encrypted in storage")
                return False
            
            # Verify metadata is present
            if "metadata" in raw_data and "encrypted_cookies" in raw_data:
                print("✅ Cookie storage structure correct")
            else:
                print("❌ Cookie storage structure incorrect")
                return False
            
            return True
        
    except Exception as e:
        print(f"❌ Cookie encryption test failed: {e}")
        return False

def test_ttl_enforcement():
    """Test TTL enforcement for cookies"""
    print("\n=== TTL Enforcement Test ===")
    
    try:
        from security_manager import SecureCookieManager
        
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["SECURE_COOKIES_DIR"] = temp_dir
            os.environ["COOKIE_TTL_HOURS"] = "1"  # 1 hour for testing
            
            manager = SecureCookieManager()
            
            # Store cookies
            test_cookies = {"test": "data"}
            manager.store_cookies(1, test_cookies, "test")
            
            # Verify cookies are active
            status = manager.get_cookie_status(1)
            if status.get("status") == "active":
                print("✅ Fresh cookies are active")
            else:
                print(f"❌ Fresh cookies not active: {status}")
                return False
            
            # Manually expire cookies by modifying storage
            storage_path = manager._get_cookie_storage_path(1)
            with open(storage_path, 'r') as f:
                storage_data = json.load(f)
            
            # Set expiration to past
            past_time = (datetime.utcnow() - timedelta(hours=2)).isoformat()
            storage_data["metadata"]["expires_at"] = past_time
            
            with open(storage_path, 'w') as f:
                json.dump(storage_data, f)
            
            # Try to retrieve expired cookies
            retrieved = manager.retrieve_cookies(1)
            
            if retrieved is None:
                print("✅ Expired cookies properly rejected")
            else:
                print(f"❌ Expired cookies not rejected: {retrieved}")
                return False
            
            # Verify cleanup occurred
            if not os.path.exists(storage_path):
                print("✅ Expired cookies automatically cleaned up")
            else:
                print("❌ Expired cookies not cleaned up")
                return False
            
            return True
        
    except Exception as e:
        print(f"❌ TTL enforcement test failed: {e}")
        return False

def test_credential_protection():
    """Test credential protection and redaction"""
    print("\n=== Credential Protection Test ===")
    
    try:
        from security_manager import CredentialProtector
        
        protector = CredentialProtector()
        
        # Test API key validation
        test_cases = [
            ("openai", "sk-1234567890123456789012345678901234567890123456", True),
            ("openai", "invalid-key", False),
            ("resend", "re_123456789012345678901234", True),
            ("resend", "invalid", False),
            ("deepgram", "a" * 32, True),
            ("deepgram", "short", False),
        ]
        
        for key_type, api_key, should_be_valid in test_cases:
            is_valid, message = protector.validate_api_key_format(key_type, api_key)
            if is_valid == should_be_valid:
                print(f"✅ API key validation for {key_type}: {is_valid}")
            else:
                print(f"❌ API key validation for {key_type} failed: expected {should_be_valid}, got {is_valid}")
                return False
        
        # Test sensitive data redaction
        sensitive_text = "The API key is sk-1234567890123456789012345678901234567890123456 and password=secret123"
        redacted = protector.redact_sensitive_data(sensitive_text)
        
        if "sk-1234567890123456789012345678901234567890123456" not in redacted:
            print("✅ API key redaction works")
        else:
            print("❌ API key not redacted")
            return False
        
        if "password=secret123" not in redacted:
            print("✅ Password redaction works")
        else:
            print("❌ Password not redacted")
            return False
        
        # Test environment security check
        security_check = protector.secure_environment_check()
        
        if isinstance(security_check, dict) and "overall_status" in security_check:
            print("✅ Environment security check works")
        else:
            print(f"❌ Environment security check failed: {security_check}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Credential protection test failed: {e}")
        return False

def test_log_redaction():
    """Test log redaction functionality"""
    print("\n=== Log Redaction Test ===")
    
    try:
        from security_manager import LogRedactor
        
        redactor = LogRedactor()
        
        # Test log message redaction
        sensitive_log = "Processing with API key sk-1234567890123456789012345678901234567890123456"
        redacted_log = redactor.redact_log_message(sensitive_log)
        
        if "sk-1234567890123456789012345678901234567890123456" not in redacted_log:
            print("✅ Log message redaction works")
        else:
            print("❌ Log message not redacted")
            return False
        
        # Test logging filter creation
        log_filter = redactor.create_safe_logging_filter()
        
        if log_filter and hasattr(log_filter, 'filter'):
            print("✅ Logging filter creation works")
        else:
            print("❌ Logging filter creation failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Log redaction test failed: {e}")
        return False

def test_security_integration():
    """Test security integration functions"""
    print("\n=== Security Integration Test ===")
    
    try:
        from security_manager import setup_secure_logging, get_security_status
        
        # Test secure logging setup (should not crash)
        setup_secure_logging()
        print("✅ Secure logging setup works")
        
        # Test security status
        status = get_security_status()
        
        required_keys = ["cookie_encryption", "log_redaction", "credential_validation", "environment_security"]
        if all(key in status for key in required_keys):
            print("✅ Security status has required keys")
        else:
            print(f"❌ Security status missing keys: {[k for k in required_keys if k not in status]}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Security integration test failed: {e}")
        return False

def test_cookie_size_limits():
    """Test cookie size limits and validation"""
    print("\n=== Cookie Size Limits Test ===")
    
    try:
        from security_manager import SecureCookieManager
        
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["SECURE_COOKIES_DIR"] = temp_dir
            os.environ["MAX_COOKIE_SIZE_KB"] = "1"  # 1KB limit for testing
            
            manager = SecureCookieManager()
            
            # Test normal size cookies
            normal_cookies = {"session": "normal_data"}
            result = manager.store_cookies(1, normal_cookies, "test")
            
            if result:
                print("✅ Normal size cookies accepted")
            else:
                print("❌ Normal size cookies rejected")
                return False
            
            # Test oversized cookies
            large_data = "x" * 2000  # 2KB of data
            large_cookies = {"large_session": large_data}
            result = manager.store_cookies(2, large_cookies, "test")
            
            if not result:
                print("✅ Oversized cookies rejected")
            else:
                print("❌ Oversized cookies not rejected")
                return False
            
            return True
        
    except Exception as e:
        print(f"❌ Cookie size limits test failed: {e}")
        return False

if __name__ == "__main__":
    print("=== Security Enhancements Test ===")
    
    cookie_manager_success = test_secure_cookie_manager()
    encryption_success = test_cookie_encryption()
    ttl_success = test_ttl_enforcement()
    credential_success = test_credential_protection()
    redaction_success = test_log_redaction()
    integration_success = test_security_integration()
    size_limits_success = test_cookie_size_limits()
    
    all_tests = [
        cookie_manager_success, encryption_success, ttl_success, 
        credential_success, redaction_success, integration_success, size_limits_success
    ]
    
    if all(all_tests):
        print("\n✅ All security enhancement tests passed!")
        print("Task 13: Add security enhancements for cookie and credential handling - COMPLETE")
        sys.exit(0)
    else:
        print(f"\n❌ Some security tests failed! Results: {all_tests}")
        sys.exit(1)