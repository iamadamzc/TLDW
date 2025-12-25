#!/usr/bin/env python3
"""
Test script to verify Task 6 requirements are fully implemented.
Tests Requirements 6.3, 6.4, 6.5, 6.6 from the transcript service enhancements spec.

Requirements being tested:
6.3: WHEN Playwright operations fail THEN they SHALL call record_failure on circuit breaker
6.4: WHEN Playwright operations succeed THEN they SHALL call record_success on circuit breaker  
6.5: WHEN circuit breaker is open THEN Playwright stage SHALL be skipped with "open → skip" logging
6.6: WHEN circuit breaker observes outcomes THEN it SHALL observe the post-retry outcome of the YouTubei attempt
"""

import sys
import os
import time
import logging
from unittest.mock import patch, MagicMock

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging to capture circuit breaker events
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_requirement_6_3_failure_recording():
    """Test Requirement 6.3: Playwright operations call record_failure on circuit breaker after failure."""
    print("🧪 Testing Requirement 6.3: Circuit breaker records failures after retry completion...")
    
    try:
        from transcript_service import (
            get_transcript_via_youtubei,
            _playwright_circuit_breaker,
            get_circuit_breaker_status
        )
        
        # Reset circuit breaker
        _playwright_circuit_breaker.record_success()
        initial_count = _playwright_circuit_breaker.failure_count
        
        # Mock internal function to always fail (after retries)
        with patch('transcript_service._get_transcript_via_youtubei_internal') as mock_internal:
            mock_internal.side_effect = Exception("TimeoutError: Persistent failure")
            
            # Call YouTubei - should fail after retries and record failure
            result = get_transcript_via_youtubei("test_video")
            
            # Verify failure was recorded
            final_count = _playwright_circuit_breaker.failure_count
            if final_count > initial_count:
                print("✅ Requirement 6.3 PASSED: Circuit breaker records failure after retry completion")
                return True
            else:
                print(f"❌ Requirement 6.3 FAILED: Failure count should increase, got {initial_count} → {final_count}")
                return False
                
    except Exception as e:
        print(f"❌ Requirement 6.3 FAILED with error: {e}")
        return False


def test_requirement_6_4_success_recording():
    """Test Requirement 6.4: Playwright operations call record_success on circuit breaker after success."""
    print("\n🧪 Testing Requirement 6.4: Circuit breaker records success after retry completion...")
    
    try:
        from transcript_service import (
            get_transcript_via_youtubei,
            _playwright_circuit_breaker,
            get_circuit_breaker_status
        )
        
        # Set up some initial failures
        _playwright_circuit_breaker.failure_count = 2
        initial_count = _playwright_circuit_breaker.failure_count
        
        # Mock internal function to succeed
        with patch('transcript_service._get_transcript_via_youtubei_internal') as mock_internal:
            mock_internal.return_value = "Successful transcript content"
            
            # Call YouTubei - should succeed and record success
            result = get_transcript_via_youtubei("test_video")
            
            # Verify success was recorded (failure count reset)
            final_count = _playwright_circuit_breaker.failure_count
            if final_count == 0 and result == "Successful transcript content":
                print("✅ Requirement 6.4 PASSED: Circuit breaker records success after retry completion")
                return True
            else:
                print(f"❌ Requirement 6.4 FAILED: Failure count should be 0, got {final_count}, result: {result}")
                return False
                
    except Exception as e:
        print(f"❌ Requirement 6.4 FAILED with error: {e}")
        return False


def test_requirement_6_5_skip_when_open():
    """Test Requirement 6.5: Circuit breaker skips Playwright stage when open with proper logging."""
    print("\n🧪 Testing Requirement 6.5: Circuit breaker skips operations when open...")
    
    try:
        from transcript_service import (
            get_transcript_via_youtubei,
            _playwright_circuit_breaker,
            get_circuit_breaker_status
        )
        
        # Force circuit breaker to open state
        _playwright_circuit_breaker.failure_count = 5  # Above threshold
        _playwright_circuit_breaker.last_failure_time = time.time()
        
        # Verify it's open
        status = get_circuit_breaker_status()
        if status["state"] != "open":
            print(f"❌ Setup failed: Circuit breaker should be open, got {status['state']}")
            return False
        
        # Capture logs to verify "skip" logging
        import io
        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.INFO)
        logger = logging.getLogger()
        logger.addHandler(handler)
        
        try:
            # Call YouTubei - should be skipped
            result = get_transcript_via_youtubei("test_video")
            
            # Check result and logs
            log_output = log_capture.getvalue()
            
            if result == "" and "skip_operation" in log_output and "circuit_breaker_open" in log_output:
                print("✅ Requirement 6.5 PASSED: Circuit breaker skips operation when open with proper logging")
                return True
            else:
                print(f"❌ Requirement 6.5 FAILED: Expected empty result and skip logging")
                print(f"   Result: '{result}'")
                print(f"   Log contains skip_operation: {'skip_operation' in log_output}")
                return False
        finally:
            logger.removeHandler(handler)
            
    except Exception as e:
        print(f"❌ Requirement 6.5 FAILED with error: {e}")
        return False


def test_requirement_6_6_post_retry_observation():
    """Test Requirement 6.6: Circuit breaker observes post-retry outcomes."""
    print("\n🧪 Testing Requirement 6.6: Circuit breaker observes post-retry outcomes...")
    
    try:
        from transcript_service import (
            get_transcript_via_youtubei,
            _playwright_circuit_breaker,
            get_circuit_breaker_status
        )
        
        # Test 1: Success after retries
        print("   Testing success after retries...")
        _playwright_circuit_breaker.record_success()  # Reset
        
        call_count = 0
        def mock_retry_then_succeed(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:  # Fail first attempt
                raise Exception("TimeoutError: Retryable error")
            return "Success after retry"
        
        with patch('transcript_service._get_transcript_via_youtubei_internal', side_effect=mock_retry_then_succeed):
            result = get_transcript_via_youtubei("test_video")
            
            # Circuit breaker should observe the final success (not the intermediate failures)
            status = get_circuit_breaker_status()
            if result == "Success after retry" and status["failure_count"] == 0:
                print("   ✅ Circuit breaker correctly observes post-retry success")
            else:
                print(f"   ❌ Circuit breaker should observe success, got failure_count: {status['failure_count']}")
                return False
        
        # Test 2: Failure after retries exhausted
        print("   Testing failure after retry exhaustion...")
        _playwright_circuit_breaker.record_success()  # Reset
        
        with patch('transcript_service._get_transcript_via_youtubei_internal') as mock_internal:
            mock_internal.side_effect = Exception("TimeoutError: Persistent failure")
            
            result = get_transcript_via_youtubei("test_video")
            
            # Circuit breaker should observe the final failure (after retries exhausted)
            status = get_circuit_breaker_status()
            if result == "" and status["failure_count"] > 0:
                print("   ✅ Circuit breaker correctly observes post-retry failure")
                print("✅ Requirement 6.6 PASSED: Circuit breaker observes post-retry outcomes")
                return True
            else:
                print(f"   ❌ Circuit breaker should observe failure, got failure_count: {status['failure_count']}")
                return False
                
    except Exception as e:
        print(f"❌ Requirement 6.6 FAILED with error: {e}")
        return False


def test_structured_logging_events():
    """Test that structured logging events are properly emitted."""
    print("\n🧪 Testing structured logging events...")
    
    try:
        from transcript_service import _playwright_circuit_breaker
        
        # Capture logs
        import io
        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.INFO)
        logger = logging.getLogger()
        logger.addHandler(handler)
        
        try:
            # Reset and trigger various events
            _playwright_circuit_breaker.record_success()
            _playwright_circuit_breaker.record_failure()
            _playwright_circuit_breaker.record_failure()
            _playwright_circuit_breaker.record_failure()  # Should activate
            _playwright_circuit_breaker.record_success()  # Should reset
            
            log_output = log_capture.getvalue()
            
            # Check for structured events
            required_events = [
                "circuit_breaker_event=failure_recorded",
                "circuit_breaker_event=activated", 
                "circuit_breaker_event=success_reset",
                "circuit_breaker_event=state_change"
            ]
            
            missing_events = []
            for event in required_events:
                if event not in log_output:
                    missing_events.append(event)
            
            if not missing_events:
                print("✅ Structured logging events working correctly")
                return True
            else:
                print(f"❌ Missing structured logging events: {missing_events}")
                return False
                
        finally:
            logger.removeHandler(handler)
            
    except Exception as e:
        print(f"❌ Structured logging test failed: {e}")
        return False


if __name__ == "__main__":
    print("=" * 80)
    print("Task 6: Circuit Breaker Integration Hooks - Requirements Verification")
    print("=" * 80)
    
    tests = [
        ("Requirement 6.3: Failure Recording", test_requirement_6_3_failure_recording),
        ("Requirement 6.4: Success Recording", test_requirement_6_4_success_recording), 
        ("Requirement 6.5: Skip When Open", test_requirement_6_5_skip_when_open),
        ("Requirement 6.6: Post-Retry Observation", test_requirement_6_6_post_retry_observation),
        ("Structured Logging Events", test_structured_logging_events)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"Running: {test_name}")
        print(f"{'='*60}")
        
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} FAILED")
    
    print(f"\n{'='*80}")
    print(f"TASK 6 REQUIREMENTS VERIFICATION SUMMARY")
    print(f"{'='*80}")
    print(f"✅ PASSED: {passed}/{total} requirements")
    
    if passed == total:
        print("🎉 ALL TASK 6 REQUIREMENTS SUCCESSFULLY IMPLEMENTED!")
        print("\nImplemented features:")
        print("- ✅ Circuit breaker integration with tenacity retry logic")
        print("- ✅ Post-retry outcome observation (success/failure recording)")
        print("- ✅ Circuit breaker skip logic with structured logging")
        print("- ✅ Comprehensive state monitoring and metrics")
        print("- ✅ Structured event emission for all state changes")
        sys.exit(0)
    else:
        print(f"❌ {total - passed} requirements still need work")
        sys.exit(1)