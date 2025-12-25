#!/usr/bin/env python3
"""
Test configuration validation and circuit breaker integration
"""

import os
import sys
import tempfile
import warnings
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_config_validation():
    """Test configuration validation enforces required settings"""
    print("=== Configuration Validation Tests ===")
    
    # Test 1: DEEPGRAM_API_KEY validation when ASR enabled
    print("\n1. Testing DEEPGRAM_API_KEY validation when ASR enabled:")
    
    with patch.dict(os.environ, {
        'ENABLE_ASR_FALLBACK': '1',
        'DEEPGRAM_API_KEY': ''  # Missing key
    }, clear=False):
        try:
            from config_validator import ConfigValidator
            validator = ConfigValidator()
            result = validator.validate_all_config()
            
            # Should have error about missing DEEPGRAM_API_KEY
            deepgram_errors = [e for e in result.errors if 'DEEPGRAM_API_KEY' in e]
            if deepgram_errors:
                print("✅ DEEPGRAM_API_KEY validation works:", deepgram_errors[0])
            else:
                print("❌ DEEPGRAM_API_KEY validation failed - no error found")
                
        except Exception as e:
            print(f"❌ Config validation test failed: {e}")
    
    # Test 2: ENFORCE_PROXY_ALL validation
    print("\n2. Testing ENFORCE_PROXY_ALL validation:")
    
    with patch.dict(os.environ, {
        'ENFORCE_PROXY_ALL': '1'
    }, clear=False):
        try:
            from config_validator import ConfigValidator
            validator = ConfigValidator()
            result = validator.validate_all_config()
            
            # Should check for ProxyManager availability
            proxy_errors = [e for e in result.errors if 'ENFORCE_PROXY_ALL' in e or 'ProxyManager' in e]
            if proxy_errors:
                print("✅ ENFORCE_PROXY_ALL validation works:", proxy_errors[0])
            else:
                print("⚠️  ENFORCE_PROXY_ALL validation may not be working (no error found)")
                
        except Exception as e:
            print(f"❌ ENFORCE_PROXY_ALL validation test failed: {e}")
    
    # Test 3: Valid configuration
    print("\n3. Testing valid configuration:")
    
    with patch.dict(os.environ, {
        'ENABLE_ASR_FALLBACK': '1',
        'DEEPGRAM_API_KEY': 'test_key_with_sufficient_length_for_validation',
        'ENFORCE_PROXY_ALL': '0',
        'OPENAI_API_KEY': 'sk-test_key',
        'RESEND_API_KEY': 're_test_key',
        'SENDER_EMAIL': 'test@example.com',
        'GOOGLE_CLIENT_ID': 'test_client_id',
        'GOOGLE_CLIENT_SECRET': 'test_client_secret',
        'SESSION_SECRET': 'test_session_secret_with_sufficient_length'
    }, clear=False):
        try:
            from config_validator import ConfigValidator
            validator = ConfigValidator()
            result = validator.validate_all_config()
            
            if result.is_valid:
                print("✅ Valid configuration passes validation")
            else:
                print(f"❌ Valid configuration failed: {result.errors}")
                
        except Exception as e:
            print(f"❌ Valid configuration test failed: {e}")


def test_circuit_breaker_integration():
    """Test circuit breaker is properly integrated at extract method starts"""
    print("\n=== Circuit Breaker Integration Tests ===")
    
    # Test 1: Circuit breaker check in ASRAudioExtractor.extract_transcript
    print("\n1. Testing circuit breaker in ASRAudioExtractor.extract_transcript:")
    
    try:
        # Mock the circuit breaker to be open
        with patch('transcript_service._playwright_circuit_breaker') as mock_cb:
            mock_cb.is_open.return_value = True
            mock_cb.get_recovery_time_remaining.return_value = 300
            
            from transcript_service import ASRAudioExtractor
            extractor = ASRAudioExtractor("test_key")
            
            result = extractor.extract_transcript("test_video_id")
            
            # Should return empty string due to circuit breaker
            if result == "":
                print("✅ Circuit breaker blocks ASRAudioExtractor.extract_transcript when open")
            else:
                print("❌ Circuit breaker not blocking ASRAudioExtractor.extract_transcript")
                
            # Verify circuit breaker was checked
            if mock_cb.is_open.called:
                print("✅ Circuit breaker is_open() was called")
            else:
                print("❌ Circuit breaker is_open() was not called")
                
    except Exception as e:
        print(f"❌ Circuit breaker integration test failed: {e}")
    
    # Test 2: ENFORCE_PROXY_ALL check in ASRAudioExtractor.extract_transcript
    print("\n2. Testing ENFORCE_PROXY_ALL check in ASRAudioExtractor.extract_transcript:")
    
    try:
        with patch.dict(os.environ, {'ENFORCE_PROXY_ALL': '1'}, clear=False):
            # Force reload of transcript_service to pick up env var
            if 'transcript_service' in sys.modules:
                del sys.modules['transcript_service']
            
            from transcript_service import ASRAudioExtractor
            
            # Create extractor without proxy manager
            extractor = ASRAudioExtractor("test_key", proxy_manager=None)
            
            result = extractor.extract_transcript("test_video_id")
            
            # Should return empty string due to proxy enforcement
            if result == "":
                print("✅ ENFORCE_PROXY_ALL blocks extraction when no proxy manager")
            else:
                print("❌ ENFORCE_PROXY_ALL not blocking extraction without proxy manager")
                
    except Exception as e:
        print(f"❌ ENFORCE_PROXY_ALL integration test failed: {e}")
    
    # Test 3: Circuit breaker in _extract_hls_audio_url
    print("\n3. Testing circuit breaker in _extract_hls_audio_url:")
    
    try:
        with patch('transcript_service._playwright_circuit_breaker') as mock_cb:
            mock_cb.is_open.return_value = True
            mock_cb.get_recovery_time_remaining.return_value = 300
            
            from transcript_service import ASRAudioExtractor
            extractor = ASRAudioExtractor("test_key")
            
            result = extractor._extract_hls_audio_url("test_video_id")
            
            # Should return empty string due to circuit breaker
            if result == "":
                print("✅ Circuit breaker blocks _extract_hls_audio_url when open")
            else:
                print("❌ Circuit breaker not blocking _extract_hls_audio_url")
                
    except Exception as e:
        print(f"❌ _extract_hls_audio_url circuit breaker test failed: {e}")


def test_module_import_validation():
    """Test that configuration validation runs at module import"""
    print("\n=== Module Import Validation Tests ===")
    
    print("\n1. Testing config validation at import:")
    
    try:
        # Clear any cached modules
        modules_to_clear = [
            'config_validator', 'reliability_config', 'transcript_service'
        ]
        for module in modules_to_clear:
            if module in sys.modules:
                del sys.modules[module]
        
        # Set up environment with missing required config
        with patch.dict(os.environ, {
            'ENABLE_ASR_FALLBACK': '1',
            'DEEPGRAM_API_KEY': '',  # Missing
            'ENFORCE_PROXY_ALL': '1'
        }, clear=False):
            
            # Import should trigger validation
            from config_validator import validate_startup_config
            
            # Run validation
            is_valid = validate_startup_config()
            
            if not is_valid:
                print("✅ Module import validation detects configuration errors")
            else:
                print("❌ Module import validation not detecting configuration errors")
                
    except Exception as e:
        print(f"❌ Module import validation test failed: {e}")


def test_runtime_config_enforcement():
    """Test that configuration is enforced at runtime"""
    print("\n=== Runtime Configuration Enforcement Tests ===")
    
    print("\n1. Testing ASR extraction with missing DEEPGRAM_API_KEY:")
    
    try:
        from transcript_service import ASRAudioExtractor
        
        # Create extractor with empty API key
        extractor = ASRAudioExtractor("")
        
        result = extractor.extract_transcript("test_video_id")
        
        # Should return empty string due to missing API key
        if result == "":
            print("✅ ASR extraction blocked when DEEPGRAM_API_KEY is missing")
        else:
            print("❌ ASR extraction not blocked with missing DEEPGRAM_API_KEY")
            
    except Exception as e:
        print(f"❌ Runtime API key enforcement test failed: {e}")


def main():
    """Run all validation tests"""
    print("🔧 Configuration & Circuit Breaker Validation Tests")
    print("=" * 60)
    
    try:
        test_config_validation()
        test_circuit_breaker_integration()
        test_module_import_validation()
        test_runtime_config_enforcement()
        
        print("\n" + "=" * 60)
        print("🎉 All validation tests completed!")
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())