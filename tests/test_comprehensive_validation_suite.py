#!/usr/bin/env python3
"""
Comprehensive Validation Suite for Transcript Service Enhancements
===================================================================

This is the master test suite that runs all validation tests for the
transcript service enhancements. It validates all requirements and
provides a comprehensive report.
"""

import os
import sys
import unittest
import subprocess
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestSuiteRunner:
    """Runs all validation test suites and provides comprehensive reporting"""
    
    def __init__(self):
        self.test_dir = Path(__file__).parent
        self.results = {}
        
    def run_test_suite(self, test_file, description):
        """Run a specific test suite and capture results"""
        print(f"\n{'='*80}")
        print(f"Running: {description}")
        print(f"File: {test_file}")
        print(f"{'='*80}")
        
        start_time = time.time()
        
        try:
            # Run the test file
            result = subprocess.run([
                sys.executable, str(self.test_dir / test_file)
            ], capture_output=True, text=True, timeout=300)
            
            duration = time.time() - start_time
            
            success = result.returncode == 0
            
            self.results[test_file] = {
                'description': description,
                'success': success,
                'duration': duration,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }
            
            if success:
                print(f"✅ {description} - PASSED ({duration:.2f}s)")
            else:
                print(f"❌ {description} - FAILED ({duration:.2f}s)")
                print(f"Return code: {result.returncode}")
                if result.stderr:
                    print(f"Errors: {result.stderr[:500]}...")
                    
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            self.results[test_file] = {
                'description': description,
                'success': False,
                'duration': duration,
                'stdout': '',
                'stderr': 'Test timed out after 300 seconds',
                'returncode': -1
            }
            print(f"⏰ {description} - TIMEOUT ({duration:.2f}s)")
            
        except Exception as e:
            duration = time.time() - start_time
            self.results[test_file] = {
                'description': description,
                'success': False,
                'duration': duration,
                'stdout': '',
                'stderr': str(e),
                'returncode': -2
            }
            print(f"💥 {description} - ERROR ({duration:.2f}s): {e}")
    
    def run_all_validation_tests(self):
        """Run all validation test suites"""
        print("Comprehensive Validation Suite for Transcript Service Enhancements")
        print("=" * 80)
        print("This suite validates all requirements from the transcript-service-enhancements spec")
        print("=" * 80)
        
        # Define all test suites to run
        test_suites = [
            # Core integration tests
            ('test_transcript_service_enhancements_integration.py', 
             'Core Integration Tests - All Enhanced Functionality'),
            
            # Specific component validation
            ('test_storage_state_validation.py', 
             'Storage State Management - Requirements 1, 11, 12, 13'),
            
            ('test_deterministic_interception_validation.py', 
             'Deterministic Interception - Requirement 2'),
            
            # Existing component tests that validate enhancements
            ('test_multi_client_profiles.py', 
             'Multi-Client Profile System - Requirement 3'),
            
            ('test_enhanced_timedtext_cookies.py', 
             'Enhanced Cookie Integration - Requirement 4'),
            
            ('test_circuit_breaker_integration.py', 
             'Circuit Breaker Integration - Requirement 6'),
            
            ('test_dom_fallback_integration.py', 
             'DOM Fallback Implementation - Requirement 7'),
            
            ('test_proxy_enforced_ffmpeg.py', 
             'Proxy-Enforced FFmpeg - Requirement 8'),
            
            ('test_ffmpeg_header_hygiene.py', 
             'FFmpeg Header Hygiene - Requirement 9'),
            
            ('test_proxy_health_metrics.py', 
             'Proxy Health Metrics - Requirement 16'),
            
            ('test_task_17_tenacity_retry_implementation.py', 
             'Tenacity Retry Implementation - Requirement 17'),
            
            # Additional existing tests that validate enhanced functionality
            ('test_enhanced_transcript_integration.py',
             'Enhanced Transcript Integration - Multiple Requirements'),
            
            ('test_end_to_end_transcript.py',
             'End-to-End Transcript Validation'),
            
            ('test_cookie_integration.py',
             'Cookie Integration Validation'),
            
            ('test_proxy_functionality.py',
             'Proxy Functionality Validation'),
        ]
        
        # Run each test suite
        for test_file, description in test_suites:
            if (self.test_dir / test_file).exists():
                self.run_test_suite(test_file, description)
            else:
                print(f"⚠️  Test file not found: {test_file}")
                self.results[test_file] = {
                    'description': description,
                    'success': False,
                    'duration': 0,
                    'stdout': '',
                    'stderr': f'Test file not found: {test_file}',
                    'returncode': -3
                }
    
    def generate_comprehensive_report(self):
        """Generate comprehensive validation report"""
        print("\n" + "=" * 80)
        print("📊 COMPREHENSIVE VALIDATION REPORT")
        print("=" * 80)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results.values() if r['success'])
        failed_tests = total_tests - passed_tests
        total_duration = sum(r['duration'] for r in self.results.values())
        
        print(f"Total Test Suites: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Total Duration: {total_duration:.2f}s")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
        
        print("\n" + "-" * 80)
        print("DETAILED RESULTS BY REQUIREMENT:")
        print("-" * 80)
        
        # Map test files to requirements
        requirement_mapping = {
            'test_storage_state_validation.py': ['Req 1: Storage State Management', 'Req 11: Netscape Conversion', 'Req 12: Host Cookie Sanitation', 'Req 13: Consent Cookie Injection'],
            'test_deterministic_interception_validation.py': ['Req 2: Deterministic Interception'],
            'test_multi_client_profiles.py': ['Req 3: Multi-Client Profiles'],
            'test_enhanced_timedtext_cookies.py': ['Req 4: Enhanced Cookie Integration'],
            'test_circuit_breaker_integration.py': ['Req 6: Circuit Breaker Integration'],
            'test_dom_fallback_integration.py': ['Req 7: DOM Fallback'],
            'test_proxy_enforced_ffmpeg.py': ['Req 8: Proxy-Enforced FFmpeg'],
            'test_ffmpeg_header_hygiene.py': ['Req 9: FFmpeg Header Hygiene'],
            'test_proxy_health_metrics.py': ['Req 16: Proxy Health Metrics'],
            'test_task_17_tenacity_retry_implementation.py': ['Req 17: Tenacity Retry Wrapper'],
            'test_transcript_service_enhancements_integration.py': ['All Requirements Integration']
        }
        
        for test_file, result in self.results.items():
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            duration = f"{result['duration']:.2f}s"
            
            print(f"{status} {test_file} ({duration})")
            print(f"     {result['description']}")
            
            if test_file in requirement_mapping:
                for req in requirement_mapping[test_file]:
                    req_status = "✅" if result['success'] else "❌"
                    print(f"     {req_status} {req}")
            
            if not result['success'] and result['stderr']:
                print(f"     Error: {result['stderr'][:200]}...")
            
            print()
        
        print("-" * 80)
        print("REQUIREMENTS COVERAGE SUMMARY:")
        print("-" * 80)
        
        requirements_status = {
            'Requirement 1: Enhanced Storage State Management': self.results.get('test_storage_state_validation.py', {}).get('success', False),
            'Requirement 2: Deterministic YouTubei Capture': self.results.get('test_deterministic_interception_validation.py', {}).get('success', False),
            'Requirement 3: Multi-Client Profile Support': self.results.get('test_multi_client_profiles.py', {}).get('success', False),
            'Requirement 4: Enhanced Cookie Integration': self.results.get('test_enhanced_timedtext_cookies.py', {}).get('success', False),
            'Requirement 5: Complete HTTP Adapter Config': self.results.get('test_transcript_service_enhancements_integration.py', {}).get('success', False),
            'Requirement 6: Circuit Breaker Integration': self.results.get('test_circuit_breaker_integration.py', {}).get('success', False),
            'Requirement 7: DOM Fallback Implementation': self.results.get('test_dom_fallback_integration.py', {}).get('success', False),
            'Requirement 8: Proxy-Enforced FFmpeg': self.results.get('test_proxy_enforced_ffmpeg.py', {}).get('success', False),
            'Requirement 9: FFmpeg Header Hygiene': self.results.get('test_ffmpeg_header_hygiene.py', {}).get('success', False),
            'Requirement 10: Comprehensive Metrics': self.results.get('test_transcript_service_enhancements_integration.py', {}).get('success', False),
            'Requirement 11: Netscape Conversion': self.results.get('test_storage_state_validation.py', {}).get('success', False),
            'Requirement 12: Host Cookie Sanitation': self.results.get('test_storage_state_validation.py', {}).get('success', False),
            'Requirement 13: Consent Cookie Injection': self.results.get('test_storage_state_validation.py', {}).get('success', False),
            'Requirement 14: Proxy Environment Builder': self.results.get('test_transcript_service_enhancements_integration.py', {}).get('success', False),
            'Requirement 15: Unified Proxy Interface': self.results.get('test_transcript_service_enhancements_integration.py', {}).get('success', False),
            'Requirement 16: Proxy Health Metrics': self.results.get('test_proxy_health_metrics.py', {}).get('success', False),
            'Requirement 17: Tenacity Retry Wrapper': self.results.get('test_task_17_tenacity_retry_implementation.py', {}).get('success', False),
        }
        
        for requirement, status in requirements_status.items():
            status_icon = "✅" if status else "❌"
            print(f"{status_icon} {requirement}")
        
        validated_requirements = sum(1 for status in requirements_status.values() if status)
        total_requirements = len(requirements_status)
        
        print(f"\nRequirements Validated: {validated_requirements}/{total_requirements}")
        print(f"Requirements Coverage: {(validated_requirements/total_requirements*100):.1f}%")
        
        return passed_tests == total_tests and validated_requirements == total_requirements
    
    def generate_failure_analysis(self):
        """Generate detailed failure analysis"""
        failed_tests = {k: v for k, v in self.results.items() if not v['success']}
        
        if not failed_tests:
            return
        
        print("\n" + "=" * 80)
        print("🔍 FAILURE ANALYSIS")
        print("=" * 80)
        
        for test_file, result in failed_tests.items():
            print(f"\n❌ FAILED: {test_file}")
            print(f"Description: {result['description']}")
            print(f"Return Code: {result['returncode']}")
            print(f"Duration: {result['duration']:.2f}s")
            
            if result['stderr']:
                print(f"Error Output:")
                print("-" * 40)
                print(result['stderr'][:1000])
                if len(result['stderr']) > 1000:
                    print("... (truncated)")
                print("-" * 40)
            
            if result['stdout']:
                print(f"Standard Output (last 500 chars):")
                print("-" * 40)
                print(result['stdout'][-500:])
                print("-" * 40)


def main():
    """Run comprehensive validation suite"""
    runner = TestSuiteRunner()
    
    # Run all validation tests
    runner.run_all_validation_tests()
    
    # Generate comprehensive report
    all_passed = runner.generate_comprehensive_report()
    
    # Generate failure analysis if needed
    runner.generate_failure_analysis()
    
    # Final summary
    print("\n" + "=" * 80)
    if all_passed:
        print("ALL VALIDATION TESTS PASSED!")
        print("Transcript Service Enhancements are fully validated")
        print("All requirements have been successfully implemented and tested")
        print("\nReady for production deployment!")
    else:
        print("SOME VALIDATION TESTS FAILED")
        print("Review the failure analysis above")
        print("Fix failing tests before deployment")
        print("\nAdditional work required before production deployment")
    
    print("=" * 80)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())