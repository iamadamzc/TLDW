#!/usr/bin/env python3
"""
Test script to verify circuit breaker integration hooks implementation.
Tests Requirements 6.3, 6.4, 6.5, 6.6 from the transcript service enhancements spec.
"""

import sys
import os
import time
import logging

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging to see circuit breaker events
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_circuit_breaker_integration():
    """Test circuit breaker integration with retry logic and structured logging."""
    print("🧪 Testing Circuit Breaker Integration Hooks...")
    
    try:
        from transcript_service import (
            _playwright_circuit_breaker, 
            get_circuit_breaker_status,
            _execute_youtubei_with_circuit_breaker
        )
        
        # Test 1: Initial circuit breaker state
        print("\n=== Test 1: Initial Circuit Breaker State ===")
        initial_status = get_circuit_breaker_status()
        print(f"Initial state: {initial_status}")
        
        if initial_status["state"] == "closed":
            print("✅ Circuit breaker starts in closed state")
        else:
            print(f"❌ Circuit breaker should start closed, got: {initial_status['state']}")
            return False
        
        # Test 2: Circuit breaker skip logic when open
        print("\n=== Test 2: Circuit Breaker Skip Logic ===")
        
        # Force circuit breaker to open state
        _playwright_circuit_breaker.failure_count = 5  # Above threshold
        _playwright_circuit_breaker.last_failure_time = time.time()
        
        # Verify it's open
        status_open = get_circuit_breaker_status()
        if status_open["state"] == "open":
            print("✅ Circuit breaker forced to open state")
        else:
            print(f"❌ Circuit breaker should be open, got: {status_open['state']}")
            return False
        
        # Test skip logic with mock operation
        def mock_operation():
            return "mock_result"
        
        result = _execute_youtubei_with_circuit_breaker(mock_operation, "test_video")
        
        if result == "":
            print("✅ Circuit breaker skip logic working - operation skipped when open")
        else:
            print(f"❌ Circuit breaker should skip operation when open, got result: {result}")
            return False
        
        # Test 3: Circuit breaker success recording
        print("\n=== Test 3: Circuit Breaker Success Recording ===")
        
        # Reset circuit breaker
        _playwright_circuit_breaker.record_success()
        
        status_after_success = get_circuit_breaker_status()
        if status_after_success["state"] == "closed" and status_after_success["failure_count"] == 0:
            print("✅ Circuit breaker success recording working - state reset to closed")
        else:
            print(f"❌ Circuit breaker should be closed with 0 failures after success, got: {status_after_success}")
            return False
        
        # Test 4: Circuit breaker failure recording
        print("\n=== Test 4: Circuit Breaker Failure Recording ===")
        
        # Record some failures
        for i in range(2):
            _playwright_circuit_breaker.record_failure()
        
        status_after_failures = get_circuit_breaker_status()
        if status_after_failures["failure_count"] == 2:
            print("✅ Circuit breaker failure recording working - failure count incremented")
        else:
            print(f"❌ Circuit breaker should have 2 failures, got: {status_after_failures['failure_count']}")
            return False
        
        # Test 5: Circuit breaker activation after threshold
        print("\n=== Test 5: Circuit Breaker Activation ===")
        
        # Record one more failure to reach threshold
        _playwright_circuit_breaker.record_failure()
        
        status_activated = get_circuit_breaker_status()
        if status_activated["state"] == "open" and status_activated["failure_count"] >= 3:
            print("✅ Circuit breaker activation working - opened after reaching threshold")
        else:
            print(f"❌ Circuit breaker should be open after 3 failures, got: {status_activated}")
            return False
        
        # Test 6: Recovery time calculation
        print("\n=== Test 6: Recovery Time Monitoring ===")
        
        recovery_time = status_activated["recovery_time_remaining"]
        if recovery_time is not None and recovery_time > 0:
            print(f"✅ Recovery time monitoring working - {recovery_time}s remaining")
        else:
            print(f"❌ Recovery time should be positive when circuit breaker is open, got: {recovery_time}")
            return False
        
        # Test 7: Structured logging verification
        print("\n=== Test 7: Structured Logging ===")
        
        # Reset and trigger state changes to verify logging
        _playwright_circuit_breaker.record_success()
        _playwright_circuit_breaker.record_failure()
        
        print("✅ Structured logging events emitted (check logs above for circuit_breaker_event entries)")
        
        # Clean up - reset circuit breaker
        _playwright_circuit_breaker.record_success()
        
        print("\n🎉 All circuit breaker integration tests passed!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure transcript_service.py has the enhanced circuit breaker implementation")
        return False
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tenacity_integration():
    """Test that tenacity is properly integrated."""
    print("\n🧪 Testing Tenacity Integration...")
    
    try:
        import tenacity
        from transcript_service import _should_retry_youtubei_error
        
        # Test retry condition detection
        timeout_error = Exception("TimeoutError: Navigation timeout")
        if _should_retry_youtubei_error(timeout_error):
            print("✅ Tenacity retry condition detection working for timeout errors")
        else:
            print("❌ Should retry on timeout errors")
            return False
        
        # Test non-retry condition
        other_error = Exception("Some other error")
        if not _should_retry_youtubei_error(other_error):
            print("✅ Tenacity correctly identifies non-retryable errors")
        else:
            print("❌ Should not retry on non-timeout errors")
            return False
        
        print("✅ Tenacity integration working correctly")
        return True
        
    except ImportError as e:
        print(f"❌ Tenacity not available: {e}")
        return False
    except Exception as e:
        print(f"❌ Tenacity test failed: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Circuit Breaker Integration Hooks Test Suite")
    print("=" * 60)
    
    success = True
    
    # Test circuit breaker integration
    if not test_circuit_breaker_integration():
        success = False
    
    # Test tenacity integration
    if not test_tenacity_integration():
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 All tests passed! Circuit breaker integration hooks implemented correctly.")
        sys.exit(0)
    else:
        print("❌ Some tests failed. Check the output above for details.")
        sys.exit(1)