"""
CloudWatch Logs Insights query validation tests.

Tests that all query templates are syntactically valid and work with
the structured JSON logging schema.
"""

import json
import logging
import unittest
import re
from io import StringIO
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logging_setup import JsonFormatter, configure_logging, set_job_ctx
from log_events import evt, StageTimer, job_received, job_finished
import cloudwatch_query_templates


class TestCloudWatchQueryValidation(unittest.TestCase):
    """Test CloudWatch Logs Insights query templates."""
    
    def setUp(self):
        """Set up test environment with sample log data."""
        # Create sample log data that matches our schema
        self.sample_logs = []
        
        # Configure logging to capture sample data
        self.log_buffer = StringIO()
        self.handler = logging.StreamHandler(self.log_buffer)
        self.handler.setFormatter(JsonFormatter())
        
        self.logger = logging.getLogger()
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)
        
        # Generate sample log events
        self._generate_sample_logs()
    
    def tearDown(self):
        """Clean up test environment."""
        self.logger.removeHandler(self.handler)
        self.handler.close()
    
    def _generate_sample_logs(self):
        """Generate sample log events for query testing."""
        # Set context for realistic logs
        set_job_ctx(job_id='j-test-123', video_id='test-video-456')
        
        # Job lifecycle events
        job_received(video_count=3, use_cookies=True, proxy_enabled=True)
        
        # Stage events with various outcomes
        with StageTimer("youtube-transcript-api", attempt=1):
            pass
        
        # Simulate error case
        try:
            with StageTimer("youtubei", attempt=2, use_proxy=True, profile="mobile"):
                raise TimeoutError("Request timed out after 30 seconds")
        except TimeoutError:
            pass
        
        # Success case
        with StageTimer("timedtext", attempt=1, use_proxy=False):
            pass
        
        # Job completion
        job_finished(
            total_duration_ms=15000,
            processed_count=2,
            video_count=3,
            outcome="partial_success",
            email_sent=True
        )
        
        # Parse generated logs
        log_output = self.log_buffer.getvalue()
        for line in log_output.strip().split('\n'):
            if line:
                try:
                    log_entry = json.loads(line)
                    self.sample_logs.append(log_entry)
                except json.JSONDecodeError:
                    pass
    
    def test_requirement_7_1_error_analysis_query(self):
        """Test Requirement 7.1: Error and timeout analysis query."""
        query = cloudwatch_query_templates.QUERY_TEMPLATES['error_analysis']
        
        # Validate query syntax
        self.assertIn('fields @timestamp, lvl, event, stage, outcome, detail', query)
        self.assertIn('filter outcome in ["error", "timeout", "blocked"]', query)
        self.assertIn('sort @timestamp desc', query)
        self.assertIn('limit 200', query)
        
        # Test that query would work with our sample data
        error_logs = [log for log in self.sample_logs 
                     if log.get('outcome') in ['error', 'timeout', 'blocked']]
        self.assertGreater(len(error_logs), 0, "Should have error logs for testing")
        
        # Verify required fields are present in error logs
        for log in error_logs:
            self.assertIn('lvl', log)
            self.assertIn('event', log)
            self.assertIn('stage', log)
            self.assertIn('outcome', log)
    
    def test_requirement_7_2_funnel_analysis_query(self):
        """Test Requirement 7.2: Funnel analysis for stage success rates."""
        query = cloudwatch_query_templates.QUERY_TEMPLATES['funnel_analysis']
        
        # Validate query syntax
        self.assertIn('fields stage, outcome', query)
        self.assertIn('filter event = "stage_result"', query)
        self.assertIn('stats countif(outcome="success")', query)
        self.assertIn('by stage', query)
        
        # Test with sample data
        stage_result_logs = [log for log in self.sample_logs 
                           if log.get('event') == 'stage_result']
        self.assertGreater(len(stage_result_logs), 0, "Should have stage_result logs")
        
        # Verify required fields are present
        for log in stage_result_logs:
            self.assertIn('stage', log)
            self.assertIn('outcome', log)
    
    def test_requirement_7_3_performance_analysis_query(self):
        """Test Requirement 7.3: Performance analysis for P95 duration by stage."""
        query = cloudwatch_query_templates.QUERY_TEMPLATES['performance_analysis']
        
        # Validate query syntax
        self.assertIn('fields stage, dur_ms', query)
        self.assertIn('filter event = "stage_result" and ispresent(dur_ms)', query)
        self.assertIn('pct(dur_ms, 95) as p95_ms', query)
        self.assertIn('by stage', query)
        
        # Test with sample data
        duration_logs = [log for log in self.sample_logs 
                        if log.get('event') == 'stage_result' and 'dur_ms' in log]
        self.assertGreater(len(duration_logs), 0, "Should have duration logs")
        
        # Verify duration fields are numeric
        for log in duration_logs:
            self.assertIsInstance(log['dur_ms'], int)
    
    def test_requirement_7_4_job_correlation_query(self):
        """Test Requirement 7.4: Job correlation queries for troubleshooting."""
        query_template = cloudwatch_query_templates.QUERY_TEMPLATES['job_correlation']
        
        # Test query formatting
        job_id = 'j-test-123'
        formatted_query = cloudwatch_query_templates.format_job_query('job_correlation', job_id)
        
        # Validate formatted query
        self.assertIn(f'filter job_id = "{job_id}"', formatted_query)
        self.assertIn('fields @timestamp, event, stage, outcome', formatted_query)
        self.assertIn('sort @timestamp asc', formatted_query)
        
        # Test with sample data
        job_logs = [log for log in self.sample_logs if log.get('job_id') == job_id]
        self.assertGreater(len(job_logs), 0, "Should have logs for the test job")
    
    def test_requirement_7_5_video_correlation_query(self):
        """Test Requirement 7.5: Video correlation across multiple jobs."""
        query_template = cloudwatch_query_templates.QUERY_TEMPLATES['video_correlation']
        
        # Test query formatting
        video_id = 'test-video-456'
        formatted_query = cloudwatch_query_templates.format_video_query('video_correlation', video_id)
        
        # Validate formatted query
        self.assertIn(f'filter video_id = "{video_id}"', formatted_query)
        self.assertIn('fields @timestamp, job_id, event, stage', formatted_query)
        
        # Test with sample data
        video_logs = [log for log in self.sample_logs if log.get('video_id') == video_id]
        self.assertGreater(len(video_logs), 0, "Should have logs for the test video")
    
    def test_all_query_templates_syntax(self):
        """Test that all query templates have valid syntax."""
        for template_name, query in cloudwatch_query_templates.QUERY_TEMPLATES.items():
            with self.subTest(template=template_name):
                # Basic syntax validation
                self.assertIsInstance(query, str)
                self.assertGreater(len(query.strip()), 0)
                
                # Should contain CloudWatch Logs Insights keywords
                keywords = ['fields', 'filter', 'sort', 'stats', 'limit']
                has_keyword = any(keyword in query for keyword in keywords)
                self.assertTrue(has_keyword, f"Query {template_name} should contain CloudWatch keywords")
                
                # Should not have obvious syntax errors
                self.assertNotIn('{{', query)  # No unresolved template variables
                self.assertNotIn('}}', query)
    
    def test_query_field_compatibility(self):
        """Test that queries reference fields that exist in our JSON schema."""
        # Define the standard fields from our JSON schema
        standard_fields = {
            'ts', 'lvl', 'job_id', 'video_id', 'stage', 'event', 'outcome', 
            'dur_ms', 'detail', 'attempt', 'use_proxy', 'profile', 'cookie_source'
        }
        
        # CloudWatch built-in fields
        cloudwatch_fields = {'@timestamp', '@message', '@logStream', '@log'}
        
        all_valid_fields = standard_fields | cloudwatch_fields
        
        for template_name, query in cloudwatch_query_templates.QUERY_TEMPLATES.items():
            with self.subTest(template=template_name):
                # Extract field references from the query
                # Look for patterns like "field_name" or field_name (without quotes)
                field_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b'
                potential_fields = re.findall(field_pattern, query)
                
                # Filter out CloudWatch keywords and common SQL words
                cloudwatch_keywords = {
                    'fields', 'filter', 'sort', 'stats', 'limit', 'by', 'as', 'and', 'or',
                    'in', 'like', 'desc', 'asc', 'count', 'countif', 'avg', 'sum', 'max',
                    'min', 'pct', 'bin', 'ispresent', 'round', 'eval'
                }
                
                referenced_fields = set()
                for field in potential_fields:
                    if (field not in cloudwatch_keywords and 
                        not field.isdigit() and 
                        field not in ['true', 'false', 'null']):
                        referenced_fields.add(field)
                
                # Check that referenced fields are valid
                for field in referenced_fields:
                    if field.startswith('@'):
                        continue  # CloudWatch built-in fields
                    if field in ['success', 'error', 'timeout', 'blocked', 'no_captions']:
                        continue  # Valid outcome values
                    if field in ['INFO', 'WARNING', 'ERROR', 'CRITICAL']:
                        continue  # Valid log levels
                    if field.endswith('_count') or field.endswith('_ms') or field.endswith('_pct'):
                        continue  # Computed fields
                    if field in ['timestamp', 'stage_result', 'job_received', 'job_finished', 'performance_metric', 'stage_start']:
                        continue  # Valid event types and CloudWatch fields
                    if field.startswith('avg_') or field.startswith('p95_') or field.startswith('max_') or field.startswith('p50_') or field.startswith('p99_'):
                        continue  # Computed aggregation fields
                    if field.endswith('_rate') or field.endswith('_attempts') or field in ['ok', 'total', 'suppressed']:
                        continue  # Computed fields in queries
                    if field in ['cpu', 'mem_mb', 'stderr_tail', 'ffmpeg']:
                        continue  # Valid data fields and stage names
                    
                    # Should be a valid schema field
                    self.assertIn(field, all_valid_fields,
                                f"Query {template_name} references unknown field: {field}")
    
    def test_query_parameter_templates(self):
        """Test query parameter templates functionality."""
        # Test time range parameters
        time_ranges = cloudwatch_query_templates.QUERY_PARAMETERS['time_ranges']
        for range_name, range_filter in time_ranges.items():
            self.assertIn('@timestamp', range_filter)
            self.assertIn('-', range_filter)  # Should have time subtraction
        
        # Test log level parameters
        log_levels = cloudwatch_query_templates.QUERY_PARAMETERS['log_levels']
        for level_name, level_filter in log_levels.items():
            self.assertIn('lvl', level_filter)
            self.assertIn('in', level_filter)
        
        # Test stage parameters
        stages = cloudwatch_query_templates.QUERY_PARAMETERS['stages']
        for stage_group, stage_filter in stages.items():
            self.assertIn('stage', stage_filter)
            self.assertIn('in', stage_filter)
    
    def test_get_query_with_filters(self):
        """Test the get_query_with_filters helper function."""
        # Test with time range filter
        filtered_query = cloudwatch_query_templates.get_query_with_filters(
            'error_analysis',
            time_range='last_24h'
        )
        
        self.assertIn('@timestamp > @timestamp - 24h', filtered_query)
        
        # Test with log level filter
        filtered_query = cloudwatch_query_templates.get_query_with_filters(
            'performance_analysis',
            log_level='errors_only'
        )
        
        self.assertIn('lvl in ["ERROR", "CRITICAL"]', filtered_query)
        
        # Test with invalid template name
        with self.assertRaises(ValueError):
            cloudwatch_query_templates.get_query_with_filters('nonexistent_template')
    
    def test_json_schema_compatibility(self):
        """Test that sample logs match the expected JSON schema."""
        required_fields = ['ts', 'lvl']
        
        for log_entry in self.sample_logs:
            # Required fields should always be present
            for field in required_fields:
                self.assertIn(field, log_entry)
            
            # Timestamp should be ISO 8601 format
            timestamp = log_entry['ts']
            self.assertRegex(timestamp, r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$')
            
            # Level should be valid
            level = log_entry['lvl']
            self.assertIn(level, ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
            
            # If outcome is present, should be valid
            if 'outcome' in log_entry:
                outcome = log_entry['outcome']
                valid_outcomes = ['success', 'no_captions', 'blocked', 'timeout', 'error', 'partial_success']
                self.assertIn(outcome, valid_outcomes)
            
            # If duration is present, should be integer
            if 'dur_ms' in log_entry:
                self.assertIsInstance(log_entry['dur_ms'], int)
    
    def test_query_performance_considerations(self):
        """Test that queries are optimized for performance."""
        for template_name, query in cloudwatch_query_templates.QUERY_TEMPLATES.items():
            with self.subTest(template=template_name):
                # Queries should have appropriate limits to prevent excessive results
                if 'stats' not in query:  # Non-aggregation queries should have limits
                    # Some queries are meant for specific correlation and don't need limits
                    if template_name not in ['job_correlation', 'job_lifecycle_trace']:
                        self.assertTrue('limit' in query or 'bin(' in query,
                                      f"Query {template_name} should have a limit or time binning")
                
                # Queries should filter early to reduce processing
                lines = query.split('\n')
                filter_line_found = False
                for i, line in enumerate(lines):
                    if 'filter' in line:
                        filter_line_found = True
                        # Filter should come before stats/sort when possible
                        break
                
                # Most queries should have some filtering
                if template_name not in ['recent_activity', 'performance_metrics']:
                    self.assertTrue(filter_line_found or 'stats' in query,
                                  f"Query {template_name} should have filtering or aggregation")


class TestQueryTemplateIntegration(unittest.TestCase):
    """Integration tests for query templates with realistic log data."""
    
    def setUp(self):
        """Set up integration test environment."""
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
    
    def test_complete_job_lifecycle_query_compatibility(self):
        """Test that job lifecycle queries work with complete job flow."""
        # Simulate complete job lifecycle
        set_job_ctx(job_id='j-lifecycle-test', video_id='lifecycle-video-123')
        
        # Job start
        job_received(video_count=2, use_cookies=False, proxy_enabled=True)
        
        # Multiple stages with different outcomes
        stages = [
            ('youtube-transcript-api', 'success', 500),
            ('timedtext', 'no_captions', 200),
            ('youtubei', 'timeout', 30000),
            ('asr', 'success', 15000)
        ]
        
        for stage, outcome, duration in stages:
            if outcome == 'success':
                with StageTimer(stage):
                    pass
            elif outcome == 'timeout':
                try:
                    with StageTimer(stage):
                        raise TimeoutError("Stage timed out")
                except TimeoutError:
                    pass
            else:  # no_captions
                evt('stage_result', stage=stage, outcome=outcome, dur_ms=duration)
        
        # Job completion
        job_finished(
            total_duration_ms=45700,
            processed_count=1,
            video_count=2,
            outcome="partial_success"
        )
        
        # Parse logs
        log_output = self.log_buffer.getvalue()
        log_entries = []
        for line in log_output.strip().split('\n'):
            if line:
                log_entries.append(json.loads(line))
        
        # Test job correlation query compatibility
        job_logs = [log for log in log_entries if log.get('job_id') == 'j-lifecycle-test']
        self.assertGreater(len(job_logs), 5)  # Should have multiple events
        
        # Test funnel analysis compatibility
        stage_results = [log for log in log_entries if log.get('event') == 'stage_result']
        self.assertGreater(len(stage_results), 3)  # Should have multiple stage results
        
        # Test performance analysis compatibility
        duration_logs = [log for log in stage_results if 'dur_ms' in log]
        self.assertGreater(len(duration_logs), 2)  # Should have duration data
        
        # Verify all logs have required fields for queries
        for log in log_entries:
            self.assertIn('ts', log)
            self.assertIn('lvl', log)
            if log.get('event') == 'stage_result':
                self.assertIn('stage', log)
                self.assertIn('outcome', log)


if __name__ == '__main__':
    unittest.main(verbosity=2)