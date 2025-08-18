#!/usr/bin/env python3
"""
Deployment validation script for Oxylabs proxy auth fix
Validates secret format and proxy health before deployment
"""

import sys
import os
import json
import requests
from typing import Dict, Tuple

def validate_secret_format(secret_data: Dict) -> Tuple[bool, str]:
    """Validate that secret follows RAW format requirements"""
    print("🔍 Validating secret format...")
    
    # Check required fields
    required_fields = ["provider", "host", "port", "username", "password"]
    for field in required_fields:
        if field not in secret_data:
            return False, f"Missing required field: {field}"
        if not secret_data[field]:
            return False, f"Empty required field: {field}"
    
    # Check host doesn't contain scheme
    host = str(secret_data["host"])
    if host.startswith(("http://", "https://")):
        return False, f"Host contains scheme (should be RAW): {host}"
    
    # Check password isn't pre-encoded
    password = str(secret_data["password"])
    if "%" in password:
        # Simple heuristic for common URL-encoded characters
        if any(encoded in password for encoded in ["%21", "%40", "%3A", "%2B"]):
            return False, f"Password appears to be URL-encoded (should be RAW)"
    
    # Check port is valid
    try:
        port = int(secret_data["port"])
        if not (1 <= port <= 65535):
            return False, f"Invalid port number: {port}"
    except ValueError:
        return False, f"Port is not a valid integer: {secret_data['port']}"
    
    print("✅ Secret format validation passed")
    return True, "Secret format is valid"

def test_proxy_connectivity(secret_data: Dict) -> Tuple[bool, str]:
    """Test proxy connectivity with the secret"""
    print("🔍 Testing proxy connectivity...")
    
    try:
        # Import after validation to ensure clean environment
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from proxy_manager import ProxyManager
        import logging
        
        # Create proxy manager
        logger = logging.getLogger(__name__)
        pm = ProxyManager(secret_data, logger)
        
        # Test preflight
        if pm.preflight(timeout=10.0):
            print("✅ Proxy connectivity test passed")
            return True, "Proxy is healthy and accessible"
        else:
            return False, "Proxy preflight failed - authentication or connectivity issue"
            
    except Exception as e:
        return False, f"Proxy connectivity test failed: {str(e)}"

def validate_environment() -> Tuple[bool, str]:
    """Validate deployment environment"""
    print("🔍 Validating deployment environment...")
    
    # Check for required environment variables
    required_env_vars = ["OXYLABS_PROXY_CONFIG"]
    for var in required_env_vars:
        if not os.getenv(var):
            return False, f"Missing required environment variable: {var}"
    
    # Check optional but recommended variables
    recommended_vars = {
        "OXY_PREFLIGHT_TTL_SECONDS": "300",
        "OXY_PREFLIGHT_MAX_PER_MINUTE": "10",
        "OXY_DISABLE_GEO": "true"
    }
    
    for var, default in recommended_vars.items():
        value = os.getenv(var, default)
        print(f"  {var}={value}")
    
    print("✅ Environment validation passed")
    return True, "Environment is properly configured"

def main():
    """Main deployment validation"""
    print("🚀 Oxylabs Proxy Auth Fix - Deployment Validation")
    print("=" * 60)
    
    # Load secret from environment or use test data
    raw_config = os.getenv('OXYLABS_PROXY_CONFIG', '').strip()
    if not raw_config:
        print("⚠️  OXYLABS_PROXY_CONFIG environment variable is empty")
        print("💡 Using test data for validation demo...")
        # Use test data to demonstrate validation
        raw_config = json.dumps({
            "provider": "oxylabs",
            "host": "pr.oxylabs.io",
            "port": 7777,
            "username": "customer-test123",
            "password": "myRawPassword123!",
            "geo_enabled": False,
            "country": "us",
            "version": 1
        })
    
    try:
        secret_data = json.loads(raw_config)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in OXYLABS_PROXY_CONFIG: {e}")
        return False
    
    # Run validation tests
    validations = [
        ("Environment", validate_environment),
        ("Secret Format", lambda: validate_secret_format(secret_data)),
        ("Proxy Connectivity", lambda: test_proxy_connectivity(secret_data)),
    ]
    
    all_passed = True
    
    for test_name, test_func in validations:
        print(f"\n📋 {test_name} Validation")
        print("-" * 40)
        
        try:
            passed, message = test_func()
            if passed:
                print(f"✅ {test_name}: {message}")
            else:
                print(f"❌ {test_name}: {message}")
                all_passed = False
        except Exception as e:
            print(f"❌ {test_name}: Validation failed with error: {e}")
            all_passed = False
    
    print("\n" + "=" * 60)
    
    if all_passed:
        print("🎉 DEPLOYMENT VALIDATION PASSED!")
        print("\n📋 Validated Components:")
        print("  ✅ RAW secret format (no pre-encoded passwords)")
        print("  ✅ Proxy connectivity and authentication")
        print("  ✅ Environment configuration")
        print("\n🚀 Ready to deploy! The 407 errors should be eliminated.")
        
        # Show example secret format
        print("\n📄 Example RAW Secret Format:")
        example_secret = {
            "provider": "oxylabs",
            "host": "pr.oxylabs.io",
            "port": 7777,
            "username": "customer-<your-account>",
            "password": "<RAW-PASSWORD-NOT-ENCODED>",
            "geo_enabled": False,
            "country": "us",
            "version": 1
        }
        print(json.dumps(example_secret, indent=2))
        
        print("\n🔧 Direct Oxylabs Test Command:")
        username = secret_data.get('username', 'customer-<USERNAME>')
        password = secret_data.get('password', 'RAW_PASSWORD')
        host = secret_data.get('host', 'pr.oxylabs.io')
        port = secret_data.get('port', 7777)
        
        print(f"curl -x 'http://{username}-sessid-test:{password}@{host}:{port}' http://ip.oxylabs.io")
        print("\n💡 If this curl command fails with 407, contact Oxylabs support:")
        print("   • Verify account is active with residential access")
        print("   • Check subuser permissions and restrictions")
        print("   • Confirm sticky session format is correct")
        
        return True
    else:
        print("❌ DEPLOYMENT VALIDATION FAILED!")
        print("\n🔧 Fix the issues above before deploying.")
        print("\n💡 Common Issues:")
        print("  • Password is URL-encoded (contains %) - store RAW password")
        print("  • Host contains http:// or https:// - use hostname only")
        print("  • Missing required fields in secret JSON")
        print("  • Proxy credentials are incorrect or expired")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)