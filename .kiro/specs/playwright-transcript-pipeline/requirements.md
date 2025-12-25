# Requirements Document

## Introduction

This feature implements a Playwright-first transcript pipeline that replaces the current primary transcript extraction method with network interception of YouTube's `/youtubei/v1/get_transcript` API calls. The system will use Playwright to capture transcript data directly from YouTube's internal API while maintaining existing fallback methods and improving reliability through proper session management, proxy enforcement, and circuit breaker decoupling from ASR processing.

## Requirements

### Requirement 1

**User Story:** As a transcript service, I want to use Playwright network interception as the primary transcript extraction method so that I can capture transcript data directly from YouTube's internal API with higher success rates.

#### Acceptance Criteria

1. WHEN get_transcript is called THEN it SHALL attempt Playwright network interception as the first method
2. WHEN Playwright launches THEN it SHALL use storage_state from ${COOKIE_DIR}/youtube_session.json for authentication
3. WHEN navigating to YouTube video pages THEN it SHALL intercept /youtubei/v1/get_transcript XHR/Fetch requests
4. WHEN transcript JSON is captured THEN it SHALL parse and transform it to standard format [{text, start, duration}, ...]
5. WHEN Playwright method succeeds THEN it SHALL return transcript data and log success metrics
6. WHEN Playwright method fails THEN it SHALL fall back to existing methods (youtube-transcript-api, timedtext)

### Requirement 2

**User Story:** As a system administrator, I want Playwright to always use proxy connections so that network requests are properly routed and don't timeout due to direct connection issues.

#### Acceptance Criteria

1. WHEN Playwright browser context is created THEN it SHALL use proxy configuration from proxy_manager.playwright_proxy()
2. WHEN proxy credentials are available THEN they SHALL be included in Playwright proxy configuration
3. WHEN no proxy is configured in production THEN it SHALL abort with error; in development it MAY proceed with direct connection and warning
4. WHEN proxy connection fails THEN it SHALL be logged with appropriate error details
5. WHEN Playwright operations timeout THEN it SHALL log effective proxy config (masked), target URL, and elapsed time without asserting cause

### Requirement 3

**User Story:** As a transcript processing system, I want proper session state management so that authenticated YouTube sessions are maintained across transcript requests.

#### Acceptance Criteria

1. WHEN storage_state file exists at ${COOKIE_DIR}/youtube_session.json THEN it SHALL be loaded for browser context
2. WHEN storage_state file is missing THEN it SHALL log a clear warning with remediation instructions
3. WHEN storage_state is invalid or corrupted THEN it SHALL log the error and continue without authentication
4. WHEN cookie_generator.py runs THEN it SHALL save storage_state to ${COOKIE_DIR}/youtube_session.json
5. WHEN COOKIE_DIR environment variable is set THEN it SHALL be used as the base path for session storage

### Requirement 4

**User Story:** As a developer debugging transcript issues, I want comprehensive logging of Playwright operations so that I can identify network, authentication, and parsing issues.

#### Acceptance Criteria

1. WHEN Playwright browser launches THEN it SHALL log proxy configuration (masked credentials), storage_state path, and user agent
2. WHEN /youtubei/v1/get_transcript request is intercepted THEN it SHALL log success with response size and duration
3. WHEN transcript JSON parsing succeeds THEN it SHALL log the number of transcript segments extracted
4. WHEN Playwright operations fail THEN it SHALL log specific error types (timeout, navigation, parsing)
5. WHEN storage_state is missing THEN it SHALL log "Run python cookie_generator.py" as remediation

### Requirement 5

**User Story:** As a system processing multiple videos, I want ASR fallback to be decoupled from circuit breaker state so that audio processing is always available when transcript methods fail.

#### Acceptance Criteria

1. WHEN all transcript methods fail THEN ASR processing SHALL be attempted regardless of circuit breaker state
2. WHEN circuit breaker is active THEN it SHALL only affect Playwright operations, not ASR processing
3. WHEN ASR is needed THEN it SHALL log "Playwright circuit breaker active - continuing to ASR fallback"
4. WHEN ASR processing succeeds THEN it SHALL return transcript data normally
5. WHEN ASR processing fails THEN it SHALL return empty result with appropriate logging

### Requirement 6

**User Story:** As a container deployment system, I want Playwright and its dependencies properly installed so that browser automation works in the production environment.

#### Acceptance Criteria

1. WHEN Docker image is built THEN it SHALL include playwright==1.46.0 dependency
2. WHEN Docker image is built THEN it SHALL install Chromium browser with python -m playwright install --with-deps chromium
3. WHEN container starts THEN ${COOKIE_DIR} directory SHALL exist at /app/cookies
4. WHEN Playwright operations run THEN they SHALL have access to installed Chromium browser
5. WHEN browser launch fails THEN it SHALL log clear error messages about missing dependencies

### Requirement 7

**User Story:** As a cookie management system, I want cookie_generator.py to save session state to the correct location so that Playwright can load authenticated sessions.

#### Acceptance Criteria

1. WHEN cookie_generator.py runs THEN it SHALL save storage_state to ${COOKIE_DIR}/youtube_session.json
2. WHEN COOKIE_DIR environment variable is not set THEN it SHALL default to /app/cookies
3. WHEN storage_state is successfully saved THEN it SHALL log the file path for verification
4. WHEN storage_state save fails THEN it SHALL log the error with file path and permissions information
5. WHEN running locally THEN developers SHALL be able to set COOKIE_DIR to their preferred location

### Requirement 8

**User Story:** As a proxy management system, I want to provide Playwright-compatible proxy configuration so that browser requests use the same network routing as other HTTP requests.

#### Acceptance Criteria

1. WHEN proxy_manager.playwright_proxy() is called THEN it SHALL return dict with server, username, password keys
2. WHEN no proxy is configured THEN playwright_proxy() SHALL return None
3. WHEN proxy URL is malformed THEN it SHALL log error and return None
4. WHEN proxy credentials are missing THEN it SHALL return server-only configuration
5. WHEN Playwright uses proxy THEN it SHALL connect through the same Oxylabs infrastructure as other requests

### Requirement 9

**User Story:** As a transcript extraction system, I want robust JSON parsing of YouTubei responses so that transcript data is correctly extracted from various response formats.

#### Acceptance Criteria

1. WHEN /youtubei/v1/get_transcript response is captured THEN it SHALL parse JSON to extract transcript cues
2. WHEN transcript cues are found THEN they SHALL be transformed to [{text, start, duration}, ...] format
3. WHEN JSON structure is unexpected THEN it SHALL log parsing errors and return None
4. WHEN multiple transcript formats exist in response THEN it SHALL prefer manual over auto-generated transcripts
5. WHEN transcript segments contain timestamps THEN they SHALL be converted to float seconds

### Requirement 10

**User Story:** As a system maintaining backward compatibility, I want existing transcript methods to remain as fallbacks so that the system continues working if Playwright fails.

#### Acceptance Criteria

1. WHEN Playwright method fails THEN youtube-transcript-api SHALL be attempted as second method
2. WHEN youtube-transcript-api fails THEN timedtext method SHALL be attempted as third method
3. WHEN all transcript methods fail THEN ASR processing SHALL be attempted as final fallback
4. WHEN fallback methods are used THEN they SHALL not trigger circuit breaker penalties
5. WHEN any method succeeds THEN processing SHALL stop and return the successful result

### Requirement 11

**User Story:** As a performance monitoring system, I want Playwright operations to include timing metrics so that performance can be tracked and optimized.

#### Acceptance Criteria

1. WHEN Playwright transcript extraction starts THEN it SHALL record start timestamp
2. WHEN transcript JSON is captured THEN it SHALL log duration_ms for performance tracking
3. WHEN Playwright operations complete THEN it SHALL log total operation time
4. WHEN operations timeout THEN it SHALL log elapsed time at timeout
5. WHEN performance metrics are logged THEN they SHALL include operation=transcript_playwright and success=true/false

### Requirement 12

**User Story:** As a development and testing system, I want clear setup instructions so that developers can properly configure Playwright locally and in CI.

#### Acceptance Criteria

1. WHEN setting up locally THEN developers SHALL run pip install -r requirements.txt to get Playwright
2. WHEN setting up locally THEN developers SHALL run python -m playwright install --with-deps chromium
3. WHEN generating cookies THEN developers SHALL set COOKIE_DIR environment variable appropriately
4. WHEN running cookie_generator.py THEN it SHALL create the session file in the correct location
5. WHEN verifying setup THEN developers SHALL be able to check ls -l "$COOKIE_DIR/youtube_session.json"

### Requirement 13

**User Story:** As a network request system, I want Playwright to handle multiple YouTube URL formats so that transcript extraction works across different video access patterns.

#### Acceptance Criteria

1. WHEN accessing videos THEN Playwright SHALL try https://www.youtube.com/watch?v={video_id}&hl=en as primary URL
2. WHEN primary URL fails THEN it SHALL try m.youtube.com/watch?v={video_id} as secondary URL
3. WHEN navigating to video pages THEN it SHALL wait for domcontentloaded before looking for transcript requests
4. WHEN page navigation times out THEN it SHALL log timeout and try next URL format
5. WHEN both URL formats fail THEN it SHALL return None and fall back to next transcript method

### Requirement 14

**User Story:** As an error handling system, I want clear error categorization so that different types of Playwright failures can be diagnosed and addressed appropriately.

#### Acceptance Criteria

1. WHEN storage_state file is missing THEN error SHALL be categorized as "authentication_missing"
2. WHEN browser launch fails THEN error SHALL be categorized as "browser_launch_failure"
3. WHEN page navigation times out THEN error SHALL be categorized as "navigation_timeout"
4. WHEN JSON parsing fails THEN error SHALL be categorized as "response_parsing_error"
5. WHEN proxy connection fails THEN error SHALL be categorized as "proxy_connection_error"

### Requirement 15

**User Story:** As a circuit breaker system, I want Playwright failures to be tracked separately from ASR availability so that transcript and audio processing failures are handled independently.

#### Acceptance Criteria

1. WHEN Playwright operations fail THEN circuit breaker SHALL track only Playwright-specific failures
2. WHEN circuit breaker is active THEN it SHALL skip Playwright but allow other transcript methods
3. WHEN circuit breaker is active THEN ASR processing SHALL remain available as final fallback
4. WHEN Playwright succeeds after circuit breaker activation THEN failure count SHALL reset
5. WHEN circuit breaker activates THEN it SHALL log "Playwright circuit breaker activated - skipping for 10 minutes"