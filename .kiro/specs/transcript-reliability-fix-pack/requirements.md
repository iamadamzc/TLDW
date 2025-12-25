# Requirements Document

## Introduction

This feature addresses critical reliability issues in the YouTube transcript extraction pipeline that are causing silent failures, timeout overruns, and inefficient processing. The fixes target three core services: youtubei_service.py (Playwright-based extraction), ffmpeg_service.py (audio processing), and transcript_service.py (orchestration layer). These improvements will significantly enhance transcript success rates, reduce processing time, and eliminate silent failure modes that currently mask extraction problems.

## Requirements

### Requirement 1: Fix YouTubei Service Silent Failures and Performance

**User Story:** As a system administrator, I want the YouTubei transcript extraction to work reliably without silent failures, so that transcript processing succeeds consistently and problems are properly logged.

#### Acceptance Criteria

1. WHEN the system needs to wait for elements THEN `locator.is_visible()` SHALL NOT be used for waiting and `locator.wait_for(state="visible", timeout=...)` SHALL be used prior to click operations
2. WHEN a YouTube video page loads THEN the system SHALL attempt to extract captions directly from `ytInitialPlayerResponse.captions.playerCaptionsTracklistRenderer.captionTracks` before any DOM interaction
3. WHEN caption tracks are found in the initial player response THEN the system SHALL fetch the transcript XML via HTTP requests, log `youtubei_captiontracks_shortcircuit` with language and ASR flags, and return immediately without DOM manipulation
4. WHEN DOM interaction is required THEN the system SHALL use the title-row menu selector `ytd-menu-renderer #button-shape button[aria-label*='More actions']` and confirm dropdown `[opened]` state before clicking 'Show transcript'
5. WHEN the direct POST fallback is triggered THEN the system SHALL extract real `INNERTUBE_API_KEY`, `INNERTUBE_CONTEXT`, and transcript params from the page, and the params value SHALL be sourced from either (a) a captured `/youtubei/v1/get_transcript` request body or (b) `ytInitialData` JSON on the page
6. WHEN making HTTP requests for transcript data THEN the system SHALL respect the `ENFORCE_PROXY_ALL` environment variable and use job-specific proxy configuration

### Requirement 2: Enforce Proxy Compliance in FFmpeg Service

**User Story:** As a security-conscious operator, I want all network requests to respect proxy enforcement settings, so that no traffic bypasses the configured proxy when `ENFORCE_PROXY_ALL=1`.

#### Acceptance Criteria

1. WHEN `ENFORCE_PROXY_ALL=1` AND no proxy is available THEN the requests fallback SHALL NOT execute and SHALL log `requests_fallback_blocked`
2. WHEN the requests streaming fallback is triggered THEN the system SHALL verify proxy availability before proceeding
3. WHEN FFmpeg processing exceeds the configured timeout THEN the system SHALL timeout and terminate the process to prevent watchdog overruns
4. WHEN FFmpeg timeout is configured THEN it SHALL be set by a single constant of 60 seconds to prevent drift back to longer timeouts
5. WHEN proxy configuration is required THEN the system SHALL use the same proxy dict generation logic as other services

### Requirement 3: Improve Transcript Service Resilience and Content Validation

**User Story:** As a transcript processing system, I want to validate response content before parsing and implement fast-fail mechanisms, so that processing time is minimized and errors are caught early.

#### Acceptance Criteria

1. WHEN receiving any transcript XML (timedtext and captionTracks baseUrl) THEN all fetches SHALL pass the same XML/HTML/empty-body validation before parsing with `ET.fromstring()`
2. WHEN timedtext returns HTML, consent pages, or captcha responses THEN the system SHALL detect these conditions and retry once with proper cookies
3. WHEN content validation fails THEN the system SHALL log specific error types (`timedtext_empty_body`, `timedtext_html_or_block`, `timedtext_not_xml`) and move to the next extraction method
4. WHEN `page.goto` or route wait exceeds the configured YouTubei hard timeout THEN the system SHALL immediately skip YouTubei retries and start ASR processing
5. WHEN ASR processing begins THEN the system SHALL start video playback immediately to trigger HLS/MPD manifest requests
6. WHEN playback is initiated for ASR capture THEN the system SHALL log `asr_playback_initiated` before listening for `.m3u8` and use keyboard shortcuts (`k` key) and video element clicks to ensure audio streams become available

### Requirement 4: Enhanced Logging and Monitoring

**User Story:** As a system operator, I want detailed logging of transcript extraction paths and failures, so that I can monitor system health and troubleshoot issues effectively.

#### Acceptance Criteria

1. Events in this requirement are normative side-effects of Requirements 1.3 (captionTracks), 2.1 (proxy block), 3.1-3.3 (content validation), and 3.6 (ASR trigger) respectively
2. WHEN proxy enforcement blocks a request THEN the system SHALL log the specific reason and service affected
3. WHEN content validation fails THEN the system SHALL log the specific validation failure type and response characteristics
4. WHEN timeouts occur THEN the system SHALL log timeout events with context about which service and operation failed
5. WHEN ASR processing is triggered THEN the system SHALL log the transition and playback initiation attempts

### Requirement 5: Backward Compatibility and Graceful Degradation

**User Story:** As an existing user of the transcript service, I want the reliability fixes to maintain existing functionality while improving success rates, so that current workflows continue to work.

#### Acceptance Criteria

1. WHEN new extraction methods fail THEN the system SHALL fall back to existing extraction paths, but fallback SHALL NOT re-enter the same failed path once within the same job execution (no loops)
2. WHEN proxy configuration is unavailable THEN the system SHALL continue with direct connections, but Requirement 2 overrides this: if `ENFORCE_PROXY_ALL=1`, no direct connections are permitted
3. WHEN DOM selectors change THEN the system SHALL log selector failures and attempt alternative approaches
4. WHEN API responses change format THEN the system SHALL handle parsing errors gracefully and move to fallback methods
5. WHEN environment variables are not set THEN the system SHALL use sensible defaults that maintain current behavior