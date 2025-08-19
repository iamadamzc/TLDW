#!/usr/bin/env python3
"""
Test deployment script functionality and cache busting approach
"""

import os
import sys
import subprocess
import tempfile
from unittest.mock import patch, MagicMock

def test_deployment_script_help():
    """Test that deployment script shows help correctly"""
    print("Testing deployment script help...")
    
    try:
        result = subprocess.run(['bash', 'deploy-apprunner.sh', '--help'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            output = result.stdout
            
            # Check for key help content
            expected_content = [
                'Usage:', '--dry-run', '--no-wait', '--timeout', 
                'APPRUNNER_SERVICE_ARN', 'Container Cache Busting'
            ]
            
            for content in expected_content:
                if content not in output:
                    print(f"❌ Missing expected help content: {content}")
                    return False
            
            print("✅ Deployment script help works correctly")
            return True
        else:
            print(f"❌ Help command failed with exit code: {result.returncode}")
            print(f"Error: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Failed to test help: {e}")
        return False

def test_deployment_script_dry_run():
    """Test deployment script dry run functionality"""
    print("Testing deployment script dry run...")
    
    # Set required environment variable for dry run
    env = os.environ.copy()
    env['APPRUNNER_SERVICE_ARN'] = 'arn:aws:apprunner:us-west-2:123456789012:service/test-service/abcd1234'
    
    try:
        result = subprocess.run(['bash', 'deploy-apprunner.sh', '--dry-run'], 
                              capture_output=True, text=True, timeout=30, env=env)
        
        output = result.stdout + result.stderr
        
        # Check for dry run indicators
        dry_run_indicators = [
            '[DRY RUN]', 'Would build Docker image', 'Would push image', 
            'Would force App Runner deployment', 'Container Cache Busting'
        ]
        
        for indicator in dry_run_indicators:
            if indicator not in output:
                print(f"❌ Missing dry run indicator: {indicator}")
                return False
        
        # Should not contain actual execution
        actual_execution = ['Successfully pushed image', 'App Runner service update initiated']
        
        for execution in actual_execution:
            if execution in output:
                print(f"❌ Dry run performed actual execution: {execution}")
                return False
        
        print("✅ Deployment script dry run works correctly")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test dry run: {e}")
        return False

def test_container_tag_generation():
    """Test that container tags are generated correctly"""
    print("Testing container tag generation...")
    
    # Create a temporary git repository to test git SHA extraction
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        
        # Initialize git repo
        subprocess.run(['git', 'init'], capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], capture_output=True)
        
        # Create a test file and commit
        with open('test.txt', 'w') as f:
            f.write('test')
        
        subprocess.run(['git', 'add', 'test.txt'], capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'test commit'], capture_output=True)
        
        # Copy deployment script to temp directory
        original_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(original_dir, 'deploy-apprunner.sh')
        
        with open(script_path, 'r') as f:
            script_content = f.read()
        
        with open('deploy-apprunner.sh', 'w') as f:
            f.write(script_content)
        
        os.chmod('deploy-apprunner.sh', 0o755)
        
        # Set environment variable
        env = os.environ.copy()
        env['APPRUNNER_SERVICE_ARN'] = 'arn:aws:apprunner:us-west-2:123456789012:service/test-service/abcd1234'
        
        try:
            result = subprocess.run(['bash', 'deploy-apprunner.sh', '--dry-run'], 
                                  capture_output=True, text=True, timeout=30, env=env)
            
            output = result.stdout + result.stderr
            
            # Check for container tag format (git-sha-timestamp)
            import re
            tag_pattern = r'Container Tag: [a-f0-9]+-\d+'
            
            if re.search(tag_pattern, output):
                print("✅ Container tag generation works correctly")
                
                # Extract the tag for verification
                tag_match = re.search(r'Container Tag: ([a-f0-9]+-\d+)', output)
                if tag_match:
                    tag = tag_match.group(1)
                    print(f"   Generated tag: {tag}")
                    
                    # Verify format: git-sha-timestamp
                    parts = tag.split('-')
                    if len(parts) == 2 and len(parts[0]) >= 7 and parts[1].isdigit():
                        print("   ✅ Tag format is correct (git-sha-timestamp)")
                        return True
                    else:
                        print(f"   ❌ Tag format is incorrect: {tag}")
                        return False
                
            else:
                print("❌ Container tag not found in output")
                print(f"Output: {output}")
                return False
                
        except Exception as e:
            print(f"❌ Failed to test tag generation: {e}")
            return False

def test_no_git_tag_pollution():
    """Test that script doesn't create or push git tags"""
    print("Testing that script avoids git tag pollution...")
    
    # Read the deployment script
    try:
        with open('deploy-apprunner.sh', 'r') as f:
            script_content = f.read()
        
        # Check that script doesn't contain git tag operations
        git_tag_operations = [
            'git tag', 'git push origin', 'git push --tags'
        ]
        
        for operation in git_tag_operations:
            if operation in script_content:
                print(f"❌ Script contains git tag operation: {operation}")
                return False
        
        # Check that it uses container-based approach
        container_indicators = [
            'IMAGE_TAG=', 'docker build', 'docker push', 'GIT_SHA-TIMESTAMP'
        ]
        
        missing_indicators = []
        for indicator in container_indicators:
            if indicator not in script_content:
                missing_indicators.append(indicator)
        
        if missing_indicators:
            print(f"❌ Missing container-based indicators: {missing_indicators}")
            return False
        
        print("✅ Script uses container-based cache busting without git tag pollution")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test git tag pollution: {e}")
        return False

def test_environment_variable_requirements():
    """Test that script properly validates required environment variables"""
    print("Testing environment variable requirements...")
    
    try:
        # Test without APPRUNNER_SERVICE_ARN
        result = subprocess.run(['bash', 'deploy-apprunner.sh', '--dry-run'], 
                              capture_output=True, text=True, timeout=10)
        
        output = result.stdout + result.stderr
        
        if 'APPRUNNER_SERVICE_ARN environment variable is required' in output:
            print("✅ Script properly validates APPRUNNER_SERVICE_ARN requirement")
            return True
        else:
            print("❌ Script doesn't validate APPRUNNER_SERVICE_ARN requirement")
            print(f"Output: {output}")
            return False
            
    except Exception as e:
        print(f"❌ Failed to test environment variables: {e}")
        return False

def test_deployment_script_structure():
    """Test that deployment script has proper structure and error handling"""
    print("Testing deployment script structure...")
    
    try:
        with open('deploy-apprunner.sh', 'r') as f:
            script_content = f.read()
        
        # Check for essential components
        essential_components = [
            'set -e',  # Fail-fast mode
            'set -euo pipefail',  # Strict error handling
            'cleanup()',  # Cleanup function
            'trap cleanup EXIT',  # Trap for cleanup
            'aws apprunner update-service',  # App Runner update
            'docker build',  # Docker build
            'docker push',  # Docker push
            'Health check',  # Health verification
        ]
        
        missing_components = []
        for component in essential_components:
            if component not in script_content:
                missing_components.append(component)
        
        if missing_components:
            print(f"❌ Missing essential components: {missing_components}")
            return False
        
        print("✅ Deployment script has proper structure and error handling")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test script structure: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing deployment script functionality...")
    print()
    
    # Change to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    tests = [
        test_deployment_script_help,
        test_deployment_script_dry_run,
        test_container_tag_generation,
        test_no_git_tag_pollution,
        test_environment_variable_requirements,
        test_deployment_script_structure
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
        print("   - Proper error handling and cleanup")
        print("   - Environment variable validation")
        print("   - Dry run functionality")
        print("   - Health check verification")
        sys.exit(0)
    else:
        print("💥 Some tests failed. Deployment script needs fixes.")
        sys.exit(1)