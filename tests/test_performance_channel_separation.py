#!/usr/bin/env python3
"""
Integration tests for performance metrics channel separation.

Tests Requirements 6.1-6.5:
- 6.1: Dedicated "perf" logger for performance metrics
- 6.2: Pipeline events can be filtered out from performance metrics
- 6.3: CPU/memory metrics use performance channel with structured fields
- 6.4: Stage events separate from resource metrics
- 6.5: Independent retention policies support
"""

import logging
import json
import io
import sys
import unittest
from unittest.mock import patch

# Add parent directory to path for imports
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the modules we're testing
from logging_setup import configure_logging, get_perf_logger
from log_events import evt, perf_evt, log_cpu_memory_metrics, StageTimer


class TestPerformanceChannelSeparation(unittest.TestCase):
    """Test performance metrics channel separation functionality."""
    
    def setUp(self):
        """Set up test environment with clean logging configuration."""
        # Clear any existing handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Clear perf logger handlers
        perf_logger = logging.getLogger('perf')
        for handler in perf_logger.handlers[:]:
            perf_logger.removeHandler(handler)
        
        # Configure logging for testing
        configure_logging(log_level="INFO", use_json=True)
        
        # Capture log output
        self.log_capture = io.StringIO()
        self.perf_capture = io.StringIO()
        
        # Get the formatter from the configured logger
        formatter = logging.getLogger().handlers[0].formatter
        
        # Clear existing handlers and add our test handlers
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        
        # Add handler for main logger
        main_handler = logging.StreamHandler(self.log_capture)
        main_handler.setFormatter(formatter)
        root_logger.addHandler(main_handler)
        
        # Configure perf logger separately
        perf_logger = get_perf_logger()
        perf_logger.handlers.clear()
        perf_logger.propagate = False  # Don't propagate to root logger
        
        perf_handler = logging.StreamHandler(self.perf_capture)
        perf_handler.setFormatter(formatter)
        perf_logger.addHandler(perf_handler)
    
    def tearDown(self):
        """Clean up after test."""
        self.log_capture.close()
        self.perf_capture.close()
    
    def get_main_logs(self):
        """Get logs from main logger as list of parsed JSON objects."""
        logs = []
        for line in self.log_capture.getvalue().strip().split('\n'):
            if line.strip():
                try:
                    logs.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return logs
    
    def get_perf_logs(self):
        """Get logs from performance logger as list of parsed JSON objects."""
        logs = []
        for line in self.perf_capture.getvalue().strip().split('\n'):
            if line.strip():
                try:
                    logs.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return logs
    
    def test_dedicated_perf_logger_creation(self):
        """Test Requirement 6.1: Dedicated 'perf' logger for performance metrics."""
        # Get the performance logger
        perf_logger = get_perf_logger()
        
        # Verify it has the correct name
        assert perf_logger.name == 'perf'
        
        # Verify it's a different instance from the main logger
        main_logger = logging.getLogger()
        assert perf_logger != main_logger
        assert perf_logger.name != main_logger.name
    
    def test_performance_metrics_use_perf_channel(self):
        """Test that performance metrics use the dedicated perf channel."""
        # Emit a performance metric
        perf_evt(cpu_percent=15.2, memory_mb=512)
        
        # Check that it appears in perf logs
        perf_logs = self.get_perf_logs()
        assert len(perf_logs) == 1
        
        perf_log = perf_logs[0]
        assert perf_log['event'] == 'performance_metric'
        assert perf_log['cpu_percent'] == 15.2
        assert perf_log['memory_mb'] == 512
        
        # Check that it doesn't appear in main logs
        main_logs = self.get_main_logs()
        performance_events = [log for log in main_logs if log.get('event') == 'performance_metric']
        assert len(performance_events) == 0
    
    def test_pipeline_events_separate_from_performance(self):
        """Test Requirement 6.2: Pipeline events can be filtered out from performance metrics."""
        # Emit a pipeline event
        evt("stage_result", stage="youtubei", outcome="success", dur_ms=1250)
        
        # Emit a performance metric
        perf_evt(metric_type="stage_duration", stage="youtubei", duration_ms=1250)
        
        # Check main logs contain pipeline event
        main_logs = self.get_main_logs()
        pipeline_events = [log for log in main_logs if log.get('event') == 'stage_result']
        assert len(pipeline_events) == 1
        
        # Check perf logs contain performance metric
        perf_logs = self.get_perf_logs()
        perf_events = [log for log in perf_logs if log.get('event') == 'performance_metric']
        assert len(perf_events) == 1
        
        # Verify filtering capability: main logs should not have performance_metric events
        main_perf_events = [log for log in main_logs if log.get('event') == 'performance_metric']
        assert len(main_perf_events) == 0
        
        # Verify filtering capability: perf logs should not have stage_result events
        perf_pipeline_events = [log for log in perf_logs if log.get('event') == 'stage_result']
        assert len(perf_pipeline_events) == 0
    
    def test_cpu_memory_metrics_structured_fields(self):
        """Test Requirement 6.3: CPU/memory metrics use performance channel with structured fields."""
        # Log CPU and memory metrics
        log_cpu_memory_metrics(cpu_percent=25.5, memory_mb=1024, disk_usage_pct=45.0)
        
        # Check perf logs
        perf_logs = self.get_perf_logs()
        assert len(perf_logs) == 1
        
        perf_log = perf_logs[0]
        assert perf_log['event'] == 'performance_metric'
        assert perf_log['metric_type'] == 'system_resources'
        assert perf_log['cpu_percent'] == 25.5
        assert perf_log['memory_mb'] == 1024
        assert perf_log['disk_usage_pct'] == 45.0
        
        # Verify structured fields are present
        required_fields = ['ts', 'lvl', 'event', 'metric_type', 'cpu_percent', 'memory_mb']
        for field in required_fields:
            assert field in perf_log
    
    def test_stage_events_separate_from_resource_metrics(self):
        """Test Requirement 6.4: Stage events separate from resource metrics."""
        # Emit stage event using StageTimer
        with StageTimer("youtubei", profile="mobile"):
            pass  # Simulate stage processing
        
        # Emit resource metrics
        log_cpu_memory_metrics(cpu_percent=30.0, memory_mb=768)
        
        # Check main logs for stage events
        main_logs = self.get_main_logs()
        stage_start_events = [log for log in main_logs if log.get('event') == 'stage_start']
        stage_result_events = [log for log in main_logs if log.get('event') == 'stage_result']
        
        assert len(stage_start_events) == 1
        assert len(stage_result_events) == 1
        assert stage_start_events[0]['stage'] == 'youtubei'
        assert stage_result_events[0]['stage'] == 'youtubei'
        
        # Check perf logs for resource metrics
        perf_logs = self.get_perf_logs()
        resource_events = [log for log in perf_logs if log.get('metric_type') == 'system_resources']
        
        assert len(resource_events) == 1
        assert resource_events[0]['cpu_percent'] == 30.0
        assert resource_events[0]['memory_mb'] == 768
        
        # Verify separation: main logs should not have resource metrics
        main_resource_events = [log for log in main_logs if log.get('metric_type') == 'system_resources']
        assert len(main_resource_events) == 0
        
        # Verify separation: perf logs should not have stage events
        perf_stage_events = [log for log in perf_logs if log.get('event') in ['stage_start', 'stage_result']]
        assert len(perf_stage_events) == 0
    
    def test_independent_retention_policies_support(self):
        """Test Requirement 6.5: Independent retention policies support."""
        # This test verifies that the channels are truly separate by checking logger names
        main_logger = logging.getLogger()
        perf_logger = get_perf_logger()
        
        # Verify different logger names enable independent configuration
        assert main_logger.name == 'root'
        assert perf_logger.name == 'perf'
        
        # Emit events to both channels
        evt("job_received", video_id="test123")
        perf_evt(metric_type="test_metric", value=42)
        
        # Verify events go to correct channels
        main_logs = self.get_main_logs()
        perf_logs = self.get_perf_logs()
        
        # Main channel should have job event
        job_events = [log for log in main_logs if log.get('event') == 'job_received']
        assert len(job_events) == 1
        
        # Perf channel should have metric event
        metric_events = [log for log in perf_logs if log.get('metric_type') == 'test_metric']
        assert len(metric_events) == 1
        
        # Cross-contamination check
        main_metric_events = [log for log in main_logs if log.get('metric_type') == 'test_metric']
        perf_job_events = [log for log in perf_logs if log.get('event') == 'job_received']
        
        assert len(main_metric_events) == 0
        assert len(perf_job_events) == 0
    
    def test_performance_event_json_schema(self):
        """Test that performance events follow the expected JSON schema."""
        # Emit various performance metrics
        perf_evt(metric_type="stage_duration", stage="youtubei", duration_ms=1500, success=True)
        perf_evt(metric_type="circuit_breaker", state="closed", failure_count=0)
        log_cpu_memory_metrics(cpu_percent=20.0, memory_mb=512)
        
        perf_logs = self.get_perf_logs()
        assert len(perf_logs) == 3
        
        # Check each log has required fields
        for log in perf_logs:
            # Standard fields
            assert 'ts' in log
            assert 'lvl' in log
            assert 'event' in log
            assert log['event'] == 'performance_metric'
            
            # Performance-specific fields
            assert 'metric_type' in log
            
            # Verify timestamp format (ISO 8601 with milliseconds)
            import re
            timestamp_pattern = r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z'
            assert re.match(timestamp_pattern, log['ts'])
    
    def test_legacy_performance_logger_compatibility(self):
        """Test that legacy performance logger calls work with new channel."""
        from structured_logging import performance_logger
        
        # Use legacy performance logger
        performance_logger.log_stage_performance(
            stage="test_stage",
            duration_ms=2000.0,
            success=True,
            video_id="test_video"
        )
        
        # Check that it appears in perf logs
        perf_logs = self.get_perf_logs()
        assert len(perf_logs) == 1
        
        perf_log = perf_logs[0]
        assert perf_log['event'] == 'performance_metric'
        assert perf_log['metric_type'] == 'stage_performance'
        assert perf_log['stage'] == 'test_stage'
        assert perf_log['duration_ms'] == 2000.0
        assert perf_log['success'] is True
        # Note: video_id is not included in the new perf_evt implementation
        # as it focuses on performance metrics rather than job correlation


if __name__ == '__main__':
    unittest.main(verbosity=2)