# CloudWatch Logs Insights Query Templates

This document provides pre-built CloudWatch Logs Insights query templates for analyzing TL;DW application logs. The queries are optimized for the structured JSON logging format used by the application.

## Quick Start

1. **Access CloudWatch Logs Insights**: Go to AWS Console → CloudWatch → Logs → Insights
2. **Select Log Group**: Choose `/aws/apprunner/tldw-transcript-service` (or your App Runner log group)
3. **Choose Time Range**: Select appropriate time range (last 1 hour, 24 hours, etc.)
4. **Copy Query**: Copy any query from this document
5. **Run Query**: Paste and execute the query

## Query Categories

### 🚨 Error Analysis

**Basic Error Analysis** - Recent errors and timeouts:
```sql
fields @timestamp, lvl, event, stage, outcome, detail, job_id, video_id, dur_ms
| filter outcome in ["error", "timeout", "blocked"]
| sort @timestamp desc
| limit 200
```

**Error Pattern Analysis** - Group errors by type:
```sql
fields @timestamp, lvl, event, stage, outcome, detail, job_id, video_id, dur_ms, attempt, use_proxy, profile
| filter outcome in ["error", "timeout", "blocked"]
| stats count() as error_count by stage, outcome, detail
| sort error_count desc
```

### 📊 Success Rate Analysis

**Pipeline Funnel Analysis** - Success rates by stage:
```sql
fields stage, outcome
| filter event = "stage_result"
| stats countif(outcome="success") as success_count, countif(outcome="error") as error_count, countif(outcome="timeout") as timeout_count, countif(outcome="blocked") as blocked_count, countif(outcome="no_captions") as no_captions_count, count(*) as total_attempts by stage
| eval success_rate = round(success_count * 100.0 / total_attempts, 2)
| eval error_rate = round(error_count * 100.0 / total_attempts, 2)
| eval timeout_rate = round(timeout_count * 100.0 / total_attempts, 2)
| sort success_rate asc
```

**Simple Success Rates**:
```sql
fields stage, outcome
| filter event = "stage_result"
| stats countif(outcome="success") as ok, count(*) as total by stage
| eval success_pct = round(ok * 100.0 / total, 2)
| sort success_pct asc
```

### ⚡ Performance Analysis

**P95 Duration by Stage**:
```sql
fields stage, dur_ms
| filter event = "stage_result" and ispresent(dur_ms) and dur_ms > 0
| stats avg(dur_ms) as avg_ms, pct(dur_ms, 50) as p50_ms, pct(dur_ms, 95) as p95_ms, pct(dur_ms, 99) as p99_ms, max(dur_ms) as max_ms, count() as sample_count by stage
| sort p95_ms desc
```

**Performance Trends Over Time**:
```sql
fields @timestamp, stage, dur_ms
| filter event = "stage_result" and ispresent(dur_ms) and dur_ms > 0
| stats avg(dur_ms) as avg_ms, pct(dur_ms, 95) as p95_ms by bin(5m), stage
| sort @timestamp desc
```

### 🔍 Job Troubleshooting

**Complete Job Trace** (replace `j-7f3d` with actual job ID):
```sql
fields @timestamp, event, stage, outcome, dur_ms, detail, attempt, use_proxy, profile
| filter job_id = "j-7f3d"
| sort @timestamp asc
```

**Job Lifecycle Events**:
```sql
fields @timestamp, event, stage, outcome, dur_ms, detail
| filter job_id = "j-7f3d"
| filter event in ["job_received", "stage_start", "stage_result", "job_finished"]
| sort @timestamp asc
```

**Video Processing History** (replace `bbz2boNSeL0` with actual video ID):
```sql
fields @timestamp, job_id, event, stage, outcome, dur_ms, detail, attempt, use_proxy, profile
| filter video_id = "bbz2boNSeL0"
| sort @timestamp desc
| limit 100
```

### 🔧 Specialized Analysis

**Failed Jobs Summary**:
```sql
fields job_id, video_id, stage, outcome, detail
| filter event = "stage_result" and outcome in ["error", "timeout", "blocked"]
| stats count() as failure_count by job_id, video_id
| sort failure_count desc
| limit 50
```

**Proxy Effectiveness**:
```sql
fields use_proxy, outcome, stage
| filter event = "stage_result" and ispresent(use_proxy)
| stats countif(outcome="success") as success_count, count() as total_attempts by use_proxy, stage
| eval success_rate = round(success_count * 100.0 / total_attempts, 2)
| sort stage, use_proxy
```

**Browser Profile Analysis**:
```sql
fields profile, outcome, stage
| filter event = "stage_result" and ispresent(profile)
| stats countif(outcome="success") as success_count, count() as total_attempts by profile, stage
| eval success_rate = round(success_count * 100.0 / total_attempts, 2)
| sort stage, success_rate desc
```

**FFmpeg Error Analysis**:
```sql
fields @timestamp, job_id, video_id, detail, stderr_tail
| filter stage = "ffmpeg" and outcome = "error"
| sort @timestamp desc
| limit 50
```

**Timeout Analysis**:
```sql
fields stage, dur_ms, detail
| filter outcome = "timeout"
| stats avg(dur_ms) as avg_timeout_ms, pct(dur_ms, 95) as p95_timeout_ms, count() as timeout_count by stage
| sort timeout_count desc
```

## Common Query Patterns

### Time Range Filters
Add these to any query to limit the time scope:

```sql
# Last hour
| filter @timestamp > @timestamp - 1h

# Last 24 hours
| filter @timestamp > @timestamp - 24h

# Last week
| filter @timestamp > @timestamp - 7d

# Specific date range
| filter @timestamp >= "2025-08-27T00:00:00.000Z" and @timestamp <= "2025-08-27T23:59:59.999Z"
```

### Log Level Filters
```sql
# Errors only
| filter lvl in ["ERROR", "CRITICAL"]

# Warnings and errors
| filter lvl in ["WARNING", "ERROR", "CRITICAL"]

# Info and above
| filter lvl in ["INFO", "WARNING", "ERROR", "CRITICAL"]
```

### Stage Filters
```sql
# Transcript extraction stages only
| filter stage in ["youtube-transcript-api", "timedtext", "youtubei", "asr"]

# Network-dependent stages
| filter stage in ["youtubei", "timedtext"]

# Processing stages
| filter stage in ["ffmpeg", "asr", "summarization"]
```

## Programmatic Usage

Use the Python module for programmatic access:

```python
from cloudwatch_query_templates import QUERY_TEMPLATES, format_job_query
from cloudwatch_logs_client import CloudWatchLogsClient

# Initialize client
client = CloudWatchLogsClient()

# Run error analysis
results = client.get_error_summary(hours_back=24)

# Trace specific job
job_trace = client.trace_job('j-7f3d', hours_back=24)

# Get performance metrics
performance = client.get_performance_summary(hours_back=24)
```

## Monitoring and Alerting

### Recommended CloudWatch Alarms

1. **High Error Rate**:
   - Query: Error analysis with success rate calculation
   - Threshold: >5% error rate over 15 minutes
   - Action: SNS notification

2. **High P95 Duration**:
   - Query: Performance analysis P95 metrics
   - Threshold: >30 seconds P95 duration
   - Action: SNS notification

3. **Job Failure Spike**:
   - Query: Failed jobs count per hour
   - Threshold: >10 failed jobs in 1 hour
   - Action: SNS notification

### Dashboard Widgets

Create CloudWatch dashboards with:

1. **Error Rate Timeline**: Line chart showing error percentage over time
2. **Stage Success Rates**: Bar chart of success rates by stage
3. **Performance Heatmap**: Duration percentiles by stage over time
4. **Recent Failures**: Table widget with recent error events

## Troubleshooting Workflows

### High Error Rate Investigation
1. Run **error analysis** to identify error patterns
2. Check **proxy effectiveness** if network-related errors
3. Use **job correlation** to trace specific failures
4. Review **FFmpeg errors** for audio extraction issues

### Performance Degradation
1. Use **performance analysis** to identify slow stages
2. Check **timeout analysis** for stages hitting limits
3. Review **performance trends** for degradation over time
4. Analyze **profile effectiveness** for optimization opportunities

### Failed Job Investigation
1. Start with **failed jobs summary** to identify problem videos
2. Use **video correlation** to see all attempts for a video
3. Run **job lifecycle trace** for complete job history
4. Check **stage funnel analysis** for pipeline bottlenecks

## Query Optimization Tips

1. **Use Time Ranges**: Always limit queries to relevant time periods to reduce cost and improve performance
2. **Filter Early**: Add filters before stats operations for better performance
3. **Limit Results**: Use `limit` clause to prevent large result sets
4. **Index Fields**: The JSON schema is optimized for common query patterns
5. **Combine Filters**: Use `and`/`or` operators efficiently

## Cost Optimization

1. **Query Scope**: Limit time ranges to reduce data scanned
2. **Log Retention**: Set appropriate retention periods (default: 30 days)
3. **Sampling**: Use sampling for high-volume analysis
4. **Scheduled Queries**: Use CloudWatch Events for regular monitoring queries

## JSON Schema Reference

The structured logs use this consistent schema:

```json
{
  "ts": "2025-08-27T16:24:06.123Z",
  "lvl": "INFO|WARNING|ERROR|CRITICAL",
  "job_id": "j-7f3d",
  "video_id": "bbz2boNSeL0",
  "stage": "youtube-transcript-api|timedtext|youtubei|asr|ffmpeg|summarization",
  "event": "job_received|stage_start|stage_result|job_finished|performance_metric",
  "outcome": "success|error|timeout|blocked|no_captions",
  "dur_ms": 1250,
  "detail": "Additional context or error message",
  "attempt": 2,
  "use_proxy": true,
  "profile": "desktop|mobile",
  "cookie_source": "s3|local"
}
```

## Support

- **Query Issues**: Check CloudWatch Logs Insights documentation
- **Application Logs**: Verify log group name and permissions
- **Custom Queries**: Modify templates based on specific needs
- **Performance**: Use time range filters and appropriate limits

For more examples, run:
```bash
python examples/cloudwatch_query_examples.py
```