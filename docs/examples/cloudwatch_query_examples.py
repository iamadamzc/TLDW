"""
CloudWatch Logs Insights Query Examples

This script demonstrates how to use the CloudWatch query templates
for analyzing TL;DW application logs.

Run with: python examples/cloudwatch_query_examples.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cloudwatch_query_templates import QUERY_TEMPLATES, format_job_query, format_video_query


def print_query_example(name: str, description: str):
    """Print a query example with description."""
    print(f"\n{'='*60}")
    print(f"Query: {name}")
    print(f"Description: {description}")
    print(f"{'='*60}")
    
    if name in QUERY_TEMPLATES:
        query = QUERY_TEMPLATES[name]
        print(query)
    else:
        print(f"Query '{name}' not found!")


def main():
    """Demonstrate CloudWatch query templates."""
    
    print("TL;DW CloudWatch Logs Insights Query Examples")
    print("=" * 60)
    
    # Error Analysis Examples
    print_query_example(
        'error_analysis',
        'Find recent errors and timeouts in the last 24 hours'
    )
    
    print_query_example(
        'error_analysis_detailed',
        'Group errors by stage, outcome, and error detail for pattern analysis'
    )
    
    # Performance Analysis Examples
    print_query_example(
        'performance_analysis',
        'Calculate P95 duration metrics by pipeline stage'
    )
    
    print_query_example(
        'funnel_analysis',
        'Analyze success rates across all pipeline stages'
    )
    
    # Troubleshooting Examples
    print_query_example(
        'failed_jobs_summary',
        'Find jobs with the most failures for investigation'
    )
    
    print_query_example(
        'proxy_analysis',
        'Compare success rates with and without proxy usage'
    )
    
    # Job Correlation Examples
    print("\n" + "="*60)
    print("Job-Specific Query Examples")
    print("="*60)
    
    example_job_id = "j-7f3d"
    job_query = format_job_query('job_correlation', example_job_id)
    print(f"\nJob Correlation Query for job_id='{example_job_id}':")
    print(job_query)
    
    lifecycle_query = format_job_query('job_lifecycle_trace', example_job_id)
    print(f"\nJob Lifecycle Trace for job_id='{example_job_id}':")
    print(lifecycle_query)
    
    # Video Analysis Examples
    print("\n" + "="*60)
    print("Video-Specific Query Examples")
    print("="*60)
    
    example_video_id = "bbz2boNSeL0"
    video_query = format_video_query('video_correlation', example_video_id)
    print(f"\nVideo Analysis Query for video_id='{example_video_id}':")
    print(video_query)
    
    # Specialized Analysis Examples
    print_query_example(
        'ffmpeg_errors',
        'Analyze FFmpeg audio extraction failures'
    )
    
    print_query_example(
        'timeout_analysis',
        'Analyze timeout patterns and durations by stage'
    )
    
    print_query_example(
        'rate_limiting_analysis',
        'Find log suppression events due to rate limiting'
    )
    
    # Usage Instructions
    print("\n" + "="*60)
    print("Usage Instructions")
    print("="*60)
    
    print("""
1. Copy any query above and paste it into CloudWatch Logs Insights
2. Select your log group: /aws/apprunner/tldw-transcript-service
3. Choose your time range (last 1 hour, 24 hours, etc.)
4. Click "Run query" to execute

For job-specific queries:
- Replace {job_id} with actual job ID (e.g., "j-7f3d")
- Replace {video_id} with actual video ID (e.g., "bbz2boNSeL0")

Common time range filters to add:
- Last hour: | filter @timestamp > @timestamp - 1h
- Last 24h: | filter @timestamp > @timestamp - 24h
- Last week: | filter @timestamp > @timestamp - 7d

Example combined query:
fields @timestamp, stage, outcome, dur_ms
| filter @timestamp > @timestamp - 1h
| filter event = "stage_result"
| filter outcome in ["error", "timeout"]
| sort @timestamp desc
""")
    
    # Available Templates
    print("\n" + "="*60)
    print("All Available Query Templates")
    print("="*60)
    
    for i, template_name in enumerate(sorted(QUERY_TEMPLATES.keys()), 1):
        print(f"{i:2d}. {template_name}")
    
    print(f"\nTotal: {len(QUERY_TEMPLATES)} query templates available")


if __name__ == "__main__":
    main()