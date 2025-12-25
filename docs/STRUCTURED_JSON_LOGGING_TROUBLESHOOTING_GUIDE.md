# Structured JSON Logging Troubleshooting Guide

## Overview

This guide helps diagnose and resolve issues with the structured JSON logging system in the TL;DW application. It includes common problems, diagnostic procedures, and example log entries for various scenarios.

## Log Format Examples

### Successful Pipeline Execution

```json
{"ts": "2025-08-27T16:24:06.123Z", "lvl": "INFO", "job_id": "j-7f3d", "video_id": "bbz2boNSeL0", "event": "job_received", "detail": "processing_started"}
{"ts": "2025-08-27T16:24:06.145Z", "lvl": "INFO", "job_id": "j-7f3d", "video_id": "bbz2boNSeL0", "stage": "youtubei", "event": "stage_start", "profile": "mobile", "use_proxy": false}
{"ts": "2025-08-27T16:24:07.398Z", "lvl": "INFO", "job_id": "j-7f3d", "video_id": "bbz2boNSeL0", "stage": "youtubei", "event": "stage_result", "outcome": "success", "dur_ms": 1253, "detail": "transcript_extracted"}
{"ts": "2025-08-27T16:24:07.425Z", "lvl": "INFO", "job_id": "j-7f3d", "video_id": "bbz2boNSeL0", "event": "job_finished", "outcome": "success", "dur_ms": 1302}
```

### Failed Pipeline with Timeout

```json
{"ts": "2025-08-27T16:24:06.123Z", "lvl": "INFO", "job_id": "j-8g4e", "video_id": "xyz123abc", "event": "job_received", "detail": "processing_started"}
{"ts": "2025-08-27T16:24:06.145Z", "lvl": "INFO", "job_id": "j-8g4e", "video_id": "xyz123abc", "stage": "youtubei", "event": "stage_start", "profile": "desktop", "use_proxy": true}
{"ts": "2025-08-27T16:24:31.148Z", "lvl": "ERROR", "job_id": "j-8g4e", "video_id": "xyz123abc", "stage": "youtubei", "event": "stage_result", "outcome": "timeout", "dur_ms": 25003, "detail": "route_intercept_timeout"}
{"ts": "2025-08-27T16:24:31.150Z", "lvl": "INFO", "job_id": "j-8g4e", "video_id": "xyz123abc", "stage": "timedtext", "event": "stage_start"}
{"ts": "2025-08-27T16:24:32.401Z", "lvl": "INFO", "job_id": "j-8g4e", "video_id": "xyz123abc", "stage": "timedtext", "event": "stage_result", "outcome": "success", "dur_ms": 1251, "detail": "captions_found"}
{"ts": "2025-08-27T16:24:32.425Z", "lvl": "INFO", "job_id": "j-8g4e", "video_id": "xyz123abc", "event": "job_finished", "outcome": "success", "dur_ms": 26302}
```

### FFmpeg Error with Stderr Capture

```json
{"ts": "2025-08-27T16:24:06.123Z", "lvl": "INFO", "job_id": "j-9h5f", "video_id": "def456ghi", "stage": "ffmpeg", "event": "stage_start", "detail": "audio_extraction"}
{"ts": "2025-08-27T16:24:11.128Z", "lvl": "ERROR", "job_id": "j-9h5f", "video_id": "def456ghi", "stage": "ffmpeg", "event": "stage_result", "outcome": "error", "dur_ms": 5005, "detail": "exit_code=1", "stderr_tail": "Input/output error\nCould not open input file: invalid URL\nConversion failed!"}
```

### Rate Limiting in Action

```json
{"ts": "2025-08-27T16:24:06.123Z", "lvl": "WARNING", "detail": "Connection timeout to proxy server"}
{"ts": "2025-08-27T16:24:06.145Z", "lvl": "WARNING", "detail": "Connection timeout to proxy server"}
{"ts": "2025-08-27T16:24:06.167Z", "lvl": "WARNING", "detail": "Connection timeout to proxy server"}
{"ts": "2025-08-27T16:24:06.189Z", "lvl": "WARNING", "detail": "Connection timeout to proxy server"}
{"ts": "2025-08-27T16:24:06.211Z", "lvl": "WARNING", "detail": "Connection timeout to proxy server"}
{"ts": "2025-08-27T16:24:06.233Z", "lvl": "WARNING", "detail": "Connection timeout to proxy server [suppressed]"}
```

### Performance Metrics Channel

```json
{"ts": "2025-08-27T16:24:06.123Z", "lvl": "INFO", "event": "performance_metric", "cpu": 12.5, "mem_mb": 512}
{"ts": "2025-08-27T16:24:36.124Z", "lvl": "INFO", "event": "performance_metric", "cpu": 18.3, "mem_mb": 547}
```

## Common Issues and Solutions

### 1. Logging Not Working

**Symptoms:**
- No JSON logs appearing in CloudWatch
- Application logs missing or in wrong format
- Old structured logging format still appearing

**Diagnostic Steps:**

```bash
# Check environment variables
echo $USE_MINIMAL_LOGGING
echo $LOG_LEVEL

# Verify logging configuration
python -c "
from logging_setup import configure_logging
import logging
configure_logging()
logger = logging.getLogger(__name__)
logger.info('Test log message')
"
```

**Common Causes and Solutions:**

1. **Environment Variable Not Set**
   ```bash
   export USE_MINIMAL_LOGGING=true
   ```

2. **Import Error**
   ```python
   # Check if logging_setup module is available
   python -c "import logging_setup; print('Module imported successfully')"
   ```

3. **CloudWatch Permissions**
   ```bash
   # Test CloudWatch connectivity
   aws logs describe-log-groups --log-group-name-prefix "/aws/apprunner/tldw"
   ```

### 2. Missing Correlation IDs

**Symptoms:**
- Log entries missing `job_id` or `video_id` fields
- Cannot trace requests through pipeline

**Example Problem Log:**
```json
{"ts": "2025-08-27T16:24:06.123Z", "lvl": "INFO", "stage": "youtubei", "event": "stage_result", "outcome": "success", "dur_ms": 1253}
```

**Diagnostic Steps:**

```python
# Check if context is being set
from logging_setup import _local
print(f"Current context: job_id={getattr(_local, 'job_id', None)}, video_id={getattr(_local, 'video_id', None)}")
```

**Solutions:**

1. **Add Context Setting**
   ```python
   from logging_setup import set_job_ctx
   
   def process_job(job_id, video_id):
       set_job_ctx(job_id=job_id, video_id=video_id)
       # ... rest of processing
   ```

2. **Check Thread Context**
   ```python
   # Ensure context is set in the correct thread
   import threading
   print(f"Current thread: {threading.current_thread().name}")
   ```

### 3. Rate Limiting Too Aggressive

**Symptoms:**
- Important log messages being suppressed
- Too many `[suppressed]` markers
- Missing error details

**Example Problem:**
```json
{"ts": "2025-08-27T16:24:06.233Z", "lvl": "ERROR", "detail": "Critical system error [suppressed]"}
```

**Diagnostic Steps:**

```bash
# Count suppression events
aws logs start-query \
  --log-group-name "/aws/apprunner/tldw-transcript-service" \
  --start-time $(date -d '1 hour ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @message | filter @message like /\[suppressed\]/ | stats count()'
```

**Solutions:**

1. **Adjust Rate Limiting Parameters**
   ```bash
   export RATE_LIMIT_PER_KEY=10
   export RATE_LIMIT_WINDOW_SEC=120
   ```

2. **Identify Noisy Log Sources**
   ```python
   # Add specific handling for known noisy sources
   import logging
   logging.getLogger('noisy_library').setLevel(logging.ERROR)
   ```

### 4. CloudWatch Query Failures

**Symptoms:**
- Queries return no results
- Syntax errors in CloudWatch Logs Insights
- Field not found errors

**Common Query Problems:**

1. **Field Name Typos**
   ```sql
   # Wrong
   fields job-id, video-id
   
   # Correct
   fields job_id, video_id
   ```

2. **Missing Time Filters**
   ```sql
   # Add time filter for better performance
   fields @timestamp, job_id, stage
   | filter @timestamp > datefloor(@timestamp, 1h) - 24h
   ```

3. **JSON Parsing Issues**
   ```sql
   # Check if logs are properly parsed as JSON
   fields @timestamp, @message
   | filter ispresent(job_id)
   | limit 5
   ```

### 5. Performance Impact

**Symptoms:**
- Application slowdown after logging deployment
- High CPU usage
- Memory leaks

**Diagnostic Steps:**

```python
# Measure logging overhead
import time
import logging
from logging_setup import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

# Benchmark logging performance
start_time = time.time()
for i in range(1000):
    logger.info("Test message", extra={"iteration": i})
end_time = time.time()

print(f"1000 log messages took {(end_time - start_time) * 1000:.2f}ms")
```

**Solutions:**

1. **Optimize Log Level**
   ```bash
   # Reduce log volume in production
   export LOG_LEVEL=WARNING
   ```

2. **Check Rate Limiting Cache Size**
   ```python
   # Monitor rate limiting cache
   from logging_setup import RateLimitFilter
   # Add cache size monitoring
   ```

### 6. FFmpeg Stderr Capture Issues

**Symptoms:**
- Missing FFmpeg error details
- Truncated error messages
- No stderr capture

**Example Problem:**
```json
{"ts": "2025-08-27T16:24:11.128Z", "lvl": "ERROR", "stage": "ffmpeg", "event": "stage_result", "outcome": "error", "dur_ms": 5005, "detail": "exit_code=1"}
```

**Solutions:**

1. **Increase Stderr Capture Lines**
   ```bash
   export FFMPEG_STDERR_TAIL_LINES=80
   ```

2. **Check FFmpeg Integration**
   ```python
   # Verify stderr capture is working
   import subprocess
   result = subprocess.run(['ffmpeg', '-invalid-option'], 
                          capture_output=True, text=True)
   print(f"Stderr: {result.stderr}")
   ```

## Diagnostic Procedures

### 1. Health Check Procedure

```bash
#!/bin/bash
# comprehensive_logging_health_check.sh

echo "=== Structured JSON Logging Health Check ==="

# Check environment variables
echo "Environment Variables:"
echo "USE_MINIMAL_LOGGING: $USE_MINIMAL_LOGGING"
echo "LOG_LEVEL: $LOG_LEVEL"
echo "CLOUDWATCH_LOG_GROUP: $CLOUDWATCH_LOG_GROUP"

# Test logging configuration
echo -e "\nTesting logging configuration..."
python3 -c "
from logging_setup import configure_logging
import logging
configure_logging()
logger = logging.getLogger('health_check')
logger.info('Health check log message')
print('Logging configuration: OK')
" || echo "Logging configuration: FAILED"

# Test CloudWatch connectivity
echo -e "\nTesting CloudWatch connectivity..."
aws logs describe-log-groups --log-group-name-prefix "/aws/apprunner/tldw" > /dev/null 2>&1 && \
echo "CloudWatch connectivity: OK" || echo "CloudWatch connectivity: FAILED"

# Check recent log entries
echo -e "\nRecent log entries:"
aws logs tail "/aws/apprunner/tldw-transcript-service" --since 5m | head -5

echo -e "\n=== Health Check Complete ==="
```

### 2. Performance Monitoring

```python
#!/usr/bin/env python3
# logging_performance_monitor.py

import time
import logging
import threading
from logging_setup import configure_logging, set_job_ctx
from log_events import evt, StageTimer

def performance_test():
    configure_logging()
    
    # Test basic logging performance
    logger = logging.getLogger(__name__)
    
    print("Testing basic logging performance...")
    start_time = time.time()
    for i in range(1000):
        logger.info(f"Test message {i}")
    basic_time = time.time() - start_time
    
    # Test structured event logging
    print("Testing structured event logging...")
    set_job_ctx(job_id="perf-test", video_id="test123")
    start_time = time.time()
    for i in range(1000):
        evt("test_event", iteration=i, detail="performance_test")
    structured_time = time.time() - start_time
    
    # Test stage timer
    print("Testing stage timer...")
    start_time = time.time()
    for i in range(100):
        with StageTimer("test_stage", iteration=i):
            time.sleep(0.001)  # Simulate work
    timer_time = time.time() - start_time
    
    print(f"\nPerformance Results:")
    print(f"Basic logging: {basic_time*1000:.2f}ms for 1000 messages ({basic_time:.3f}ms per message)")
    print(f"Structured events: {structured_time*1000:.2f}ms for 1000 messages ({structured_time:.3f}ms per message)")
    print(f"Stage timers: {timer_time*1000:.2f}ms for 100 timers ({timer_time*10:.3f}ms per timer)")

if __name__ == "__main__":
    performance_test()
```

### 3. Log Format Validation

```python
#!/usr/bin/env python3
# validate_log_format.py

import json
import logging
from logging_setup import configure_logging, set_job_ctx
from log_events import evt, StageTimer

def validate_log_format():
    # Capture log output
    import io
    import sys
    
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    
    configure_logging()
    logger = logging.getLogger(__name__)
    logger.addHandler(handler)
    
    # Generate test logs
    set_job_ctx(job_id="test-job", video_id="test-video")
    
    evt("test_event", outcome="success", detail="validation_test")
    
    with StageTimer("test_stage"):
        pass
    
    # Validate log format
    log_output = log_capture.getvalue()
    log_lines = [line.strip() for line in log_output.split('\n') if line.strip()]
    
    print("Validating log format...")
    for i, line in enumerate(log_lines):
        try:
            log_entry = json.loads(line)
            
            # Check required fields
            required_fields = ['ts', 'lvl']
            for field in required_fields:
                if field not in log_entry:
                    print(f"ERROR: Missing required field '{field}' in log entry {i+1}")
                    return False
            
            # Validate timestamp format
            import datetime
            try:
                datetime.datetime.fromisoformat(log_entry['ts'].replace('Z', '+00:00'))
            except ValueError:
                print(f"ERROR: Invalid timestamp format in log entry {i+1}: {log_entry['ts']}")
                return False
            
            print(f"✓ Log entry {i+1}: Valid JSON with correct schema")
            
        except json.JSONDecodeError:
            print(f"ERROR: Invalid JSON in log entry {i+1}: {line}")
            return False
    
    print("✓ All log entries validated successfully")
    return True

if __name__ == "__main__":
    validate_log_format()
```

## Emergency Procedures

### 1. Immediate Rollback

If the logging system causes critical issues:

```bash
#!/bin/bash
# emergency_rollback.sh

echo "=== EMERGENCY LOGGING ROLLBACK ==="

# Disable new logging system
export USE_MINIMAL_LOGGING=false
export LOGGING_MIGRATION_MODE=rollback

# Restart application
if command -v systemctl &> /dev/null; then
    sudo systemctl restart tldw-app
elif command -v docker &> /dev/null; then
    docker restart tldw-container
else
    # AWS App Runner - redeploy
    ./deploy-apprunner.sh --environment production --timeout 300
fi

echo "Rollback initiated. Monitor application health."
```

### 2. Log Volume Emergency

If logs are consuming too much storage:

```bash
#!/bin/bash
# reduce_log_volume.sh

echo "=== REDUCING LOG VOLUME ==="

# Increase log level to reduce volume
export LOG_LEVEL=ERROR

# Increase rate limiting
export RATE_LIMIT_PER_KEY=2
export RATE_LIMIT_WINDOW_SEC=300

# Restart application
echo "Restarting with reduced logging..."
```

## Monitoring and Alerting

### CloudWatch Alarms for Logging Health

```bash
# Create alarm for logging errors
aws cloudwatch put-metric-alarm \
  --alarm-name "TL-DW-Logging-Errors" \
  --alarm-description "Alert on logging system errors" \
  --metric-name "LoggingErrors" \
  --namespace "TL-DW/System" \
  --statistic "Sum" \
  --period 300 \
  --threshold 10 \
  --comparison-operator "GreaterThanThreshold" \
  --alarm-actions "arn:aws:sns:us-east-1:123456789012:tldw-alerts"

# Create alarm for high suppression rate
aws cloudwatch put-metric-alarm \
  --alarm-name "TL-DW-High-Log-Suppression" \
  --alarm-description "Alert on high log suppression rate" \
  --metric-name "LogSuppressionRate" \
  --namespace "TL-DW/System" \
  --statistic "Average" \
  --period 300 \
  --threshold 50 \
  --comparison-operator "GreaterThanThreshold"
```

## Best Practices for Troubleshooting

1. **Start with Recent Logs**: Always check the most recent log entries first
2. **Use Job Correlation**: Follow `job_id` through the entire pipeline
3. **Check Context**: Verify thread-local context is properly set
4. **Monitor Performance**: Watch for logging overhead impact
5. **Validate JSON**: Ensure logs are properly formatted JSON
6. **Test Queries**: Validate CloudWatch queries with small time ranges first
7. **Document Issues**: Keep a record of common problems and solutions

## Getting Help

### Internal Resources
- **Development Team**: Check internal documentation and team channels
- **DevOps Team**: For CloudWatch and infrastructure issues
- **On-call Engineer**: For production emergencies

### External Resources
- **AWS CloudWatch Logs Documentation**: https://docs.aws.amazon.com/cloudwatch/
- **Python Logging Documentation**: https://docs.python.org/3/library/logging.html
- **JSON Schema Validation**: https://json-schema.org/

### Escalation Procedures

1. **Level 1**: Check this troubleshooting guide
2. **Level 2**: Contact development team with specific error messages
3. **Level 3**: Engage DevOps team for infrastructure issues
4. **Level 4**: Emergency rollback if system stability is affected