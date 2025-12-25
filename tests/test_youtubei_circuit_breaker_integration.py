#!/usr/bin/env python3
"""
Test script to verify YouTubei circuit breaker integration in the full pipeline.
Tests the complete integration of circuit breaker with retry logic and YouTubei method.
"""

import sys
import os
import time
import logging
from unittest.mock import patch, MagicMock

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging to see circuit breaker events
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_youtubei_circuit_breaker_integration():
    """Test YouTubei method with circuit breaker integration."""
    print("🧪 Testing YouTubei Circuit Breaker Integration...")
    
    try:
        from transcript_service import (
            get_transcript_via_youtubei,
            _playwright_circuit_breaker,
            get_circuit_breaker_status
        )
        
        # Reset circuit breaker to clean state
        _playwright_circuit_breaker.record_success()
        
        print("\n=== Test 1: Circuit Breaker Blocks YouTubei When Open ===")
        
        # Force circuit breaker to open
        _playwright_circuit_breaker.failure_count = 5
        _playwright_circuit_breaker.last_failure_time = time.time()
        
        # Verify circuit breaker is open
        status = get_circuit_breaker_status()
        if status["state"] != "open":
            print(f"❌ Circuit breaker should be open, got: {status['state']}")
            return False
        
        # Call YouTubei method - should be skipped
        result = get_transcript_via_youtubei("test_video_id")
        
        if result == "":
            print("✅ YouTubei method correctly skipped when circuit breaker is open")
        else:
            print(f"❌ YouTubei should return empty string when circuit breaker is open, got: {result}")
            return False
        
        print("\n=== Test 2: Circuit Breaker Allows YouTubei When Closed ===")
        
        # Reset circuit breaker to closed state
        _playwright_circuit_breaker.record_success()
        
        status = get_circuit_breaker_status()
        if status["state"] != "closed":
            print(f"❌ Circuit breaker should be closed, got: {status['state']}")
            return False
        
        # Mock the internal YouTubei function to avoid actual Playwright execution
        with patch('transcript_service._get_transcript_via_youtubei_internal') as mock_internal:
            mock_internal.return_value = "Mock transcript content"
            
            result = get_transcript_via_youtubei("test_video_id")
            
            if result == "Mock transcript content":
                print("✅ YouTubei method correctly executed when circuit breaker is closed")
            else:
                print(f"❌ YouTubei should return mock content, got: {result}")
                return False
        
        print("\n=== Test 3: Circuit Breaker Records Success After Successful YouTubei ===")
        
        # Set up some initial failures
        _playwright_circuit_breaker.failure_count = 2
        
        with patch('transcript_service._get_transcript_via_youtubei_internal') as mock_internal:
            mock_internal.return_value = "Successful transcript"
            
            result = get_transcript_via_youtubei("test_video_id")
            
            # Check that circuit breaker was reset after success
            status = get_circuit_breaker_status()
            if status["failure_count"] == 0:
                print("✅ Circuit breaker correctly reset after successful YouTubei operation")
            else:
                print(f"❌ Circuit breaker should be reset after success, failure_count: {status['failure_count']}")
                return False
        
        print("\n=== Test 4: Circuit Breaker Records Failure After Failed YouTubei ===")
        
        # Reset to clean state
        _playwright_circuit_breaker.record_success()
        
        with patch('transcript_service._get_transcript_via_youtubei_internal') as mock_internal:
            # Simulate a retryable error that exhausts retries
            mock_internal.side_effect = Exception("TimeoutError: Navigation timeout")
            
            result = get_transcript_via_youtubei("test_video_id")
            
            # Check that circuit breaker recorded the failure
            status = get_circuit_breaker_status()
            if status["failure_count"] > 0:
                print("✅ Circuit breaker correctly recorded failure after failed YouTubei operation")
            else:
                print(f"❌ Circuit breaker should record failure, failure_count: {status['failure_count']}")
                return False
        
        print("\n=== Test 5: Retry Logic Integration ===")
        
        # Reset circuit breaker
        _playwright_circuit_breaker.record_success()
        
        # Test that retries are attempted before circuit breaker records failure
        call_count = 0
        def mock_failing_operation(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:  # Fail first 2 attempts
                raise Exception("TimeoutError: Retryable error")
            return "Success after retries"
        
        with patch('transcript_service._get_transcript_via_youtubei_internal', side_effect=mock_failing_operation):
            result = get_transcript_via_youtubei("test_video_id")
            
            if result == "Success after retries" and call_count == 3:
                print("✅ Retry logic working correctly - succeeded on 3rd attempt")
            else:
                print(f"❌ Retry logic failed, result: {result}, call_count: {call_count}")
                return False
        
        # Clean up
        _playwright_circuit_breaker.record_success()
        
        print("\n🎉 All YouTubei circuit breaker integration tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_circuit_breaker_state_monitoring():
    """Test circuit breaker state monitoring and structured logging."""
    print("\n🧪 Testing Circuit Breaker State Monitoring...")
    
    try:
        from transcript_service import get_circuit_breaker_status, _playwright_circuit_breaker
        
        # Reset to clean state
        _playwright_circuit_breaker.record_success()
        
        print("\n=== Monitoring Circuit Breaker State Transitions ===")
        
        # Test closed state
        status = get_circuit_breaker_status()
        print(f"Closed state: {status}")
        
        # Trigger failures to see state transitions
        for i in range(1, 4):
            _playwright_circuit_breaker.record_failure()
            status = get_circuit_breaker_status()
            print(f"After failure {i}: state={status['state']}, count={status['failure_count']}")
        
        # Test recovery time
        if status["recovery_time_remaining"] is not None:
            print(f"✅ Recovery time monitoring: {status['recovery_time_remaining']}s remaining")
        else:
            print("❌ Recovery time should be available when circuit breaker is open")
            return False
        
        # Test success reset
        _playwright_circuit_breaker.record_success()
        status = get_circuit_breaker_status()
        print(f"After success reset: {status}")
        
        if status["state"] == "closed" and status["failure_count"] == 0:
            print("✅ Circuit breaker state monitoring working correctly")
        else:
            print("❌ Circuit breaker should be closed with 0 failures after success")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ State monitoring test failed: {e}")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("YouTubei Circuit Breaker Integration Test Suite")
    print("=" * 70)
    
    success = True
    
    # Test YouTubei circuit breaker integration
    if not test_youtubei_circuit_breaker_integration():
        success = False
    
    # Test circuit breaker state monitoring
    if not test_circuit_breaker_state_monitoring():
        success = False
    
    print("\n" + "=" * 70)
    if success:
        print("🎉 All YouTubei circuit breaker integration tests passed!")
        print("Circuit breaker integration hooks are working correctly.")
        sys.exit(0)
    else:
        print("❌ Some tests failed. Check the output above for details.")
        sys.exit(1)