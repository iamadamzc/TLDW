#!/usr/bin/env python3
"""
Test Task 17: Tenacity Retry Wrapper Implementation

This test verifies that the tenacity retry wrapper is properly implemented
for the YouTubei attempt function with exponential backoff and jitter.

Requirements tested:
- 17.1: Exponential backoff with jitter for navigation timeouts
- 17.2: 2-3 retry attempts for interception failures  
- 17.3: Transient timeouts recover on second/third try
- 17.4: Circuit breaker activates after retry exhaustion
- 17.5: Uses tenacity for retry logic
- 17.6: YouTubei attempt function as single tenacity-wrapped unit
"""

import sys
import os
import time
import logging
from unittest.mock import patch, MagicMock
from typing import Dict, Any

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def test_tenacity_retry_condition_function():
    """Test that _should_retry_youtubei_error correctly identifies retryable errors."""
    print("🧪 Testing tenacity retry condition function...")
    
    from transcript_service import _should_retry_youtubei_error
    
    # Test cases for retryable errors (should return True)
    retryable_cases = [
        # Navigation timeout errors (Requirement 17.1)
        Exception("TimeoutError: Navigation timeout"),
        Exception("asyncio.TimeoutError: page.goto timeout"),
        Exception("Navigation failed due to timeout"),
        
        # Navigation errors (Requirement 17.1)
        Exception("NavigationError: Failed to navigate to page"),
        Exception("Page navigation failed"),
        
        # Interception failures (Requirement 17.2)
        Exception("Route handler failed to process request"),
        Exception("Route.fetch() failed with error"),
        Exception("Route interception error occurred"),
        
        # Network errors (transient)
        Exception("net::ERR_CONNECTION_REFUSED"),
        Exception("Connection refused by server"),
        Exception("DNS resolution failed"),
        
        # Blocking errors (potentially transient)
        Exception("Request blocked by server"),
        Exception("Rate limit exceeded"),
        Exception("Service unavailable"),
    ]
    
    # Test cases for non-retryable errors (should return False)
    non_retryable_cases = [
        Exception("Video not found"),
        Exception("Invalid video ID"),
        Exception("Transcript disabled"),
        Exception("Age restricted content"),
        Exception("Private video"),
        Exception("Parsing error in response"),
    ]
    
    # Test retryable cases
    for i, exc in enumerate(retryable_cases, 1):
        should_retry = _should_retry_youtubei_error(exc)
        assert should_retry, f"Case {i} should be retryable: {exc}"
        print(f"  ✅ Retryable case {i}: {str(exc)[:50]}...")
    
    # Test non-retryable cases
    for i, exc in enumerate(non_retryable_cases, 1):
        should_retry = _should_retry_youtubei_error(exc)
        assert not should_retry, f"Case {i} should NOT be retryable: {exc}"
        print(f"  ✅ Non-retryable case {i}: {str(exc)[:50]}...")
    
    print("  ✅ Retry condition function working correctly")


def test_tenacity_retry_configuration():
    """Test that tenacity retry is configured with correct parameters."""
    print("🧪 Testing tenacity retry configuration...")
    
    from transcript_service import _execute_youtubei_with_circuit_breaker
    import inspect
    
    # Get the source code to verify tenacity configuration
    source = inspect.getsource(_execute_youtubei_with_circuit_breaker)
    
    # Verify tenacity configuration parameters
    assert "tenacity.retry" in source, "Should use tenacity.retry decorator"
    assert "stop_after_attempt(3)" in source, "Should have 3 retry attempts (Requirement 17.2)"
    assert "wait_exponential_jitter" in source, "Should use exponential backoff with jitter (Requirement 17.1)"
    assert "initial=1" in source, "Should start with 1 second initial delay"
    assert "max=10" in source, "Should cap at 10 seconds maximum delay"
    assert "jitter=2" in source, "Should add jitter for randomization"
    assert "_should_retry_youtubei_error" in source, "Should use custom retry condition function"
    
    print("  ✅ Tenacity configuration parameters correct")


def test_retry_with_transient_failures():
    """Test that transient failures recover on second/third try (Requirement 17.3)."""
    print("🧪 Testing retry behavior with transient failures...")
    
    from transcript_service import get_transcript_via_youtubei
    
    call_count = 0
    
    def mock_internal_with_transient_failure(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        
        if call_count == 1:
            # First attempt fails with timeout
            raise Exception("TimeoutError: Navigation timeout")
        elif call_count == 2:
            # Second attempt fails with interception error
            raise Exception("Route handler failed")
        else:
            # Third attempt succeeds
            return "Mock transcript content"
    
    with patch('transcript_service._get_transcript_via_youtubei_internal', side_effect=mock_internal_with_transient_failure):
        result = get_transcript_via_youtubei("test_video_id")
        
        # Should succeed after retries
        assert result == "Mock transcript content", "Should succeed after transient failures"
        assert call_count == 3, f"Should make 3 attempts, made {call_count}"
        
    print("  ✅ Transient failures recover on retry")


def test_circuit_breaker_activation_after_retry_exhaustion():
    """Test that circuit breaker activates after retry exhaustion (Requirement 17.4)."""
    print("🧪 Testing circuit breaker activation after retry exhaustion...")
    
    from transcript_service import get_transcript_via_youtubei, _playwright_circuit_breaker
    
    # Reset circuit breaker state
    _playwright_circuit_breaker.failure_count = 0
    _playwright_circuit_breaker.last_failure_time = None
    
    initial_failure_count = _playwright_circuit_breaker.failure_count
    
    with patch('transcript_service._get_transcript_via_youtubei_internal') as mock_internal:
        # Mock persistent failure that exhausts retries
        mock_internal.side_effect = Exception("TimeoutError: Persistent navigation timeout")
        
        result = get_transcript_via_youtubei("test_video_id")
        
        # Should fail and return empty string
        assert result == "", "Should return empty string after retry exhaustion"
        
        # Circuit breaker should record failure
        assert _playwright_circuit_breaker.failure_count > initial_failure_count, "Circuit breaker should record failure"
        
        # Should have made 3 attempts (original + 2 retries)
        assert mock_internal.call_count == 3, f"Should make 3 attempts, made {mock_internal.call_count}"
    
    print("  ✅ Circuit breaker activates after retry exhaustion")


def test_single_tenacity_wrapped_unit():
    """Test that the complete YouTubei attempt function is wrapped as single unit (Requirement 17.6)."""
    print("🧪 Testing single tenacity-wrapped unit...")
    
    from transcript_service import get_transcript_via_youtubei
    
    call_count = 0
    
    def mock_internal_tracking_calls(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        
        # Simulate the complete YouTubei attempt (nav + route + parse)
        if call_count < 2:
            # Fail first attempt to trigger retry
            raise Exception("TimeoutError: Complete attempt failed")
        else:
            # Succeed on second attempt
            return "Complete attempt succeeded"
    
    with patch('transcript_service._get_transcript_via_youtubei_internal', side_effect=mock_internal_tracking_calls):
        result = get_transcript_via_youtubei("test_video_id")
        
        # Should succeed after one retry
        assert result == "Complete attempt succeeded", "Should succeed after retry"
        assert call_count == 2, f"Should make 2 attempts (original + 1 retry), made {call_count}"
    
    print("  ✅ Complete YouTubei attempt function wrapped as single tenacity unit")


def test_exponential_backoff_timing():
    """Test that exponential backoff with jitter is working (Requirement 17.1)."""
    print("🧪 Testing exponential backoff timing...")
    
    from transcript_service import get_transcript_via_youtubei
    import time
    
    call_times = []
    
    def mock_internal_with_timing(*args, **kwargs):
        call_times.append(time.time())
        # Always fail to test retry timing
        raise Exception("TimeoutError: Testing backoff timing")
    
    with patch('transcript_service._get_transcript_via_youtubei_internal', side_effect=mock_internal_with_timing):
        start_time = time.time()
        result = get_transcript_via_youtubei("test_video_id")
        total_time = time.time() - start_time
        
        # Should fail after retries
        assert result == "", "Should fail after retry exhaustion"
        assert len(call_times) == 3, f"Should make 3 attempts, made {len(call_times)}"
        
        # Check that there were delays between attempts (exponential backoff)
        if len(call_times) >= 2:
            delay1 = call_times[1] - call_times[0]
            print(f"    First retry delay: {delay1:.2f}s")
            assert delay1 >= 0.8, f"First retry delay should be ~1s (with jitter), was {delay1:.2f}s"
            assert delay1 <= 4.0, f"First retry delay should not exceed 4s, was {delay1:.2f}s"
        
        if len(call_times) >= 3:
            delay2 = call_times[2] - call_times[1]
            print(f"    Second retry delay: {delay2:.2f}s")
            assert delay2 >= 1.5, f"Second retry delay should be ~2s+ (exponential), was {delay2:.2f}s"
            assert delay2 <= 8.0, f"Second retry delay should not exceed 8s, was {delay2:.2f}s"
    
    print("  ✅ Exponential backoff with jitter working correctly")


def test_retry_logging():
    """Test that retry attempts are properly logged."""
    print("🧪 Testing retry logging...")
    
    from transcript_service import get_transcript_via_youtubei
    import logging
    
    # Capture log messages
    log_messages = []
    
    class TestLogHandler(logging.Handler):
        def emit(self, record):
            log_messages.append(record.getMessage())
    
    # Add test handler
    test_handler = TestLogHandler()
    test_handler.setLevel(logging.INFO)
    logging.getLogger().addHandler(test_handler)
    
    try:
        with patch('transcript_service._get_transcript_via_youtubei_internal') as mock_internal:
            # Mock failure that triggers retries
            mock_internal.side_effect = Exception("TimeoutError: Testing retry logging")
            
            result = get_transcript_via_youtubei("test_video_id")
            
            # Check for retry-related log messages
            retry_logs = [msg for msg in log_messages if "youtubei_retry_attempt" in msg]
            assert len(retry_logs) >= 2, f"Should have retry attempt logs, found {len(retry_logs)}"
            
            # Check for retry completion logs
            completion_logs = [msg for msg in log_messages if "youtubei_retry_exhausted" in msg]
            assert len(completion_logs) >= 1, f"Should have retry exhaustion log, found {len(completion_logs)}"
            
    finally:
        # Remove test handler
        logging.getLogger().removeHandler(test_handler)
    
    print("  ✅ Retry logging working correctly")


def run_all_tests():
    """Run all Task 17 tests."""
    print("🚀 Starting Task 17: Tenacity Retry Wrapper Implementation Tests")
    print("=" * 70)
    
    try:
        test_tenacity_retry_condition_function()
        test_tenacity_retry_configuration()
        test_retry_with_transient_failures()
        test_circuit_breaker_activation_after_retry_exhaustion()
        test_single_tenacity_wrapped_unit()
        test_exponential_backoff_timing()
        test_retry_logging()
        
        print("\n" + "=" * 70)
        print("✅ ALL TASK 17 TESTS PASSED!")
        print("\nRequirements verified:")
        print("  ✅ 17.1: Exponential backoff with jitter for navigation timeouts")
        print("  ✅ 17.2: 2-3 retry attempts for interception failures")
        print("  ✅ 17.3: Transient timeouts recover on second/third try")
        print("  ✅ 17.4: Circuit breaker activates after retry exhaustion")
        print("  ✅ 17.5: Uses tenacity for retry logic")
        print("  ✅ 17.6: YouTubei attempt function as single tenacity-wrapped unit")
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)