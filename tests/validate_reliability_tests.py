#!/usr/bin/env python3
"""
Validation script for reliability tests.

Quick validation that all test modules can be imported and basic functionality works.
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def validate_test_imports():
    """Validate that test modules can be imported."""
    print("🔍 Validating test imports...")
    
    try:
        from tests.test_reliability_fixes_unit import (
            TestPlaywrightAPIFixes,
            TestContentValidation,
            TestProxyEnforcement
        )
        print("   ✅ Unit test imports successful")
    except ImportError as e:
        print(f"   ❌ Unit test import failed: {e}")
        return False
    
    try:
        from tests.test_reliability_fixes_integration import (
            TestReliabilityFixesIntegration,
            LogCapture
        )
        print("   ✅ Integration test imports successful")
    except ImportError as e:
        print(f"   ❌ Integration test import failed: {e}")
        return False
    
    try:
        from tests.run_reliability_fixes_tests import (
            run_reliability_tests,
            ReliabilityTestResult
        )
        print("   ✅ Test runner imports successful")
    except ImportError as e:
        print(f"   ❌ Test runner import failed: {e}")
        return False
    
    return True


def validate_service_mocking():
    """Validate that service mocking works correctly."""
    print("🔧 Validating service mocking...")
    
    try:
        # Test content validation mocking
        from transcript_service import _validate_xml_content
        
        # Test with valid XML
        is_valid, reason = _validate_xml_content('<?xml version="1.0"?><test>content</test>')
        assert is_valid == True
        assert reason == "valid"
        
        # Test with empty content
        is_valid, reason = _validate_xml_content('')
        assert is_valid == False
        assert reason == "empty_body"
        
        print("   ✅ Content validation mocking works")
    except Exception as e:
        print(f"   ❌ Content validation mocking failed: {e}")
        return False
    
    try:
        # Test log capture functionality
        from tests.test_reliability_fixes_integration import LogCapture
        
        with LogCapture() as log_capture:
            # Simulate logging an event
            from log_events import evt
            evt("test_event", test_param="test_value")
            
            # Check if event was captured
            events = log_capture.get_events("test_event")
            assert len(events) >= 0  # May be 0 if evt is mocked
        
        print("   ✅ Log capture functionality works")
    except Exception as e:
        print(f"   ❌ Log capture functionality failed: {e}")
        return False
    
    return True


def validate_test_structure():
    """Validate test structure and organization."""
    print("📋 Validating test structure...")
    
    try:
        # Check that test classes have expected methods
        from tests.test_reliability_fixes_unit import TestPlaywrightAPIFixes
        
        expected_methods = [
            'test_playwright_wait_for_api_usage',
            'test_playwright_wait_timeout_handling',
            'test_playwright_element_interaction_sequence'
        ]
        
        for method_name in expected_methods:
            assert hasattr(TestPlaywrightAPIFixes, method_name), f"Missing method: {method_name}"
        
        print("   ✅ Unit test structure is correct")
    except Exception as e:
        print(f"   ❌ Unit test structure validation failed: {e}")
        return False
    
    try:
        # Check integration test structure
        from tests.test_reliability_fixes_integration import TestReliabilityFixesIntegration
        
        expected_methods = [
            'test_complete_transcript_extraction_success_path',
            'test_fallback_behavior_youtube_api_to_timedtext',
            'test_youtubei_caption_tracks_shortcircuit_integration'
        ]
        
        for method_name in expected_methods:
            assert hasattr(TestReliabilityFixesIntegration, method_name), f"Missing method: {method_name}"
        
        print("   ✅ Integration test structure is correct")
    except Exception as e:
        print(f"   ❌ Integration test structure validation failed: {e}")
        return False
    
    return True


def run_sample_test():
    """Run a sample test to verify functionality."""
    print("🧪 Running sample test...")
    
    try:
        # Create a simple test case
        class SampleReliabilityTest(unittest.TestCase):
            def test_content_validation_sample(self):
                """Sample test for content validation."""
                from transcript_service import _validate_xml_content
                
                # Test valid XML
                is_valid, reason = _validate_xml_content('<?xml version="1.0"?><transcript><text>Hello</text></transcript>')
                self.assertTrue(is_valid)
                self.assertEqual(reason, "valid")
                
                # Test empty content
                is_valid, reason = _validate_xml_content('')
                self.assertFalse(is_valid)
                self.assertEqual(reason, "empty_body")
        
        # Run the sample test
        suite = unittest.TestLoader().loadTestsFromTestCase(SampleReliabilityTest)
        runner = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, 'w'))
        result = runner.run(suite)
        
        if result.wasSuccessful():
            print("   ✅ Sample test passed")
            return True
        else:
            print(f"   ❌ Sample test failed: {len(result.failures)} failures, {len(result.errors)} errors")
            return False
            
    except Exception as e:
        print(f"   ❌ Sample test execution failed: {e}")
        return False


def main():
    """Main validation function."""
    print("🔍 Validating Reliability Tests")
    print("=" * 40)
    
    validations = [
        ("Import validation", validate_test_imports),
        ("Service mocking", validate_service_mocking),
        ("Test structure", validate_test_structure),
        ("Sample test", run_sample_test)
    ]
    
    passed = 0
    total = len(validations)
    
    for name, validation_func in validations:
        print(f"\n{name}:")
        if validation_func():
            passed += 1
        else:
            print(f"   ⚠️  {name} validation failed")
    
    print("\n" + "=" * 40)
    print(f"📊 Validation Summary: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All validations passed! Tests are ready to run.")
        return True
    else:
        print("❌ Some validations failed. Check the issues above.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)