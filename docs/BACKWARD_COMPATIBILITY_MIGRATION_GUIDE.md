# Backward Compatibility Migration Guide

## Overview

The structured logging system now includes a backward compatibility layer that allows gradual migration from the legacy verbose JSON logging to the new minimal JSON logging system. This guide explains how to use the feature flag and migrate safely.

## Feature Flag

The migration is controlled by the `USE_MINIMAL_LOGGING` environment variable:

- `USE_MINIMAL_LOGGING=false` (default): Uses legacy structured logging
- `USE_MINIMAL_LOGGING=true`: Uses new minimal JSON logging system

## Migration Steps

### Phase 1: Preparation

1. **Verify Current System**: Ensure your application is working with the current structured logging
2. **Test Environment**: Set up a test environment to validate the new logging system
3. **Review Dependencies**: Ensure `logging_setup.py` and `log_events.py` are available

### Phase 2: Testing

1. **Enable Minimal Logging in Test**:
   ```bash
   export USE_MINIMAL_LOGGING=true
   ```

2. **Run Application Tests**:
   ```bash
   python tests/test_backward_compatibility.py
   python tests/test_backward_compatibility_integration.py
   ```

3. **Verify Log Output**: Check that logs are in the new minimal JSON format

### Phase 3: Gradual Rollout

1. **Staging Environment**:
   ```bash
   # Enable minimal logging in staging
   export USE_MINIMAL_LOGGING=true
   ```

2. **Monitor Logs**: Verify that:
   - All log events are captured
   - JSON schema is consistent
   - Performance is acceptable
   - CloudWatch queries work

3. **Production Rollout**:
   ```bash
   # Enable minimal logging in production
   export USE_MINIMAL_LOGGING=true
   ```

### Phase 4: Cleanup (Optional)

After successful migration and validation:

1. **Remove Feature Flag**: Set `USE_MINIMAL_LOGGING=true` permanently
2. **Clean Up Legacy Code**: Remove unused legacy logging components
3. **Update Documentation**: Update logging documentation to reflect new system

## API Compatibility

All existing APIs continue to work unchanged:

### Context Management
```python
from structured_logging import log_context, get_contextual_logger

# Works in both modes
with log_context(video_id="abc123", job_id="job456"):
    logger = get_contextual_logger("service_name")
    logger.info("Processing video")
```

### Performance Logging
```python
from structured_logging import log_performance, performance_logger

# Context manager - works in both modes
with log_performance("operation_name", video_id="abc123"):
    # Do work
    pass

# Direct logging - works in both modes
performance_logger.log_stage_performance(
    stage="transcript_extraction",
    duration_ms=1500.0,
    success=True,
    video_id="abc123"
)
```

### Contextual Logging
```python
from structured_logging import get_contextual_logger

logger = get_contextual_logger("service_name")
logger.info("Message", extra_field="value")  # Works in both modes
```

## Log Format Differences

### Legacy Format (USE_MINIMAL_LOGGING=false)
```json
{
  "timestamp": "2025-08-27T18:41:13.711889Z",
  "level": "INFO",
  "logger": "service_name",
  "message": "Processing video",
  "service": "tldw-transcript-service",
  "environment": "production",
  "version": "unknown",
  "hostname": "unknown",
  "thread": "MainThread",
  "process_id": 27240,
  "correlation_id": "abc-123",
  "video_id": "video123",
  "extra": {
    "custom_field": "value"
  }
}
```

### Minimal Format (USE_MINIMAL_LOGGING=true)
```json
{
  "ts": "2025-08-27T18:41:13.733Z",
  "lvl": "INFO",
  "job_id": "job456",
  "video_id": "video123",
  "stage": "processing",
  "event": "stage_result",
  "outcome": "success",
  "dur_ms": 1500,
  "detail": "Processing completed"
}
```

## CloudWatch Queries

### Legacy Queries
```sql
fields @timestamp, level, message, correlation_id, video_id
| filter level = "ERROR"
| sort @timestamp desc
```

### Minimal Queries
```sql
fields ts, lvl, job_id, video_id, stage, event, outcome, dur_ms, detail
| filter lvl = "ERROR"
| sort ts desc
```

## Error Handling

The backward compatibility layer includes robust error handling:

1. **Import Failures**: Falls back to legacy logging if minimal logging unavailable
2. **Configuration Errors**: Uses basic logging as last resort
3. **Runtime Errors**: Continues operation with available logging system

## Rollback Plan

If issues occur during migration:

1. **Immediate Rollback**:
   ```bash
   export USE_MINIMAL_LOGGING=false
   # Restart application
   ```

2. **Verify Rollback**: Check that logs return to legacy format

3. **Investigate Issues**: Review logs and error messages

## Testing

### Unit Tests
```bash
python tests/test_backward_compatibility.py
```

### Integration Tests
```bash
python tests/test_backward_compatibility_integration.py
```

### Demonstration
```bash
python demo_backward_compatibility.py
```

## Environment Variables

### Current Variables (Maintained)
- `ENABLE_STRUCTURED_LOGGING`: Still supported for backward compatibility
- `LOG_LEVEL`: Controls logging level in both systems

### New Variables
- `USE_MINIMAL_LOGGING`: Controls which logging system to use

## Performance Considerations

### Legacy System
- More verbose JSON output
- Higher memory usage
- More detailed context information

### Minimal System
- Streamlined JSON output
- Lower memory usage
- Faster log processing
- Better CloudWatch Logs Insights performance

## Troubleshooting

### Common Issues

1. **Import Errors**:
   - Ensure `logging_setup.py` and `log_events.py` are available
   - Check Python path and module imports

2. **Log Format Changes**:
   - Update CloudWatch queries for new schema
   - Adjust log parsing tools

3. **Context Issues**:
   - Verify thread-local context is working
   - Check job_id and video_id propagation

### Debug Steps

1. **Check Feature Flag**:
   ```python
   import structured_logging
   print(f"USE_MINIMAL_LOGGING: {structured_logging.USE_MINIMAL_LOGGING}")
   print(f"MINIMAL_AVAILABLE: {structured_logging._MINIMAL_LOGGING_AVAILABLE}")
   ```

2. **Test Logging**:
   ```python
   from structured_logging import setup_structured_logging
   setup_structured_logging()
   
   import logging
   logging.info("Test message")
   ```

3. **Verify Context**:
   ```python
   from structured_logging import log_context
   with log_context(video_id="test123"):
       logging.info("Context test")
   ```

## Support

For issues during migration:

1. Check the demonstration script: `python demo_backward_compatibility.py`
2. Run the test suites to verify functionality
3. Review error logs for specific failure modes
4. Use the rollback plan if needed

The backward compatibility layer ensures a smooth transition while maintaining all existing functionality.