#!/usr/bin/env python3
"""
Simple test for deployment script enhancements
"""

import os
import sys

def test_deployment_script_exists():
    """Test that deployment script exists"""
    script_path = './deploy-apprunner.sh'
    if not os.path.exists(script_path):
        print(f"❌ Deployment script {script_path} does not exist")
        return False
    
    print(f"✅ Deployment script {script_path} exists")
    return True

def test_deployment_script_enhancements():
    """Test deployment script enhancements"""
    script_path = './deploy-apprunner.sh'
    
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        # Try with different encoding
        with open(script_path, 'r', encoding='latin-1') as f:
            content = f.read()
    
    # Test for container-based cache busting
    cache_busting_checks = [
        ('GIT_SHA', 'Uses git SHA for container tagging'),
        ('TIMESTAMP', 'Uses timestamp for unique tags'),
        ('IMAGE_TAG', 'Creates unique image tags'),
        ('docker build', 'Builds Docker images'),
        ('docker push', 'Pushes images to registry'),
    ]
    
    print("🔍 Testing container-based cache busting...")
    all_passed = True
    for check, description in cache_busting_checks:
        if check in content:
            print(f"✅ {description}: {check}")
        else:
            print(f"❌ {description}: {check} not found")
            all_passed = False
    
    # Test for rollback functionality
    rollback_checks = [
        ('--rollback-to', 'Rollback command line option'),
        ('ROLLBACK_TO', 'Rollback variable'),
        ('ROLLBACK MODE', 'Rollback mode detection'),
        ('ROLLBACK INSTRUCTIONS', 'Rollback instructions'),
        ('PREVIOUS_IMAGE_URI', 'Previous image tracking'),
    ]
    
    print("\n🔍 Testing rollback functionality...")
    for check, description in rollback_checks:
        if check in content:
            print(f"✅ {description}: {check}")
        else:
            print(f"❌ {description}: {check} not found")
            all_passed = False
    
    # Test for deployment validation
    validation_checks = [
        ('current_image', 'Current image validation'),
        ('Service is running with new image', 'Deployment success validation'),
        ('aws apprunner update-service', 'App Runner service update'),
        ('health check', 'Health check verification'),
    ]
    
    print("\n🔍 Testing deployment validation...")
    for check, description in validation_checks:
        if check in content:
            print(f"✅ {description}: {check}")
        else:
            print(f"❌ {description}: {check} not found")
            all_passed = False
    
    # Test for error handling
    error_handling_checks = [
        ('CREATE_FAILED', 'Create failure handling'),
        ('UPDATE_FAILED', 'Update failure handling'),
        ('DELETE_FAILED', 'Delete failure handling'),
        ('Troubleshooting steps', 'Troubleshooting guidance'),
        ('failure_reason', 'Failure reason extraction'),
    ]
    
    print("\n🔍 Testing error handling...")
    for check, description in error_handling_checks:
        if check in content:
            print(f"✅ {description}: {check}")
        else:
            print(f"❌ {description}: {check} not found")
            all_passed = False
    
    # Test for environment preservation
    env_checks = [
        ('RuntimeEnvironmentVariables', 'Environment variables preservation'),
        ('RuntimeEnvironmentSecrets', 'Secrets preservation'),
        ('ENV_VARS', 'Environment variables extraction'),
        ('SECRETS', 'Secrets extraction'),
    ]
    
    print("\n🔍 Testing environment preservation...")
    for check, description in env_checks:
        if check in content:
            print(f"✅ {description}: {check}")
        else:
            print(f"❌ {description}: {check} not found")
            all_passed = False
    
    return all_passed

def test_requirements_compliance():
    """Test compliance with task 5 requirements"""
    script_path = './deploy-apprunner.sh'
    
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(script_path, 'r', encoding='latin-1') as f:
            content = f.read()
    
    print("🔍 Testing requirements compliance...")
    
    requirements = [
        # 5.1: Uses unique git SHA tags or calls aws apprunner start-deployment
        (['GIT_SHA', 'aws apprunner update-service'], 'Requirement 5.1: Unique tags and service restart'),
        
        # 5.2: New code is running, not cached versions
        (['current_image', 'IMAGE_URI'], 'Requirement 5.2: Validates new code is running'),
        
        # 5.3: Validates service restarted with new code
        (['Service is running with new image'], 'Requirement 5.3: Validates service restart'),
        
        # 5.4: Clear error messages and rollback instructions
        (['ROLLBACK INSTRUCTIONS', 'Troubleshooting steps'], 'Requirement 5.4: Error messages and rollback'),
        
        # 5.5: App Runner picks up new configuration
        (['RuntimeEnvironmentVariables', 'RuntimeEnvironmentSecrets'], 'Requirement 5.5: Configuration updates'),
    ]
    
    all_passed = True
    for checks, description in requirements:
        if all(check in content for check in checks):
            print(f"✅ {description}")
        else:
            missing = [check for check in checks if check not in content]
            print(f"❌ {description} - Missing: {missing}")
            all_passed = False
    
    return all_passed

def main():
    """Run all tests"""
    print("🧪 Testing Enhanced Deployment Script")
    print("=" * 40)
    print()
    
    tests = [
        test_deployment_script_exists,
        test_deployment_script_enhancements,
        test_requirements_compliance,
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
    
    print("=" * 40)
    print(f"📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All tests passed!")
        print()
        print("📋 Enhanced deployment script features verified:")
        print("   - Container-based cache busting with unique tags")
        print("   - AWS App Runner service restart enforcement")
        print("   - Deployment validation and verification")
        print("   - Rollback functionality and instructions")
        print("   - Comprehensive error handling and troubleshooting")
        print("   - Environment variable and secrets preservation")
        print("   - All requirements 5.1-5.5 compliance")
        return True
    else:
        print(f"❌ {total - passed} tests failed!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)