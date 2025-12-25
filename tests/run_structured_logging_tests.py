#!/usr/bin/env python3
"""
Simple test runner for structured JSON logging comprehensive test suite.

This script runs all the comprehensive tests for the structured logging
implementation without requiring external dependencies like psutil.
"""

import unittest
import sys
import os
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_comprehensive_tests():
    """Run the comprehensive test suite."""
    print("="*80)
    print("STRUCTURED JSON LOGGING - COMPREHENSIVE TEST SUITE")
    print("="*80)
    print()
    
    # Test modules to run
    test_modules = [
        'tests.test_structured_logging_comprehensive',
        'tests.test_cloudwatch_query_validation', 
        'tests.test_pipeline_logging_integration',
    ]
    
    # Performance tests (may skip some if psutil not available)
    performance_modules = [
        'tests.test_logging_performance',
    ]
    
    total_tests = 0
    total_failures = 0
    total_errors = 0
    start_time = time.time()
    
    # Run main test modules
    print("Running Core Tests...")
    print("-" * 40)
    
    for module_name in test_modules:
        print(f"\nRunning {module_name}...")
        
        try:
            # Load and run tests from module
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromName(module_name)
            runner = unittest.TextTestRunner(verbosity=1, stream=sys.stdout)
            result = runner.run(suite)
            
            total_tests += result.testsRun
            total_failures += len(result.failures)
            total_errors += len(result.errors)
            
            if result.failures:
                print(f"  ❌ {len(result.failures)} failures")
            if result.errors:
                print(f"  ❌ {len(result.errors)} errors")
            if not result.failures and not result.errors:
                print(f"  ✅ All {result.testsRun} tests passed")
                
        except Exception as e:
            print(f"  ❌ Error loading module: {e}")
            total_errors += 1
    
    # Run performance tests
    print(f"\n\nRunning Performance Tests...")
    print("-" * 40)
    
    for module_name in performance_modules:
        print(f"\nRunning {module_name}...")
        
        try:
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromName(module_name)
            runner = unittest.TextTestRunner(verbosity=1, stream=sys.stdout)
            result = runner.run(suite)
            
            total_tests += result.testsRun
            total_failures += len(result.failures)
            total_errors += len(result.errors)
            
            if result.failures:
                print(f"  ❌ {len(result.failures)} failures")
            if result.errors:
                print(f"  ❌ {len(result.errors)} errors")
            if not result.failures and not result.errors:
                print(f"  ✅ All {result.testsRun} tests passed")
                
        except Exception as e:
            print(f"  ❌ Error loading module: {e}")
            total_errors += 1
    
    # Print summary
    end_time = time.time()
    duration = end_time - start_time
    
    print("\n" + "="*80)
    print("TEST SUITE SUMMARY")
    print("="*80)
    print(f"Total Tests Run: {total_tests}")
    print(f"Failures: {total_failures}")
    print(f"Errors: {total_errors}")
    print(f"Duration: {duration:.2f} seconds")
    
    if total_failures == 0 and total_errors == 0:
        print("\n🎉 ALL TESTS PASSED!")
        print("\nStructured JSON logging implementation is ready for deployment.")
        return True
    else:
        print(f"\n❌ {total_failures + total_errors} TESTS FAILED")
        print("\nPlease review the failures above before deployment.")
        return False


def run_specific_requirement_tests():
    """Run tests for specific requirements."""
    print("\n" + "="*80)
    print("REQUIREMENT-SPECIFIC TEST VALIDATION")
    print("="*80)
    
    # Key requirement tests to validate
    requirement_tests = [
        ('1.1 - JSON Schema', 'tests.test_structured_logging_comprehensive.TestJsonFormatterComprehensive.test_requirement_1_1_standardized_json_schema'),
        ('1.2 - Timestamp Format', 'tests.test_structured_logging_comprehensive.TestJsonFormatterComprehensive.test_requirement_1_2_iso8601_timestamp_format'),
        ('2.4 - Thread Isolation', 'tests.test_structured_logging_comprehensive.TestContextManagementComprehensive.test_requirement_2_4_thread_isolation'),
        ('3.1 - Rate Limiting', 'tests.test_structured_logging_comprehensive.TestRateLimitingComprehensive.test_requirement_3_1_rate_limit_enforcement'),
        ('4.1 - Stage Timer', 'tests.test_structured_logging_comprehensive.TestStageTimerComprehensive.test_requirement_4_1_stage_start_event_emission'),
        ('7.1 - CloudWatch Queries', 'tests.test_cloudwatch_query_validation.TestCloudWatchQueryValidation.test_requirement_7_1_error_analysis_query'),
        ('10.5 - Job Lifecycle', 'tests.test_pipeline_logging_integration.TestPipelineLoggingIntegration.test_requirement_10_5_complete_job_lifecycle_trace'),
    ]
    
    passed_requirements = 0
    
    for req_name, test_name in requirement_tests:
        print(f"\nTesting {req_name}...")
        
        try:
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromName(test_name)
            
            # Run with minimal output
            stream = open(os.devnull, 'w')
            runner = unittest.TextTestRunner(verbosity=0, stream=stream)
            result = runner.run(suite)
            stream.close()
            
            if result.wasSuccessful():
                print(f"  ✅ PASSED")
                passed_requirements += 1
            else:
                print(f"  ❌ FAILED")
                if result.failures:
                    print(f"    Failures: {len(result.failures)}")
                if result.errors:
                    print(f"    Errors: {len(result.errors)}")
        
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
    
    print(f"\nRequirement Validation: {passed_requirements}/{len(requirement_tests)} passed")
    
    return passed_requirements == len(requirement_tests)


def main():
    """Main test runner."""
    print("Starting Structured JSON Logging Test Suite...")
    
    # Run comprehensive tests
    comprehensive_passed = run_comprehensive_tests()
    
    # Run requirement-specific validation
    requirements_passed = run_specific_requirement_tests()
    
    # Final summary
    print("\n" + "="*80)
    print("FINAL RESULTS")
    print("="*80)
    
    if comprehensive_passed and requirements_passed:
        print("✅ ALL TESTS PASSED - Implementation is ready!")
        print("\nTask 12 (Create Comprehensive Test Suite) is COMPLETE.")
        print("\nThe structured JSON logging system has been thoroughly tested and validated.")
        return 0
    else:
        print("❌ SOME TESTS FAILED - Please review and fix issues.")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)