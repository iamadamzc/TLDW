"""
CloudWatch Logs Insights Client for TL;DW Application

This module provides a simple interface for running CloudWatch Logs Insights queries
using the pre-built query templates.

Usage:
    from cloudwatch_logs_client import CloudWatchLogsClient
    
    client = CloudWatchLogsClient()
    results = client.run_query('error_analysis', hours_back=24)
"""

import boto3
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from cloudwatch_query_templates import QUERY_TEMPLATES, format_job_query, format_video_query


class CloudWatchLogsClient:
    """Client for running CloudWatch Logs Insights queries."""
    
    def __init__(self, log_group_name: str = None, region_name: str = 'us-east-1'):
        """
        Initialize CloudWatch Logs client.
        
        Args:
            log_group_name: CloudWatch log group name (defaults to App Runner log group)
            region_name: AWS region name
        """
        self.logs_client = boto3.client('logs', region_name=region_name)
        self.log_group_name = log_group_name or '/aws/apprunner/tldw-transcript-service'
    
    def run_query(self, 
                  template_name: str, 
                  hours_back: int = 24,
                  job_id: str = None,
                  video_id: str = None,
                  wait_for_completion: bool = True,
                  max_wait_seconds: int = 300) -> Dict[str, Any]:
        """
        Run a CloudWatch Logs Insights query using a template.
        
        Args:
            template_name: Name of the query template to use
            hours_back: How many hours back to query (default: 24)
            job_id: Job ID for job-specific queries
            video_id: Video ID for video-specific queries
            wait_for_completion: Whether to wait for query completion
            max_wait_seconds: Maximum time to wait for query completion
            
        Returns:
            Dictionary containing query results and metadata
        """
        if template_name not in QUERY_TEMPLATES:
            raise ValueError(f"Unknown query template: {template_name}")
        
        # Get the query string
        if job_id:
            query_string = format_job_query(template_name, job_id)
        elif video_id:
            query_string = format_video_query(template_name, video_id)
        else:
            query_string = QUERY_TEMPLATES[template_name]
        
        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours_back)
        
        # Start the query
        response = self.logs_client.start_query(
            logGroupName=self.log_group_name,
            startTime=int(start_time.timestamp()),
            endTime=int(end_time.timestamp()),
            queryString=query_string
        )
        
        query_id = response['queryId']
        
        if not wait_for_completion:
            return {
                'query_id': query_id,
                'status': 'Running',
                'query_string': query_string,
                'start_time': start_time,
                'end_time': end_time
            }
        
        # Wait for completion
        start_wait = time.time()
        while time.time() - start_wait < max_wait_seconds:
            result = self.logs_client.get_query_results(queryId=query_id)
            
            if result['status'] == 'Complete':
                return {
                    'query_id': query_id,
                    'status': 'Complete',
                    'results': result['results'],
                    'statistics': result.get('statistics', {}),
                    'query_string': query_string,
                    'start_time': start_time,
                    'end_time': end_time,
                    'record_count': len(result['results'])
                }
            elif result['status'] == 'Failed':
                return {
                    'query_id': query_id,
                    'status': 'Failed',
                    'error': 'Query execution failed',
                    'query_string': query_string
                }
            
            time.sleep(2)  # Wait 2 seconds before checking again
        
        # Timeout
        return {
            'query_id': query_id,
            'status': 'Timeout',
            'error': f'Query did not complete within {max_wait_seconds} seconds',
            'query_string': query_string
        }
    
    def get_error_summary(self, hours_back: int = 24) -> Dict[str, Any]:
        """Get a summary of recent errors."""
        return self.run_query('error_analysis_detailed', hours_back=hours_back)
    
    def get_performance_summary(self, hours_back: int = 24) -> Dict[str, Any]:
        """Get performance metrics summary."""
        return self.run_query('performance_analysis', hours_back=hours_back)
    
    def get_success_rates(self, hours_back: int = 24) -> Dict[str, Any]:
        """Get success rates by stage."""
        return self.run_query('stage_funnel_analysis', hours_back=hours_back)
    
    def trace_job(self, job_id: str, hours_back: int = 24) -> Dict[str, Any]:
        """Trace a specific job through the pipeline."""
        return self.run_query('job_lifecycle_trace', job_id=job_id, hours_back=hours_back)
    
    def analyze_video(self, video_id: str, hours_back: int = 168) -> Dict[str, Any]:
        """Analyze all processing attempts for a specific video (default: 1 week)."""
        return self.run_query('video_correlation', video_id=video_id, hours_back=hours_back)
    
    def get_recent_activity(self, hours_back: int = 1) -> Dict[str, Any]:
        """Get recent activity overview."""
        return self.run_query('recent_activity', hours_back=hours_back)
    
    def get_error_rate_metrics(self, hours_back: int = 1) -> Dict[str, Any]:
        """Get error rate metrics for alerting."""
        return self.run_query('error_rate_by_stage', hours_back=hours_back)
    
    def get_performance_degradation_metrics(self, hours_back: int = 1) -> Dict[str, Any]:
        """Get performance degradation metrics for alerting."""
        return self.run_query('performance_degradation_alert', hours_back=hours_back)
    
    def get_job_failure_metrics(self, hours_back: int = 1) -> Dict[str, Any]:
        """Get job failure spike metrics for alerting."""
        return self.run_query('job_failure_spike', hours_back=hours_back)
    
    def list_available_queries(self) -> List[str]:
        """List all available query templates."""
        return list(QUERY_TEMPLATES.keys())
    
    def format_results_table(self, results: List[List[Dict[str, str]]]) -> str:
        """
        Format query results as a readable table.
        
        Args:
            results: Query results from CloudWatch Logs Insights
            
        Returns:
            Formatted table string
        """
        if not results:
            return "No results found."
        
        # Get column headers from first result
        headers = [field['field'] for field in results[0]]
        
        # Calculate column widths
        col_widths = {}
        for header in headers:
            col_widths[header] = len(header)
        
        for row in results:
            for field in row:
                field_name = field['field']
                value = field.get('value', '')
                col_widths[field_name] = max(col_widths[field_name], len(str(value)))
        
        # Build table
        lines = []
        
        # Header row
        header_row = " | ".join(header.ljust(col_widths[header]) for header in headers)
        lines.append(header_row)
        lines.append("-" * len(header_row))
        
        # Data rows
        for row in results:
            values = []
            for header in headers:
                field_value = next((f['value'] for f in row if f['field'] == header), '')
                values.append(str(field_value).ljust(col_widths[header]))
            lines.append(" | ".join(values))
        
        return "\n".join(lines)


# Example usage and testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Run CloudWatch Logs Insights queries')
    parser.add_argument('query', help='Query template name')
    parser.add_argument('--hours', type=int, default=24, help='Hours back to query')
    parser.add_argument('--job-id', help='Job ID for job-specific queries')
    parser.add_argument('--video-id', help='Video ID for video-specific queries')
    parser.add_argument('--log-group', help='CloudWatch log group name')
    parser.add_argument('--list-queries', action='store_true', help='List available queries')
    
    args = parser.parse_args()
    
    client = CloudWatchLogsClient(log_group_name=args.log_group)
    
    if args.list_queries:
        print("Available query templates:")
        for query_name in client.list_available_queries():
            print(f"  - {query_name}")
        exit(0)
    
    try:
        result = client.run_query(
            args.query,
            hours_back=args.hours,
            job_id=args.job_id,
            video_id=args.video_id
        )
        
        if result['status'] == 'Complete':
            print(f"Query completed successfully ({result['record_count']} records)")
            print(f"Query: {result['query_string']}")
            print("\nResults:")
            print(client.format_results_table(result['results']))
        else:
            print(f"Query failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"Error running query: {e}")