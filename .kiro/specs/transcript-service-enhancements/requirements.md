# Requirements Document

## Introduction

This feature implements comprehensive enhancements to the TL;DW transcript service pipeline, building upon existing Playwright integration and cookie management systems. The enhancements focus on improving reliability, deterministic behavior, multi-client support, and better integration between transcript extraction methods, cookie management, and proxy infrastructure. These improvements address production issues with timeout handling, cookie authentication, and network resilience while maintaining backward compatibility with existing functionality.

## Requirements

### Requirement 1: Enhanced Playwright Storage State Management

**User Story:** As a transcript service, I want Playwright to automatically load authenticated YouTube sessions so that transcript extraction can access restricted content without manual authentication.

#### Acceptance Criteria

1. WHEN creating Playwright browser context THEN it SHALL check for ${COOKIE_DIR}/youtube_session.json storage state file
2. WHEN storage_state file exists THEN it SHALL load it with browser.new_context(storage_state=path, locale="en-US")
3. WHEN storage_state is loaded THEN document.cookie on YouTube SHALL contain CONSENT/VISITOR cookies without re-consenting
4. WHEN first navigation occurs THEN it SHALL not show GDPR consent wall for authenticated sessions
5. WHEN storage_state file is missing THEN it SHALL log clear warning with remediation instructions
6. WHEN only Netscape cookies exist THEN it SHALL run the converter (Requirement 11) before Playwright launch

### Requirement 2: Deterministic YouTubei Transcript Capture

**User Story:** As a transcript extraction system, I want deterministic network interception without timing dependencies so that transcript capture is reliable and predictable.

#### Acceptance Criteria

1. WHEN intercepting /youtubei/v1/get_transcript requests THEN it SHALL use page.route() with asyncio.Future resolution
2. WHEN route is intercepted THEN it SHALL call route.continue_() and resolve Future from response body
3. WHEN Future is resolved THEN it SHALL return transcript data without any fixed wait_for_timeout calls
4. WHEN Future times out after 20-25 seconds THEN it SHALL fall back to next transcript method
5. WHEN transcript is captured THEN it SHALL return non-empty text for videos with available transcripts

### Requirement 3: Multi-Client Profile Support

**User Story:** As a transcript service, I want to try different YouTube client profiles so that I can access transcripts that are only available to specific client types.

#### Acceptance Criteria

1. WHEN transcript extraction starts THEN it SHALL attempt desktop profile first (no-proxy → proxy)
2. WHEN desktop profile fails THEN it SHALL attempt mobile profile (no-proxy → proxy)
3. WHEN switching profiles THEN it SHALL use appropriate User-Agent and viewport settings
4. WHEN creating new contexts THEN it SHALL reuse one browser instance with clean UA per profile
5. WHEN logging attempts THEN it SHALL show attempts across profiles for debugging
6. WHEN using desktop profile THEN UA SHALL be Chrome XX on Windows 10 with viewport 1920×1080
7. WHEN using mobile profile THEN UA SHALL be Android Chrome XX with viewport 390×844

### Requirement 4: Enhanced Cookie Integration for Timed-Text

**User Story:** As a transcript service, I want timed-text extraction to prefer user-specific cookies so that restricted content can be accessed with proper authentication.

#### Acceptance Criteria

1. WHEN _fetch_timedtext_json3 is called THEN it SHALL accept cookies header string or dict parameter
2. WHEN _fetch_timedtext_xml is called THEN it SHALL accept cookies header string or dict parameter
3. WHEN user cookies are available THEN they SHALL be used over environment/file cookies
4. WHEN user cookies are not available THEN it SHALL fall back to environment/file cookies
5. WHEN member-only or region-gated content is accessed THEN user cookies SHALL be included in requests
6. WHEN making timed-text requests THEN they SHALL log cookie_source=user|env at debug level

### Requirement 5: Complete HTTP Adapter Configuration

**User Story:** As a network client, I want HTTP retry adapters for both HTTP and HTTPS so that all requests benefit from retry logic.

#### Acceptance Criteria

1. WHEN creating HTTP session THEN it SHALL mount retry adapter for https:// URLs
2. WHEN creating HTTP session THEN it SHALL mount retry adapter for http:// URLs
3. WHEN HTTP redirects occur THEN they SHALL use the same retry logic as HTTPS
4. WHEN adapter mounting completes THEN it SHALL not generate warnings about unmounted adapters
5. WHEN retries are triggered THEN they SHALL apply equally to HTTP and HTTPS requests

### Requirement 6: Playwright Circuit Breaker Integration

**User Story:** As a resilient system, I want Playwright operations to integrate with circuit breaker patterns so that repeated failures don't overwhelm the system.

#### Acceptance Criteria

1. WHEN Playwright transcript attempt starts THEN it SHALL be wrapped in 2-3 tenacity retries
2. WHEN timeout or blocked errors occur THEN they SHALL trigger tenacity retry logic
3. WHEN Playwright operations fail THEN they SHALL call record_failure on circuit breaker
4. WHEN Playwright operations succeed THEN they SHALL call record_success on circuit breaker
5. WHEN circuit breaker is open THEN Playwright stage SHALL be skipped with "open → skip" logging
6. WHEN circuit breaker observes outcomes THEN it SHALL observe the post-retry outcome of the YouTubei attempt

### Requirement 7: DOM Fallback After Network Timeout

**User Story:** As a transcript extraction system, I want DOM-based fallback when network interception fails so that blocked network calls don't prevent transcript extraction.

#### Acceptance Criteria

1. WHEN network route Future times out THEN it SHALL poll DOM selectors for transcript content
2. WHEN polling DOM THEN it SHALL check for transcript line selectors for 3-5 seconds
3. WHEN transcript text nodes are found in DOM THEN it SHALL extract and return the text
4. WHEN DOM extraction succeeds THEN it SHALL log successful DOM fallback
5. WHEN network is blocked but DOM renders THEN transcript extraction SHALL still succeed

### Requirement 8: Proxy-Enforced FFmpeg Audio Extraction

**User Story:** As an audio processing system, I want FFmpeg to use proxy connections for HTTPS requests so that audio extraction works consistently with network routing.

#### Acceptance Criteria

1. WHEN ASRAudioExtractor._extract_audio_to_wav runs THEN it SHALL compute proxy URL via proxy manager
2. WHEN proxy is available THEN it SHALL set http_proxy and https_proxy environment variables
3. WHEN FFmpeg subprocess runs THEN it SHALL inherit proxy environment variables
4. WHEN proxy is broken THEN audio extraction SHALL fail immediately with clear error
5. WHEN proxy is working THEN external IP observed by httpbin SHALL change when proxy is set

### Requirement 9: FFmpeg Header Hygiene and Placement

**User Story:** As an audio extraction system, I want proper HTTP header formatting for FFmpeg so that authentication headers work correctly without exposing sensitive data.

#### Acceptance Criteria

1. WHEN building FFmpeg headers THEN they SHALL be CRLF-joined into single string
2. WHEN adding headers to command THEN -headers parameter SHALL appear before -i parameter
3. WHEN Cookie headers are present THEN they SHALL remain masked in all log output
4. WHEN FFmpeg runs THEN it SHALL not generate "No trailing CRLF" or header parsing errors
5. WHEN logging FFmpeg commands THEN raw cookie values SHALL never appear in logs

### Requirement 10: Comprehensive Metrics and Structured Logging

**User Story:** As a system administrator, I want detailed metrics and structured logging so that I can monitor transcript pipeline performance and circuit breaker behavior.

#### Acceptance Criteria

1. WHEN circuit breaker state changes THEN it SHALL emit structured events for open/closed/half-open states
2. WHEN transcript stages complete THEN they SHALL log stage durations and success/failure
3. WHEN transcript is found THEN it SHALL log which attempt succeeded (timedtext/YouTubei/ASR)
4. WHEN Playwright operations run THEN they SHALL log breaker_state and operation timings
5. WHEN metrics are collected THEN dashboards SHALL show counts and latencies per stage
6. WHEN emitting metrics THEN it SHALL include stage_duration_ms with labels {stage, proxy_used, profile} and compute p50/p95 in dashboards

### Requirement 11: Netscape to Storage State Conversion

**User Story:** As a cookie management system, I want to convert Netscape cookie files to Playwright storage state so that users can provide cookies in either format.

#### Acceptance Criteria

1. WHEN cookie_generator.py runs with --from-netscape flag THEN it SHALL convert cookies.txt to storage_state
2. WHEN conversion runs THEN it SHALL produce ${COOKIE_DIR}/youtube_session.json with sanitized cookies
3. WHEN conversion completes THEN it SHALL create minimal origins structure for Playwright compatibility
4. WHEN converted storage_state is used THEN Playwright SHALL load it without errors
5. WHEN CLI flag is provided THEN it SHALL accept cookies.txt file path as parameter

### Requirement 12: Host Cookie Sanitation

**User Story:** As a cookie processing system, I want __Host- cookies to be properly sanitized so that Playwright accepts them without validation errors.

#### Acceptance Criteria

1. WHEN processing __Host- cookies THEN they SHALL be normalized with secure=True
2. WHEN processing __Host- cookies THEN they SHALL be normalized with path="/"
3. WHEN processing __Host- cookies THEN they SHALL have no domain field (use url field instead)
4. WHEN sanitized cookies are loaded THEN Playwright SHALL not generate __Host- cookie errors
5. WHEN cookies appear in context THEN they SHALL be properly accessible to YouTube pages

### Requirement 13: Explicit SOCS/CONSENT Cookie Injection

**User Story:** As a cookie management system, I want to ensure consent cookies are present so that YouTube pages don't show consent dialogs.

#### Acceptance Criteria

1. WHEN cookie generation/conversion completes THEN it SHALL check for SOCS or CONSENT cookies
2. WHEN neither SOCS nor CONSENT is present THEN it SHALL synthesize safe "accepted" values
3. WHEN synthesizing consent cookies THEN they SHALL be scoped to .youtube.com with long expiry
4. WHEN storage_state is created THEN it SHALL always include one of SOCS/CONSENT cookies
5. WHEN consent cookies are present THEN YouTube pages SHALL not show GDPR consent walls
6. WHEN synthesizing cookies THEN it SHALL occur in cookie_generator.py after conversion/warm-up if SOCS/CONSENT missing

### Requirement 14: Proxy Environment Builder for Subprocesses

**User Story:** As a proxy management system, I want to provide subprocess-ready environment variables so that FFmpeg and other tools can use proxy connections.

#### Acceptance Criteria

1. WHEN proxy_env_for_subprocess() is called THEN it SHALL return dict with http_proxy and https_proxy
2. WHEN proxy configuration is available THEN environment variables SHALL use existing secret/session builder
3. WHEN no proxy is configured THEN it SHALL return empty dict
4. WHEN ASRAudioExtractor needs proxy THEN it SHALL call pm.proxy_env_for_subprocess()
5. WHEN subprocess.run is called THEN proxy environment SHALL be passed directly

### Requirement 15: Unified Proxy Dictionary Interface

**User Story:** As a proxy consumer, I want a single method to get proxy configuration for different clients so that proxy setup is consistent across the application.

#### Acceptance Criteria

1. WHEN proxy_dict_for("requests") is called THEN it SHALL return {"http":..., "https":...} format
2. WHEN proxy_dict_for("playwright") is called THEN it SHALL return {"server":..., "username":..., "password":...} format
3. WHEN proxy configuration uses current ProxySecret THEN it SHALL use session token generator
4. WHEN transcript service needs proxies THEN it SHALL obtain them with one method per consumer
5. WHEN proxy format is wrong THEN it SHALL log error and return appropriate fallback

### Requirement 16: Proxy Health Metrics and Preflight Monitoring

**User Story:** As a system administrator, I want proxy health monitoring with masked credentials so that I can track proxy performance without exposing sensitive data.

#### Acceptance Criteria

1. WHEN preflight checks run THEN they SHALL log counters for hits/misses
2. WHEN logging proxy status THEN it SHALL include masked username tail for identification
3. WHEN proxy health is checked THEN it SHALL provide healthy boolean accessor
4. WHEN structured logs are emitted THEN they SHALL show proxy health without leaking secrets
5. WHEN metrics are collected THEN they SHALL show preflight rates and proxy performance

### Requirement 17: Playwright Retry with Jitter

**User Story:** As a resilient system, I want Playwright operations to retry with exponential backoff so that transient failures don't cause permanent transcript extraction failures.

#### Acceptance Criteria

1. WHEN Playwright navigation times out THEN it SHALL retry with exponential backoff + jitter
2. WHEN Playwright interception fails THEN it SHALL retry 2-3 times before giving up
3. WHEN transient timeouts occur THEN they SHALL recover on second/third try
4. WHEN sustained failures occur THEN circuit breaker SHALL activate after retries are exhausted
5. WHEN retry logic runs THEN it SHALL use tenacity or existing retry utilities
6. WHEN applying retries THEN the YouTubei attempt function (nav + route + parse) SHALL be the single tenacity-wrapped unit

## Constraints & Non-Functional Requirements

### Constraint 1: Preserved Stage Order and Early Exit

**User Story:** As a transcript pipeline, I want to maintain existing stage order while improving reliability so that the enhancement doesn't change fundamental processing flow.

#### Acceptance Criteria

1. WHEN transcript extraction runs THEN it SHALL maintain order: yt-api → timedtext → YouTubei → ASR
2. WHEN any stage succeeds THEN processing SHALL stop and return successful result
3. WHEN enhancements are applied THEN they SHALL only improve reliability within each stage
4. WHEN stage order is preserved THEN existing fallback logic SHALL continue working
5. WHEN early exit occurs THEN subsequent stages SHALL not be attempted

### Constraint 2: Backward Compatibility Maintenance

**User Story:** As an existing system, I want all enhancements to maintain backward compatibility so that existing functionality continues working without modification.

#### Acceptance Criteria

1. WHEN enhancements are deployed THEN existing API interfaces SHALL remain unchanged
2. WHEN new parameters are added THEN they SHALL be optional with sensible defaults
3. WHEN new functionality is used THEN it SHALL not break existing transcript extraction
4. WHEN configuration is missing THEN system SHALL fall back to previous behavior
5. WHEN testing existing flows THEN they SHALL continue working as before

### Constraint 3: Development and Production Environment Support

**User Story:** As a developer and system administrator, I want enhancements to work in both development and production environments so that testing and deployment are consistent.

#### Acceptance Criteria

1. WHEN running locally THEN developers SHALL be able to set COOKIE_DIR to preferred location
2. WHEN running in production THEN COOKIE_DIR SHALL default to /app/cookies
3. WHEN Playwright dependencies are missing THEN it SHALL provide clear installation instructions
4. WHEN proxy configuration differs between environments THEN it SHALL adapt appropriately
5. WHEN debugging issues THEN logs SHALL provide environment-appropriate guidance