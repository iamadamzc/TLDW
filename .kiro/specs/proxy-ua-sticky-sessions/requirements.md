# Requirements Document

## Introduction

This feature implements reliable proxy and user agent handling for transcript fetching and yt-dlp operations using sticky sessions. The system will use residential proxies from Oxylabs with consistent session management per video, ensuring reliable access to YouTube content while avoiding bot detection and rate limiting.

## Requirements

### Requirement 1

**User Story:** As a system administrator, I want sticky proxy sessions per video so that transcript fetching and audio downloading use the same proxy session for consistency and reliability.

#### Acceptance Criteria

1. WHEN a video requires processing THEN the system SHALL generate a unique session ID derived from the video_id
2. WHEN generating a session ID THEN the system SHALL sanitize the video_id to contain only alphanumeric characters [A-Za-z0-9]
3. WHEN creating a proxy session THEN the system SHALL use the residential entrypoint pr.oxylabs.io:7777
4. WHEN building proxy username THEN the system SHALL use the format "customer-<SUBUSER>-cc-<country>-sessid-<SESSION_ID>" where -cc-<country> is optional if the account isn't geo-enabled
5. WHEN the account doesn't support geo-targeting THEN the system SHALL omit the -cc-<country> segment from the username
6. WHEN building proxy credentials THEN the system SHALL URL-encode both username and password using quote(..., safe="")
7. WHEN a ProxySession is created THEN it SHALL contain both proxy_url and session_id properties
8. WHEN the same video is processed THEN both transcript fetching and yt-dlp SHALL use the identical proxy session

### Requirement 2

**User Story:** As a developer, I want proper credential management so that proxy authentication uses secure credentials from AWS Secrets Manager.

#### Acceptance Criteria

1. WHEN building proxy username THEN the system SHALL retrieve SUBUSER from AWS Secrets Manager
2. WHEN constructing proxy URL THEN the system SHALL use the format "http://<ENC_USER>:<ENC_PASS>@pr.oxylabs.io:7777"
3. WHEN encoding credentials THEN the system SHALL properly URL-encode username and password or use a URL-safe password as MVP shortcut
4. WHEN logging operations THEN the system SHALL never log full credentials; only log the sticky username with the password redacted
5. WHEN proxy authentication fails THEN the system SHALL log the failure without exposing credentials

### Requirement 3

**User Story:** As a system operator, I want intelligent retry logic so that temporary proxy issues don't cause permanent failures.

#### Acceptance Criteria

1. WHEN a response has status 403 or 429 THEN the system SHALL perform exactly one automatic rotate and retry
2. WHEN response body contains "Sign in to confirm you're not a bot" THEN the system SHALL perform exactly one automatic rotate and retry
3. WHEN the second attempt fails THEN the system SHALL fall back to ASR (yt-dlp → transcribe) or return failure
4. WHEN retry logic is triggered THEN the system SHALL generate a new session ID for the retry attempt
5. WHEN falling back to ASR THEN the system SHALL still use proxy for yt-dlp audio download
6. WHEN making HTTP calls THEN the system SHALL use default timeouts of 15 seconds to prevent hanging requests

### Requirement 4

**User Story:** As a content processor, I want discovery gating so that the system doesn't waste time trying to fetch transcripts that don't exist.

#### Acceptance Criteria

1. WHEN checking video metadata THEN the system SHALL query videos.list.contentDetails.caption
2. WHEN caption field is not "true" THEN the system SHALL skip transcript scraping entirely
3. WHEN skipping transcript scraping THEN the system SHALL go directly to yt-dlp → ASR workflow
4. WHEN using ASR fallback THEN the system SHALL still apply proxy and user agent to yt-dlp

### Requirement 5

**User Story:** As a system administrator, I want consistent user agent application so that both transcript requests and yt-dlp use the same browser identity.

#### Acceptance Criteria

1. WHEN processing a video THEN the system SHALL get a user agent from UserAgentManager
2. WHEN making transcript requests THEN the system SHALL apply the user agent to HTTP headers
3. WHEN making transcript requests THEN the system SHALL include Accept-Language: en-US,en;q=0.9 in HTTP headers
4. WHEN calling yt-dlp THEN the system SHALL pass the same user agent via --user-agent parameter
5. WHEN logging operations THEN the system SHALL indicate ua_applied=true in structured logs

### Requirement 6

**User Story:** As a developer, I want proper environment variable handling so that existing HTTP_PROXY settings don't interfere with our proxy configuration.

#### Acceptance Criteria

1. WHEN HTTP_PROXY or HTTPS_PROXY environment variables are set THEN the system SHALL ignore them for both transcript HTTP and yt-dlp when an explicit sticky proxy is provided
2. WHEN ignoring environment proxy settings THEN the system SHALL log a one-line warning
3. WHEN calling yt-dlp THEN the system SHALL explicitly pass our proxy URL via --proxy parameter
4. WHEN environment variables are ignored THEN the system SHALL not affect other parts of the application

### Requirement 7

**User Story:** As a system operator, I want structured logging so that I can monitor proxy performance and troubleshoot issues effectively.

#### Acceptance Criteria

1. WHEN starting transcript fetch THEN the system SHALL log "STRUCTURED_LOG step=transcript video_id=<id> session=<sid> ua_applied=true latency_ms=<ms>"
2. WHEN starting yt-dlp THEN the system SHALL log "STRUCTURED_LOG step=ytdlp video_id=<id> session=<sid> ua_applied=true latency_ms=<ms>"
3. WHEN an error occurs THEN the system SHALL log "STRUCTURED_LOG step=<step> video_id=<id> status=<error_type>"
4. WHEN logging error status THEN the system SHALL use specific codes: proxy_407, bot_check, blocked_403, blocked_429, timeout
5. WHEN the same video uses transcript and yt-dlp THEN the logs SHALL show identical session IDs
6. WHEN logging operations THEN the system SHALL never log the password or full proxy URL; only log customer-<subuser>-cc-<country>-sessid-<sid>

### Requirement 8

**User Story:** As a quality assurance tester, I want reliable proxy authentication so that no 407 Proxy Authentication Required errors occur during normal operation.

#### Acceptance Criteria

1. WHEN running tests on 3 videos THEN the system SHALL not produce any 407 Proxy Authentication Required errors
2. WHEN proxy authentication is required THEN the system SHALL provide properly formatted credentials
3. WHEN credentials are rejected THEN the system SHALL attempt session rotation before failing
4. WHEN testing proxy functionality THEN the system SHALL demonstrate successful authentication across multiple videos
5. WHEN proving sticky sessions work THEN one curl to https://ipinfo.io via the sticky proxy SHALL return 200 and the same IP when rerun with the same sessid

### Requirement 9

**User Story:** As a system administrator, I want graceful bot detection handling so that temporary blocks don't cause permanent failures.

#### Acceptance Criteria

1. WHEN the first attempt hits bot-check THEN the system SHALL rotate to a new session automatically
2. WHEN the second attempt succeeds THEN the system SHALL continue with normal processing
3. WHEN the second attempt also fails THEN the system SHALL fail fast to ASR with audio downloaded via proxy
4. WHEN falling back to ASR THEN the system SHALL reuse the same session for yt-dlp audio download
5. WHEN bot-check repeats after one rotate THEN the system SHALL not loop but fail fast to ASR
6. WHEN bot detection occurs THEN the system SHALL log the incident with appropriate error codes

## Definition of Done

- 0 occurrences of 407 Proxy Authentication Required across 3 test videos
- If first attempt hits bot-check, second (new sessid) succeeds; otherwise ASR path succeeds (audio downloaded via proxy)
- Logs show identical session=<sid> for transcript + yt-dlp per video, with ua_applied=true and latency_ms present