# Implementation Plan

- [x] 1. Create Core Logging Infrastructure





  - Create `logging_setup.py` with JsonFormatter, RateLimitFilter, and context management
  - Implement thread-local context storage with set_job_ctx() function
  - Add configure_logging() function with library noise suppression
  - Write unit tests for JsonFormatter field order and timestamp format
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 5.1, 5.2, 5.3, 5.4_

- [x] 2. Implement Rate Limiting and Deduplication





  - Add RateLimitFilter class with sliding window algorithm
  - Implement message key generation from log level and content
  - Add suppression marker logic for exceeded rate limits
  - Create thread-safe cache with automatic window reset
  - Write unit tests for rate limiting behavior and thread safety
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 3. Create Event Helper Functions





  - Create `log_events.py` with evt() function for consistent event emission
  - Implement StageTimer context manager with automatic duration calculation
  - Add exception handling in StageTimer with error outcome logging
  - Ensure consistent field naming and JSON schema compliance
  - Write unit tests for StageTimer duration accuracy and exception handling
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 4. Implement Performance Metrics Channel Separation





  - Create dedicated "perf" logger for performance metrics
  - Modify performance logging to use separate channel
  - Update existing performance_logger calls to use new channel
  - Add performance_metric event type for CPU/memory metrics
  - Write integration tests for channel separation and filtering
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 5. Enhance FFmpeg Error Handling





  - Modify ffmpeg subprocess calls to capture stderr to memory buffer
  - Implement stderr tail extraction (last 40 lines) on failure
  - Add structured logging for ffmpeg success with byte counts
  - Update ffmpeg timeout handling with duration logging
  - Write unit tests for stderr capture and tail extraction
  - _Requirements: 5.5, 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 6. Integrate Context Management in Pipeline





  - Update job processing functions to call set_job_ctx() at start
  - Add context clearing on job completion or failure
  - Modify transcript pipeline stages to include stage context
  - Update proxy and profile context setting in YouTubei attempts
  - Write integration tests for context propagation across pipeline stages
  - _Requirements: 2.4, 2.5, 10.1, 10.2, 10.3_

- [x] 7. Migrate Core Pipeline Logging





  - Replace transcript_service.py logging calls with evt() and StageTimer
  - Update youtube-transcript-api stage with structured events
  - Migrate timedtext extraction logging to new format
  - Convert YouTubei pipeline logging to use StageTimer
  - Update ASR pipeline logging with structured events
  - _Requirements: 4.1, 4.2, 4.3, 10.2, 10.4_

- [x] 8. Add Job Lifecycle Tracking





  - Implement job_received event emission at job start
  - Add stage_result events for each pipeline stage completion
  - Implement job_finished event with total duration calculation
  - Add failure event classification for different error types
  - Write integration tests for complete job lifecycle tracking
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 9. Create CloudWatch Logs Insights Query Templates





  - Create query templates for error and timeout analysis
  - Implement funnel analysis query for stage success rates
  - Add performance analysis query for P95 duration by stage
  - Create job correlation queries for troubleshooting
  - Document query templates in deployment guide
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 10. Implement Backward Compatibility Layer





  - Create feature flag USE_MINIMAL_LOGGING for gradual migration
  - Maintain existing structured_logging.py imports during transition
  - Add fallback to basic logging on initialization errors
  - Implement drop-in replacement functions for existing log calls
  - Write migration tests to ensure no functionality regression
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 11. Update Application Entry Points





  - Modify app.py to call configure_logging() on startup
  - Update main.py and wsgi.py to initialize minimal logging
  - Add logging configuration to container startup scripts
  - Set appropriate environment variables for production deployment
  - Write deployment tests for logging initialization
  - _Requirements: 8.1, 8.2, 8.3_

- [x] 12. Create Comprehensive Test Suite





  - Write unit tests for all new logging components
  - Create integration tests for pipeline logging flow
  - Add performance tests for logging overhead measurement
  - Implement CloudWatch query validation tests
  - Create load tests for rate limiting under spam conditions
  - _Requirements: All requirements validation through testing_

- [x] 13. Update Monitoring and Alerting





  - Configure CloudWatch Logs Insights for new JSON schema
  - Update existing dashboards to use new log format
  - Create alerts for error rates and performance thresholds
  - Implement log-based metrics for stage success rates
  - Write monitoring validation tests
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 14. Documentation and Deployment Preparation





  - Create deployment guide with environment variable configuration
  - Document CloudWatch query templates and usage examples
  - Update troubleshooting guide with new log format examples
  - Create migration checklist for production deployment
  - Write operational runbook for log analysis procedures
  - _Requirements: Documentation aspects of all requirements_

- [x] 15. Production Migration and Cleanup





  - Deploy with feature flag enabled in staging environment
  - Validate log output and query functionality in staging
  - Enable minimal logging in production with monitoring
  - Remove deprecated structured logging code after validation
  - Update all documentation references to new logging system
  - _Requirements: 8.4, 8.5 and production readiness_