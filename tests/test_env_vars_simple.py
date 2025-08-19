#!/usr/bin/env python3
"""
Simple test for environment variable standardization
"""

import os
import sys

def test_migration_script_exists():
    """Test that migration script exists"""
    script_path = 'deployment/migrate-env-vars.sh'
    if not os.path.exists(script_path):
        print(f"❌ Migration script {script_path} does not exist")
        return False
    
    print(f"✅ Migration script {script_path} exists")
    return True

def test_migration_script_content():
    """Test migration script content"""
    script_path = 'deployment/migrate-env-vars.sh'
    
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        # Try with different encoding
        with open(script_path, 'r', encoding='latin-1') as f:
            content = f.read()
    
    # Check for correct variable mappings
    checks = [
        ('GOOGLE_OAUTH_CLIENT_ID', 'Contains legacy variable name'),
        ('GOOGLE_CLIENT_ID', 'Contains new variable name'),
        ('GOOGLE_OAUTH_CLIENT_SECRET', 'Contains legacy secret variable'),
        ('GOOGLE_CLIENT_SECRET', 'Contains new secret variable'),
    ]
    
    all_passed = True
    for check, description in checks:
        if check in content:
            print(f"✅ {description}: {check}")
        else:
            print(f"❌ {description}: {check} not found")
            all_passed = False
    
    return all_passed

def test_shared_managers_exists():
    """Test that shared_managers.py exists and has correct structure"""
    if not os.path.exists('shared_managers.py'):
        print("❌ shared_managers.py does not exist")
        return False
    
    with open('shared_managers.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ('class SharedManagers', 'SharedManagers class exists'),
        ('get_proxy_manager', 'get_proxy_manager method exists'),
        ('get_proxy_http_client', 'get_proxy_http_client method exists'),
        ('get_user_agent_manager', 'get_user_agent_manager method exists'),
        ('_instance = None', 'Singleton pattern implemented'),
    ]
    
    all_passed = True
    for check, description in checks:
        if check in content:
            print(f"✅ {description}")
        else:
            print(f"❌ {description}: {check} not found")
            all_passed = False
    
    return all_passed

def test_transcript_service_cleanup():
    """Test that TranscriptService has been cleaned up"""
    with open('transcript_service.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check that duplicate initialization is removed
    if 'def _create_proxy_manager(self):' in content:
        print("❌ TranscriptService still has duplicate _create_proxy_manager method")
        return False
    else:
        print("✅ Duplicate _create_proxy_manager method removed from TranscriptService")
    
    # Check that it uses shared managers
    if 'shared_managers.get_proxy_manager()' in content:
        print("✅ TranscriptService uses shared managers")
    else:
        print("❌ TranscriptService does not use shared managers")
        return False
    
    return True

def test_google_auth_variables():
    """Test google_auth.py variable usage"""
    with open('google_auth.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for backwards compatibility
    if 'GOOGLE_OAUTH_CLIENT_ID' in content and 'GOOGLE_CLIENT_ID' in content:
        print("✅ google_auth.py has backwards compatibility for environment variables")
    else:
        print("❌ google_auth.py missing backwards compatibility")
        return False
    
    # Check for proper fallback logic
    if 'os.environ.get("GOOGLE_CLIENT_ID") or os.environ.get("GOOGLE_OAUTH_CLIENT_ID"' in content:
        print("✅ google_auth.py has proper fallback logic")
    else:
        print("❌ google_auth.py missing proper fallback logic")
        return False
    
    return True

def test_deployment_scripts():
    """Test deployment script consistency"""
    # Check deploy-apprunner.sh
    with open('deploy-apprunner.sh', 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'GOOGLE_OAUTH_CLIENT_ID' in content and 'GOOGLE_CLIENT_ID' in content:
        print("✅ deploy-apprunner.sh has environment variable migration")
    else:
        print("❌ deploy-apprunner.sh missing environment variable migration")
        return False
    
    return True

def main():
    """Run all tests"""
    print("🧪 Running Environment Variable Standardization Tests")
    print("=" * 55)
    print()
    
    tests = [
        test_migration_script_exists,
        test_migration_script_content,
        test_shared_managers_exists,
        test_transcript_service_cleanup,
        test_google_auth_variables,
        test_deployment_scripts,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        print(f"Running {test.__name__}...")
        try:
            if test():
                passed += 1
            print()
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with error: {e}")
            print()
    
    print("=" * 55)
    print(f"📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All tests passed!")
        print()
        print("📋 Code cleanup and environment variable standardization complete:")
        print("   - Removed duplicate manager initialization in TranscriptService")
        print("   - Standardized Google OAuth environment variable names")
        print("   - Added backwards compatibility for legacy variable names")
        print("   - Created migration script for deployment rollout")
        print("   - Updated deployment scripts for consistency")
        return True
    else:
        print(f"❌ {total - passed} tests failed!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)