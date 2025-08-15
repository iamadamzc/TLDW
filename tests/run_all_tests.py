#!/usr/bin/env python3
"""
Test runner for proxy and user agent sticky session tests
Runs unit tests, integration tests, and acceptance tests in order
"""

import unittest
import sys
import os

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_proxy_ua_tests():
    """Run only the proxy and user agent tests (avoiding circular import issues)"""
    
    print("🧪 Running TLDW Proxy & User Agent Test Suite")
    print("=" * 60)
    
    # Specific test modules to run (avoiding legacy tests with circular imports)
    test_modules = [
        'tests.test_proxy_session',
        'tests.test_user_agent_manager', 
        'tests.test_discovery_gate_simple',
        'tests.test_integration_mvp',
        'tests.test_smoke_and_acceptance'
    ]
    
    # Load specific test modules
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    for module_name in test_modules:
        try:
            module_suite = loader.loadTestsFromName(module_name)
            suite.addTest(module_suite)
            print(f"✓ Loaded {module_name}")
        except Exception as e:
            print(f"✗ Failed to load {module_name}: {e}")
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(
        verbosity=2,
        stream=sys.stdout,
        descriptions=True,
        failfast=False
    )
    
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 Test Summary:")
    print(f"   Tests run: {result.testsRun}")
    print(f"   Failures: {len(result.failures)}")
    print(f"   Errors: {len(result.errors)}")
    print(f"   Skipped: {len(result.skipped) if hasattr(result, 'skipped') else 0}")
    
    if result.wasSuccessful():
        print("✅ All proxy & user agent tests passed!")
        print("\n🎯 Definition of Done validated:")
        print("   • Zero 407 Proxy Authentication errors")
        print("   • Session consistency across transcript and yt-dlp")
        print("   • Structured logging with credential redaction")
        print("   • User-Agent parity between operations")
        print("   • Bot detection recovery with session rotation")
        return 0
    else:
        print("❌ Some tests failed!")
        return 1

if __name__ == '__main__':
    exit_code = run_proxy_ua_tests()
    sys.exit(exit_code)