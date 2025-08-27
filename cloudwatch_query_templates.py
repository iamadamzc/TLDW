"""
CloudWatch Logs Insights Query Templates for TL;DW Application

This module provides pre-built query templates for common troubleshooting and analysis
scenarios using the structured JSON logging format.

Usage:
    from cloudwatch_query_templates import QUERY_TEMPLATES
    
    # Get error analysis query
    error_query = QUERY_TEMPLATES['error_analysis']
    
    # Use with boto3 CloudWatch Logs client
    response = logs_client.start_query(
        logGroupName='/aws/apprunner/tldw-transcript-service',
        startTime=start_timestamp,
        endTime=end_timestamp,
        queryString=error_query
    )
"""

# Query templates for CloudWatch Logs Insights
QUERY_TEMPLATES = {
    
    # Requirement 7.1: Error and timeout analysis query
    'error_analysis': '''
fields @timestamp, lvl, event, stage, outcome, detail, job_id, video_id, dur_ms
| filter outcome in ["error", "timeout", "blocked"]
| sort @timestamp desc
| limit 200
'''.strip(),

    # Real-time error monitoring (last 15 minutes)
    'error_analysis_realtime': '''
fields @timestamp, lvl, event, stage, outcome, detail, job_id, video_id, dur_ms, attempt, use_proxy, profile
| filter @timestamp > @timestamp - 15m
| filter outcome in ["error", "timeout", "blocked"]
| sort @timestamp desc
| limit 100
'''.strip(),

    # Extended error analysis with error classification
    'error_analysis_detailed': '''
fields @timestamp, lvl, event, stage, outcome, detail, job_id, video_id, dur_ms, attempt, use_proxy, profile
| filter outcome in ["error", "timeout", "blocked"]
| stats count() as error_count by stage, outcome, detail
| sort error_count desc
'''.strip(),

    # Requirement 7.2: Funnel analysis for stage success rates
    'funnel_analysis': '''
fields stage, outcome
| filter event = "stage_result"
| stats countif(outcome="success") as success_count, countif(outcome="error") as error_count, countif(outcome="timeout") as timeout_count, countif(outcome="blocked") as blocked_count, countif(outcome="no_captions") as no_captions_count, count(*) as total_attempts by stage
| eval success_rate = round(success_count * 100.0 / total_attempts, 2)
| eval error_rate = round(error_count * 100.0 / total_attempts, 2)
| eval timeout_rate = round(timeout_count * 100.0 / total_attempts, 2)
| sort success_rate asc
'''.strip(),

    # Stage-by-stage funnel analysis
    'stage_funnel_analysis': '''
fields stage, outcome
| filter event = "stage_result"
| stats countif(outcome="success") as ok, count(*) as total by stage
| eval success_pct = round(ok * 100.0 / total, 2)
| sort success_pct asc
'''.strip(),

    # Requirement 7.3: Performance analysis for P95 duration by stage
    'performance_analysis': '''
fields stage, dur_ms
| filter event = "stage_result" and ispresent(dur_ms) and dur_ms > 0
| stats avg(dur_ms) as avg_ms, pct(dur_ms, 50) as p50_ms, pct(dur_ms, 95) as p95_ms, pct(dur_ms, 99) as p99_ms, max(dur_ms) as max_ms, count() as sample_count by stage
| sort p95_ms desc
'''.strip(),

    # Performance trends over time
    'performance_trends': '''
fields @timestamp, stage, dur_ms
| filter event = "stage_result" and ispresent(dur_ms) and dur_ms > 0
| stats avg(dur_ms) as avg_ms, pct(dur_ms, 95) as p95_ms by bin(5m), stage
| sort @timestamp desc
'''.strip(),

    # Requirement 7.4: Job correlation queries for troubleshooting
    'job_correlation': '''
fields @timestamp, event, stage, outcome, dur_ms, detail, attempt, use_proxy, profile
| filter job_id = "{job_id}"
| sort @timestamp asc
'''.strip(),

    # Video correlation across multiple jobs
    'video_correlation': '''
fields @timestamp, job_id, event, stage, outcome, dur_ms, detail, attempt, use_proxy, profile
| filter video_id = "{video_id}"
| sort @timestamp desc
| limit 100
'''.strip(),

    # Complete job lifecycle trace
    'job_lifecycle_trace': '''
fields @timestamp, event, stage, outcome, dur_ms, detail
| filter job_id = "{job_id}"
| filter event in ["job_received", "stage_start", "stage_result", "job_finished"]
| sort @timestamp asc
'''.strip(),

    # Requirement 7.5: Additional troubleshooting queries
    
    # Failed jobs summary
    'failed_jobs_summary': '''
fields job_id, video_id, stage, outcome, detail
| filter event = "stage_result" and outcome in ["error", "timeout", "blocked"]
| stats count() as failure_count by job_id, video_id
| sort failure_count desc
| limit 50
'''.strip(),

    # Proxy effectiveness analysis
    'proxy_analysis': '''
fields use_proxy, outcome, stage
| filter event = "stage_result" and ispresent(use_proxy)
| stats countif(outcome="success") as success_count, count() as total_attempts by use_proxy, stage
| eval success_rate = round(success_count * 100.0 / total_attempts, 2)
| sort stage, use_proxy
'''.strip(),

    # Profile effectiveness analysis
    'profile_analysis': '''
fields profile, outcome, stage
| filter event = "stage_result" and ispresent(profile)
| stats countif(outcome="success") as success_count, count() as total_attempts by profile, stage
| eval success_rate = round(success_count * 100.0 / total_attempts, 2)
| sort stage, success_rate desc
'''.strip(),

    # Recent activity overview
    'recent_activity': '''
fields @timestamp, job_id, video_id, event, stage, outcome, dur_ms
| filter @timestamp > @timestamp - 1h
| filter event in ["job_received", "job_finished", "stage_result"]
| sort @timestamp desc
| limit 100
'''.strip(),

    # Performance metrics channel analysis
    'performance_metrics': '''
fields @timestamp, cpu, mem_mb
| filter event = "performance_metric"
| stats avg(cpu) as avg_cpu, avg(mem_mb) as avg_mem_mb by bin(5m)
| sort @timestamp desc
'''.strip(),

    # Rate limiting analysis
    'rate_limiting_analysis': '''
fields @timestamp, detail
| filter detail like /suppressed/
| stats count() as suppressed_count by bin(1m)
| sort @timestamp desc
'''.strip(),

    # Alert-focused queries for monitoring
    'error_rate_by_stage': '''
fields stage, outcome
| filter @timestamp > @timestamp - 1h
| filter event = "stage_result"
| stats countif(outcome="error") as errors, countif(outcome="timeout") as timeouts, count(*) as total by stage
| eval error_rate = round((errors + timeouts) * 100.0 / total, 2)
| sort error_rate desc
'''.strip(),

    'performance_degradation_alert': '''
fields stage, dur_ms
| filter @timestamp > @timestamp - 1h
| filter event = "stage_result" and ispresent(dur_ms) and dur_ms > 0
| stats pct(dur_ms, 95) as p95_ms, avg(dur_ms) as avg_ms by stage
| filter p95_ms > 30000
| sort p95_ms desc
'''.strip(),

    'job_failure_spike': '''
fields @timestamp, job_id, outcome
| filter @timestamp > @timestamp - 1h
| filter event = "job_finished" and outcome in ["failed", "error"]
| stats count() as failed_jobs by bin(5m)
| sort @timestamp desc
'''.strip(),

    # FFmpeg error analysis
    'ffmpeg_errors': '''
fields @timestamp, job_id, video_id, detail, stderr_tail
| filter stage = "ffmpeg" and outcome = "error"
| sort @timestamp desc
| limit 50
'''.strip(),

    # Timeout analysis by stage
    'timeout_analysis': '''
fields stage, dur_ms, detail
| filter outcome = "timeout"
| stats avg(dur_ms) as avg_timeout_ms, pct(dur_ms, 95) as p95_timeout_ms, count() as timeout_count by stage
| sort timeout_count desc
'''.strip()
}

# Query parameter templates for common use cases
QUERY_PARAMETERS = {
    'time_ranges': {
        'last_hour': '@timestamp > @timestamp - 1h',
        'last_24h': '@timestamp > @timestamp - 24h',
        'last_week': '@timestamp > @timestamp - 7d',
        'last_30_days': '@timestamp > @timestamp - 30d'
    },
    
    'log_levels': {
        'errors_only': 'lvl in ["ERROR", "CRITICAL"]',
        'warnings_and_errors': 'lvl in ["WARNING", "ERROR", "CRITICAL"]',
        'info_and_above': 'lvl in ["INFO", "WARNING", "ERROR", "CRITICAL"]'
    },
    
    'stages': {
        'transcript_stages': 'stage in ["youtube-transcript-api", "timedtext", "youtubei", "asr"]',
        'network_stages': 'stage in ["youtubei", "timedtext"]',
        'processing_stages': 'stage in ["ffmpeg", "asr", "summarization"]'
    }
}

def get_query_with_filters(template_name: str, **filters) -> str:
    """
    Get a query template with additional filters applied.
    
    Args:
        template_name: Name of the query template
        **filters: Additional filter conditions
        
    Returns:
        Query string with filters applied
        
    Example:
        query = get_query_with_filters(
            'error_analysis',
            time_range='last_24h',
            log_level='errors_only'
        )
    """
    if template_name not in QUERY_TEMPLATES:
        raise ValueError(f"Unknown query template: {template_name}")
    
    query = QUERY_TEMPLATES[template_name]
    
    # Add time range filter
    if 'time_range' in filters and filters['time_range'] in QUERY_PARAMETERS['time_ranges']:
        time_filter = QUERY_PARAMETERS['time_ranges'][filters['time_range']]
        query = query.replace('| filter', f'| filter {time_filter} and (') + ')'
    
    # Add log level filter
    if 'log_level' in filters and filters['log_level'] in QUERY_PARAMETERS['log_levels']:
        level_filter = QUERY_PARAMETERS['log_levels'][filters['log_level']]
        if '| filter' in query:
            query = query.replace('| filter', f'| filter {level_filter} and (') + ')'
        else:
            query = query.replace('| stats', f'| filter {level_filter}\n| stats')
    
    return query

def format_job_query(template_name: str, job_id: str) -> str:
    """
    Format a job-specific query template with the provided job_id.
    
    Args:
        template_name: Name of the query template
        job_id: Job ID to filter by
        
    Returns:
        Formatted query string
    """
    if template_name not in QUERY_TEMPLATES:
        raise ValueError(f"Unknown query template: {template_name}")
    
    return QUERY_TEMPLATES[template_name].format(job_id=job_id)

def format_video_query(template_name: str, video_id: str) -> str:
    """
    Format a video-specific query template with the provided video_id.
    
    Args:
        template_name: Name of the query template
        video_id: Video ID to filter by
        
    Returns:
        Formatted query string
    """
    if template_name not in QUERY_TEMPLATES:
        raise ValueError(f"Unknown query template: {template_name}")
    
    return QUERY_TEMPLATES[template_name].format(video_id=video_id)

# Example usage and testing
if __name__ == "__main__":
    print("Available Query Templates:")
    for name in QUERY_TEMPLATES.keys():
        print(f"  - {name}")
    
    print("\nExample Error Analysis Query:")
    print(QUERY_TEMPLATES['error_analysis'])
    
    print("\nExample Job Correlation Query:")
    print(format_job_query('job_correlation', 'j-7f3d'))