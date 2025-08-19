#!/usr/bin/env python3
"""
Test proxy secret validation functionality
"""

import os
import sys
import json
import tempfile
from unittest.mock import patch, MagicMock

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_valid_secret_schema():
    """Test validation of a complete, valid secret"""
    print("Testing valid secret schema...")
    
    try:
        from validate_proxy_secret import validate_secret_schema
        
        valid_secret = {
            "provider": "oxylabs",
            "host": "pr.oxylabs.io",
            "port": 60000,
            "username": "test_user",
            "password": "test_pass",
            "protocol": "http"
        }
        
        is_valid, missing_fields = validate_secret_schema(valid_secret)
        
        if not is_valid:
            print(f"❌ Valid secret marked as invalid: {missing_fields}")
            return False
        
        if missing_fields:
            print(f"❌ Valid secret has missing fields: {missing_fields}")
            return False
        
        print("✅ Valid secret schema correctly validated")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test valid schema: {e}")
        return False

def test_missing_provider_field():
    """Test detection of missing provider field (the main production issue)"""
    print("Testing missing provider field detection...")
    
    try:
        from validate_proxy_secret import validate_secret_schema
        
        # Secret missing provider field (the actual production issue)
        invalid_secret = {
            "host": "pr.oxylabs.io",
            "port": 60000,
            "username": "test_user",
            "password": "test_pass",
            "protocol": "http"
        }
        
        is_valid, missing_fields = validate_secret_schema(invalid_secret)
        
        if is_valid:
            print("❌ Invalid secret (missing provider) marked as valid")
            return False
        
        if "provider" not in missing_fields:
            print(f"❌ Missing provider field not detected: {missing_fields}")
            return False
        
        print("✅ Missing provider field correctly detected")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test missing provider: {e}")
        return False

def test_multiple_missing_fields():
    """Test detection of multiple missing fields"""
    print("Testing multiple missing fields...")
    
    try:
        from validate_proxy_secret import validate_secret_schema
        
        # Secret with multiple missing fields
        incomplete_secret = {
            "host": "pr.oxylabs.io",
            "username": "test_user"
            # Missing: provider, port, password, protocol
        }
        
        is_valid, missing_fields = validate_secret_schema(incomplete_secret)
        
        if is_valid:
            print("❌ Incomplete secret marked as valid")
            return False
        
        expected_missing = ["provider", "port", "password", "protocol"]
        for field in expected_missing:
            if field not in missing_fields:
                print(f"❌ Missing field not detected: {field}")
                return False
        
        print(f"✅ All missing fields detected: {missing_fields}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test multiple missing fields: {e}")
        return False

def test_empty_field_values():
    """Test detection of empty field values"""
    print("Testing empty field values...")
    
    try:
        from validate_proxy_secret import validate_secret_schema
        
        # Secret with empty values
        empty_secret = {
            "provider": "",  # Empty string
            "host": "pr.oxylabs.io",
            "port": 60000,
            "username": "   ",  # Whitespace only
            "password": "test_pass",
            "protocol": "http"
        }
        
        is_valid, missing_fields = validate_secret_schema(empty_secret)
        
        if is_valid:
            print("❌ Secret with empty fields marked as valid")
            return False
        
        # Should detect empty provider and whitespace-only username
        if "provider (empty)" not in missing_fields:
            print(f"❌ Empty provider not detected: {missing_fields}")
            return False
        
        if "username (empty)" not in missing_fields:
            print(f"❌ Whitespace-only username not detected: {missing_fields}")
            return False
        
        print("✅ Empty field values correctly detected")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test empty fields: {e}")
        return False

def test_example_secret_creation():
    """Test creation of example secret"""
    print("Testing example secret creation...")
    
    try:
        from validate_proxy_secret import create_example_secret
        
        example = create_example_secret()
        
        # Should be a valid secret
        from validate_proxy_secret import validate_secret_schema
        is_valid, missing_fields = validate_secret_schema(example)
        
        if not is_valid:
            print(f"❌ Example secret is invalid: {missing_fields}")
            return False
        
        # Should contain all required fields
        required_fields = ["provider", "host", "port", "username", "password", "protocol"]
        for field in required_fields:
            if field not in example:
                print(f"❌ Example missing required field: {field}")
                return False
        
        # Should have reasonable default values
        if example["provider"] != "oxylabs":
            print(f"❌ Unexpected provider: {example['provider']}")
            return False
        
        if not isinstance(example["port"], int):
            print(f"❌ Port should be integer: {type(example['port'])}")
            return False
        
        print("✅ Example secret creation works correctly")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test example creation: {e}")
        return False

def test_aws_secret_retrieval_mock():
    """Test AWS secret retrieval with mocked boto3"""
    print("Testing AWS secret retrieval (mocked)...")
    
    try:
        # Mock boto3 client
        mock_client = MagicMock()
        mock_response = {
            'SecretString': json.dumps({
                "provider": "oxylabs",
                "host": "pr.oxylabs.io",
                "port": 60000,
                "username": "test_user",
                "password": "test_pass",
                "protocol": "http"
            })
        }
        mock_client.get_secret_value.return_value = mock_response
        
        with patch('boto3.client', return_value=mock_client):
            from validate_proxy_secret import get_secret_from_aws
            
            secret_data = get_secret_from_aws("test-secret", "us-west-2")
            
            # Should return parsed JSON
            if not isinstance(secret_data, dict):
                print(f"❌ Expected dict, got {type(secret_data)}")
                return False
            
            if secret_data["provider"] != "oxylabs":
                print(f"❌ Unexpected provider: {secret_data['provider']}")
                return False
            
            # Verify boto3 was called correctly
            mock_client.get_secret_value.assert_called_once_with(SecretId="test-secret")
        
        print("✅ AWS secret retrieval works correctly")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test AWS retrieval: {e}")
        return False

def test_aws_secret_update_mock():
    """Test AWS secret update with mocked boto3"""
    print("Testing AWS secret update (mocked)...")
    
    try:
        # Mock boto3 client
        mock_client = MagicMock()
        
        with patch('boto3.client', return_value=mock_client):
            from validate_proxy_secret import update_secret_in_aws
            
            test_secret = {
                "provider": "oxylabs",
                "host": "pr.oxylabs.io",
                "port": 60000,
                "username": "test_user",
                "password": "test_pass",
                "protocol": "http"
            }
            
            result = update_secret_in_aws("test-secret", test_secret, "us-west-2")
            
            if not result:
                print("❌ Update should return True on success")
                return False
            
            # Verify boto3 was called correctly
            mock_client.update_secret.assert_called_once()
            call_args = mock_client.update_secret.call_args
            
            if call_args[1]['SecretId'] != "test-secret":
                print(f"❌ Wrong SecretId: {call_args[1]['SecretId']}")
                return False
            
            # Verify secret string is valid JSON
            secret_string = call_args[1]['SecretString']
            parsed = json.loads(secret_string)
            
            if parsed["provider"] != "oxylabs":
                print(f"❌ Provider not preserved in update: {parsed['provider']}")
                return False
        
        print("✅ AWS secret update works correctly")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test AWS update: {e}")
        return False

def test_error_handling():
    """Test error handling for various failure scenarios"""
    print("Testing error handling...")
    
    try:
        from validate_proxy_secret import validate_secret_schema
        
        # Test with None input
        is_valid, missing_fields = validate_secret_schema(None)
        if is_valid:
            print("❌ None input should be invalid")
            return False
        
        # Test with non-dict input
        is_valid, missing_fields = validate_secret_schema("not a dict")
        if is_valid:
            print("❌ String input should be invalid")
            return False
        
        # Test with empty dict
        is_valid, missing_fields = validate_secret_schema({})
        if is_valid:
            print("❌ Empty dict should be invalid")
            return False
        
        if len(missing_fields) != 6:  # Should be missing all 6 required fields
            print(f"❌ Empty dict should have 6 missing fields, got {len(missing_fields)}")
            return False
        
        print("✅ Error handling works correctly")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test error handling: {e}")
        return False

def test_command_line_interface():
    """Test command line interface functionality"""
    print("Testing command line interface...")
    
    try:
        # Test that the script can be imported without errors
        import validate_proxy_secret
        
        # Test that main functions exist
        required_functions = [
            'validate_secret_schema',
            'create_example_secret',
            'get_secret_from_aws',
            'update_secret_in_aws'
        ]
        
        for func_name in required_functions:
            if not hasattr(validate_proxy_secret, func_name):
                print(f"❌ Missing required function: {func_name}")
                return False
        
        print("✅ Command line interface structure is correct")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test CLI: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing proxy secret validation functionality...")
    print()
    
    tests = [
        test_valid_secret_schema,
        test_missing_provider_field,
        test_multiple_missing_fields,
        test_empty_field_values,
        test_example_secret_creation,
        test_aws_secret_retrieval_mock,
        test_aws_secret_update_mock,
        test_error_handling,
        test_command_line_interface
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
        print()
    
    print(f"📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Proxy secret validation is working correctly.")
        print("📝 Key features verified:")
        print("   - Valid secret schema detection")
        print("   - Missing provider field detection (fixes production issue)")
        print("   - Multiple missing fields detection")
        print("   - Empty field value detection")
        print("   - Example secret creation")
        print("   - AWS integration (mocked)")
        print("   - Error handling for edge cases")
        print("   - Command line interface structure")
        sys.exit(0)
    else:
        print("💥 Some tests failed. Proxy secret validation needs fixes.")
        sys.exit(1)