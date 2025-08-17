# Requirements Document

## Introduction

This feature hardens the YouTube download pipeline against extraction failures by removing GEO variability, implementing mandatory A/B testing with/without cookies, expanding failure detection patterns, and improving diagnostic logging. The system builds upon existing proxy authentication fixes and cookie frameworks to provide more resilient video extraction while maintaining clear audit trails for debugging.

## Requirements

### Requirement 1

**User Story:** As a system administrator, I want GEO variability removed at runtime so that region-specific extractor pitfalls are avoided and proxy behavior is consistent.

#### Acceptance Criteria

1. WHEN the system starts THEN it SHALL set OXY_DISABLE_GEO=true environment variable to disable geo-targeting
2. WHEN the system starts THEN PROXY_COUNTRY environment variable SHALL be unset in the service configuration to prevent country-specific proxy segments
3. WHEN proxy usernames are generated THEN they SHALL NOT contain -cc-<country> segments
4. WHEN health checks run THEN they SHALL log whether -cc- segments are present in proxy usernames
5. WHEN INFO logs are generated during yt-dlp calls THEN they SHALL show proxy_username=customer-<user>-sessid-... format without country codes
6. WHEN OXY_DISABLE_GEO=true is set THEN it SHALL take precedence over any PROXY_COUNTRY configuration to avoid confusion

### Requirement 2

**User Story:** As a system handling extraction failures, I want mandatory A/B testing with/without cookies so that cookie-related issues are isolated from extractor problems regardless of cookie freshness.

#### Acceptance Criteria

1. WHEN attempt 1 fails with any extraction failure THEN the system SHALL **always perform attempt 2 with use_cookies=false even if cookies are fresh**
2. WHEN _detect_extraction_failure returns true THEN the system SHALL **force attempt 2 without cookies regardless of cookie freshness status**
3. WHEN attempt 2 runs due to extraction failure THEN it SHALL log retry_reason=extraction_failure
4. WHEN cookies are provided but stale (>12h) THEN attempt 1 SHALL log reason=stale_cookiefile and use_cookies=false
5. WHEN transitioning from attempt 1 to attempt 2 THEN the system SHALL introduce a 1-2 second sleep to reduce transient throttling
6. WHEN both attempts fail THEN the system SHALL raise RuntimeError that includes the string "consider updating yt-dlp" for operational alerting

### Requirement 3

**User Story:** As a developer debugging modern YouTube extraction issues, I want expanded failure detection patterns so that newer error messages are properly caught and handled.

#### Acceptance Criteria

1. WHEN _detect_extraction_failure analyzes error text THEN it SHALL check for "unable to extract yt initial data" (case-insensitive)
2. WHEN _detect_extraction_failure analyzes error text THEN it SHALL check for "failed to parse json" (case-insensitive)
3. WHEN _detect_extraction_failure analyzes error text THEN it SHALL check for "unable to extract player version" (case-insensitive)
4. WHEN _detect_extraction_failure analyzes error text THEN it SHALL check for "failed to extract any player response" (case-insensitive)
5. WHEN _detect_extraction_failure analyzes error text THEN it SHALL maintain existing patterns: "unable to extract player response", "video data", "extraction failed", "video unavailable"

### Requirement 4

**User Story:** As a system operator debugging extraction issues, I want unambiguous logs about which attempt path ran and why so that I can quickly identify the root cause of failures.

#### Acceptance Criteria

1. WHEN attempt 1 starts THEN it SHALL log yt_dlp_attempt=1 use_cookies=<bool>
2. WHEN attempt 2 starts THEN it SHALL log yt_dlp_attempt=2 use_cookies=false retry_reason=<reason>
3. WHEN cookies are invalid THEN attempt 2 SHALL log retry_reason=cookie_invalid
4. WHEN extraction fails THEN attempt 2 SHALL log retry_reason=extraction_failure
5. WHEN cookies are stale THEN attempt 1 SHALL log reason=stale_cookiefile
6. WHEN YoutubeDL is constructed THEN it SHALL log yt_dlp.proxy.in_use=true proxy_username=<masked_username>
7. WHEN proxy username is logged THEN it SHALL use _extract_proxy_username to avoid exposing secrets
8. WHEN logging structured data THEN log fields MUST use exactly these keys with lowercase values: yt_dlp_attempt, use_cookies, reason (attempt 1), retry_reason (attempt 2)
9. WHEN cookies are present AND GEO is disabled THEN the system SHALL log a WARN about potential region mismatch between cookie origin and proxy location

### Requirement 5

**User Story:** As a system administrator, I want runtime toggle capabilities so that I can validate the no-cookie path end-to-end without code changes.

#### Acceptance Criteria

1. WHEN DISABLE_COOKIES=true environment variable is set THEN the system SHALL skip cookie usage entirely
2. WHEN DISABLE_COOKIES=true is active THEN all attempts SHALL use use_cookies=false
3. WHEN DISABLE_COOKIES=true is used THEN it SHALL log cookies disabled via environment flag
4. WHEN canary testing with DISABLE_COOKIES=true THEN at least one public video SHALL download successfully
5. WHEN canary validation completes THEN DISABLE_COOKIES SHALL be reverted to allow normal cookie usage

### Requirement 6

**User Story:** As a transcript service consumer, I want the call site to maintain proper error handling so that retries happen inside the helper and structured logging shows attempt status.

#### Acceptance Criteria

1. WHEN transcript_service calls download_audio_with_retry THEN it SHALL pass user_id parameter
2. WHEN top-level error handling occurs THEN it SHALL NOT short-circuit internal retry logic
3. WHEN retries complete THEN structured log lines SHALL show attempt number and final status
4. WHEN download_audio_with_retry is called THEN all retry logic SHALL happen within the helper function
5. WHEN final status is logged THEN it SHALL indicate success/failure and which attempt succeeded

### Requirement 7

**User Story:** As a system administrator, I want startup visibility into yt-dlp version information so that I can correlate extractor breakages to specific versions in logs.

#### Acceptance Criteria

1. WHEN the application starts THEN it SHALL log structured JSON with yt-dlp version information
2. WHEN version logging occurs THEN it SHALL be in structured format for easy parsing
3. WHEN extractor issues arise THEN version information SHALL be available in startup logs for correlation
4. WHEN debugging extraction failures THEN yt-dlp version SHALL be easily identifiable from application logs
5. WHEN version information is logged THEN it SHALL not expose sensitive configuration details

### Requirement 8

**User Story:** As a system that needs to maintain backwards compatibility, I want all existing functionality to continue working unchanged while hardening is applied.

#### Acceptance Criteria

1. WHEN hardening features are deployed THEN all existing API endpoints SHALL return the same response structure
2. WHEN no cookies are provided THEN the system SHALL behave identically to previous versions
3. WHEN existing retry logic is enhanced THEN it SHALL maintain the same public interface signatures
4. WHEN logging is improved THEN it SHALL preserve existing structured log formats while adding new fields
5. WHEN error handling is enhanced THEN it SHALL maintain existing error propagation patterns

### Requirement 9

**User Story:** As a security-conscious administrator, I want proxy credentials and sensitive information properly masked in logs so that security is maintained while debugging capability is preserved.

#### Acceptance Criteria

1. WHEN proxy usernames are logged THEN they SHALL be masked using _extract_proxy_username function
2. WHEN sensitive proxy information is logged THEN only non-sensitive portions SHALL be visible
3. WHEN debugging information is logged THEN it SHALL provide sufficient detail without exposing credentials
4. WHEN structured logs are generated THEN they SHALL not contain raw proxy passwords or authentication tokens
5. WHEN log analysis occurs THEN masked information SHALL still be sufficient for troubleshooting proxy issues

### Requirement 10

**User Story:** As a system operator monitoring extraction reliability, I want circuit breaker protection and metrics so that repeated failures are handled gracefully and system health is visible.

#### Acceptance Criteria

1. WHEN N consecutive failures occur for the same video/user within M minutes THEN the system SHALL stop retrying and surface a clean error
2. WHEN circuit breaker triggers THEN it SHALL log circuit_breaker=open with video_id and user_id for debugging
3. WHEN extraction attempts occur THEN the system SHALL emit structured INFO logs with counters for: attempts_with_cookies, attempts_without_cookies, extraction_failures, cookie_invalid, successes
4. WHEN metrics are logged THEN they SHALL be in structured format for easy aggregation and monitoring
5. WHEN circuit breaker state changes THEN it SHALL be logged with timestamp and trigger conditions

### Requirement 11

**User Story:** As a developer ensuring system reliability, I want comprehensive test coverage so that hardening changes are validated and regressions are prevented.

#### Acceptance Criteria

1. WHEN _detect_extraction_failure is tested THEN unit tests SHALL verify all new error patterns: "unable to extract yt initial data", "failed to parse json", "unable to extract player version", "failed to extract any player response"
2. WHEN stale cookie logic is tested THEN unit tests SHALL verify reason=stale_cookiefile is emitted for cookies older than 12 hours
3. WHEN extraction failure retry is tested THEN integration tests SHALL verify attempt 1 failure with "failed to parse json" triggers attempt 2 with use_cookies=false
4. WHEN canary testing occurs THEN the system SHALL successfully download one public video with DISABLE_COOKIES=true AND OXY_DISABLE_GEO=true
5. WHEN test suite runs THEN it SHALL include end-to-end validation of the complete A/B testing flow with proper logging