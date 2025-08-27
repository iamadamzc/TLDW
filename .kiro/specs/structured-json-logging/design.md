# Design Document

## Overview

The streamlined JSON logging system replaces the current verbose structured logging with a minimal, query-friendly approach optimized for CloudWatch Logs Insights and production monitoring. The design focuses on consistent single-line JSON events, automatic correlation, noise reduction, and performance observability.

## Architecture

### Core Components

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Application   │───▶│  Logging Setup   │───▶│  JSON Formatter │
│     Code        │    │   & Context      │    │   & Filters     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │  Thread-Local    │    │   Log Output    │
                       │    Context       │    │  (CloudWatch)   │
                       └──────────────────┘    └─────────────────┘
```

### Key Design Principles

1. **Minimal Schema**: Fixed JSON structure with stable field ordering
2. **Thread Safety**: Thread-local context for correlation without race conditions  
3. **Performance First**: Low-overhead logging with efficient filtering
4. **Query Optimization**: Schema designed for CloudWatch Logs Insights patterns
5. **Graceful Degradation**: Fallback to basic logging if structured logging fails

## Components and Interfaces

### 1. JSON Formatter (`JsonFormatter`)

**Purpose**: Convert log records to standardized JSON format

**Interface**:
```python
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Returns single-line JSON with stable field order
```

**Key Features**:
- Fixed field order: `ts`, `lvl`, `job_id`, `video_id`, `stage`, `event`, `outcome`, `dur_ms`, `detail`
- ISO 8601 timestamps with millisecond precision
- Automatic null value omission
- Thread-local context injection

### 2. Rate Limit Filter (`RateLimitFilter`)

**Purpose**: Prevent log spam from recurring messages

**Interface**:
```python
class RateLimitFilter(logging.Filter):
    def __init__(self, per_key: int = 5, window_sec: int = 60):
    def filter(self, record: logging.LogRecord) -> bool:
        # Returns True if message should be logged
```

**Algorithm**:
- Key: `(log_level, message_template)`
- Window: Sliding 60-second windows
- Limit: 5 messages per key per window
- Suppression: One "[suppressed]" marker per window after limit

### 3. Context Manager (`set_job_ctx`, `_local`)

**Purpose**: Thread-safe correlation ID management

**Interface**:
```python
_local = threading.local()

def set_job_ctx(job_id: str = None, video_id: str = None):
    # Sets context for current thread
```

**Implementation**:
- Uses `threading.local()` for isolation
- Automatic context injection in formatter
- Context clearing on job completion

### 4. Event Helpers (`evt`, `StageTimer`)

**Purpose**: Consistent event emission and stage timing

**Interface**:
```python
def evt(event: str, **fields):
    # Emits structured event with consistent fields

class StageTimer:
    def __init__(self, name: str, **fields):
    def __enter__(self):
    def __exit__(self, exc_type, exc, tb):
        # Context manager for automatic stage timing
```

**Features**:
- Automatic duration calculation
- Exception handling with error outcomes
- Consistent field naming and types

### 5. Library Noise Suppression

**Purpose**: Reduce third-party library log volume

**Configuration**:
```python
LIBRARY_LOG_LEVELS = {
    "playwright": logging.WARNING,
    "urllib3": logging.WARNING, 
    "botocore": logging.WARNING,
    "boto3": logging.WARNING,
    "asyncio": logging.WARNING
}
```

**FFmpeg Handling**:
- Capture stderr to memory buffer
- Log only last 40 lines on failure
- Success events with byte counts only

## Data Models

### Standard Event Schema

```json
{
  "ts": "2025-08-27T16:24:06.123Z",
  "lvl": "INFO", 
  "job_id": "j-7f3d",
  "video_id": "bbz2boNSeL0",
  "stage": "youtubei",
  "event": "stage_result",
  "outcome": "timeout",
  "dur_ms": 24783,
  "detail": "route_intercept_timeout"
}
```

### Optional Context Fields

```json
{
  "attempt": 2,
  "use_proxy": true,
  "profile": "mobile", 
  "cookie_source": "s3"
}
```

### Performance Metrics Schema

```json
{
  "ts": "2025-08-27T16:24:06.123Z",
  "lvl": "INFO",
  "event": "performance_metric",
  "cpu": 12.5,
  "mem_mb": 512
}
```

## Error Handling

### Logging System Failures

1. **Formatter Errors**: Fall back to basic string formatting
2. **Context Errors**: Log without correlation IDs
3. **Rate Limit Errors**: Allow all messages through
4. **JSON Serialization Errors**: Use `str()` representation

### Application Error Logging

```python
# Exception in stage timer
{
  "ts": "2025-08-27T16:24:06.123Z",
  "lvl": "ERROR",
  "job_id": "j-7f3d", 
  "video_id": "bbz2boNSeL0",
  "stage": "youtubei",
  "event": "stage_result",
  "outcome": "error",
  "dur_ms": 1250,
  "detail": "ConnectionTimeout: Request timed out"
}
```

### FFmpeg Error Handling

```python
# FFmpeg failure with stderr capture
{
  "ts": "2025-08-27T16:24:06.123Z",
  "lvl": "ERROR",
  "job_id": "j-7f3d",
  "video_id": "bbz2boNSeL0", 
  "stage": "ffmpeg",
  "event": "stage_result",
  "outcome": "error",
  "dur_ms": 5000,
  "detail": "exit_code=1",
  "stderr_tail": "Last 40 lines of stderr..."
}
```

## Testing Strategy

### Unit Tests

1. **JsonFormatter Tests**
   - Field order consistency
   - Timestamp format validation
   - Context injection accuracy
   - Null value omission

2. **RateLimitFilter Tests**
   - Window sliding behavior
   - Suppression marker emission
   - Key collision handling
   - Thread safety

3. **Context Management Tests**
   - Thread isolation
   - Context inheritance
   - Memory leak prevention

### Integration Tests

1. **End-to-End Pipeline Tests**
   - Job correlation across stages
   - Performance metric separation
   - Error propagation

2. **CloudWatch Query Tests**
   - Query template validation
   - Field accessibility
   - Performance analysis

### Performance Tests

1. **Logging Overhead**
   - Baseline vs structured logging performance
   - Memory usage under load
   - Thread contention measurement

2. **Rate Limiting Efficiency**
   - Filter performance under spam conditions
   - Memory usage of suppression cache

## Migration Strategy

### Phase 1: Drop-in Replacement Files

1. Create `logging_setup.py` with new components
2. Create `log_events.py` with helper functions
3. Maintain existing `structured_logging.py` for compatibility

### Phase 2: Gradual Migration

1. Replace `configure_logging()` call in `app.py`
2. Migrate high-traffic areas first (transcript pipeline)
3. Update stage timing in critical paths
4. Add job context setting in worker functions

### Phase 3: Cleanup

1. Remove old structured logging imports
2. Delete deprecated logging code
3. Update documentation and examples

### Rollback Plan

- Keep old logging system available via environment variable
- Feature flag: `USE_MINIMAL_LOGGING=true/false`
- Automatic fallback on initialization errors

## Performance Considerations

### Logging Overhead

- **Target**: <1ms per log event under normal load
- **JSON Serialization**: Use `separators=(',', ':')` for minimal output
- **String Formatting**: Pre-compute static fields where possible
- **Context Lookup**: Cache thread-local access patterns

### Memory Usage

- **Rate Limit Cache**: Bounded size with LRU eviction
- **Context Storage**: Minimal thread-local footprint
- **Buffer Management**: Streaming JSON output, no accumulation

### Concurrency

- **Thread Safety**: All components must be thread-safe
- **Lock Contention**: Minimize shared state access
- **Context Isolation**: Perfect isolation between concurrent jobs

## Monitoring and Observability

### CloudWatch Logs Insights Queries

**Error Analysis**:
```sql
fields @timestamp, lvl, event, stage, outcome, detail, job_id, video_id, dur_ms
| filter outcome in ["error","timeout"] 
| sort @timestamp desc 
| limit 200
```

**Success Rate Funnel**:
```sql
fields stage, outcome
| filter event = "stage_result"
| stats countif(outcome="success") as ok, count(*) as total, ok*100.0/total as pct by stage
| sort pct asc
```

**Performance Analysis**:
```sql
fields stage, dur_ms
| filter event="stage_result" and ispresent(dur_ms)
| stats pct(dur_ms,95) as p95_ms by stage
| sort p95_ms desc
```

### Dashboard Integration

- **Real-time Metrics**: Stage success rates, P95 durations
- **Alert Thresholds**: Error rate >5%, timeout rate >10%
- **Correlation Views**: Job traces, video processing timelines

## Security Considerations

### Sensitive Data Handling

1. **Credential Masking**: Automatic detection and masking of tokens, cookies, passwords
2. **URL Sanitization**: Remove query parameters from logged URLs
3. **User Data Protection**: Hash or truncate user identifiers

### Log Access Control

1. **CloudWatch Permissions**: Restrict access to production logs
2. **Retention Policies**: Automatic cleanup of old log data
3. **Export Controls**: Secure log export for analysis

## Deployment Considerations

### Environment Configuration

```bash
# Required environment variables
LOG_LEVEL=INFO
USE_MINIMAL_LOGGING=true
CLOUDWATCH_LOG_GROUP=/aws/apprunner/tldw-transcript-service

# Optional tuning
RATE_LIMIT_PER_KEY=5
RATE_LIMIT_WINDOW_SEC=60
FFMPEG_STDERR_TAIL_LINES=40
```

### Container Integration

- **Stdout/Stderr**: All logs to stdout for container log drivers
- **Log Rotation**: Handled by container runtime
- **Health Checks**: Logging system health in application health endpoints

### AWS App Runner Integration

- **Log Groups**: Automatic CloudWatch Logs integration
- **Retention**: 30-day default retention for cost optimization
- **Insights**: Enable CloudWatch Logs Insights for query capability