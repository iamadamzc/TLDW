"""
Monitoring Validation Tests for TL;DW Application

Tests the monitoring and alerting infrastructure including CloudWatch integration,
dashboard configurations, alert configurations, and metrics publishing.
"""

import json
import logging
import unittest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from io import StringIO
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cloudwatch_dashboard_config import CloudWatchDashboardConfig
from cloudwatch_alerts_config import CloudWatchAlertsConfig
from cloudwatch_metrics_publisher import (
    LogBasedMetricsCollector, 
    CloudWatchMetricsPublisher, 
    MetricsCollectionScheduler,
    MetricData
)
from cloudwatch_logs_client import CloudWatchLogsClient
from cloudwatch_query_templates import QUERY_TEMPLATES
from logging_setup import JsonFormatter, configure_logging, set_job_ctx
from log_events import evt, StageTimer, job_received, job_finished


class TestCloudWatchDashboardConfig(unittest.TestCase):
    """Test CloudWatch dashboard configuration generation."""
    
    def setUp(self):
        """Set up test environment."""
        self.config = CloudWatchDashboardConfig()
    
    def test_main_dashboard_creation(self):
        """Test main dashboard configuration creation."""
        dashboard = self.config.create_main_dashboard()
        
        # Should have widgets
        self.assertIn('widgets', dashboard)
        self.assertGreater(len(dashboard['widgets']), 5)
        
        # Check widget structure
        for widget in dashboard['widgets']:
            self.assertIn('type', widget)
            self.assertIn('properties', widget)
            self.assertIn('title', widget['properties'])
            
            # Log widgets should have query
            if widget['type'] == 'log':
                self.assertIn('query', widget['properties'])
                self.assertIn('region', widget['properties'])
    
    def test_performance_dashboard_creation(self):
        """Test performance dashboard configuration creation."""
        dashboard = self.config.create_performance_dashboard()
        
        self.assertIn('widgets', dashboard)
        self.assertGreater(len(dashboard['widgets']), 3)
        
        # Should have performance-specific widgets
        widget_titles = [w['properties']['title'] for w in dashboard['widgets']]
        self.assertTrue(any('Duration' in title for title in widget_titles))
        self.assertTrue(any('Performance' in title for title in widget_titles))
    
    def test_error_analysis_dashboard_creation(self):
        """Test error analysis dashboard configuration creation."""
        dashboard = self.config.create_error_analysis_dashboard()
        
        self.assertIn('widgets', dashboard)
        self.assertGreater(len(dashboard['widgets']), 3)
        
        # Should have error-specific widgets
        widget_titles = [w['properties']['title'] for w in dashboard['widgets']]
        self.assertTrue(any('Error' in title for title in widget_titles))
        self.assertTrue(any('Failed' in title for title in widget_titles))
    
    def test_dashboard_json_export(self):
        """Test dashboard JSON export functionality."""
        # Test main dashboard export
        json_output = self.config.export_dashboard_json('main')
        dashboard_data = json.loads(json_output)
        
        self.assertIn('widgets', dashboard_data)
        
        # Test performance dashboard export
        json_output = self.config.export_dashboard_json('performance')
        dashboard_data = json.loads(json_output)
        
        self.assertIn('widgets', dashboard_data)
        
        # Test invalid dashboard type
        with self.assertRaises(ValueError):
            self.config.export_dashboard_json('invalid')
    
    def test_widget_query_validation(self):
        """Test that widget queries are valid CloudWatch Logs Insights syntax."""
        dashboard = self.config.create_main_dashboard()
        
        for widget in dashboard['widgets']:
            if widget['type'] == 'log':
                query = widget['properties']['query']
                
                # Should contain SOURCE directive
                self.assertIn('SOURCE', query)
                
                # Should contain valid CloudWatch syntax
                self.assertTrue(
                    any(keyword in query for keyword in ['fields', 'filter', 'stats', 'sort']),
                    f"Query missing CloudWatch keywords: {query[:100]}..."
                )
    
    def test_dashboard_url_generation(self):
        """Test dashboard URL generation."""
        url = self.config.get_dashboard_url('test-dashboard')
        
        self.assertIn('console.aws.amazon.com', url)
        self.assertIn('cloudwatch', url)
        self.assertIn('dashboards', url)
        self.assertIn('test-dashboard', url)


class TestCloudWatchAlertsConfig(unittest.TestCase):
    """Test CloudWatch alerts configuration generation."""
    
    def setUp(self):
        """Set up test environment."""
        self.config = CloudWatchAlertsConfig(
            sns_topic_arn='arn:aws:sns:us-east-1:123456789012:test-topic'
        )
    
    def test_error_rate_alerts_creation(self):
        """Test error rate alert configurations."""
        alerts = self.config.create_error_rate_alerts()
        
        self.assertGreater(len(alerts), 2)
        
        # Check alert structure
        for alert in alerts:
            self.assertIn('AlarmName', alert)
            self.assertIn('AlarmDescription', alert)
            self.assertIn('MetricName', alert)
            self.assertIn('Threshold', alert)
            self.assertIn('ComparisonOperator', alert)
            self.assertIn('LogInsightsQuery', alert)
            
            # Should have SNS topic configured
            self.assertIn('AlarmActions', alert)
            self.assertEqual(len(alert['AlarmActions']), 1)
    
    def test_performance_alerts_creation(self):
        """Test performance alert configurations."""
        alerts = self.config.create_performance_alerts()
        
        self.assertGreater(len(alerts), 2)
        
        # Check for performance-specific alerts
        alert_names = [alert['AlarmName'] for alert in alerts]
        self.assertTrue(any('P95' in name or 'Duration' in name for name in alert_names))
    
    def test_system_health_alerts_creation(self):
        """Test system health alert configurations."""
        alerts = self.config.create_system_health_alerts()
        
        self.assertGreater(len(alerts), 2)
        
        # Check for system health alerts
        alert_names = [alert['AlarmName'] for alert in alerts]
        self.assertTrue(any('Circuit' in name or 'Memory' in name for name in alert_names))
    
    def test_all_alerts_creation(self):
        """Test creation of all alert configurations."""
        all_alerts = self.config.create_all_alerts()
        
        self.assertGreater(len(all_alerts), 8)  # Should have multiple alert types
        
        # Check uniqueness of alert names
        alert_names = [alert['AlarmName'] for alert in all_alerts]
        self.assertEqual(len(alert_names), len(set(alert_names)))
    
    def test_cloudformation_template_export(self):
        """Test CloudFormation template export."""
        template_json = self.config.export_cloudformation_template()
        template = json.loads(template_json)
        
        # Check CloudFormation structure
        self.assertIn('AWSTemplateFormatVersion', template)
        self.assertIn('Description', template)
        self.assertIn('Parameters', template)
        self.assertIn('Resources', template)
        
        # Check parameters
        self.assertIn('SNSTopicArn', template['Parameters'])
        self.assertIn('LogGroupName', template['Parameters'])
        
        # Check resources
        self.assertGreater(len(template['Resources']), 5)
        
        # Check resource structure
        for resource_name, resource in template['Resources'].items():
            self.assertEqual(resource['Type'], 'AWS::CloudWatch::Alarm')
            self.assertIn('Properties', resource)
    
    def test_terraform_config_export(self):
        """Test Terraform configuration export."""
        terraform_config = self.config.export_terraform_config()
        
        # Should contain Terraform resource blocks
        self.assertIn('resource "aws_cloudwatch_metric_alarm"', terraform_config)
        self.assertIn('alarm_name', terraform_config)
        self.assertIn('threshold', terraform_config)
        
        # Should have multiple resources
        resource_count = terraform_config.count('resource "aws_cloudwatch_metric_alarm"')
        self.assertGreater(resource_count, 5)
    
    def test_alert_query_validation(self):
        """Test that alert queries are valid."""
        all_alerts = self.config.create_all_alerts()
        
        for alert in all_alerts:
            query = alert.get('LogInsightsQuery', '')
            if query:
                # Should contain SOURCE directive
                self.assertIn('SOURCE', query)
                
                # Should contain valid CloudWatch syntax
                self.assertTrue(
                    any(keyword in query for keyword in ['fields', 'filter', 'stats']),
                    f"Alert {alert['AlarmName']} has invalid query"
                )
    
    def test_alert_thresholds_reasonable(self):
        """Test that alert thresholds are reasonable."""
        all_alerts = self.config.create_all_alerts()
        
        for alert in all_alerts:
            threshold = alert['Threshold']
            
            # Thresholds should be positive
            self.assertGreater(threshold, 0)
            
            # Rate-based thresholds should be reasonable percentages
            if 'Rate' in alert['AlarmName']:
                self.assertLessEqual(threshold, 100)  # Should not exceed 100%
            
            # Duration thresholds should be reasonable
            if 'Duration' in alert['AlarmName']:
                self.assertLessEqual(threshold, 300000)  # Should not exceed 5 minutes


class TestLogBasedMetricsCollector(unittest.TestCase):
    """Test log-based metrics collection."""
    
    def setUp(self):
        """Set up test environment."""
        self.collector = LogBasedMetricsCollector()
        
        # Mock the CloudWatch clients
        self.collector.cloudwatch_client = Mock()
        self.collector.logs_client = Mock()
    
    def test_stage_success_rates_collection(self):
        """Test stage success rate metrics collection."""
        # Mock query result
        mock_result = {
            'status': 'Complete',
            'results': [
                [
                    {'field': 'stage', 'value': 'youtube-transcript-api'},
                    {'field': 'success_pct', 'value': '85.5'},
                    {'field': 'total', 'value': '100'}
                ],
                [
                    {'field': 'stage', 'value': 'youtubei'},
                    {'field': 'success_pct', 'value': '72.3'},
                    {'field': 'total', 'value': '50'}
                ]
            ]
        }
        
        self.collector.logs_client.run_query.return_value = mock_result
        
        metrics = self.collector.collect_stage_success_rates()
        
        # Should have metrics for both stages
        self.assertGreater(len(metrics), 2)
        
        # Check metric structure
        for metric in metrics:
            self.assertIsInstance(metric, MetricData)
            self.assertIn(metric.metric_name, ['StageSuccessRate', 'StageAttemptCount'])
            self.assertIn('Stage', metric.dimensions)
            self.assertGreater(metric.value, 0)
    
    def test_performance_metrics_collection(self):
        """Test performance metrics collection."""
        mock_result = {
            'status': 'Complete',
            'results': [
                [
                    {'field': 'stage', 'value': 'youtubei'},
                    {'field': 'avg_ms', 'value': '5000'},
                    {'field': 'p95_ms', 'value': '12000'},
                    {'field': 'p99_ms', 'value': '25000'},
                    {'field': 'sample_count', 'value': '25'}
                ]
            ]
        }
        
        self.collector.logs_client.run_query.return_value = mock_result
        
        metrics = self.collector.collect_performance_metrics()
        
        # Should have multiple performance metrics
        self.assertGreater(len(metrics), 2)
        
        # Check for expected metric types
        metric_names = [m.metric_name for m in metrics]
        self.assertIn('StageDurationAverage', metric_names)
        self.assertIn('StageDurationP95', metric_names)
        self.assertIn('StageDurationP99', metric_names)
    
    def test_error_rate_metrics_collection(self):
        """Test error rate metrics collection."""
        mock_result = {
            'status': 'Complete',
            'results': [
                [
                    {'field': 'stage', 'value': 'youtubei'},
                    {'field': 'error_rate', 'value': '15.5'},
                    {'field': 'errors', 'value': '10'},
                    {'field': 'timeouts', 'value': '5'},
                    {'field': 'total', 'value': '100'}
                ]
            ]
        }
        
        self.collector.logs_client.run_query.return_value = mock_result
        
        metrics = self.collector.collect_error_rate_metrics()
        
        # Should have error metrics
        self.assertGreater(len(metrics), 2)
        
        # Check for expected metric types
        metric_names = [m.metric_name for m in metrics]
        self.assertIn('StageErrorRate', metric_names)
        self.assertIn('StageErrorCount', metric_names)
    
    def test_collection_error_handling(self):
        """Test error handling in metrics collection."""
        # Mock failed query
        self.collector.logs_client.run_query.return_value = {
            'status': 'Failed',
            'error': 'Query execution failed'
        }
        
        # Should handle errors gracefully
        metrics = self.collector.collect_stage_success_rates()
        self.assertEqual(len(metrics), 0)
        
        # Test exception handling
        self.collector.logs_client.run_query.side_effect = Exception("Connection error")
        
        metrics = self.collector.collect_performance_metrics()
        self.assertEqual(len(metrics), 0)
    
    def test_collect_all_metrics(self):
        """Test collection of all metric types."""
        # Mock successful results for all collection methods
        mock_result = {
            'status': 'Complete',
            'results': [
                [
                    {'field': 'stage', 'value': 'test'},
                    {'field': 'success_pct', 'value': '80'},
                    {'field': 'total', 'value': '10'}
                ]
            ]
        }
        
        self.collector.logs_client.run_query.return_value = mock_result
        
        # Mock CloudWatch query for job and system metrics
        self.collector.cloudwatch_client.start_query.return_value = {'queryId': 'test-query-id'}
        self.collector.cloudwatch_client.get_query_results.return_value = {
            'status': 'Complete',
            'results': [
                [
                    {'field': 'received', 'value': '5'},
                    {'field': 'completed_success', 'value': '4'},
                    {'field': 'completed_failed', 'value': '1'}
                ]
            ]
        }
        
        all_metrics = self.collector.collect_all_metrics()
        
        # Should collect metrics from multiple sources
        self.assertGreater(len(all_metrics), 5)


class TestCloudWatchMetricsPublisher(unittest.TestCase):
    """Test CloudWatch metrics publishing."""
    
    def setUp(self):
        """Set up test environment."""
        self.publisher = CloudWatchMetricsPublisher()
        self.publisher.cloudwatch_client = Mock()
    
    def test_metrics_publishing(self):
        """Test publishing metrics to CloudWatch."""
        # Create test metrics
        metrics = [
            MetricData(
                metric_name='TestMetric1',
                value=100.0,
                unit='Count',
                dimensions={'Stage': 'test'},
                timestamp=datetime.utcnow()
            ),
            MetricData(
                metric_name='TestMetric2',
                value=50.5,
                unit='Percent',
                dimensions={'Stage': 'test', 'Type': 'success'},
                timestamp=datetime.utcnow()
            )
        ]
        
        # Publish metrics
        success = self.publisher.publish_metrics(metrics)
        
        self.assertTrue(success)
        self.publisher.cloudwatch_client.put_metric_data.assert_called_once()
        
        # Check the call arguments
        call_args = self.publisher.cloudwatch_client.put_metric_data.call_args
        self.assertIn('Namespace', call_args[1])
        self.assertIn('MetricData', call_args[1])
        
        metric_data = call_args[1]['MetricData']
        self.assertEqual(len(metric_data), 2)
    
    def test_batch_publishing(self):
        """Test publishing large batches of metrics."""
        # Create more metrics than batch size
        metrics = []
        for i in range(25):  # More than batch_size (20)
            metrics.append(MetricData(
                metric_name=f'TestMetric{i}',
                value=float(i),
                unit='Count',
                dimensions={'Index': str(i)},
                timestamp=datetime.utcnow()
            ))
        
        success = self.publisher.publish_metrics(metrics)
        
        self.assertTrue(success)
        
        # Should make multiple calls due to batching
        self.assertGreater(self.publisher.cloudwatch_client.put_metric_data.call_count, 1)
    
    def test_empty_metrics_handling(self):
        """Test handling of empty metrics list."""
        success = self.publisher.publish_metrics([])
        
        self.assertTrue(success)
        self.publisher.cloudwatch_client.put_metric_data.assert_not_called()
    
    def test_publishing_error_handling(self):
        """Test error handling during publishing."""
        self.publisher.cloudwatch_client.put_metric_data.side_effect = Exception("AWS Error")
        
        metrics = [MetricData(
            metric_name='TestMetric',
            value=100.0,
            unit='Count',
            dimensions={},
            timestamp=datetime.utcnow()
        )]
        
        success = self.publisher.publish_metrics(metrics)
        
        self.assertFalse(success)


class TestMetricsCollectionScheduler(unittest.TestCase):
    """Test metrics collection scheduler."""
    
    def setUp(self):
        """Set up test environment."""
        self.scheduler = MetricsCollectionScheduler(collection_interval=1)  # 1 second for testing
        
        # Mock the collector and publisher
        self.scheduler.collector = Mock()
        self.scheduler.publisher = Mock()
    
    def test_one_time_collection(self):
        """Test one-time metrics collection and publishing."""
        # Mock successful collection
        mock_metrics = [
            MetricData('TestMetric', 100.0, 'Count', {}, datetime.utcnow())
        ]
        self.scheduler.collector.collect_all_metrics.return_value = mock_metrics
        self.scheduler.publisher.publish_metrics.return_value = True
        
        count = self.scheduler.collect_and_publish_once()
        
        self.assertEqual(count, 1)
        self.scheduler.collector.collect_all_metrics.assert_called_once()
        self.scheduler.publisher.publish_metrics.assert_called_once_with(mock_metrics)
    
    def test_scheduler_start_stop(self):
        """Test scheduler start and stop functionality."""
        # Mock collection to avoid actual CloudWatch calls
        self.scheduler.collector.collect_all_metrics.return_value = []
        
        # Start scheduler
        self.scheduler.start()
        self.assertTrue(self.scheduler.running)
        self.assertIsNotNone(self.scheduler.scheduler_thread)
        
        # Let it run briefly
        time.sleep(0.1)
        
        # Stop scheduler
        self.scheduler.stop()
        self.assertFalse(self.scheduler.running)
    
    def test_collection_loop_error_handling(self):
        """Test error handling in collection loop."""
        # Mock collection to raise exception
        self.scheduler.collector.collect_all_metrics.side_effect = Exception("Collection error")
        
        # Start and stop quickly to test error handling
        self.scheduler.start()
        time.sleep(0.1)
        self.scheduler.stop()
        
        # Should not crash despite the exception


class TestMonitoringIntegration(unittest.TestCase):
    """Integration tests for monitoring components."""
    
    def setUp(self):
        """Set up integration test environment."""
        # Set up logging to capture structured logs
        self.log_buffer = StringIO()
        self.handler = logging.StreamHandler(self.log_buffer)
        self.handler.setFormatter(JsonFormatter())
        
        self.logger = logging.getLogger()
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)
    
    def tearDown(self):
        """Clean up integration test environment."""
        self.logger.removeHandler(self.handler)
        self.handler.close()
    
    def test_end_to_end_monitoring_flow(self):
        """Test complete monitoring flow from logs to metrics."""
        # Generate sample log events
        set_job_ctx(job_id='j-monitor-test', video_id='monitor-video-123')
        
        # Job lifecycle with various outcomes
        job_received(video_count=2, use_cookies=True, proxy_enabled=True)
        
        # Successful stage
        with StageTimer("youtube-transcript-api", attempt=1):
            time.sleep(0.01)  # Small delay for realistic duration
        
        # Failed stage
        try:
            with StageTimer("youtubei", attempt=2, use_proxy=True, profile="mobile"):
                raise TimeoutError("Request timed out")
        except TimeoutError:
            pass
        
        # Job completion
        job_finished(
            total_duration_ms=1500,
            processed_count=1,
            video_count=2,
            outcome="partial_success"
        )
        
        # Parse generated logs
        log_output = self.log_buffer.getvalue()
        log_entries = []
        for line in log_output.strip().split('\n'):
            if line:
                log_entries.append(json.loads(line))
        
        # Verify log structure for monitoring
        self.assertGreater(len(log_entries), 3)
        
        # Check that logs have required fields for metrics
        for log_entry in log_entries:
            self.assertIn('ts', log_entry)
            self.assertIn('lvl', log_entry)
            
            if log_entry.get('event') == 'stage_result':
                self.assertIn('stage', log_entry)
                self.assertIn('outcome', log_entry)
                self.assertIn('dur_ms', log_entry)
    
    def test_dashboard_query_compatibility(self):
        """Test that dashboard queries work with generated log format."""
        # Generate logs with various scenarios
        set_job_ctx(job_id='j-dashboard-test', video_id='dashboard-video-456')
        
        # Multiple stage results for funnel analysis
        evt('stage_result', stage='youtube-transcript-api', outcome='success', dur_ms=500)
        evt('stage_result', stage='timedtext', outcome='no_captions', dur_ms=200)
        evt('stage_result', stage='youtubei', outcome='timeout', dur_ms=30000)
        evt('stage_result', stage='asr', outcome='success', dur_ms=15000)
        
        # Performance metrics
        evt('performance_metric', cpu=25.5, mem_mb=512)
        
        log_output = self.log_buffer.getvalue()
        log_entries = []
        for line in log_output.strip().split('\n'):
            if line:
                log_entries.append(json.loads(line))
        
        # Test that logs contain fields referenced in dashboard queries
        config = CloudWatchDashboardConfig()
        dashboard = config.create_main_dashboard()
        
        # Extract field references from queries
        referenced_fields = set()
        for widget in dashboard['widgets']:
            if widget['type'] == 'log':
                query = widget['properties']['query']
                # Simple field extraction (this is a basic test)
                if 'stage' in query:
                    referenced_fields.add('stage')
                if 'outcome' in query:
                    referenced_fields.add('outcome')
                if 'dur_ms' in query:
                    referenced_fields.add('dur_ms')
        
        # Verify that our logs contain the referenced fields
        stage_result_logs = [log for log in log_entries if log.get('event') == 'stage_result']
        self.assertGreater(len(stage_result_logs), 0)
        
        for log in stage_result_logs:
            for field in referenced_fields:
                if field in ['stage', 'outcome', 'dur_ms']:  # Core fields
                    self.assertIn(field, log, f"Log missing field {field} referenced in dashboard")
    
    def test_alert_query_compatibility(self):
        """Test that alert queries work with generated log format."""
        # Generate logs that would trigger alerts
        set_job_ctx(job_id='j-alert-test', video_id='alert-video-789')
        
        # Generate error events
        for i in range(10):
            evt('stage_result', stage='youtubei', outcome='error', dur_ms=1000, 
                detail=f'Connection error {i}')
        
        # Generate timeout events
        for i in range(5):
            evt('stage_result', stage='youtubei', outcome='timeout', dur_ms=30000,
                detail='Request timeout')
        
        log_output = self.log_buffer.getvalue()
        log_entries = []
        for line in log_output.strip().split('\n'):
            if line:
                log_entries.append(json.loads(line))
        
        # Test alert query compatibility
        config = CloudWatchAlertsConfig()
        alerts = config.create_error_rate_alerts()
        
        # Check that error logs have fields needed for alerts
        error_logs = [log for log in log_entries if log.get('outcome') in ['error', 'timeout']]
        self.assertGreater(len(error_logs), 10)
        
        for log in error_logs:
            # Fields commonly used in alert queries
            self.assertIn('outcome', log)
            self.assertIn('stage', log)
            if 'dur_ms' in log:
                self.assertIsInstance(log['dur_ms'], int)


class TestMonitoringRequirements(unittest.TestCase):
    """Test that monitoring implementation meets specific requirements."""
    
    def test_requirement_7_1_cloudwatch_integration(self):
        """Test Requirement 7.1: CloudWatch Logs Insights integration."""
        # Test that query templates exist and are valid
        self.assertIn('error_analysis', QUERY_TEMPLATES)
        self.assertIn('funnel_analysis', QUERY_TEMPLATES)
        self.assertIn('performance_analysis', QUERY_TEMPLATES)
        
        # Test dashboard configuration
        config = CloudWatchDashboardConfig()
        dashboard = config.create_main_dashboard()
        
        self.assertIn('widgets', dashboard)
        self.assertGreater(len(dashboard['widgets']), 5)
    
    def test_requirement_7_2_dashboard_updates(self):
        """Test Requirement 7.2: Dashboard updates for new log format."""
        config = CloudWatchDashboardConfig()
        
        # Test all dashboard types
        main_dashboard = config.create_main_dashboard()
        perf_dashboard = config.create_performance_dashboard()
        error_dashboard = config.create_error_analysis_dashboard()
        
        # All should have widgets
        for dashboard in [main_dashboard, perf_dashboard, error_dashboard]:
            self.assertIn('widgets', dashboard)
            self.assertGreater(len(dashboard['widgets']), 3)
            
            # Widgets should reference structured log fields
            for widget in dashboard['widgets']:
                if widget['type'] == 'log':
                    query = widget['properties']['query']
                    # Should use structured fields
                    self.assertTrue(
                        any(field in query for field in ['stage', 'outcome', 'dur_ms', 'event']),
                        f"Widget query doesn't use structured fields: {query[:100]}..."
                    )
    
    def test_requirement_7_3_error_rate_alerts(self):
        """Test Requirement 7.3: Error rate and performance threshold alerts."""
        config = CloudWatchAlertsConfig()
        
        # Test error rate alerts
        error_alerts = config.create_error_rate_alerts()
        self.assertGreater(len(error_alerts), 2)
        
        # Test performance alerts
        perf_alerts = config.create_performance_alerts()
        self.assertGreater(len(perf_alerts), 2)
        
        # Check alert structure
        all_alerts = error_alerts + perf_alerts
        for alert in all_alerts:
            self.assertIn('AlarmName', alert)
            self.assertIn('Threshold', alert)
            self.assertIn('ComparisonOperator', alert)
            self.assertIn('LogInsightsQuery', alert)
    
    def test_requirement_7_4_log_based_metrics(self):
        """Test Requirement 7.4: Log-based metrics for stage success rates."""
        collector = LogBasedMetricsCollector()
        
        # Mock successful query results
        collector.logs_client = Mock()
        collector.logs_client.run_query.return_value = {
            'status': 'Complete',
            'results': [
                [
                    {'field': 'stage', 'value': 'youtube-transcript-api'},
                    {'field': 'success_pct', 'value': '85.0'},
                    {'field': 'total', 'value': '100'}
                ]
            ]
        }
        
        # Test metrics collection
        metrics = collector.collect_stage_success_rates()
        
        self.assertGreater(len(metrics), 0)
        
        # Check metric structure
        for metric in metrics:
            self.assertIsInstance(metric, MetricData)
            self.assertIn(metric.metric_name, ['StageSuccessRate', 'StageAttemptCount'])
            self.assertIsInstance(metric.value, float)
            self.assertIsInstance(metric.dimensions, dict)
    
    def test_requirement_7_5_monitoring_validation(self):
        """Test Requirement 7.5: Monitoring validation tests."""
        # This test validates that the monitoring validation tests exist and work
        
        # Test dashboard config validation
        config = CloudWatchDashboardConfig()
        self.assertIsNotNone(config.create_main_dashboard())
        
        # Test alert config validation
        alert_config = CloudWatchAlertsConfig()
        alerts = alert_config.create_all_alerts()
        self.assertGreater(len(alerts), 5)
        
        # Test metrics collection validation
        collector = LogBasedMetricsCollector()
        self.assertIsNotNone(collector)
        
        # Test metrics publishing validation
        publisher = CloudWatchMetricsPublisher()
        self.assertIsNotNone(publisher)


if __name__ == '__main__':
    # Configure logging for tests
    logging.basicConfig(level=logging.WARNING)
    
    unittest.main(verbosity=2)