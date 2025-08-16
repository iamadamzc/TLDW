# Requirements Document

## Introduction

This feature addresses critical bugs in the TL;DW backend that are causing transcript API failures and yt-dlp download failures in production. The system needs immediate fixes for YouTube Transcript API version compatibility, yt-dlp cookie passing, client selection stability, and proxy error handling to restore full functionality.

## Requirements

### Requirement 1

**User Story:** As a system administrator, I want the YouTube Transcript API to work reliably so that transcript fetching doesn't fail due to version incompatibility.

#### Acceptance Criteria

1. WHEN the system calls YouTubeTranscriptApi.get_transcript THEN it SHALL use the correct API signature for the installed version
2. WHEN requirements.txt is updated THEN it SHALL pin youtube-transcript-api to version 0.6.2 for stability
3. WHEN requirements.txt is updated THEN it SHALL pin yt-dlp to a specific version verified in CI
4. WHEN the transcript API is called THEN it SHALL not raise AttributeError about missing get_transcript method
5. WHEN the system starts THEN it SHALL successfully import and initialize YouTubeTranscriptApi without version conflicts

### Requirement 2

**User Story:** As a user with uploaded cookies, I want yt-dlp to actually use my cookies so that video downloads succeed instead of failing with extraction errors.

#### Acceptance Criteria

1. WHEN cookiefile parameter is passed to download_audio_with_fallback THEN it SHALL be included in both ydl_opts_step1 and ydl_opts_step2 configurations
2. WHEN a cookie file exists for the current user THEN the system SHALL pass cookiefile=<path> to both yt-dlp steps
3. WHEN cookies are absent THEN the system SHALL proceed without cookies and log cookies=false in structured logs
4. WHEN cookies are available THEN yt-dlp SHALL use them for authentication during player response extraction
5. WHEN yt-dlp runs with cookies THEN it SHALL not fail with "Failed to extract any player response" errors
6. WHEN yt-dlp runs with cookies THEN it SHALL not return "Only images available" errors due to authentication failure

### Requirement 3

**User Story:** As a system that needs stable video extraction, I want yt-dlp to use consistent client selection so that downloads don't fail due to unstable client switching.

#### Acceptance Criteria

1. WHEN yt-dlp is configured THEN it SHALL use extractor_args with {"youtube": {"player_client": ["web"]}} for stable web client preference
2. WHEN yt-dlp attempts extraction THEN it SHALL prioritize the web client which works best with cookies
3. WHEN yt-dlp is configured THEN it SHALL maintain the existing format fallback strategy of bestaudio[ext=m4a]/bestaudio/best
4. WHEN client selection is applied THEN it SHALL be identical in step1 and step2 including extractor_args configuration for re-encode fallback

### Requirement 4

**User Story:** As a system handling proxy authentication errors, I want 407 errors to be handled efficiently so that proxy rotation happens quickly without wasting time on failed credentials.

#### Acceptance Criteria

1. WHEN a 407 Proxy Authentication Required error occurs THEN the system SHALL fail-fast and rotate to a different proxy
2. WHEN two consecutive 407 errors occur THEN the system SHALL optionally allow a guarded no-proxy retry
3. WHEN the no-proxy fallback on repeated 407s is used THEN it SHALL be controlled by ALLOW_NO_PROXY_ON_407 environment variable and default to disabled
4. WHEN 407 errors are detected in _fetch_transcript_with_session THEN the system SHALL rotate proxy and mark session as failed
5. WHEN 407 errors are detected in _attempt_ytdlp_download THEN the system SHALL rotate proxy and retry once before final failure

### Requirement 5

**User Story:** As a developer debugging extraction failures, I want to see the actual yt-dlp error messages so that I can identify the root cause of download failures.

#### Acceptance Criteria

1. WHEN yt-dlp raises a DownloadError THEN the system SHALL preserve and propagate the original error message
2. WHEN both step1 and step2 fail THEN the system SHALL combine error messages with " || " separator for complete debugging information
3. WHEN the helper function fails THEN it SHALL return a normalized error string combining step1/step2 failures for structured logs
4. WHEN bot detection patterns are found in error messages THEN the _detect_bot_check function SHALL properly identify them
5. WHEN logging yt-dlp errors THEN the system SHALL include sufficient detail for troubleshooting without exposing sensitive information

### Requirement 6

**User Story:** As a system that relies on backwards compatibility, I want all existing functionality to continue working unchanged while the bugs are fixed.

#### Acceptance Criteria

1. WHEN the fixes are deployed THEN all existing API endpoints SHALL return the same response structure
2. WHEN no cookiefile is provided THEN download_audio_with_fallback SHALL behave identically to the previous version
3. WHEN the transcript service is called THEN it SHALL maintain the same public interface signatures
4. WHEN logging occurs THEN the system SHALL maintain existing structured log formats
5. WHEN the downloaded file is m4a THEN the Deepgram request SHALL use the correct content-type audio/mp4 or transcode to mp3 before upload

### Requirement 7

**User Story:** As a system administrator, I want health endpoints and CI validation to ensure the fixes work correctly and catch regressions early.

#### Acceptance Criteria

1. WHEN /healthz is called THEN it SHALL expose yt_dlp_version, ffmpeg_location, and a boolean indicating whether cookies were used in the last yt-dlp attempt
2. WHEN CI runs THEN it SHALL execute an end-to-end smoke test covering both transcript and ASR paths against a known public video
3. WHEN the CI smoke test fails THEN it SHALL fail the build to prevent regression deployment
4. WHEN health diagnostics are exposed THEN they SHALL not leak sensitive information like cookie contents or proxy credentials