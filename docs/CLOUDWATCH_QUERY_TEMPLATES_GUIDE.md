# CloudWatch Logs Insights Query Templates Guide

## Overview

This guide provides pre-built CloudWatch Logs Insights query templates for analyzing the structured JSON logging output from the TL;DW application. These queries are optimized for the standardized JSON schema and common troubleshooting scenarios.

## JSON Schema Reference

The structured logging system uses this standardized JSON format:

```json
{
  "ts": "2025-08-27T16:24:06.123Z",
  "lvl": "INFO",
  "job_id": "j-7f3d",
  "video_id": "bbz2boNSeL0", 
  "stage": "youtubei",
  "event": "stage_result",
  "outcome": "success",
  "dur_ms": 1250,
  "detail": "transcript_extracted"
}
```

### Field Descriptions

- **ts**: ISO 8601 timestamp with millisecond precision
- **lvl**: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **job_id**: Unique job identifier for correlation
- **video_id**: YouTube video ID being processed
- **stage**: Pipeline stage (youtubei, timedtext, asr, etc.)
- **event**: Event type (stage_start, stage_result, job_received, etc.)
- **outcome**: Result status (success, error, timeout, blocked, no_captions)
- **dur_ms**: Duration in milliseconds (for timed events)
- **detail**: Additional context or error information

## Error Analysis Queries

### 1. Recent Errors and Timeouts

Find all errors and timeouts in the last 24 hours:

```sql
fields @timestamp, lvl, event, stage, outcome, detail, job_id, video_id, dur_ms
| filter outcome in ["error", "timeout"] 
| sort @timestamp desc 
| limit 200
```

**Use Case**: Quick overview of recent failures for incident response.

### 2. Error Distribution by Stage

Analyze which pipeline stages are failing most frequently:

```sql
fields stage, outcome, detail
| filter outcome = "error"
| stats count() as error_count by stage, detail
| sort error_count desc
| limit 50
```

**Use Case**: Identify problematic pipeline stages for targeted fixes.

### 3. Timeout Analysis

Find stages with frequent timeouts and their durations:

```sql
fields stage, dur_ms, detail, video_id
| filter outcome = "timeout"
| stats count() as timeout_count, avg(dur_ms) as avg_duration_ms, max(dur_ms) as max_duration_ms by stage
| sort timeout_count desc
```

**Use Case**: Optimize timeout thresholds and identify slow stages.

### 4. Error Details by Video

Investigate failures for specific videos:

```sql
fields @timestamp, stage, outcome, detail, dur_ms
| filter video_id = "YOUR_VIDEO_ID" and outcome in ["error", "timeout"]
| sort @timestamp asc
```

**Use Case**: Debug specific video processing failures.

## Success Rate Analysis

### 5. Stage Success Rate Funnel

Calculate success rates for each pipeline stage:

```sql
fields stage, outcome
| filter event = "stage_result"
| stats countif(outcome="success") as success_count, count() as total_attempts, success_count*100.0/total_attempts as success_rate by stage
| sort success_rate asc
```

**Use Case**: Identify stages with low success rates for improvement.

### 6. Daily Success Trends

Track success rates over time:

```sql
fields @timestamp, stage, outcome
| filter event = "stage_result"
| bin(@timestamp, 1h) as hour
| stats countif(outcome="success") as success, count() as total, success*100.0/total as success_rate by hour, stage
| sort hour desc, success_rate asc
```

**Use Case**: Monitor success rate trends and identify degradation periods.

### 7. Job Completion Rate

Analyze overall job completion rates:

```sql
fields job_id, event, outcome
| filter event in ["job_received", "job_finished"]
| stats countif(event="job_received") as started, countif(event="job_finished") as completed, completed*100.0/started as completion_rate
```

**Use Case**: Track end-to-end job success metrics.

## Performance Analysis

### 8. Stage Duration Analysis (P95)

Find 95th percentile durations by stage:

```sql
fields stage, dur_ms
| filter event = "stage_result" and ispresent(dur_ms)
| stats pct(dur_ms, 95) as p95_ms, pct(dur_ms, 50) as p50_ms, avg(dur_ms) as avg_ms by stage
| sort p95_ms desc
```

**Use Case**: Identify slow stages and set appropriate timeout thresholds.

### 9. Job Duration Distribution

Analyze end-to-end job processing times:

```sql
fields job_id, dur_ms
| filter event = "job_finished" and ispresent(dur_ms)
| stats pct(dur_ms, 95) as p95_ms, pct(dur_ms, 50) as p50_ms, avg(dur_ms) as avg_ms, min(dur_ms) as min_ms, max(dur_ms) as max_ms
```

**Use Case**: Understand overall system performance characteristics.

### 10. Slowest Jobs

Find the slowest processing jobs:

```sql
fields @timestamp, job_id, video_id, dur_ms, outcome
| filter event = "job_finished" and ispresent(dur_ms)
| sort dur_ms desc
| limit 20
```

**Use Case**: Investigate performance outliers and optimization opportunities.

## Job Correlation and Tracing

### 11. Complete Job Trace

Follow a specific job through the entire pipeline:

```sql
fields @timestamp, stage, event, outcome, dur_ms, detail
| filter job_id = "YOUR_JOB_ID"
| sort @timestamp asc
```

**Use Case**: Debug specific job failures with complete timeline.

### 12. Video Processing History

See all processing attempts for a specific video:

```sql
fields @timestamp, job_id, stage, event, outcome, dur_ms, detail
| filter video_id = "YOUR_VIDEO_ID"
| sort @timestamp desc
| limit 100
```

**Use Case**: Understand video-specific processing patterns and issues.

### 13. Concurrent Job Analysis

Analyze system load and concurrent processing:

```sql
fields @timestamp, job_id, event
| filter event in ["job_received", "job_finished"]
| bin(@timestamp, 5m) as time_window
| stats countif(event="job_received") as started, countif(event="job_finished") as completed by time_window
| sort time_window desc
```

**Use Case**: Monitor system load and identify peak processing periods.

## Proxy and Network Analysis

### 14. Proxy Usage Analysis

Analyze proxy usage patterns and success rates:

```sql
fields use_proxy, outcome, stage
| filter ispresent(use_proxy) and event = "stage_result"
| stats countif(outcome="success") as success, count() as total, success*100.0/total as success_rate by use_proxy, stage
| sort stage, use_proxy
```

**Use Case**: Evaluate proxy effectiveness and optimize routing decisions.

### 15. Profile Performance Comparison

Compare success rates across different browser profiles:

```sql
fields profile, outcome, stage
| filter ispresent(profile) and event = "stage_result"
| stats countif(outcome="success") as success, count() as total, success*100.0/total as success_rate by profile, stage
| sort stage, success_rate desc
```

**Use Case**: Optimize browser profile selection for better success rates.

## Rate Limiting and System Health

### 16. Rate Limiting Activity

Monitor rate limiting suppression events:

```sql
fields @message, @timestamp
| filter @message like /\[suppressed\]/
| stats count() as suppression_count by bin(@timestamp, 1h)
| sort @timestamp desc
```

**Use Case**: Monitor log spam and adjust rate limiting parameters.

### 17. System Resource Metrics

Analyze performance metrics from the dedicated performance channel:

```sql
fields @timestamp, cpu, mem_mb
| filter event = "performance_metric"
| bin(@timestamp, 5m) as time_window
| stats avg(cpu) as avg_cpu, avg(mem_mb) as avg_memory_mb, max(cpu) as max_cpu, max(mem_mb) as max_memory_mb by time_window
| sort time_window desc
```

**Use Case**: Monitor system resource usage and identify resource constraints.

## Custom Query Examples

### 18. Failed Jobs with Context

Find failed jobs with full context for debugging:

```sql
fields @timestamp, job_id, video_id, stage, outcome, detail, dur_ms, use_proxy, profile
| filter outcome in ["error", "timeout", "blocked"]
| sort @timestamp desc
| limit 50
```

### 19. High-Duration Stages

Identify stages taking longer than expected:

```sql
fields @timestamp, job_id, video_id, stage, dur_ms, outcome, detail
| filter event = "stage_result" and dur_ms > 30000
| sort dur_ms desc
| limit 30
```

### 20. Cookie Source Analysis

Analyze success rates by cookie source:

```sql
fields cookie_source, outcome, stage
| filter ispresent(cookie_source) and event = "stage_result"
| stats countif(outcome="success") as success, count() as total, success*100.0/total as success_rate by cookie_source, stage
| sort stage, success_rate desc
```

## Query Optimization Tips

### Performance Best Practices

1. **Use Time Filters**: Always include time range filters to limit data scanned
2. **Filter Early**: Apply filters before stats operations
3. **Limit Results**: Use `limit` to prevent large result sets
4. **Index Fields**: Queries on `job_id`, `video_id`, and `stage` are optimized

### Example Optimized Query Structure

```sql
# Good: Filter first, then aggregate
fields stage, outcome
| filter @timestamp > datefloor(@timestamp, 1h) - 24h  # Time filter
| filter event = "stage_result"                        # Event filter
| stats count() by stage, outcome                      # Aggregate
| limit 100                                           # Limit results

# Avoid: Aggregating before filtering
fields stage, outcome
| stats count() by stage, outcome                      # Expensive without filters
| filter event = "stage_result"                        # Too late
```

## Alerting Integration

### CloudWatch Alarms

Create alarms based on query results:

```bash
# Example: Alert on high error rate
aws cloudwatch put-metric-alarm \
  --alarm-name "TL-DW-High-Error-Rate" \
  --alarm-description "Alert when error rate exceeds 10%" \
  --metric-name "ErrorRate" \
  --namespace "TL-DW/Pipeline" \
  --statistic "Average" \
  --period 300 \
  --threshold 10.0 \
  --comparison-operator "GreaterThanThreshold"
```

### Custom Metrics from Logs

Use CloudWatch Logs metric filters to create custom metrics:

```bash
# Create metric filter for error events
aws logs put-metric-filter \
  --log-group-name "/aws/apprunner/tldw-transcript-service" \
  --filter-name "ErrorEvents" \
  --filter-pattern '{ $.outcome = "error" }' \
  --metric-transformations \
    metricName=ErrorCount,metricNamespace=TL-DW/Pipeline,metricValue=1
```

## Troubleshooting Query Issues

### Common Problems

1. **No Results**: Check time range and log group name
2. **Syntax Errors**: Validate field names against JSON schema
3. **Slow Queries**: Add time filters and reduce result set size
4. **Missing Fields**: Use `ispresent(field_name)` to check field existence

### Debug Queries

Test field availability:

```sql
# Check available fields in recent logs
fields @timestamp, @message
| limit 10
```

Validate JSON structure:

```sql
# Verify JSON parsing
fields @timestamp, ts, lvl, job_id, video_id, stage, event
| filter ispresent(ts)
| limit 5
```

## Integration with Dashboards

### CloudWatch Dashboard Widgets

Example dashboard widget configuration:

```json
{
  "type": "log",
  "properties": {
    "query": "SOURCE '/aws/apprunner/tldw-transcript-service'\n| fields @timestamp, stage, outcome\n| filter event = \"stage_result\"\n| stats countif(outcome=\"success\") as success, count() as total by stage\n| sort success desc",
    "region": "us-east-1",
    "title": "Stage Success Rates",
    "view": "table"
  }
}
```

### Grafana Integration

For Grafana dashboards, use the CloudWatch Logs data source with these queries as templates.

## Best Practices

1. **Save Frequently Used Queries**: Use CloudWatch Logs Insights saved queries feature
2. **Document Custom Queries**: Maintain team documentation for custom analysis queries
3. **Regular Review**: Periodically review and update query templates
4. **Performance Monitoring**: Monitor query execution time and optimize as needed
5. **Access Control**: Ensure proper IAM permissions for query execution