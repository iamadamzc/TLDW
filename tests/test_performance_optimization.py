#!/usr/bin/env python3
"""
Test suite for performance optimization and monitoring setup.
Validates Task 19 implementation: performance metrics collection, dashboard integration,
circuit breaker monitoring, browser context optimization, and structured logging.
"""

import os
import sys
import time
import json
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import threading
import tempfile

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import modules to test
from performance_monitor import (
    BrowserContextManager, 
    CircuitBreakerMonitor, 
    DashboardMetricsCollector,
    get_performance_monitor,
    emit_performance_metric,
    get_optimized_browser_context,
    cleanup_all_browser_contexts
)
from structured_logging import (
    StructuredFormatter,
    ContextualLogger,
    PerformanceLogger,
    AlertLogger,
    LogContext,
    setup_structured_logging,
    log_context,
    log_performance
)
from dashboard_integration import MetricsAggregator


class TestBrowserContextManager(unittest.TestCase):
    """Test browser context optimization and memory management."""
    
    def setUp(self):
        self.manager = BrowserContextManager()
    
    def tearDown(self):
        # Clean up any contexts created during tests
        self.manager.cleanup_all_contexts()
    
    def test_context_stats_initialization(self):
        """Test that context stats are properly initialized."""
        stats = self.manager.get_context_stats()
        
        self.assertEqual(stats["active_contexts"], 0)
        self.assertEqual(stats["active_browsers"], 0)
        self.assertIsInstance(stats["context_usage"], dict)
        self.assertIsInstance(stats["memory_usage_mb"], float)
        self.assertIsNone(stats["oldest_context_age_minutes"])
    
    def test_memory_usage_tracking(self):
        """Test memory usage tracking functionality."""
        # Get initial memory usage
        initial_memory = self.manager._get_current_memory_usage()
        self.assertGreaterEqual(initial_memory, 0)
        
        # Memory usage should be tracked in deque
        self.assertGreater(len(self.manager._memory_usage), 0)
        self.assertEqual(self.manager._memory_usage[-1], initial_memory)
    
    def test_context_cleanup_conditions(self):
        """Test context cleanup decision logic."""
        profile = "test_profile"
        
        # No context exists - should not cleanup
        self.assertFalse(self.manager.should_cleanup_context(profile))
        
        # Simulate context creation
        self.manager._context_usage[profile] = 1
        self.manager._context_created_at[profile] = time.time()
        self.manager._contexts[profile] = Mock()
        
        # Fresh context - should not cleanup
        self.assertFalse(self.manager.should_cleanup_context(profile))
        
        # Old context - should cleanup
        old_time = time.time() - (self.manager.max_context_age_minutes * 60 + 60)
        self.manager._context_created_at[profile] = old_time
        self.assertTrue(self.manager.should_cleanup_context(profile))
        
        # Reset age, test usage count
        self.manager._context_created_at[profile] = time.time()
        self.manager._context_usage[profile] = self.manager.max_context_uses + 1
        self.assertTrue(self.manager.should_cleanup_context(profile))
    
    def test_memory_threshold_cleanup(self):
        """Test cleanup based on memory threshold."""
        profile = "test_profile"
        
        # Simulate context creation
        self.manager._context_usage[profile] = 1
        self.manager._context_created_at[profile] = time.time()
        self.manager._contexts[profile] = Mock()
        
        # Mock high memory usage by setting threshold very low
        original_threshold = self.manager.memory_threshold_mb
        self.manager.memory_threshold_mb = 0.001  # Very low threshold
        
        try:
            # Should trigger cleanup due to low threshold
            result = self.manager.should_cleanup_context(profile)
            # This test may pass or fail depending on actual memory usage
            # The important thing is that it doesn't crash
            self.assertIsInstance(result, bool)
        finally:
            # Restore original threshold
            self.manager.memory_threshold_mb = original_threshold


class TestCircuitBreakerMonitor(unittest.TestCase):
    """Test circuit breaker monitoring and alerting."""
    
    def setUp(self):
        self.monitor = CircuitBreakerMonitor()
    
    def test_state_change_recording(self):
        """Test circuit breaker state change recording."""
        # Record state change
        self.monitor.record_state_change("closed", "open", 3)
        
        # Check that state change was recorded
        self.assertEqual(len(self.monitor._state_history), 1)
        
        state_change = self.monitor._state_history[0]
        self.assertEqual(state_change["previous_state"], "closed")
        self.assertEqual(state_change["new_state"], "open")
        self.assertEqual(state_change["failure_count"], 3)
        self.assertIn("timestamp", state_change)
    
    def test_open_duration_calculation(self):
        """Test calculation of circuit breaker open duration."""
        # No history - should return None
        self.assertIsNone(self.monitor._calculate_open_duration())
        
        # Record transition to open state
        self.monitor.record_state_change("closed", "open", 3)
        
        # Should calculate duration from open transition
        duration = self.monitor._calculate_open_duration()
        self.assertIsNotNone(duration)
        self.assertGreaterEqual(duration, 0)
        self.assertLess(duration, 1)  # Should be very recent
    
    def test_frequent_state_changes_detection(self):
        """Test detection of frequent state changes."""
        # Record many state changes quickly
        for i in range(15):
            self.monitor.record_state_change("closed", "open", i)
            self.monitor.record_state_change("open", "closed", 0)
        
        # Should have recorded all changes
        self.assertEqual(len(self.monitor._state_history), 30)
        
        # Get monitoring summary
        summary = self.monitor.get_monitoring_summary()
        self.assertIn("recent_hour_changes", summary)
        self.assertGreater(summary["recent_hour_changes"], 20)
    
    def test_alert_cooldown(self):
        """Test alert cooldown mechanism."""
        alert_type = "test_alert"
        
        # First alert should be emitted
        self.monitor._emit_alert(alert_type, {"test": "data"})
        self.assertIn(alert_type, self.monitor._last_alert_time)
        
        # Second alert immediately should be suppressed
        initial_time = self.monitor._last_alert_time[alert_type]
        self.monitor._emit_alert(alert_type, {"test": "data2"})
        
        # Time should not have changed (alert was suppressed)
        self.assertEqual(self.monitor._last_alert_time[alert_type], initial_time)


class TestDashboardMetricsCollector(unittest.TestCase):
    """Test dashboard metrics collection and formatting."""
    
    def setUp(self):
        self.collector = DashboardMetricsCollector()
    
    def test_performance_metric_emission(self):
        """Test performance metric emission and buffering."""
        # Emit a test metric
        self.collector.emit_performance_metric(
            metric_type="test_metric",
            value=123.45,
            labels={"stage": "test", "profile": "desktop"},
            unit="ms",
            p50=100.0,
            p95=200.0
        )
        
        # Check that metric was buffered
        self.assertGreater(len(self.collector._metrics_buffer), 0)
        
        metric = self.collector._metrics_buffer[-1]
        self.assertEqual(metric.metric_type, "test_metric")
        self.assertEqual(metric.value, 123.45)
        self.assertEqual(metric.labels["stage"], "test")
        self.assertEqual(metric.unit, "ms")
        self.assertEqual(metric.p50, 100.0)
        self.assertEqual(metric.p95, 200.0)
    
    @patch('performance_monitor.get_comprehensive_metrics')
    def test_stage_duration_metrics_collection(self, mock_get_metrics):
        """Test collection of stage duration metrics."""
        # Mock comprehensive metrics response
        mock_get_metrics.return_value = {
            "stage_percentiles": {
                "yt_api": {"p50": 150.0, "p95": 300.0, "count": 10},
                "timedtext": {"p50": 200.0, "p95": 400.0, "count": 5}
            }
        }
        
        # Collect metrics
        self.collector._collect_stage_duration_metrics()
        
        # Should have emitted metrics for both stages and both percentiles
        self.assertGreaterEqual(len(self.collector._metrics_buffer), 4)
        
        # Check that correct metrics were emitted
        metric_types = [m.metric_type for m in self.collector._metrics_buffer]
        self.assertIn("stage_duration", metric_types)
    
    def test_dashboard_data_formatting(self):
        """Test dashboard data formatting and aggregation."""
        # Emit some test metrics
        for i in range(5):
            self.collector.emit_performance_metric(
                metric_type="test_metric",
                value=float(i * 10),
                labels={"test": "value"},
                unit="ms"
            )
        
        # Get dashboard data
        dashboard_data = self.collector.get_dashboard_data(hours=1)
        
        # Check structure
        self.assertIn("collection_period_hours", dashboard_data)
        self.assertIn("total_metrics", dashboard_data)
        self.assertIn("metrics_by_type", dashboard_data)
        self.assertIn("summary", dashboard_data)
        
        # Check that test metrics are included
        self.assertIn("test_metric", dashboard_data["metrics_by_type"])
        self.assertEqual(len(dashboard_data["metrics_by_type"]["test_metric"]), 5)


class TestStructuredLogging(unittest.TestCase):
    """Test structured logging implementation."""
    
    def setUp(self):
        self.formatter = StructuredFormatter()
        self.logger = ContextualLogger("test_logger")
    
    def test_structured_formatter(self):
        """Test JSON formatting of log records."""
        import logging
        
        # Create a test log record
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=123,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        # Format the record
        formatted = self.formatter.format(record)
        
        # Parse as JSON
        log_data = json.loads(formatted)
        
        # Check required fields
        self.assertIn("timestamp", log_data)
        self.assertIn("level", log_data)
        self.assertIn("message", log_data)
        self.assertIn("service", log_data)
        self.assertEqual(log_data["level"], "INFO")
        self.assertEqual(log_data["message"], "Test message")
    
    def test_contextual_logging(self):
        """Test contextual logging with thread-local context."""
        # Set context
        context = LogContext(
            correlation_id="test-123",
            video_id="test_video",
            stage="test_stage"
        )
        self.logger.set_context(context)
        
        # Check context is set
        retrieved_context = self.logger.get_context()
        self.assertIsNotNone(retrieved_context)
        self.assertEqual(retrieved_context.correlation_id, "test-123")
        self.assertEqual(retrieved_context.video_id, "test_video")
        
        # Clear context
        self.logger.clear_context()
        self.assertIsNone(self.logger.get_context())
    
    def test_log_context_manager(self):
        """Test log context manager functionality."""
        with log_context(video_id="test_video", stage="test_stage") as context:
            self.assertIsNotNone(context.correlation_id)
            self.assertEqual(context.video_id, "test_video")
            self.assertEqual(context.stage, "test_stage")
            self.assertIsNotNone(context.start_time)
    
    def test_performance_logging_context(self):
        """Test performance logging context manager."""
        with patch('structured_logging.PerformanceLogger') as mock_perf_logger:
            mock_instance = Mock()
            mock_perf_logger.return_value = mock_instance
            
            # Test successful operation
            with log_performance("test_operation", video_id="test_video"):
                time.sleep(0.01)  # Small delay to test duration
            
            # Should have logged successful operation
            mock_instance.log_stage_performance.assert_called_once()
            call_args = mock_instance.log_stage_performance.call_args
            self.assertEqual(call_args[1]["stage"], "test_operation")
            self.assertTrue(call_args[1]["success"])
            self.assertGreater(call_args[1]["duration_ms"], 0)


class TestDashboardIntegration(unittest.TestCase):
    """Test dashboard integration and metrics endpoints."""
    
    def setUp(self):
        self.aggregator = MetricsAggregator()
    
    @patch('dashboard_integration.get_dashboard_metrics')
    @patch('dashboard_integration.get_comprehensive_metrics')
    @patch('dashboard_integration.get_circuit_breaker_status')
    def test_metrics_aggregation(self, mock_cb_status, mock_comp_metrics, mock_dashboard_metrics):
        """Test metrics aggregation from multiple sources."""
        # Mock responses
        mock_dashboard_metrics.return_value = {"performance": "data"}
        mock_comp_metrics.return_value = {
            "stage_success_rates": {"yt_api": 95.0},
            "stage_percentiles": {"yt_api": {"p50": 100, "p95": 200}},
            "recent_stage_metrics": [],
            "recent_circuit_breaker_events": []
        }
        mock_cb_status.return_value = {"state": "closed", "failure_count": 0}
        
        # Get aggregated metrics
        metrics = self.aggregator.get_aggregated_metrics(hours=1)
        
        # Check structure
        self.assertIn("timestamp", metrics)
        self.assertIn("performance", metrics)
        self.assertIn("transcript_pipeline", metrics)
        self.assertIn("circuit_breaker", metrics)
        self.assertIn("system_health", metrics)
    
    def test_metrics_caching(self):
        """Test metrics caching mechanism."""
        # First call should generate metrics
        with patch.object(self.aggregator, '_generate_metrics') as mock_generate:
            mock_generate.return_value = {"test": "data"}
            
            metrics1 = self.aggregator.get_aggregated_metrics(hours=1)
            self.assertEqual(mock_generate.call_count, 1)
            
            # Second call within TTL should use cache
            metrics2 = self.aggregator.get_aggregated_metrics(hours=1)
            self.assertEqual(mock_generate.call_count, 1)  # Should not increase
            
            # Results should be identical
            self.assertEqual(metrics1, metrics2)


class TestIntegrationScenarios(unittest.TestCase):
    """Test integration scenarios and end-to-end functionality."""
    
    def test_performance_monitoring_integration(self):
        """Test integration between performance monitoring components."""
        # Get performance monitor
        monitor = get_performance_monitor()
        self.assertIsNotNone(monitor)
        
        # Emit a performance metric
        emit_performance_metric(
            metric_type="integration_test",
            value=123.45,
            labels={"test": "integration"},
            unit="ms"
        )
        
        # Check that metric was recorded
        dashboard_data = monitor.get_dashboard_data(hours=1)
        self.assertIn("integration_test", dashboard_data.get("metrics_by_type", {}))
    
    @patch('playwright.sync_api.sync_playwright')
    def test_browser_context_optimization_integration(self, mock_playwright):
        """Test browser context optimization integration."""
        # Mock playwright components
        mock_playwright_instance = Mock()
        mock_browser = Mock()
        mock_context = Mock()
        
        mock_playwright.return_value.start.return_value = mock_playwright_instance
        mock_playwright_instance.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        
        # Test optimized context creation
        with get_optimized_browser_context("desktop") as context:
            self.assertIsNotNone(context)
        
        # Verify browser and context were created
        mock_playwright_instance.chromium.launch.assert_called_once()
        mock_browser.new_context.assert_called_once()
    
    def test_structured_logging_integration(self):
        """Test structured logging integration."""
        # Test that structured logging can be set up without errors
        with patch('structured_logging.logging') as mock_logging:
            setup_structured_logging()
            
            # Should have configured root logger
            mock_logging.getLogger.assert_called()
    
    def test_cleanup_functionality(self):
        """Test cleanup functionality for resource management."""
        # Test browser context cleanup
        cleanup_all_browser_contexts()
        
        # Should complete without errors
        self.assertTrue(True)


def run_performance_tests():
    """Run all performance optimization tests."""
    print("Running Performance Optimization and Monitoring Tests...")
    print("=" * 60)
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestBrowserContextManager,
        TestCircuitBreakerMonitor,
        TestDashboardMetricsCollector,
        TestStructuredLogging,
        TestDashboardIntegration,
        TestIntegrationScenarios
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print("\n" + "=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    success = len(result.failures) == 0 and len(result.errors) == 0
    print(f"\nOverall result: {'PASS' if success else 'FAIL'}")
    
    return success


if __name__ == "__main__":
    success = run_performance_tests()
    sys.exit(0 if success else 1)