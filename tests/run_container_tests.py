#!/usr/bin/env python3
"""
Simple test runner for container deployment tests
"""

import subprocess
import sys
import os

def run_test_suite():
    """Run the container deployment test suite"""
    print("🧪 Running Container Deployment MVP Tests")
    print("=" * 50)
    
    # Ensure we're in the right directory
    if not os.path.exists("test_container_deployment.py"):
        print("❌ test_container_deployment.py not found")
        print("Make sure you're running this from the project root directory")
        return False
    
    try:
        # Run the test suite
        result = subprocess.run([
            sys.executable, "test_container_deployment.py"
        ], check=False)
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False

def main():
    """Main entry point"""
    success = run_test_suite()
    
    if success:
        print("\n🎉 All container deployment tests passed!")
        print("✅ Ready for deployment to App Runner")
    else:
        print("\n💥 Some tests failed!")
        print("❌ Fix issues before deploying to App Runner")
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()