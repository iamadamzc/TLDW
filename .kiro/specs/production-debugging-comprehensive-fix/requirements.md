# Requirements Document

## Introduction

This feature addresses critical production issues in the TL;DW backend that are causing complete system failures. The system is experiencing ProxyManager crashes due to missing AWS Secrets Manager fields, yt-dlp extraction failures due to outdated versions and missing player clients, and deployment issues that prevent proper service restarts. This comprehensive fix ensures the service can reliably download YouTube audio, handle proxy authentication, and maintain system health.

## Requirements

### Requirement 1

**User Story:** As a system administrator, I want the ProxyManager to handle missing or malformed AWS Secrets Manager configurations gracefully so that the service doesn't crash on startup.

#### Acceptance Criteria

1. WHEN AWS Secrets Manager secret is missing the "provider" field THEN ProxyManager SHALL log the error and continue with in_use=False instead of crashing
2. WHEN the proxy secret JSON is malformed THEN the system SHALL gracefully degrade to no-proxy mode with appropriate logging
3. WHEN ProxyManager initializes successfully THEN it SHALL validate the secret contains all required fields: provider, host, port, username, password, protocol
4. WHEN proxy configuration is invalid THEN the system SHALL expose proxy_in_use=false in health endpoints
5. WHEN the service starts with invalid proxy config THEN it SHALL not prevent the application from serving requests

### Requirement 2

**User Story:** As a system that needs reliable YouTube extraction, I want yt-dlp to use the latest version with multiple player clients so that "Failed to extract any player response" errors are eliminated.

#### Acceptance Criteria

1. WHEN the Docker container builds THEN it SHALL install the latest yt-dlp version or a pinned version controlled by YTDLP_VERSION build arg
2. WHEN yt-dlp is configured THEN it SHALL use extractor_args with multiple player clients: ["android", "web", "web_safari"] for maximum compatibility
3. WHEN the container builds THEN it SHALL log the installed yt-dlp version for debugging and health checks
4. WHEN yt-dlp attempts extraction THEN it SHALL try multiple player clients to avoid JSONDecodeError failures
5. WHEN the system starts THEN it SHALL expose the yt-dlp version in health endpoints for monitoring

### Requirement 3

**User Story:** As a developer debugging extraction failures, I want comprehensive error handling and logging so that I can identify root causes of download failures quickly.

#### Acceptance Criteria

1. WHEN yt-dlp raises a DownloadError THEN the system SHALL preserve and propagate the original error message
2. WHEN both step1 and step2 fail THEN the system SHALL combine error messages with " || " separator for complete debugging information
3. WHEN bot detection patterns are found in error messages THEN the _detect_bot_check function SHALL properly identify them
4. WHEN logging yt-dlp errors THEN the system SHALL include sufficient detail for troubleshooting without exposing sensitive information
5. WHEN proxy authentication fails THEN the system SHALL log 407 errors and rotate proxies immediately

### Requirement 4

**User Story:** As a system administrator, I want enhanced health endpoints that provide comprehensive diagnostic information so that I can monitor system status effectively.

#### Acceptance Criteria

1. WHEN /healthz is called THEN it SHALL expose yt_dlp_version, ffmpeg_location, proxy_in_use boolean, and last_download_used_cookies
2. WHEN /health/yt-dlp endpoint is accessed THEN it SHALL return version and proxy status information
3. WHEN cookie files are used THEN the system SHALL log cookie freshness (mtime + account) at download start
4. WHEN health diagnostics are exposed THEN they SHALL not leak sensitive information like cookie contents or proxy credentials
5. WHEN the system tracks download attempts THEN it SHALL maintain metadata about last successful download without PII

### Requirement 5

**User Story:** As a system that relies on AWS App Runner deployments, I want deployment scripts that force proper service restarts so that code changes are actually deployed.

#### Acceptance Criteria

1. WHEN deploy-apprunner.sh runs THEN it SHALL either push unique git SHA tags or call aws apprunner start-deployment to force restart
2. WHEN App Runner deployment completes THEN the new code SHALL be running, not cached previous versions
3. WHEN deployment scripts execute THEN they SHALL validate that the service restarted with new code
4. WHEN deployment fails THEN the scripts SHALL provide clear error messages and rollback instructions
5. WHEN environment variables change THEN the deployment SHALL ensure App Runner picks up the new configuration

### Requirement 6

**User Story:** As a developer maintaining code quality, I want to eliminate code duplications and standardize environment variable naming so that the codebase is maintainable.

#### Acceptance Criteria

1. WHEN TranscriptService initializes THEN it SHALL not duplicate ProxyManager, ProxyHTTPClient, and UserAgentManager initialization
2. WHEN Google OAuth is configured THEN environment variable names SHALL be consistent between GOOGLE_CLIENT_* and GOOGLE_OAUTH_CLIENT_*
3. WHEN deployment scripts run THEN they SHALL use the same environment variable names as the application code
4. WHEN google_auth.py executes THEN it SHALL match the environment variable names used in deployment configuration
5. WHEN OAuth integration is tested THEN it SHALL work with consistent environment variable naming

### Requirement 7

**User Story:** As a system that needs reliable CI/CD, I want comprehensive smoke tests that validate the complete pipeline so that regressions are caught before production deployment.

#### Acceptance Criteria

1. WHEN CI runs THEN it SHALL execute end-to-end smoke tests for both transcript and ASR paths using known public videos
2. WHEN smoke tests run THEN they SHALL test both step1 (m4a) and step2 (mp3) download scenarios
3. WHEN tests execute THEN they SHALL include scenarios with cookies and without cookies for realistic conditions
4. WHEN Deepgram integration is tested THEN responses SHALL be mocked to test complete pipeline without external API calls
5. WHEN smoke tests fail THEN CI SHALL fail the build to prevent regression deployment

### Requirement 8

**User Story:** As a system that processes audio files, I want correct Content-Type headers for Deepgram uploads so that ASR processing works reliably.

#### Acceptance Criteria

1. WHEN audio files are sent to Deepgram THEN the system SHALL use explicit MIME type mapping for common formats
2. WHEN .m4a or .mp4 files are uploaded THEN Content-Type SHALL be "audio/mp4"
3. WHEN .mp3 files are uploaded THEN Content-Type SHALL be "audio/mpeg"
4. WHEN unknown file extensions are encountered THEN the system SHALL fallback to "application/octet-stream"
5. WHEN Content-Type headers are set THEN they SHALL improve Deepgram processing success rates

### Requirement 9

**User Story:** As a system that relies on backwards compatibility, I want all existing functionality to continue working unchanged while critical bugs are fixed.

#### Acceptance Criteria

1. WHEN the fixes are deployed THEN all existing API endpoints SHALL return the same response structure
2. WHEN no cookiefile is provided THEN download_audio_with_fallback SHALL behave identically to the previous version
3. WHEN the transcript service is called THEN it SHALL maintain the same public interface signatures
4. WHEN logging occurs THEN the system SHALL maintain existing structured log formats
5. WHEN proxy configuration is missing THEN the system SHALL gracefully degrade without breaking existing functionality