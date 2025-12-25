#!/usr/bin/env python3
"""
Debug script to understand circuit breaker state detection
"""

import time
from transcript_service import ProxyAwareCircuitBreaker
from unittest.mock import patch

def debug_circuit_breaker():
    print("=== Circuit Breaker Debug ===")
    
    # Test the half-open state detection scenario from the failing test
    with patch('transcript_service.ENFORCE_PROXY_ALL', True):
        circuit_breaker = ProxyAwareCircuitBreaker()
        
        print(f"Initial state: {circuit_breaker.get_state()}")
        print(f"Initial failure_count: {circuit_breaker.failure_count}")
        print(f"Initial last_failure_time: {circuit_breaker.last_failure_time}")
        print(f"Recovery time: {circuit_breaker.RECOVERY_TIME_SECONDS} seconds")
        print()
        
        # Set up the scenario from test_half_open_state_detection
        print("=== Setting up test scenario ===")
        # First trigger circuit breaker with 5 failures
        for i in range(5):
            circuit_breaker.record_failure()
            print(f"After failure {i+1}: state={circuit_breaker.get_state()}, count={circuit_breaker.failure_count}")
        
        print()
        print("=== Testing time-based state transitions ===")
        
        # Test different time offsets
        current_time = time.time()
        print(f"Current time: {current_time}")
        print(f"Last failure time: {circuit_breaker.last_failure_time}")
        
        # Test at different time offsets
        time_offsets = [0, 60, 120, 180, 240, 300, 360]  # 0 to 6 minutes
        
        for offset in time_offsets:
            # Mock time.time() to return current_time + offset
            with patch('time.time', return_value=current_time + offset):
                state = circuit_breaker.get_state()
                time_since_failure = offset
                recovery_progress = (time_since_failure / circuit_breaker.RECOVERY_TIME_SECONDS) * 100
                print(f"Time offset: {offset}s ({recovery_progress:.1f}% of recovery): state={state}")
        
        print()
        print("=== Testing the specific failing scenario ===")
        
        # Reset and test the exact scenario from test_record_failure_with_proxy_half_open_state
        circuit_breaker = ProxyAwareCircuitBreaker()
        circuit_breaker.failure_count = 4  # Just below threshold
        circuit_breaker.last_failure_time = time.time() - 240  # 4 minutes ago (80% of 5 minutes)
        
        print(f"Setup: failure_count={circuit_breaker.failure_count}, time_since_failure=240s")
        print(f"Recovery time: {circuit_breaker.RECOVERY_TIME_SECONDS}s")
        print(f"80% of recovery time: {circuit_breaker.RECOVERY_TIME_SECONDS * 0.8}s")
        print(f"Current state: {circuit_breaker.get_state()}")
        
        # Test record_failure
        initial_count = circuit_breaker.failure_count
        print(f"Before record_failure: count={circuit_breaker.failure_count}")
        circuit_breaker.record_failure()
        print(f"After record_failure: count={circuit_breaker.failure_count}")
        print(f"Expected: {initial_count + 0.5}")
        print(f"Actual increment: {circuit_breaker.failure_count - initial_count}")

if __name__ == '__main__':
    debug_circuit_breaker()
