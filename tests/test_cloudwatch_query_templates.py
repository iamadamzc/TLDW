"""
Tests for CloudWatch Logs Insights query templates.

This module tests the query templates to ensure they are syntactically correct
and follow CloudWatch Logs Insights query syntax.
"""

import unittest
import re
from cloudwatch_query_templates import (
    QUERY_TEMPLATES, 
    QUERY_PARAMETERS,
    get_query_with_filters,
    format_job_query,
    format_video_query
)


class TestCloudWatchQueryTemplates(unittest.TestCase):
    """Test CloudWatch Logs Insights query templates."""
    
    def test_all_templates_exist(self):
        """Test that all required query templates exist."""
        required_templates = [
            'error_analysis',
            'error_analysis_detailed', 
            'funnel_analysis',
            'stage_funnel_analysis',
            'performance_analysis',
            'performance_trends',
            'job_correlation',
            'video_correlation',
            'job_lifecycle_trace',
            'failed_jobs_summary',
            'proxy_analysis',
            'profile_analysis',
            'recent_activity',
            'performance_metrics',
            'rate_limiting_analysis',
            'ffmpeg_errors',
            'timeout_analysis'
        ]
        
        for template_name in required_templates:
            self.assertIn(template_name, QUERY_TEMPLATES, 
                         f"Required template '{template_name}' not found")
    
    def test_query_syntax_basic(self):
        """Test basic CloudWatch Logs Insights query syntax."""
        for name, query in QUERY_TEMPLATES.items():
            with self.subTest(template=name):
                # Check that query is not empty
                self.assertTrue(query.strip(), f"Query '{name}' is empty")
                
                # Check for basic CloudWatch syntax elements
                self.assertTrue(
                    'fields' in query or 'filter' in query or 'stats' in query,
                    f"Query '{name}' missing basic CloudWatch syntax"
                )
    
    def test_error_analysis_queries(self):
        """Test error analysis query templates."""
        # Basic error analysis
        query = QUERY_TEMPLATES['error_analysis']
        self.assertIn('outcome in ["error", "timeout", "blocked"]', query)
        self.assertIn('sort @timestamp desc', query)
        self.assertIn('limit 200', query)
        
        # Detailed error analysis
        detailed_query = QUERY_TEMPLATES['error_analysis_detailed']
        self.assertIn('stats count() as error_count', detailed_query)
        self.assertIn('by stage, outcome, detail', detailed_query)
    
    def test_funnel_analysis_queries(self):
        """Test funnel analysis query templates."""
        # Main funnel analysis
        query = QUERY_TEMPLATES['funnel_analysis']
        self.assertIn('event = "stage_result"', query)
        self.assertIn('countif(outcome="success")', query)
        self.assertIn('countif(outcome="error")', query)
        self.assertIn('countif(outcome="timeout")', query)
        self.assertIn('success_rate = round(success_count * 100.0 / total_attempts, 2)', query)
        
        # Simple stage funnel
        stage_query = QUERY_TEMPLATES['stage_funnel_analysis']
        self.assertIn('countif(outcome="success") as ok', stage_query)
        self.assertIn('by stage', stage_query)
    
    def test_performance_analysis_queries(self):
        """Test performance analysis query templates."""
        query = QUERY_TEMPLATES['performance_analysis']
        self.assertIn('event = "stage_result"', query)
        self.assertIn('ispresent(dur_ms)', query)
        self.assertIn('pct(dur_ms, 95) as p95_ms', query)
        self.assertIn('pct(dur_ms, 99) as p99_ms', query)
        self.assertIn('by stage', query)
    
    def test_correlation_queries(self):
        """Test job and video correlation queries."""
        # Job correlation
        job_query = QUERY_TEMPLATES['job_correlation']
        self.assertIn('job_id = "{job_id}"', job_query)
        self.assertIn('sort @timestamp asc', job_query)
        
        # Video correlation
        video_query = QUERY_TEMPLATES['video_correlation']
        self.assertIn('video_id = "{video_id}"', video_query)
        
        # Job lifecycle trace
        lifecycle_query = QUERY_TEMPLATES['job_lifecycle_trace']
        self.assertIn('event in ["job_received", "stage_start", "stage_result", "job_finished"]', lifecycle_query)
    
    def test_specialized_queries(self):
        """Test specialized analysis queries."""
        # Proxy analysis
        proxy_query = QUERY_TEMPLATES['proxy_analysis']
        self.assertIn('ispresent(use_proxy)', proxy_query)
        self.assertIn('by use_proxy, stage', proxy_query)
        
        # Profile analysis
        profile_query = QUERY_TEMPLATES['profile_analysis']
        self.assertIn('ispresent(profile)', profile_query)
        self.assertIn('by profile, stage', profile_query)
        
        # FFmpeg errors
        ffmpeg_query = QUERY_TEMPLATES['ffmpeg_errors']
        self.assertIn('stage = "ffmpeg"', ffmpeg_query)
        self.assertIn('outcome = "error"', ffmpeg_query)
        
        # Timeout analysis
        timeout_query = QUERY_TEMPLATES['timeout_analysis']
        self.assertIn('outcome = "timeout"', timeout_query)
        self.assertIn('avg(dur_ms) as avg_timeout_ms', timeout_query)
    
    def test_query_parameters(self):
        """Test query parameter templates."""
        # Time ranges
        self.assertIn('time_ranges', QUERY_PARAMETERS)
        time_ranges = QUERY_PARAMETERS['time_ranges']
        self.assertIn('last_hour', time_ranges)
        self.assertIn('last_24h', time_ranges)
        self.assertIn('last_week', time_ranges)
        
        # Log levels
        self.assertIn('log_levels', QUERY_PARAMETERS)
        log_levels = QUERY_PARAMETERS['log_levels']
        self.assertIn('errors_only', log_levels)
        self.assertIn('warnings_and_errors', log_levels)
        
        # Stages
        self.assertIn('stages', QUERY_PARAMETERS)
        stages = QUERY_PARAMETERS['stages']
        self.assertIn('transcript_stages', stages)
        self.assertIn('network_stages', stages)
    
    def test_get_query_with_filters(self):
        """Test query filtering functionality."""
        # Test with time range filter
        filtered_query = get_query_with_filters('error_analysis', time_range='last_24h')
        self.assertIn('@timestamp > @timestamp - 24h', filtered_query)
        
        # Test with log level filter
        filtered_query = get_query_with_filters('performance_analysis', log_level='errors_only')
        self.assertIn('lvl in ["ERROR", "CRITICAL"]', filtered_query)
        
        # Test with invalid template
        with self.assertRaises(ValueError):
            get_query_with_filters('nonexistent_template')
    
    def test_format_job_query(self):
        """Test job-specific query formatting."""
        job_id = 'j-test-123'
        formatted_query = format_job_query('job_correlation', job_id)
        self.assertIn(f'job_id = "{job_id}"', formatted_query)
        
        # Test with invalid template
        with self.assertRaises(ValueError):
            format_job_query('nonexistent_template', job_id)
    
    def test_format_video_query(self):
        """Test video-specific query formatting."""
        video_id = 'bbz2boNSeL0'
        formatted_query = format_video_query('video_correlation', video_id)
        self.assertIn(f'video_id = "{video_id}"', formatted_query)
        
        # Test with invalid template
        with self.assertRaises(ValueError):
            format_video_query('nonexistent_template', video_id)
    
    def test_query_field_consistency(self):
        """Test that queries use consistent field names."""
        expected_fields = [
            '@timestamp', 'lvl', 'job_id', 'video_id', 'stage', 
            'event', 'outcome', 'dur_ms', 'detail'
        ]
        
        # Check that main queries reference expected fields
        main_queries = ['error_analysis', 'funnel_analysis', 'performance_analysis']
        
        for query_name in main_queries:
            query = QUERY_TEMPLATES[query_name]
            with self.subTest(template=query_name):
                # Should reference at least some core fields
                field_count = sum(1 for field in expected_fields if field in query)
                self.assertGreater(field_count, 0, 
                                 f"Query '{query_name}' doesn't reference expected fields")
    
    def test_query_outcome_values(self):
        """Test that queries use correct outcome values."""
        expected_outcomes = ['success', 'error', 'timeout', 'blocked', 'no_captions']
        
        # Check queries that filter by outcome
        outcome_queries = ['error_analysis', 'funnel_analysis', 'timeout_analysis']
        
        for query_name in outcome_queries:
            query = QUERY_TEMPLATES[query_name]
            with self.subTest(template=query_name):
                # Should use at least one expected outcome value
                outcome_count = sum(1 for outcome in expected_outcomes if outcome in query)
                self.assertGreater(outcome_count, 0,
                                 f"Query '{query_name}' doesn't use expected outcome values")
    
    def test_query_aggregation_functions(self):
        """Test that statistical queries use proper aggregation functions."""
        # Performance analysis should use percentile functions
        perf_query = QUERY_TEMPLATES['performance_analysis']
        self.assertIn('pct(dur_ms, 95)', perf_query)
        self.assertIn('avg(dur_ms)', perf_query)
        self.assertIn('max(dur_ms)', perf_query)
        
        # Funnel analysis should use countif
        funnel_query = QUERY_TEMPLATES['funnel_analysis']
        self.assertIn('countif(outcome="success")', funnel_query)
        self.assertIn('count(*)', funnel_query)
    
    def test_query_sorting_and_limits(self):
        """Test that queries have appropriate sorting and limits."""
        # Error analysis should sort by timestamp desc
        error_query = QUERY_TEMPLATES['error_analysis']
        self.assertIn('sort @timestamp desc', error_query)
        self.assertIn('limit 200', error_query)
        
        # Job correlation should sort by timestamp asc
        job_query = QUERY_TEMPLATES['job_correlation']
        self.assertIn('sort @timestamp asc', job_query)
        
        # Performance analysis should sort by p95_ms desc
        perf_query = QUERY_TEMPLATES['performance_analysis']
        self.assertIn('sort p95_ms desc', perf_query)


class TestQueryTemplateRequirements(unittest.TestCase):
    """Test that query templates meet specific requirements."""
    
    def test_requirement_7_1_error_timeout_analysis(self):
        """Test Requirement 7.1: Error and timeout analysis query."""
        query = QUERY_TEMPLATES['error_analysis']
        
        # Should filter for errors and timeouts
        self.assertIn('outcome in ["error", "timeout", "blocked"]', query)
        
        # Should include key fields for analysis
        required_fields = ['@timestamp', 'lvl', 'event', 'stage', 'outcome', 'detail', 'job_id', 'video_id']
        for field in required_fields:
            self.assertIn(field, query)
        
        # Should sort by timestamp and limit results
        self.assertIn('sort @timestamp desc', query)
        self.assertIn('limit', query)
    
    def test_requirement_7_2_funnel_analysis(self):
        """Test Requirement 7.2: Funnel analysis for stage success rates."""
        query = QUERY_TEMPLATES['funnel_analysis']
        
        # Should filter for stage results
        self.assertIn('event = "stage_result"', query)
        
        # Should calculate success rates
        self.assertIn('countif(outcome="success")', query)
        self.assertIn('success_rate', query)
        
        # Should group by stage
        self.assertIn('by stage', query)
    
    def test_requirement_7_3_performance_analysis(self):
        """Test Requirement 7.3: P95 duration analysis by stage."""
        query = QUERY_TEMPLATES['performance_analysis']
        
        # Should filter for stage results with duration
        self.assertIn('event = "stage_result"', query)
        self.assertIn('ispresent(dur_ms)', query)
        
        # Should calculate P95 percentile
        self.assertIn('pct(dur_ms, 95)', query)
        
        # Should group by stage
        self.assertIn('by stage', query)
        
        # Should sort by P95 duration
        self.assertIn('sort p95_ms desc', query)
    
    def test_requirement_7_4_job_correlation(self):
        """Test Requirement 7.4: Job correlation queries."""
        # Job correlation query
        job_query = QUERY_TEMPLATES['job_correlation']
        self.assertIn('job_id = "{job_id}"', job_query)
        self.assertIn('sort @timestamp asc', job_query)
        
        # Video correlation query
        video_query = QUERY_TEMPLATES['video_correlation']
        self.assertIn('video_id = "{video_id}"', video_query)
        
        # Job lifecycle trace
        lifecycle_query = QUERY_TEMPLATES['job_lifecycle_trace']
        self.assertIn('job_id = "{job_id}"', lifecycle_query)
        self.assertIn('event in ["job_received", "stage_start", "stage_result", "job_finished"]', lifecycle_query)
    
    def test_requirement_7_5_cloudwatch_integration(self):
        """Test Requirement 7.5: CloudWatch Logs Insights integration."""
        # All queries should use valid CloudWatch syntax
        for name, query in QUERY_TEMPLATES.items():
            with self.subTest(template=name):
                # Should start with fields, filter, or stats
                query_start = query.strip().split('\n')[0].strip()
                self.assertTrue(
                    query_start.startswith(('fields', 'filter', 'stats')),
                    f"Query '{name}' doesn't start with valid CloudWatch command"
                )
                
                # Should use pipe syntax for command chaining
                if '\n' in query:
                    lines = query.strip().split('\n')
                    for line in lines[1:]:  # Skip first line
                        line = line.strip()
                        if line:  # Skip empty lines
                            self.assertTrue(
                                line.startswith('|'),
                                f"Query '{name}' has invalid pipe syntax: {line}"
                            )


if __name__ == '__main__':
    unittest.main()