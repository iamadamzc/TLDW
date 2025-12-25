#!/usr/bin/env python3
"""
Debug script to understand the mocking issue
"""

import time
from unittest.mock import patch, MagicMock
from transcript_service import ProxyAwareCircuitBreaker

def test_mock_behavior():
    """Test if the mock is working correctly"""
    
    print("=== Testing Mock Behavior ===")
    
    # Test 1: Direct mock test
    with patch('transcript_service.get_reliability_config') as mock_config:
        mock_config.return_value.enforce_proxy_all = True
        
        # Import and call the function directly
        from transcript_service import get_reliability_config
        config = get_reliability_config()
        print(f"Direct call result: enforce_proxy_all = {config.enforce_proxy_all}")
        
        # Test circuit breaker
        circuit_breaker = ProxyAwareCircuitBreaker()
        circuit_breaker.failure_count = 4
        circuit_breaker.last_failure_time = time.time() - 240  # 4 minutes ago
        
        print(f"Before record_failure: failure_count = {circuit_breaker.failure_count}")
        print(f"State before: {circuit_breaker.get_state()}")
        
        circuit_breaker.record_failure()
        
        print(f"After record_failure: failure_count = {circuit_breaker.failure_count}")
        print(f"Expected: 4.5, Actual: {circuit_breaker.failure_count}")

if __name__ == '__main__':
    test_mock_behavior()
