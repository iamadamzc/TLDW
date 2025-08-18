# Requirements Document

## Introduction

This feature addresses recurring 407 Proxy Authentication errors by implementing a strict Oxylabs secret contract, runtime validation, and proxy preflight checks. The solution enforces fail-fast behavior when proxy authentication is unhealthy and prevents reuse of failed sessions to eliminate the "whack-a-mole" 407 errors.

## Requirements

### Requirement 1

**User Story:** As a system administrator, I want a strict proxy secret contract enforced at runtime, so that malformed or pre-encoded secrets are rejected before causing 407 authentication errors.

#### Acceptance Criteria

1. WHEN the proxy secret is loaded THEN the system SHALL validate it contains RAW credentials (not URL-encoded)
2. WHEN the secret password contains '%' characters THEN the system SHALL reject it as likely pre-encoded
3. WHEN the secret host contains 'http://' or 'https://' THEN the system SHALL reject it as malformed
4. WHEN required fields (provider, host, port, username, password) are missing THEN the system SHALL fail with clear error messages
5. WHEN the secret validation fails THEN the system SHALL provide actionable error messages for fixing the secret

### Requirement 2

**User Story:** As a developer, I want proxy preflight validation before any transcript/yt-dlp operations, so that the system fails fast when proxy authentication is unhealthy.

#### Acceptance Criteria

1. WHEN starting any transcript or yt-dlp operation THEN the system SHALL perform a proxy preflight check
2. WHEN the preflight check fails with 401/407 THEN the system SHALL return 502 with PROXY_AUTH_FAILED error code
3. WHEN the preflight succeeds with 204 status THEN the system SHALL proceed with the operation
4. WHEN preflight is disabled via OXY_PREFLIGHT_DISABLED THEN the system SHALL skip validation and proceed
5. WHEN preflight fails due to connectivity THEN the system SHALL return 503 with PROXY_UNREACHABLE error code
6. WHEN proxy is misconfigured THEN the system SHALL return 502 with PROXY_MISCONFIGURED error code
7. WHEN returning errors THEN response SHALL include JSON with code, message, and correlation_id

### Requirement 3

**User Story:** As a system operator, I want unique sticky sessions per video that are never reused after authentication failures, so that failed sessions don't cause recurring 407 errors.

#### Acceptance Criteria

1. WHEN processing a video THEN the system SHALL generate a unique session token with video ID and timestamp
2. WHEN a session encounters 401/407/429/403 errors THEN the system SHALL never reuse that session token
3. WHEN retrying after auth failure THEN the system SHALL generate a new session token
4. WHEN building proxy URLs THEN the system SHALL append -sessid-<token> to the base username
5. WHEN normalizing usernames THEN the system SHALL strip existing -sessid- suffixes to avoid duplication
6. WHEN rotating sessions THEN the system SHALL cap attempts (default 2) with exponential backoff
7. WHEN session rotation occurs THEN it SHALL apply across all workers and processes

### Requirement 4

**User Story:** As a security-conscious developer, I want all proxy operations to use properly encoded credentials without exposing sensitive data in logs, so that authentication is secure and debuggable.

#### Acceptance Criteria

1. WHEN building proxy URLs THEN the system SHALL URL-encode passwords only at runtime
2. WHEN logging proxy operations THEN the system SHALL never log sensitive credential values
3. WHEN reporting proxy health THEN the system SHALL only log boolean status and masked information
4. WHEN handling proxy errors THEN the system SHALL log structured error information without credentials
5. WHEN storing secrets THEN the system SHALL use RAW format in AWS Secrets Manager
6. WHEN structured logging is used THEN it SHALL ignore unknown fields and SHALL NOT raise exceptions
7. WHEN logging events THEN standard keys SHALL include component, step, status, attempt, video_id, and reason

### Requirement 5

**User Story:** As a system administrator, I want a proxy health endpoint for monitoring, so that I can verify proxy authentication status without exposing credentials.

#### Acceptance Criteria

1. WHEN accessing /health/ready THEN the system SHALL return cached proxy health status
2. WHEN proxy preflight succeeds THEN the endpoint SHALL return 200 with proxy_healthy: true
3. WHEN proxy preflight fails THEN the endpoint SHALL return 503 with proxy_healthy: false and reason
4. WHEN proxy is misconfigured THEN the endpoint SHALL return clear error messages for troubleshooting
5. WHEN App Runner health checks run THEN they SHALL use /health/ready endpoint
6. WHEN preflight results are cached THEN TTL SHALL be 300s with ±10% jitter
7. WHEN TTL expires THEN background refresh MAY be triggered
8. WHEN accessing /health/live THEN the system SHALL always return 200 if process is running

### Requirement 6

**User Story:** As a developer, I want transcript and yt-dlp services to integrate seamlessly with the new proxy validation, so that all video processing operations benefit from reliable proxy authentication.

#### Acceptance Criteria

1. WHEN transcript service starts processing THEN it SHALL validate proxy health before proceeding
2. WHEN proxy validation fails THEN transcript service SHALL return 502 with clear error message
3. WHEN yt-dlp operations begin THEN they SHALL use validated proxy configuration with unique sessions
4. WHEN any operation encounters 401/407 THEN it SHALL not retry with the same session
5. WHEN proxy is healthy THEN all video processing operations SHALL proceed normally
6. WHEN cookiefile is invalid/empty THEN the system SHALL skip it and log cookies_invalid status
7. WHEN processing videos THEN fallback order SHALL be: Transcript API → ASR via yt-dlp (cookies) → ASR via yt-dlp (no cookies)
8. WHEN proxy is unhealthy THEN the system SHALL abort earlier without attempting fallback operations

### Requirement 7

**User Story:** As a deployment engineer, I want the secret format documented and validated, so that I can ensure proper secret configuration in AWS Secrets Manager.

#### Acceptance Criteria

1. WHEN configuring secrets THEN the documentation SHALL specify the exact RAW JSON schema required
2. WHEN secrets are malformed THEN the system SHALL provide examples of correct format
3. WHEN deploying THEN the system SHALL validate secret format before proceeding
4. WHEN secret validation fails THEN clear instructions SHALL be provided for fixing the secret
5. WHEN secrets are updated THEN the system SHALL verify the new format meets requirements
6. WHEN configuring environment THEN flags SHALL be documented: OXY_PREFLIGHT_DISABLED, OXY_PREFLIGHT_TTL_SECONDS, OXY_DISABLE_GEO, OXY_SECRETS_MANAGER_NAME, OXY_PROVIDER
7. WHEN using secrets THEN no hardcoded secret names SHALL be used in code
###
 Requirement 8

**User Story:** As a system administrator, I want automatic secret refresh and proper precedence handling, so that the system can adapt to credential rotations without downtime.

#### Acceptance Criteria

1. WHEN secrets are refreshed THEN the system SHALL support on-demand and periodic refresh (default 10m)
2. WHEN loading secrets THEN precedence SHALL be: RuntimeEnvironmentSecrets JSON → AWS Secrets Manager → env vars (local dev)
3. WHEN a refreshed secret fails validation THEN the system SHALL keep the last known-good secret
4. WHEN using invalid refreshed secret THEN the system SHALL surface PROXY_MISCONFIGURED error
5. WHEN secret refresh occurs THEN it SHALL not interrupt ongoing operations

### Requirement 9

**User Story:** As a system operator, I want comprehensive metrics and observability, so that I can monitor proxy health and meet reliability SLOs.

#### Acceptance Criteria

1. WHEN proxy operations occur THEN the system SHALL emit counters: proxy_preflight_ok, proxy_preflight_407, proxy_preflight_other, ytdlp_407, transcript_success, asr_fallback
2. WHEN measuring reliability THEN SLO SHALL be: proxy_preflight_ok_rate ≥ 99% over 15m
3. WHEN monitoring health THEN metrics SHALL be available for alerting and dashboards
4. WHEN operations complete THEN success/failure rates SHALL be tracked per operation type
5. WHEN errors occur THEN error types SHALL be categorized and counted separately

## Verification Requirements

### Unit Testing
1. WHEN testing validator THEN it SHALL verify rejection of host with scheme, password with %, and missing required fields
2. WHEN testing session rotation THEN it SHALL verify unique tokens and no reuse after failures
3. WHEN testing structured logging THEN it SHALL verify acceptance of unknown fields without exceptions

### Integration Testing
1. WHEN testing with mock proxy THEN it SHALL verify 407 response handling and fail-fast behavior
2. WHEN testing preflight THEN it SHALL verify caching behavior and TTL expiration
3. WHEN testing secret refresh THEN it SHALL verify precedence and fallback to known-good secrets

### Smoke Testing
1. WHEN proxy preflight fails THEN it SHALL prove no transcript/yt-dlp attempts are made
2. WHEN end-to-end flow runs THEN it SHALL verify complete proxy authentication and video processing
3. WHEN health endpoints are accessed THEN they SHALL return expected status codes and response formats