#!/usr/bin/env python3
"""
Test deployment script content and structure (Windows compatible)
"""

import os
import sys
import re

def read_script_content():
    """Read script content with proper encoding"""
    try:
        with open('deploy-apprunner.sh', 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        # Fallback to latin-1 if utf-8 fails
        with open('deploy-apprunner.sh', 'r', encoding='latin-1') as f:
            return f.read()

def test_script_exists():
    """Test that deployment script exists"""
    print("Testing deployment script exists...")
    
    if os.path.exists('deploy-apprunner.sh'):
        print("✅ Deployment script exists")
        return True
    else:
        print("❌ Deployment script not found")
        return False

def test_container_based_cache_busting():
    """Test that script uses container-based cache busting"""
    print("Testing container-based cache busting approach...")
    
    try:
        content = read_script_content()
        
        # Should use container tagging
        container_indicators = [
            'IMAGE_TAG=',
            'docker build',
            'docker push',
            'Container Cache Busting'
        ]
        
        missing = []
        for indicator in container_indicators:
            if indicator not in content:
                missing.append(indicator)
        
        if missing:
            print(f"❌ Missing container-based indicators: {missing}")
            return False
        
        # Should NOT use git tags for deployment (check for actual commands, not comments)
        git_tag_commands = [
            'git tag "$',  # Variable assignment to git tag
            'git push origin "$',  # Pushing tags
            'git push --tags'  # Pushing all tags
        ]
        
        found_git_ops = []
        for command in git_tag_commands:
            if command in content:
                found_git_ops.append(command)
        
        if found_git_ops:
            print(f"❌ Found git tag commands (should avoid): {found_git_ops}")
            return False
        
        # Check that comments mention avoiding git tags (good practice)
        if 'git tag pollution' in content or 'don\'t push git tags' in content:
            print("   ✅ Script explicitly mentions avoiding git tag pollution")
        else:
            print("   ⚠️  Script doesn't mention git tag avoidance in comments")
        
        print("✅ Script uses container-based cache busting without git tag pollution")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test cache busting: {e}")
        return False

def test_unique_image_tagging():
    """Test that script generates unique image tags"""
    print("Testing unique image tagging...")
    
    try:
        content = read_script_content()
        
        # Check for git SHA extraction
        if 'git rev-parse --short HEAD' not in content:
            print("❌ Missing git SHA extraction")
            return False
        
        # Check for timestamp generation
        if 'date +%s' not in content:
            print("❌ Missing timestamp generation")
            return False
        
        # Check for combined tag pattern
        if 'GIT_SHA' not in content or 'TIMESTAMP' not in content:
            print("❌ Missing git SHA or timestamp variables")
            return False
        
        print("✅ Script generates unique image tags with git SHA and timestamp")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test image tagging: {e}")
        return False

def test_app_runner_integration():
    """Test App Runner service integration"""
    print("Testing App Runner service integration...")
    
    try:
        content = read_script_content()
        
        # Check for App Runner operations
        apprunner_operations = [
            'apprunner update-service',
            'apprunner describe-service',
            'APPRUNNER_SERVICE_ARN'
        ]
        
        missing = []
        for operation in apprunner_operations:
            if operation not in content:
                missing.append(operation)
        
        if missing:
            print(f"❌ Missing App Runner operations: {missing}")
            return False
        
        print("✅ App Runner integration is properly configured")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test App Runner integration: {e}")
        return False

def test_error_handling():
    """Test error handling and cleanup"""
    print("Testing error handling and cleanup...")
    
    try:
        content = read_script_content()
        
        # Check for error handling
        error_handling = [
            'set -e',
            'set -euo pipefail',
            'cleanup()',
            'trap cleanup'
        ]
        
        missing = []
        for handler in error_handling:
            if handler not in content:
                missing.append(handler)
        
        if missing:
            print(f"❌ Missing error handling: {missing}")
            return False
        
        print("✅ Proper error handling and cleanup configured")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test error handling: {e}")
        return False

def test_health_check_verification():
    """Test health check verification"""
    print("Testing health check verification...")
    
    try:
        content = read_script_content()
        
        # Check for health check operations
        health_checks = [
            '/healthz',
            'curl',
            'Health check'
        ]
        
        missing = []
        for check in health_checks:
            if check not in content:
                missing.append(check)
        
        if missing:
            print(f"❌ Missing health check components: {missing}")
            return False
        
        print("✅ Health check verification is included")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test health checks: {e}")
        return False

def test_environment_variable_validation():
    """Test environment variable validation"""
    print("Testing environment variable validation...")
    
    try:
        content = read_script_content()
        
        # Check for required environment variable validation
        if 'APPRUNNER_SERVICE_ARN' not in content:
            print("❌ Missing APPRUNNER_SERVICE_ARN validation")
            return False
        
        # Check for error message when missing
        if 'environment variable is required' not in content:
            print("❌ Missing environment variable error message")
            return False
        
        print("✅ Environment variable validation is properly implemented")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test environment validation: {e}")
        return False

def test_command_line_options():
    """Test command line options"""
    print("Testing command line options...")
    
    try:
        content = read_script_content()
        
        # Check for command line options
        options = [
            '--dry-run',
            '--no-wait',
            '--timeout',
            '--help'
        ]
        
        missing = []
        for option in options:
            if option not in content:
                missing.append(option)
        
        if missing:
            print(f"❌ Missing command line options: {missing}")
            return False
        
        print("✅ Command line options are properly implemented")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test command line options: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing deployment script content and structure...")
    print()
    
    tests = [
        test_script_exists,
        test_container_based_cache_busting,
        test_unique_image_tagging,
        test_app_runner_integration,
        test_error_handling,
        test_health_check_verification,
        test_environment_variable_validation,
        test_command_line_options
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
        print("🎉 All tests passed! Deployment script is properly configured.")
        print("📝 Key features verified:")
        print("   - Container-based cache busting (no git tag pollution)")
        print("   - Unique image tags with git SHA and timestamp")
        print("   - App Runner service integration")
        print("   - Proper error handling and cleanup")
        print("   - Environment variable validation")
        print("   - Command line options support")
        print("   - Health check verification")
        sys.exit(0)
    else:
        print("💥 Some tests failed. Deployment script needs fixes.")
        sys.exit(1)