#!/usr/bin/env python3
"""
Test for configuration management and validation system
"""
import os
import sys
import logging

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_config_validator_initialization():
    """Test ConfigValidator initialization"""
    print("=== ConfigValidator Initialization Test ===")
    
    try:
        from config_validator import ConfigValidator, ConfigValidationResult
        
        validator = ConfigValidator()
        print("✅ ConfigValidator initialized successfully")
        
        # Test ConfigValidationResult dataclass
        result = ConfigValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            config={}
        )
        print("✅ ConfigValidationResult dataclass works")
        
        return True
        
    except Exception as e:
        print(f"❌ ConfigValidator initialization failed: {e}")
        return False

def test_feature_flag_validation():
    """Test feature flag validation"""
    print("\n=== Feature Flag Validation Test ===")
    
    try:
        from config_validator import ConfigValidator
        
        validator = ConfigValidator()
        
        # Save original env vars
        original_env = {}
        flags = ["ENABLE_YT_API", "ENABLE_TIMEDTEXT", "ENABLE_YOUTUBEI", "ENABLE_ASR_FALLBACK"]
        for flag in flags:
            original_env[flag] = os.environ.get(flag)
        
        try:
            # Test valid flag values
            os.environ["ENABLE_YT_API"] = "1"
            os.environ["ENABLE_TIMEDTEXT"] = "1"
            os.environ["ENABLE_YOUTUBEI"] = "0"
            os.environ["ENABLE_ASR_FALLBACK"] = "0"
            
            config, errors, warnings = validator._validate_feature_flags()
            
            if not errors:
                print("✅ Valid feature flags pass validation")
            else:
                print(f"❌ Valid feature flags failed: {errors}")
                return False
            
            # Test invalid flag values
            os.environ["ENABLE_YT_API"] = "invalid"
            config, errors, warnings = validator._validate_feature_flags()
            
            if errors and "must be '0' or '1'" in str(errors):
                print("✅ Invalid feature flag values detected")
            else:
                print(f"❌ Invalid feature flag values not detected: {errors}")
                return False
            
            # Test flag combination validation
            os.environ["ENABLE_YT_API"] = "0"
            os.environ["ENABLE_TIMEDTEXT"] = "0"
            config, errors, warnings = validator._validate_feature_flags()
            
            if errors and "At least one of" in str(errors):
                print("✅ Feature flag combination validation works")
            else:
                print(f"❌ Feature flag combination validation failed: {errors}")
                return False
            
            return True
            
        finally:
            # Restore original env vars
            for flag, value in original_env.items():
                if value is not None:
                    os.environ[flag] = value
                elif flag in os.environ:
                    del os.environ[flag]
        
    except Exception as e:
        print(f"❌ Feature flag validation test failed: {e}")
        return False

def test_performance_config_validation():
    """Test performance configuration validation"""
    print("\n=== Performance Config Validation Test ===")
    
    try:
        from config_validator import ConfigValidator
        
        validator = ConfigValidator()
        
        # Save original env vars
        original_env = {}
        settings = ["WORKER_CONCURRENCY", "PW_NAV_TIMEOUT_MS", "ASR_MAX_VIDEO_MINUTES", "USE_PROXY_FOR_TIMEDTEXT"]
        for setting in settings:
            original_env[setting] = os.environ.get(setting)
        
        try:
            # Test valid performance settings
            os.environ["WORKER_CONCURRENCY"] = "2"
            os.environ["PW_NAV_TIMEOUT_MS"] = "15000"
            os.environ["ASR_MAX_VIDEO_MINUTES"] = "20"
            os.environ["USE_PROXY_FOR_TIMEDTEXT"] = "0"
            
            config, errors, warnings = validator._validate_performance_config()
            
            if not errors:
                print("✅ Valid performance config passes validation")
            else:
                print(f"❌ Valid performance config failed: {errors}")
                return False
            
            # Test invalid values
            os.environ["WORKER_CONCURRENCY"] = "invalid"
            config, errors, warnings = validator._validate_performance_config()
            
            if errors and "must be a valid integer" in str(errors):
                print("✅ Invalid integer values detected")
            else:
                print(f"❌ Invalid integer values not detected: {errors}")
                return False
            
            # Test out of range values
            os.environ["WORKER_CONCURRENCY"] = "100"  # Too high
            config, errors, warnings = validator._validate_performance_config()
            
            if errors and "must be between" in str(errors):
                print("✅ Out of range values detected")
            else:
                print(f"❌ Out of range values not detected: {errors}")
                return False
            
            return True
            
        finally:
            # Restore original env vars
            for setting, value in original_env.items():
                if value is not None:
                    os.environ[setting] = value
                elif setting in os.environ:
                    del os.environ[setting]
        
    except Exception as e:
        print(f"❌ Performance config validation test failed: {e}")
        return False

def test_service_credentials_validation():
    """Test service credentials validation"""
    print("\n=== Service Credentials Validation Test ===")
    
    try:
        from config_validator import ConfigValidator
        
        validator = ConfigValidator()
        
        # Save original env vars
        original_env = {}
        creds = ["OPENAI_API_KEY", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "SESSION_SECRET"]
        for cred in creds:
            original_env[cred] = os.environ.get(cred)
        
        try:
            # Test missing credentials
            for cred in creds:
                if cred in os.environ:
                    del os.environ[cred]
            
            config, errors, warnings = validator._validate_service_credentials()
            
            if len(errors) == len(creds):
                print("✅ Missing credentials detected")
            else:
                print(f"❌ Missing credentials not properly detected: {len(errors)} vs {len(creds)}")
                return False
            
            # Test valid credentials
            os.environ["OPENAI_API_KEY"] = "sk-test123456789"
            os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
            os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"
            os.environ["SESSION_SECRET"] = "a" * 32  # 32 characters
            
            config, errors, warnings = validator._validate_service_credentials()
            
            if not errors:
                print("✅ Valid credentials pass validation")
            else:
                print(f"❌ Valid credentials failed: {errors}")
                return False
            
            # Test credential format warnings
            os.environ["OPENAI_API_KEY"] = "invalid-format"
            os.environ["SESSION_SECRET"] = "short"
            
            config, errors, warnings = validator._validate_service_credentials()
            
            if warnings and len(warnings) >= 2:
                print("✅ Credential format warnings generated")
            else:
                print(f"❌ Credential format warnings not generated: {warnings}")
                return False
            
            return True
            
        finally:
            # Restore original env vars
            for cred, value in original_env.items():
                if value is not None:
                    os.environ[cred] = value
                elif cred in os.environ:
                    del os.environ[cred]
        
    except Exception as e:
        print(f"❌ Service credentials validation test failed: {e}")
        return False

def test_asr_config_validation():
    """Test ASR configuration validation"""
    print("\n=== ASR Config Validation Test ===")
    
    try:
        from config_validator import ConfigValidator
        
        validator = ConfigValidator()
        
        # Save original env vars
        original_env = {
            "ENABLE_ASR_FALLBACK": os.environ.get("ENABLE_ASR_FALLBACK"),
            "DEEPGRAM_API_KEY": os.environ.get("DEEPGRAM_API_KEY")
        }
        
        try:
            # Test ASR disabled (should not require Deepgram key)
            os.environ["ENABLE_ASR_FALLBACK"] = "0"
            if "DEEPGRAM_API_KEY" in os.environ:
                del os.environ["DEEPGRAM_API_KEY"]
            
            config, errors, warnings = validator._validate_asr_config()
            
            if not errors:
                print("✅ ASR disabled config passes validation")
            else:
                print(f"❌ ASR disabled config failed: {errors}")
                return False
            
            # Test ASR enabled without Deepgram key (should error)
            os.environ["ENABLE_ASR_FALLBACK"] = "1"
            
            config, errors, warnings = validator._validate_asr_config()
            
            if errors and "DEEPGRAM_API_KEY is required" in str(errors):
                print("✅ ASR enabled without key detected")
            else:
                print(f"❌ ASR enabled without key not detected: {errors}")
                return False
            
            # Test ASR enabled with key (should pass)
            os.environ["DEEPGRAM_API_KEY"] = "a" * 32  # 32 character key
            
            config, errors, warnings = validator._validate_asr_config()
            
            if not errors:
                print("✅ ASR enabled with key passes validation")
            else:
                print(f"❌ ASR enabled with key failed: {errors}")
                return False
            
            return True
            
        finally:
            # Restore original env vars
            for var, value in original_env.items():
                if value is not None:
                    os.environ[var] = value
                elif var in os.environ:
                    del os.environ[var]
        
    except Exception as e:
        print(f"❌ ASR config validation test failed: {e}")
        return False

def test_full_validation():
    """Test full configuration validation"""
    print("\n=== Full Validation Test ===")
    
    try:
        from config_validator import ConfigValidator
        
        validator = ConfigValidator()
        
        # Test full validation
        result = validator.validate_all_config()
        
        if hasattr(result, 'is_valid') and hasattr(result, 'errors') and hasattr(result, 'warnings'):
            print("✅ Full validation returns proper result structure")
        else:
            print("❌ Full validation result structure incorrect")
            return False
        
        # Test config summary
        summary = validator.get_config_summary()
        
        required_keys = ['validation_status', 'feature_flags', 'services_configured', 'performance_settings']
        if all(key in summary for key in required_keys):
            print("✅ Config summary has required keys")
        else:
            print(f"❌ Config summary missing keys: {[k for k in required_keys if k not in summary]}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Full validation test failed: {e}")
        return False

def test_startup_integration():
    """Test startup integration functions"""
    print("\n=== Startup Integration Test ===")
    
    try:
        from config_validator import validate_startup_config, get_validated_config
        
        # Test startup validation
        result = validate_startup_config()
        if isinstance(result, bool):
            print("✅ Startup validation returns boolean")
        else:
            print("❌ Startup validation should return boolean")
            return False
        
        # Test validated config
        config = get_validated_config()
        if isinstance(config, dict):
            print("✅ Validated config returns dictionary")
        else:
            print("❌ Validated config should return dictionary")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Startup integration test failed: {e}")
        return False

if __name__ == "__main__":
    print("=== Configuration Management Test ===")
    
    init_success = test_config_validator_initialization()
    flags_success = test_feature_flag_validation()
    perf_success = test_performance_config_validation()
    creds_success = test_service_credentials_validation()
    asr_success = test_asr_config_validation()
    full_success = test_full_validation()
    startup_success = test_startup_integration()
    
    all_tests = [init_success, flags_success, perf_success, creds_success, asr_success, full_success, startup_success]
    
    if all(all_tests):
        print("\n✅ All configuration management tests passed!")
        print("Task 11: Add configuration management and validation - COMPLETE")
        sys.exit(0)
    else:
        print(f"\n❌ Some configuration tests failed! Results: {all_tests}")
        sys.exit(1)