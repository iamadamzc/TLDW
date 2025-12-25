#!/usr/bin/env python3
"""
Clean, focused test for ProxyAwareCircuitBreaker functionality.
Tests the core behaviors without complex mocking or timing dependencies.
"""

import unittest
import time
from unittest.mock import patch
from transcript_service import ProxyAwareCircuitBreaker, PlaywrightCircuitBreaker


class TestProxyAwareCircuitBreaker(unittest.TestCase):
    """Clean test suite for ProxyAwareCircuitBreaker"""

    def test_initialization(self):
        """Test that ProxyAwareCircuitBreaker has correct thresholds"""
        cb = ProxyAwareCircuitBreaker()
        
        # Should have more lenient thresholds than standard circuit breaker
        self.assertEqual(cb.FAILURE_THRESHOLD, 5)
        self.assertEqual(cb.RECOVERY_TIME_SECONDS, 300)
        
        # Should inherit from PlaywrightCircuitBreaker
        self.assertIsInstance(cb, PlaywrightCircuitBreaker)

    def test_basic_state_transitions(self):
        """Test basic state transitions: closed -> open -> closed"""
        cb = ProxyAwareCircuitBreaker()
        
        # Initial state should be closed
        self.assertEqual(cb.get_state(), "closed")
        self.assertEqual(cb.failure_count, 0)
        
        # Add failures up to threshold
        for i in range(5):
            cb.record_failure()
            if i < 4:
                self.assertEqual(cb.get_state(), "closed")
            else:
                self.assertEqual(cb.get_state(), "open")
        
        # Should be open with 5 failures
        self.assertEqual(cb.get_state(), "open")
        self.assertEqual(cb.failure_count, 5)

    def test_half_open_state_detection(self):
        """Test half-open state detection at 80% recovery time"""
        cb = ProxyAwareCircuitBreaker()
        
        # Trigger circuit breaker
        for _ in range(5):
            cb.record_failure()
        self.assertEqual(cb.get_state(), "open")
        
        # Manually set time to 80% of recovery (240 seconds)
        cb.last_failure_time = time.time() - 240
        self.assertEqual(cb.get_state(), "half-open")
        
        # Set time past full recovery (301 seconds)
        cb.last_failure_time = time.time() - 301
        self.assertEqual(cb.get_state(), "closed")

    def test_partial_failure_counting_in_half_open_state(self):
        """Test that failures in half-open state count as 0.5 when proxy enforcement is enabled"""
        with patch('reliability_config.get_reliability_config') as mock_config:
            # Mock enforce_proxy_all = True
            mock_config.return_value.enforce_proxy_all = True
            
            cb = ProxyAwareCircuitBreaker()
            
            # Set up half-open state: 5 failures (above threshold), 240 seconds ago (80% of 300s recovery)
            cb.failure_count = 5.0
            cb.last_failure_time = time.time() - 240
            
            # Verify we're in half-open state
            self.assertEqual(cb.get_state(), "half-open")
            
            # Record a failure in half-open state
            cb.record_failure()
            
            # Should add 0.5 instead of 1.0
            self.assertEqual(cb.failure_count, 5.5)

    def test_normal_failure_counting_without_proxy_enforcement(self):
        """Test that failures count as 1.0 when proxy enforcement is disabled"""
        with patch('reliability_config.get_reliability_config') as mock_config:
            # Mock enforce_proxy_all = False
            mock_config.return_value.enforce_proxy_all = False
            
            cb = ProxyAwareCircuitBreaker()
            
            # Set up half-open state: 5 failures (above threshold), 240 seconds ago
            cb.failure_count = 5.0
            cb.last_failure_time = time.time() - 240
            self.assertEqual(cb.get_state(), "half-open")
            
            # Record a failure
            cb.record_failure()
            
            # Should add full 1.0 even in half-open state
            self.assertEqual(cb.failure_count, 6.0)

    def test_normal_failure_counting_in_closed_state(self):
        """Test that failures always count as 1.0 in closed state"""
        with patch('reliability_config.get_reliability_config') as mock_config:
            mock_config.return_value.enforce_proxy_all = True
            
            cb = ProxyAwareCircuitBreaker()
            
            # Ensure we're in closed state
            self.assertEqual(cb.get_state(), "closed")
            
            # Record failures
            cb.record_failure()
            self.assertEqual(cb.failure_count, 1.0)
            
            cb.record_failure()
            self.assertEqual(cb.failure_count, 2.0)

    def test_normal_failure_counting_in_open_state(self):
        """Test that failures always count as 1.0 in open state"""
        with patch('reliability_config.get_reliability_config') as mock_config:
            mock_config.return_value.enforce_proxy_all = True
            
            cb = ProxyAwareCircuitBreaker()
            
            # Set up open state: above threshold, recent failure
            cb.failure_count = 5.0
            cb.last_failure_time = time.time() - 60  # 1 minute ago
            self.assertEqual(cb.get_state(), "open")
            
            # Record failure in open state
            cb.record_failure()
            
            # Should add full 1.0
            self.assertEqual(cb.failure_count, 6.0)

    def test_success_reset(self):
        """Test that record_success resets the circuit breaker"""
        cb = ProxyAwareCircuitBreaker()
        
        # Add some failures
        for _ in range(3):
            cb.record_failure()
        
        self.assertEqual(cb.failure_count, 3)
        self.assertIsNotNone(cb.last_failure_time)
        
        # Record success
        cb.record_success()
        
        # Should reset everything
        self.assertEqual(cb.failure_count, 0)
        self.assertIsNone(cb.last_failure_time)
        self.assertEqual(cb.get_state(), "closed")

    def test_recovery_time_remaining(self):
        """Test recovery time remaining calculation"""
        cb = ProxyAwareCircuitBreaker()
        
        # Initially no recovery time
        self.assertIsNone(cb.get_recovery_time_remaining())
        
        # Trigger circuit breaker
        for _ in range(5):
            cb.record_failure()
        
        # Should have recovery time remaining
        remaining = cb.get_recovery_time_remaining()
        self.assertIsNotNone(remaining)
        self.assertGreater(remaining, 0)
        self.assertLessEqual(remaining, 300)

    def test_comparison_with_standard_circuit_breaker(self):
        """Test that ProxyAwareCircuitBreaker is more lenient than standard"""
        proxy_cb = ProxyAwareCircuitBreaker()
        standard_cb = PlaywrightCircuitBreaker()
        
        # Add 4 failures to both
        for _ in range(4):
            proxy_cb.record_failure()
            standard_cb.record_failure()
        
        # Proxy-aware should still be closed (threshold 5)
        # Standard should be open (threshold 3)
        self.assertEqual(proxy_cb.get_state(), "closed")
        self.assertEqual(standard_cb.get_state(), "open")


if __name__ == '__main__':
    unittest.main(verbosity=2)
