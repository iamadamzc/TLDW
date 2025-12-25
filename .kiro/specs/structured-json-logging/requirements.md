# Requirements Document

## Introduction

This feature implements a streamlined JSON logging system for the TL;DW application to replace the current verbose structured logging with a minimal, query-friendly approach. The goal is to provide clean one-line JSON events with stable fields, reduced noise from third-party libraries, consistent job correlation, and clear stage breadcrumbs with durations. This will enable better observability through CloudWatch Logs Insights and other log analysis tools.

## Requirements

### Requirement 1: Minimal JSON Event Schema

**User Story:** As a DevOps engineer, I want consistent JSON log events with stable fields, so that I can write reliable queries and build dashboards.

#### Acceptance Criteria

1. WHEN the system logs any event THEN it SHALL use a standardized JSON schema with these exact keys in order: `ts`, `lvl`, `job_id`, `video_id`, `stage`, `event`, `outcome`, `dur_ms`, `detail`
2. WHEN logging events THEN the system SHALL use ISO 8601 timestamp format with millisecond precision (e.g., "2025-08-27T16:24:06.123Z")
3. WHEN logging stage results THEN the system SHALL use standardized outcome values: `success`, `no_captions`, `blocked`, `timeout`, `error`
4. WHEN additional context is relevant THEN the system SHALL include optional keys: `attempt`, `use_proxy`, `profile`, `cookie_source`
5. WHEN logging events THEN the system SHALL ensure all JSON is single-line format for easy parsing

### Requirement 2: Thread-Safe Context Management

**User Story:** As a developer, I want automatic job and video correlation in all log entries, so that I can trace requests across the entire pipeline.

#### Acceptance Criteria

1. WHEN a job starts processing THEN the system SHALL set thread-local context with `job_id` and `video_id`
2. WHEN any log event is emitted THEN the system SHALL automatically include the current thread's `job_id` and `video_id`
3. WHEN context is not available THEN the system SHALL omit null values from JSON output
4. WHEN multiple videos are processed concurrently THEN each thread SHALL maintain separate context isolation
5. WHEN context is cleared THEN subsequent logs SHALL not include stale correlation IDs

### Requirement 3: Rate Limiting and Deduplication

**User Story:** As a system administrator, I want to prevent log spam from recurring warnings, so that important events are not buried in noise.

#### Acceptance Criteria

1. WHEN the same log message repeats frequently THEN the system SHALL limit to maximum 5 occurrences per 60-second window
2. WHEN rate limit is exceeded THEN the system SHALL emit exactly one "[suppressed]" marker per window
3. WHEN rate limiting activates THEN the system SHALL track by combination of log level and message content
4. WHEN a new time window begins THEN the system SHALL reset counters and allow messages again
5. WHEN suppression occurs THEN the system SHALL append "[suppressed]" to the message text

### Requirement 4: Stage Timer and Event Helpers

**User Story:** As a developer, I want simple helpers for timing pipeline stages, so that I can easily add consistent performance logging.

#### Acceptance Criteria

1. WHEN entering a pipeline stage THEN the system SHALL emit a `stage_start` event with stage name and context
2. WHEN exiting a stage successfully THEN the system SHALL emit a `stage_result` event with `success` outcome and duration
3. WHEN a stage fails with exception THEN the system SHALL emit a `stage_result` event with `error` outcome and exception details
4. WHEN using stage timers THEN the system SHALL calculate duration in milliseconds with integer precision
5. WHEN stage context is provided THEN the system SHALL include fields like `profile`, `use_proxy` in events

### Requirement 5: Third-Party Library Noise Reduction

**User Story:** As a log analyst, I want to see only application-relevant events, so that I can focus on pipeline behavior without library noise.

#### Acceptance Criteria

1. WHEN configuring logging THEN the system SHALL set Playwright logger to WARNING level or higher
2. WHEN configuring logging THEN the system SHALL set urllib3 logger to WARNING level or higher  
3. WHEN configuring logging THEN the system SHALL set botocore/boto3 loggers to WARNING level or higher
4. WHEN configuring logging THEN the system SHALL set asyncio logger to WARNING level or higher
5. WHEN ffmpeg produces stderr output THEN the system SHALL capture and only log last 40 lines on non-zero exit

### Requirement 6: Performance Metrics Channel Separation

**User Story:** As a monitoring engineer, I want to separate pipeline events from performance metrics, so that I can query each type independently.

#### Acceptance Criteria

1. WHEN logging performance metrics THEN the system SHALL use a dedicated "perf" logger name
2. WHEN querying pipeline events THEN I SHALL be able to filter out performance metrics with `event != "performance_metric"`
3. WHEN logging CPU/memory metrics THEN the system SHALL use the performance channel with structured fields
4. WHEN analyzing pipeline flow THEN the system SHALL keep stage events separate from resource metrics
5. WHEN configuring log analysis THEN the system SHALL support independent retention policies for each channel

### Requirement 7: CloudWatch Logs Insights Integration

**User Story:** As a DevOps engineer, I want pre-built CloudWatch queries for common troubleshooting scenarios, so that I can quickly diagnose issues.

#### Acceptance Criteria

1. WHEN troubleshooting errors THEN the system SHALL provide a query template for errors and timeouts in last 24 hours
2. WHEN analyzing success rates THEN the system SHALL provide a query template for funnel analysis per stage
3. WHEN investigating performance THEN the system SHALL provide a query template for P95 duration by stage
4. WHEN correlating issues THEN queries SHALL support filtering by `job_id`, `video_id`, and `stage`
5. WHEN building dashboards THEN the system SHALL ensure all queries work with the standardized JSON schema

### Requirement 8: Backward Compatibility and Migration

**User Story:** As a developer, I want to migrate from existing logging without breaking current functionality, so that the transition is seamless.

#### Acceptance Criteria

1. WHEN implementing new logging THEN the system SHALL maintain existing log.info() call signatures during transition
2. WHEN migrating to new system THEN the system SHALL provide drop-in replacement functions
3. WHEN both systems coexist THEN the system SHALL not duplicate log entries
4. WHEN migration is complete THEN the system SHALL remove deprecated logging code
5. WHEN errors occur during migration THEN the system SHALL fall back to basic logging to prevent service disruption

### Requirement 9: FFmpeg Error Handling

**User Story:** As a developer, I want clean ffmpeg error reporting without spam, so that I can diagnose audio extraction issues efficiently.

#### Acceptance Criteria

1. WHEN ffmpeg succeeds THEN the system SHALL log a single success event with byte count
2. WHEN ffmpeg fails THEN the system SHALL capture stderr and log only the last 40 lines
3. WHEN ffmpeg produces warnings THEN the system SHALL not flood logs with intermediate output
4. WHEN ffmpeg times out THEN the system SHALL log timeout event with duration
5. WHEN ffmpeg errors occur THEN the system SHALL include exit code and truncated stderr in structured event

### Requirement 10: Job Lifecycle Tracking

**User Story:** As a system administrator, I want to track complete job lifecycles, so that I can measure end-to-end performance and identify bottlenecks.

#### Acceptance Criteria

1. WHEN a job is received THEN the system SHALL emit `job_received` event with configuration parameters
2. WHEN each stage completes THEN the system SHALL emit `stage_result` event with outcome and duration
3. WHEN a job finishes THEN the system SHALL emit `job_finished` event with total duration and final outcome
4. WHEN jobs fail THEN the system SHALL emit failure events with error classification
5. WHEN analyzing job performance THEN the system SHALL provide complete trace from received to finished