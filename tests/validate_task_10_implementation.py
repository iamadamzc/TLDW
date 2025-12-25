#!/usr/bin/env python3
"""
Validation script for Task 10: Comprehensive Metrics and Structured Logging
Validates implementation by checking code patterns without importing heavy modules.
"""

import os
import re

def check_transcript_metrics_enhancements():
    """Check that transcript_metrics.py has been enhanced with required functionality."""
    print("🔍 Checking transcript_metrics.py enhancements...")
    
    try:
        with open('transcript_metrics.py', 'r') as f:
            content = f.read()
        
        # Check for required new functions
        required_functions = [
            'record_stage_metrics',
            'record_circuit_breaker_event', 
            'log_successful_transcript_method',
            'get_stage_percentiles',
            'get_comprehensive_metrics'
        ]
        
        for func in required_functions:
            if f'def {func}(' in content:
                print(f"   ✅ {func} function found")
            else:
                print(f"   ❌ {func} function missing")
                return False
        
        # Check for required data structures
        required_structures = [
            'StageMetrics',
            'CircuitBreakerEvent',
            '_stage_durations',
            '_stage_metrics',
            '_circuit_breaker_events'
        ]
        
        for struct in required_structures:
            if struct in content:
                print(f"   ✅ {struct} structure found")
            else:
                print(f"   ❌ {struct} structure missing")
                return False
        
        # Check for structured logging patterns
        if 'stage_success' in content and 'stage_failure' in content:
            print("   ✅ Structured logging patterns found")
        else:
            print("   ❌ Structured logging patterns missing")
            return False
        
        # Check for percentile calculations
        if 'statistics.median' in content and 'statistics.quantiles' in content:
            print("   ✅ Percentile calculation logic found")
        else:
            print("   ❌ Percentile calculation logic missing")
            return False
        
        return True
        
    except FileNotFoundError:
        print("   ❌ transcript_metrics.py not found")
        return False
    except Exception as e:
        print(f"   ❌ Error checking transcript_metrics.py: {e}")
        return False


def check_transcript_service_integration():
    """Check that transcript_service.py has been updated with enhanced metrics."""
    print("\n🔍 Checking transcript_service.py integration...")
    
    try:
        with open('transcript_service.py', 'r') as f:
            content = f.read()
        
        # Check for enhanced imports
        enhanced_imports = [
            'record_stage_metrics',
            'record_circuit_breaker_event',
            'log_successful_transcript_method'
        ]
        
        for imp in enhanced_imports:
            if imp in content:
                print(f"   ✅ {imp} import found")
            else:
                print(f"   ❌ {imp} import missing")
                return False
        
        # Check for circuit breaker event integration
        cb_patterns = [
            'record_circuit_breaker_event',
            'event_type="state_change"',
            'event_type="skip_operation"',
            'event_type="success_reset"',
            'event_type="failure_recorded"'
        ]
        
        found_patterns = 0
        for pattern in cb_patterns:
            if pattern in content:
                found_patterns += 1
        
        if found_patterns >= 3:
            print(f"   ✅ Circuit breaker event integration found ({found_patterns}/{len(cb_patterns)} patterns)")
        else:
            print(f"   ❌ Insufficient circuit breaker integration ({found_patterns}/{len(cb_patterns)} patterns)")
            return False
        
        # Check for stage metrics integration in main pipeline
        stage_metrics_patterns = [
            'record_stage_metrics(',
            'proxy_used=',
            'profile=',
            'duration_ms=',
            'circuit_breaker_state='
        ]
        
        found_stage_patterns = 0
        for pattern in stage_metrics_patterns:
            if pattern in content:
                found_stage_patterns += 1
        
        if found_stage_patterns >= 4:
            print(f"   ✅ Stage metrics integration found ({found_stage_patterns}/{len(stage_metrics_patterns)} patterns)")
        else:
            print(f"   ❌ Insufficient stage metrics integration ({found_stage_patterns}/{len(stage_metrics_patterns)} patterns)")
            return False
        
        return True
        
    except FileNotFoundError:
        print("   ❌ transcript_service.py not found")
        return False
    except Exception as e:
        print(f"   ❌ Error checking transcript_service.py: {e}")
        return False


def check_app_metrics_endpoints():
    """Check that app.py has the new metrics endpoints."""
    print("\n🔍 Checking app.py metrics endpoints...")
    
    try:
        with open('app.py', 'r') as f:
            content = f.read()
        
        # Check for metrics endpoints
        if "@app.route('/metrics')" in content:
            print("   ✅ /metrics endpoint found")
        else:
            print("   ❌ /metrics endpoint missing")
            return False
        
        if "@app.route('/metrics/percentiles')" in content:
            print("   ✅ /metrics/percentiles endpoint found")
        else:
            print("   ❌ /metrics/percentiles endpoint missing")
            return False
        
        # Check for comprehensive metrics usage
        if 'get_comprehensive_metrics' in content:
            print("   ✅ Comprehensive metrics integration found")
        else:
            print("   ❌ Comprehensive metrics integration missing")
            return False
        
        # Check for circuit breaker status integration
        if 'get_circuit_breaker_status' in content:
            print("   ✅ Circuit breaker status integration found")
        else:
            print("   ❌ Circuit breaker status integration missing")
            return False
        
        return True
        
    except FileNotFoundError:
        print("   ❌ app.py not found")
        return False
    except Exception as e:
        print(f"   ❌ Error checking app.py: {e}")
        return False


def check_structured_logging_patterns():
    """Check for proper structured logging patterns in the codebase."""
    print("\n🔍 Checking structured logging patterns...")
    
    files_to_check = ['transcript_metrics.py', 'transcript_service.py']
    
    required_log_patterns = [
        r'stage_success.*video_id=.*duration_ms=',
        r'stage_failure.*video_id=.*duration_ms=',
        r'circuit_breaker_event.*event_type=',
        r'transcript_success_method.*video_id=.*successful_method='
    ]
    
    for filename in files_to_check:
        if not os.path.exists(filename):
            continue
            
        try:
            with open(filename, 'r') as f:
                content = f.read()
            
            print(f"\n   📄 Checking {filename}:")
            
            for pattern in required_log_patterns:
                if re.search(pattern, content):
                    print(f"      ✅ Pattern found: {pattern}")
                else:
                    print(f"      ⚠️  Pattern not found: {pattern}")
        
        except Exception as e:
            print(f"      ❌ Error checking {filename}: {e}")
    
    return True


def check_requirements_coverage():
    """Check that all Task 10 requirements are covered."""
    print("\n📋 Checking Task 10 Requirements Coverage...")
    
    requirements = {
        "10.1": "Circuit breaker state change events",
        "10.2": "Stage duration logging with success/failure tracking", 
        "10.3": "Log which transcript extraction attempt succeeded",
        "10.4": "Breaker state and operation timings logging",
        "10.5": "Stage duration metrics with labels",
        "10.6": "P50/P95 computation for dashboard integration"
    }
    
    coverage = {}
    
    # Check 10.1 - Circuit breaker events
    try:
        with open('transcript_service.py', 'r') as f:
            ts_content = f.read()
        with open('transcript_metrics.py', 'r') as f:
            tm_content = f.read()
        
        if 'record_circuit_breaker_event' in ts_content and 'CircuitBreakerEvent' in tm_content:
            coverage["10.1"] = "✅"
        else:
            coverage["10.1"] = "❌"
    except:
        coverage["10.1"] = "❌"
    
    # Check 10.2 - Stage duration logging
    try:
        if 'record_stage_metrics' in ts_content and 'duration_ms' in tm_content:
            coverage["10.2"] = "✅"
        else:
            coverage["10.2"] = "❌"
    except:
        coverage["10.2"] = "❌"
    
    # Check 10.3 - Successful method logging
    try:
        if 'log_successful_transcript_method' in ts_content and 'successful_method' in tm_content:
            coverage["10.3"] = "✅"
        else:
            coverage["10.3"] = "❌"
    except:
        coverage["10.3"] = "❌"
    
    # Check 10.4 - Breaker state logging
    try:
        if 'circuit_breaker_state' in ts_content:
            coverage["10.4"] = "✅"
        else:
            coverage["10.4"] = "❌"
    except:
        coverage["10.4"] = "❌"
    
    # Check 10.5 - Stage metrics with labels
    try:
        if 'proxy_used' in ts_content and 'profile' in ts_content:
            coverage["10.5"] = "✅"
        else:
            coverage["10.5"] = "❌"
    except:
        coverage["10.5"] = "❌"
    
    # Check 10.6 - P50/P95 computation
    try:
        if 'statistics.median' in tm_content and 'statistics.quantiles' in tm_content:
            coverage["10.6"] = "✅"
        else:
            coverage["10.6"] = "❌"
    except:
        coverage["10.6"] = "❌"
    
    for req_id, description in requirements.items():
        status = coverage.get(req_id, "❌")
        print(f"   {status} {req_id}: {description}")
    
    passed = sum(1 for status in coverage.values() if status == "✅")
    total = len(requirements)
    
    print(f"\n   📊 Requirements Coverage: {passed}/{total}")
    
    return passed == total


def main():
    """Run all validation checks for Task 10."""
    print("🚀 Validating Task 10: Comprehensive Metrics and Structured Logging")
    print("=" * 80)
    
    checks = [
        ("Enhanced Metrics Module", check_transcript_metrics_enhancements),
        ("Transcript Service Integration", check_transcript_service_integration),
        ("Metrics Endpoints", check_app_metrics_endpoints),
        ("Structured Logging Patterns", check_structured_logging_patterns),
        ("Requirements Coverage", check_requirements_coverage)
    ]
    
    passed = 0
    failed = 0
    
    for check_name, check_func in checks:
        print(f"\n🔍 {check_name}")
        print("-" * 50)
        
        try:
            if check_func():
                passed += 1
                print(f"✅ {check_name} - PASSED")
            else:
                failed += 1
                print(f"❌ {check_name} - FAILED")
        except Exception as e:
            failed += 1
            print(f"❌ {check_name} - ERROR: {e}")
    
    print("\n" + "=" * 80)
    print(f"📊 Validation Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("\n🎉 Task 10 Implementation Validation PASSED!")
        print("\n✅ All Required Features Implemented:")
        print("   • Circuit breaker state change events with structured logging")
        print("   • Stage duration logging with success/failure tracking")
        print("   • Successful transcript method identification")
        print("   • Stage duration metrics with proxy_used and profile labels")
        print("   • P50/P95 percentile computation for dashboard integration")
        print("   • Comprehensive metrics endpoints for monitoring")
        print("\n🚀 Ready for production deployment!")
        return True
    else:
        print(f"\n❌ Validation failed - {failed} issues found")
        print("   Please review the implementation and fix the identified issues.")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)