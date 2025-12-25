#!/usr/bin/env python3
"""
Debug script to understand the exact circuit breaker behavior
"""

import time
from unittest.mock import patch
from transcript_service import ProxyAwareCircuitBreaker, ENFORCE_PROXY_ALL

def debug_half_open_state():
    """Debug the half-open state detection issue"""
    print("=== DEBUG: Half-Open State Detection ===")
    
    circuit_breaker = ProxyAwareCircuitBreaker()
    print(f"Initial state: {circuit_breaker.get_state()}")
    print(f"Initial failure_count: {circuit_breaker.failure_count}")
    print(f"Initial last_failure_time: {circuit_breaker.last_failure_time}")
    print(f"FAILURE_THRESHOLD: {circuit_breaker.FAILURE_THRESHOLD}")
    print(f"RECOVERY_TIME_SECONDS: {circuit_breaker.RECOVERY_TIME_SECONDS}")
    
    # Trigger circuit breaker
    for i in range(5):
        circuit_breaker.record_failure()
        print(f"After failure {i+1}: state={circuit_breaker.get_state()}, count={circuit_breaker.failure_count}")
    
    print(f"\nAfter 5 failures: state={circuit_breaker.get_state()}")
    
    # Move to 80% of recovery time (4 minutes = 240 seconds)
    current_time = time.time()
    target_time = current_time + 240  # 4 minutes later
    
    print(f"\nSimulating time passage to 80% recovery (240s later)...")
    with patch('time.time', return_value=target_time):
        state = circuit_breaker.get_state()
        print(f"State at 240s: {state}")
        
        # Debug the calculation
        time_since_failure = target_time - circuit_breaker.last_failure_time
        recovery_threshold = circuit_breaker.RECOVERY_TIME_SECONDS * 0.8
        print(f"time_since_failure: {time_since_failure}")
        print(f"recovery_threshold (80%): {recovery_threshold}")
        print(f"full recovery time: {circuit_breaker.RECOVERY_TIME_SECONDS}")
        print(f"Is time_since_failure > recovery_threshold? {time_since_failure > recovery_threshold}")


def debug_partial_failure_counting():
    """Debug the partial failure counting issue"""
    print("\n=== DEBUG: Partial Failure Counting ===")
    
    with patch('transcript_service.ENFORCE_PROXY_ALL', True):
        circuit_breaker = ProxyAwareCircuitBreaker()
        
        # Test multiple partial failures
        circuit_breaker.failure_count = 4.0
        circuit_breaker.last_failure_time = time.time() - 240  # 4 minutes ago
        
        print(f"Initial setup:")
        print(f"  failure_count: {circuit_breaker.failure_count}")
        print(f"  last_failure_time: {circuit_breaker.last_failure_time}")
        print(f"  current state: {circuit_breaker.get_state()}")
        print(f"  ENFORCE_PROXY_ALL: {ENFORCE_PROXY_ALL}")
        
        # Record multiple partial failures
        for i in range(4):
            print(f"\nBefore failure {i+1}:")
            print(f"  current state: {circuit_breaker.get_state()}")
            print(f"  failure_count: {circuit_breaker.failure_count}")
            
            circuit_breaker.record_failure()
            
            print(f"After failure {i+1}:")
            print(f"  failure_count: {circuit_breaker.failure_count}")
            print(f"  current state: {circuit_breaker.get_state()}")
        
        print(f"\nFinal failure_count: {circuit_breaker.failure_count}")
        print(f"Expected: 6.0 (4.0 + 4 * 0.5)")


def debug_proxy_half_open_failure():
    """Debug the proxy half-open state failure counting"""
    print("\n=== DEBUG: Proxy Half-Open State Failure ===")
    
    with patch('transcript_service.ENFORCE_PROXY_ALL', True):
        circuit_breaker = ProxyAwareCircuitBreaker()
        
        # Set to half-open state
        circuit_breaker.failure_count = 4  # Just below threshold
        circuit_breaker.last_failure_time = time.time() - 240  # 4 minutes ago (80% of 5 minutes)
        
        print(f"Setup:")
        print(f"  failure_count: {circuit_breaker.failure_count}")
        print(f"  last_failure_time: {circuit_breaker.last_failure_time}")
        print(f"  current state: {circuit_breaker.get_state()}")
        print(f"  ENFORCE_PROXY_ALL: {ENFORCE_PROXY_ALL}")
        
        # Record failure in half-open state
        initial_count = circuit_breaker.failure_count
        print(f"\nBefore record_failure:")
        print(f"  initial_count: {initial_count}")
        print(f"  state: {circuit_breaker.get_state()}")
        
        circuit_breaker.record_failure()
        
        print(f"\nAfter record_failure:")
        print(f"  failure_count: {circuit_breaker.failure_count}")
        print(f"  expected: {initial_count + 0.5}")
        print(f"  actual increment: {circuit_breaker.failure_count - initial_count}")


if __name__ == '__main__':
    debug_half_open_state()
    debug_partial_failure_counting()
    debug_proxy_half_open_failure()
