#!/usr/bin/env python3
"""
Test runner for Oxylabs proxy auth fix
"""

import sys
import os
import subprocess

# Add parent directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

def run_test(test_file):
    """Run a single test file"""
    test_path = os.path.join(os.path.dirname(__file__), test_file)
    try:
        result = subprocess.run([sys.executable, test_path], 
                              capture_output=True, text=True, timeout=30)
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Test timed out after 30 seconds"
    except Exception as e:
        return False, "", str(e)

def main():
    """Run all proxy auth fix tests"""
    print("🧪 Running Oxylabs Proxy Auth Fix Test Suite")
    print("=" * 60)
    
    tests = [
        "test_proxy_secret_validation.py",
        "test_preflight_cache.py", 
        "test_proxy_manager.py",
        "test_health_endpoints.py",
        "test_transcript_integration.py",
        "test_youtube_download_service.py",
        "test_enhanced_407_handling.py",
        "test_ffmpeg_path_fix.py",
        "test_mvp_complete.py",
        "test_deployment_validation.py"
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        print(f"\n📋 Running {test}...")
        success, stdout, stderr = run_test(test)
        
        if success:
            passed += 1
            print(f"✅ {test} PASSED")
        else:
            failed += 1
            print(f"❌ {test} FAILED")
            if stderr:
                print(f"Error: {stderr[:200]}...")
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 ALL PROXY AUTH FIX TESTS PASSED!")
        return True
    else:
        print("❌ Some tests failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)