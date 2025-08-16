#!/usr/bin/env python3
"""
Quick test runner for TLDW proxy and user agent functionality
Run this from the project root directory
"""

import subprocess
import sys

def main():
    """Run the proxy and user agent test suite"""
    try:
        result = subprocess.run([
            sys.executable, 'tests/run_all_tests.py'
        ], check=False)
        
        return result.returncode
    except Exception as e:
        print(f"Error running tests: {e}")
        return 1

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)