#!/usr/bin/env python3
"""
Test suite for Task 16: Proxy Health Metrics and Preflight Monitoring

This test validates the implementation of:
- Requirement 16.1: Preflight check counters for hits/misses logging
- Requirement 16.2: Masked username tail logging for identification  
- Requirement 16.3: Healthy boolean accessor for proxy status
- Requirement 16.4: Structured logs showing proxy health without credential leakage
- Requirement 16.5: Preflight rates and proxy performance metrics
"""

import unittest
import logging
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from proxy_manager import ProxyManager, ProxySecret


class TestProxyHealthMetrics(unittest.TestCase):
    """Test proxy health metrics and preflight monitoring functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_logger = Mock()
        
        # Mock secret data for testing
        self.test_secret_data = {
            "provider": "oxylabs",
            "host": "pr.oxylabs.io",
            "port": 10000,
            "username": "testuser123456",
            "password": "testpass+special",
            "session_ttl_minutes": 10
        }
        
        # Create ProxyManager with mock logger
        self.proxy_manager = ProxyManager(self.test_secret_data, self.mock_logger)
        
        # Access the SafeStructuredLogger's underlying logger for testing
        self.structured_logger = self.proxy_manager.logger
        self.underlying_logger = self.structured_logger.logger
    
    def test_masked_username_tail_generation(self):
        """Test Requirement 16.2: Masked username tail logging for identification"""
        # Test normal username
        masked = self.proxy_manager._get_masked_username_tail()
        self.assertEqual(masked, "...3456")  # Last 4 chars of "testuser123456"
        
        # Test short username
        short_secret = self.test_secret_data.copy()
        short_secret["username"] = "abc"
        pm_short = ProxyManager(short_secret, self.mock_logger)
        masked_short = pm_short._get_masked_username_tail()
        self.assertEqual(masked_short, "***")
        
        # Test no username
        no_user_secret = self.test_secret_data.copy()
        no_user_secret["username"] = ""
        pm_no_user = ProxyManager(no_user_secret, self.mock_logger)
        masked_no_user = pm_no_user._get_masked_username_tail()
        self.assertEqual(masked_no_user, "***")
    
    def test_healthy_boolean_accessor(self):
        """Test Requirement 16.3: Healthy boolean accessor for proxy status"""
        # Initially should be None (not checked yet)
        self.assertIsNone(self.proxy_manager.healthy)
        
        # Set healthy status
        self.proxy_manager._healthy = True
        self.assertTrue(self.proxy_manager.healthy)
        
        # Set unhealthy status
        self.proxy_manager._healthy = False
        self.assertFalse(self.proxy_manager.healthy)
        
        # Test with cached result
        self.proxy_manager._healthy = None
        self.proxy_manager.preflight_cache.set(True)
        self.assertTrue(self.proxy_manager.healthy)
    
    def test_preflight_metrics_collection(self):
        """Test Requirement 16.1, 16.5: Preflight check counters and performance metrics"""
        # Initialize metrics
        self.assertEqual(self.proxy_manager._preflight_hits, 0)
        self.assertEqual(self.proxy_manager._preflight_misses, 0)
        self.assertEqual(self.proxy_manager._preflight_total, 0)
        
        # Simulate cache hit
        self.proxy_manager._preflight_hits = 5
        self.proxy_manager._preflight_misses = 3
        self.proxy_manager._preflight_total = 8
        self.proxy_manager._preflight_durations.extend([0.1, 0.2, 0.15])
        
        metrics = self.proxy_manager.get_preflight_metrics()
        
        self.assertEqual(metrics["preflight_hits"], 5)
        self.assertEqual(metrics["preflight_misses"], 3)
        self.assertEqual(metrics["preflight_total"], 8)
        self.assertEqual(metrics["hit_rate"], 0.625)  # 5/8
        self.assertAlmostEqual(metrics["avg_duration_ms"], 150.0, places=1)  # (0.1+0.2+0.15)/3 * 1000
        self.assertEqual(metrics["proxy_username_tail"], "...3456")
    
    @patch('requests.get')
    def test_preflight_cache_hit_logging(self, mock_get):
        """Test Requirement 16.1: Cache hit logging"""
        # Set up cached result
        self.proxy_manager.preflight_cache.set(True)
        
        # Call preflight - should be cache hit
        result = self.proxy_manager.preflight()
        
        # Verify cache hit was logged
        self.assertTrue(result)
        
        # Check that structured logging was called with cache hit info
        log_calls = [call for call in self.underlying_logger.log.call_args_list 
                    if len(call[0]) > 1 and "cache hit" in str(call).lower()]
        self.assertTrue(len(log_calls) > 0, f"Cache hit should be logged. Actual calls: {self.underlying_logger.log.call_args_list}")
        
        # Verify hit counter was incremented
        self.assertEqual(self.proxy_manager._preflight_hits, 1)
        self.assertEqual(self.proxy_manager._preflight_total, 1)
    
    @patch('requests.get')
    def test_preflight_cache_miss_logging(self, mock_get):
        """Test Requirement 16.1: Cache miss logging with actual preflight"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 204
        mock_get.return_value = mock_response
        
        # Ensure cache is expired/empty
        self.proxy_manager.preflight_cache = type(self.proxy_manager.preflight_cache)()
        
        # Call preflight - should be cache miss
        result = self.proxy_manager.preflight()
        
        # Verify preflight succeeded
        self.assertTrue(result)
        
        # Verify miss counter was incremented
        self.assertEqual(self.proxy_manager._preflight_misses, 1)
        self.assertEqual(self.proxy_manager._preflight_total, 1)
    
    def test_structured_health_status_logging(self):
        """Test Requirement 16.4: Structured logs showing proxy health without credential leakage"""
        # Set up some metrics
        self.proxy_manager._preflight_hits = 10
        self.proxy_manager._preflight_total = 15
        self.proxy_manager._healthy = True
        self.proxy_manager._last_preflight_time = time.time()
        
        # Reset mock to clear previous calls
        self.underlying_logger.reset_mock()
        
        # Emit health status
        self.proxy_manager.emit_health_status()
        
        # Verify structured logging was called
        self.assertTrue(self.underlying_logger.log.called, f"log should be called. Calls: {self.underlying_logger.log.call_args_list}")
        
        # Get the last log call
        last_call = self.underlying_logger.log.call_args_list[-1]
        log_level, log_message = last_call[0]
        log_kwargs = last_call[1].get("extra", {}).get("evt", {})
        
        # Verify no credentials are leaked
        self.assertNotIn("password", str(log_kwargs))
        self.assertNotIn("testpass", str(log_kwargs))
        self.assertNotIn("testuser123456", str(log_kwargs))  # Full username should not appear
        
        # Verify masked username is present
        self.assertIn("username_tail", log_kwargs)
        self.assertEqual(log_kwargs["username_tail"], "...3456")
        
        # Verify health metrics are included
        self.assertIn("healthy", log_kwargs)
        self.assertIn("hit_rate", log_kwargs)
        self.assertIn("total_checks", log_kwargs)
    
    def test_health_status_no_proxy_configured(self):
        """Test health status logging when proxy is not configured"""
        # Create new mock logger for this test
        mock_logger_no_proxy = Mock()
        
        # Create ProxyManager without proxy
        pm_no_proxy = ProxyManager({}, mock_logger_no_proxy)
        
        # Emit health status
        pm_no_proxy.emit_health_status()
        
        # Verify appropriate logging
        self.assertTrue(mock_logger_no_proxy.log.called)
        last_call = mock_logger_no_proxy.log.call_args_list[-1]
        log_kwargs = last_call[1].get("extra", {}).get("evt", {})
        
        self.assertFalse(log_kwargs["proxy_available"])
        self.assertFalse(log_kwargs["healthy"])
        self.assertEqual(log_kwargs["username_tail"], "N/A")
    
    @patch('requests.get')
    def test_preflight_performance_metrics(self, mock_get):
        """Test Requirement 16.5: Performance metrics collection"""
        # Mock response with delay
        mock_response = Mock()
        mock_response.status_code = 204
        
        def delayed_response(*args, **kwargs):
            time.sleep(0.1)  # Simulate 100ms response time
            return mock_response
        
        mock_get.side_effect = delayed_response
        
        # Clear cache to force actual preflight
        self.proxy_manager.preflight_cache = type(self.proxy_manager.preflight_cache)()
        
        # Perform preflight
        start_time = time.time()
        result = self.proxy_manager.preflight()
        duration = time.time() - start_time
        
        # Verify success
        self.assertTrue(result)
        
        # Verify duration was recorded
        self.assertTrue(len(self.proxy_manager._preflight_durations) > 0)
        recorded_duration = self.proxy_manager._preflight_durations[-1]
        self.assertGreaterEqual(recorded_duration, 0.1)  # At least 100ms due to sleep
        
        # Verify metrics include duration
        metrics = self.proxy_manager.get_preflight_metrics()
        self.assertGreater(metrics["avg_duration_ms"], 100)  # Should be > 100ms
    
    @patch('requests.get')
    def test_preflight_failure_logging_with_metrics(self, mock_get):
        """Test comprehensive failure logging with performance metrics"""
        # Mock auth failure
        mock_response = Mock()
        mock_response.status_code = 407
        mock_get.return_value = mock_response
        
        # Clear cache to force actual preflight
        self.proxy_manager.preflight_cache = type(self.proxy_manager.preflight_cache)()
        
        # Perform preflight - should fail
        with self.assertRaises(Exception):
            self.proxy_manager.preflight()
        
        # Verify failure was logged with metrics
        auth_failure_logs = [call for call in self.underlying_logger.log.call_args_list 
                           if len(call[0]) > 1 and "auth failed" in str(call).lower()]
        self.assertTrue(len(auth_failure_logs) > 0, f"Auth failure should be logged. Actual calls: {self.underlying_logger.log.call_args_list}")
        
        # Verify failure log includes performance data - check the extra field
        failure_log = auth_failure_logs[0]
        log_kwargs = failure_log[1].get("extra", {}).get("evt", {})
        self.assertIn("duration_ms", log_kwargs)
        self.assertIn("username_tail", log_kwargs)
        self.assertIn("status_code", log_kwargs)
        self.assertEqual(log_kwargs["status_code"], 407)
    
    def test_no_credential_leakage_in_logs(self):
        """Test that no credentials are leaked in any log output"""
        # Perform various operations that generate logs
        self.proxy_manager.emit_health_status()
        self.proxy_manager.get_preflight_metrics()
        
        # Check all log calls for credential leakage
        for call in self.underlying_logger.log.call_args_list:
            log_message = str(call)
            
            # Verify no password leakage
            self.assertNotIn("testpass", log_message)
            self.assertNotIn("+special", log_message)
            
            # Verify no full username leakage
            self.assertNotIn("testuser123456", log_message)
            
            # Verify no proxy URL with credentials
            self.assertNotIn("testuser123456:testpass", log_message)


class TestProxyHealthIntegration(unittest.TestCase):
    """Integration tests for proxy health monitoring"""
    
    def setUp(self):
        """Set up integration test fixtures"""
        self.mock_logger = Mock()
        
        # Use realistic proxy configuration
        self.test_secret_data = {
            "provider": "oxylabs",
            "host": "pr.oxylabs.io", 
            "port": 10000,
            "username": "customer-user123",
            "password": "secure+password!",
            "session_ttl_minutes": 10
        }
    
    @patch('requests.get')
    def test_end_to_end_health_monitoring(self, mock_get):
        """Test complete health monitoring workflow"""
        # Mock successful preflight
        mock_response = Mock()
        mock_response.status_code = 204
        mock_get.return_value = mock_response
        
        # Create proxy manager
        pm = ProxyManager(self.test_secret_data, self.mock_logger)
        
        # Perform multiple preflights to build metrics
        for i in range(5):
            pm.preflight()
            time.sleep(0.01)  # Small delay to vary timing
        
        # Emit health status
        pm.emit_health_status()
        
        # Verify comprehensive metrics
        metrics = pm.get_preflight_metrics()
        
        self.assertEqual(metrics["preflight_total"], 5)
        self.assertGreater(metrics["preflight_hits"], 0)  # Should have cache hits
        self.assertGreater(metrics["hit_rate"], 0.0)
        self.assertEqual(metrics["proxy_username_tail"], "...r123")  # Last 4 of "customer-user123"
        self.assertTrue(metrics["healthy"])
        
        # Verify no credentials in logs
        all_log_output = str(self.mock_logger.log_event.call_args_list)
        self.assertNotIn("secure+password!", all_log_output)
        self.assertNotIn("customer-user123", all_log_output)  # Full username should not appear


if __name__ == "__main__":
    # Set up logging for test output
    logging.basicConfig(level=logging.INFO)
    
    # Run tests
    unittest.main(verbosity=2)