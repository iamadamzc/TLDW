# Requirements Document

## Introduction

This feature enhances the YouTube Transcript API integration in TL;DW by adding proper user context and cookie support, implementing critical timeout fixes, and improving error handling in the transcript fetching pipeline. The system needs to support per-user S3 cookie loading, YouTubei timeout protection, circuit breaker integration, and better fallback strategies when the standard YouTube Transcript API fails due to authentication or access restrictions. This addresses critical production issues where transcript operations hang indefinitely and cookie authentication fails.

## Requirements

### Requirement 1

**User Story:** As a user with uploaded cookies, I want the transcript service to use my cookies when fetching transcripts so that I can access restricted or private video transcripts that would otherwise be unavailable.

#### Acceptance Criteria

1. WHEN TranscriptService is initialized THEN it SHALL support setting a current_user_id for cookie loading
2. WHEN get_captions_via_api is called with a user_id set THEN it SHALL attempt direct HTTP transcript fetch with user cookies first
3. WHEN user cookies are available THEN the system SHALL use get_transcript_with_cookies_fixed function for enhanced cookie support
4. WHEN user cookies are not available THEN the system SHALL fallback to standard library approaches
5. WHEN cookies are used THEN the system SHALL log the user ID without exposing cookie contents
6. WHEN loading cookies THEN it SHALL first attempt S3 bucket loading with load_user_cookies_from_s3(user_id)
7. WHEN S3 cookies are found THEN they SHALL take precedence over environment/file cookies

### Requirement 2

**User Story:** As a system processing video transcripts, I want multiple fallback strategies for transcript fetching so that I can maximize success rates when individual methods fail.

#### Acceptance Criteria

1. WHEN get_captions_via_api is called THEN it SHALL try direct HTTP with cookies as Strategy 1
2. WHEN Strategy 1 fails THEN it SHALL try the original YouTube Transcript API library as Strategy 2
3. WHEN Strategy 2 fails THEN it SHALL try direct get_transcript as Strategy 3 (final fallback)
4. WHEN any strategy succeeds THEN it SHALL return the transcript text and log the successful method
5. WHEN all strategies fail THEN it SHALL return empty string and log appropriate warnings

### Requirement 3

**User Story:** As a developer debugging transcript failures, I want detailed logging of each transcript fetching attempt so that I can identify which methods work for different types of videos.

#### Acceptance Criteria

1. WHEN attempting direct HTTP transcript fetch THEN it SHALL log "Attempting direct HTTP transcript fetch with user {user_id} cookies"
2. WHEN library-based approach is used THEN it SHALL log "Attempting library-based transcript fetch for {video_id}"
3. WHEN transcript source is identified THEN it SHALL log the source info (manual/auto, language)
4. WHEN methods fail THEN it SHALL log specific error types and messages for debugging
5. WHEN YouTube blocks requests THEN it SHALL identify and log XML parsing errors appropriately

### Requirement 4

**User Story:** As a transcript service, I want to intelligently select the best available transcript so that users get the highest quality captions available.

#### Acceptance Criteria

1. WHEN multiple transcripts are available THEN it SHALL prefer manual transcripts over auto-generated ones
2. WHEN searching for transcripts THEN it SHALL check preferred languages (en, en-US, es) in order
3. WHEN no preferred language transcript exists THEN it SHALL use any available transcript as fallback
4. WHEN filtering transcript segments THEN it SHALL exclude noise markers like "[Music]", "[Applause]", "[Laughter]"
5. WHEN transcript is found THEN it SHALL log the transcript type (manual/auto) and language

### Requirement 5

**User Story:** As a system that needs user context, I want the transcript service to automatically detect the current user so that appropriate cookies are loaded without manual configuration.

#### Acceptance Criteria

1. WHEN get_transcript is called with user_id parameter THEN it SHALL set the current_user_id for cookie loading
2. WHEN set_current_user_id method is called THEN it SHALL store the user ID for subsequent cookie operations
3. WHEN user context is established THEN subsequent transcript operations SHALL use the user's cookies
4. WHEN no user context is provided THEN the system SHALL operate without user-specific cookies
5. WHEN user ID is set THEN it SHALL be available for cookie loading functions

### Requirement 6

**User Story:** As a system administrator, I want proper error handling and logging so that transcript failures are properly categorized and don't break the overall processing pipeline.

#### Acceptance Criteria

1. WHEN XML parsing errors occur THEN the system SHALL identify them as YouTube blocking indicators
2. WHEN NoTranscriptFound exceptions occur THEN the system SHALL log them appropriately and continue
3. WHEN library errors occur THEN the system SHALL log the error type and message for debugging
4. WHEN all transcript methods fail THEN the system SHALL return empty string rather than raising exceptions
5. WHEN logging errors THEN the system SHALL provide context about which strategy failed and why

### Requirement 7

**User Story:** As a system that integrates with existing transcript pipeline, I want the enhanced API to maintain compatibility with existing interfaces so that no breaking changes are introduced.

#### Acceptance Criteria

1. WHEN get_transcript method is called THEN it SHALL maintain the existing method signature
2. WHEN new user_id parameter is provided THEN it SHALL be optional and not break existing calls
3. WHEN enhanced get_captions_via_api is used THEN it SHALL return the same data format as before
4. WHEN set_current_user_id is called THEN it SHALL not affect other transcript service functionality
5. WHEN the service is used without user context THEN it SHALL behave identically to the previous version

### Requirement 8

**User Story:** As a system using proxy connections, I want the enhanced transcript API to work with existing proxy infrastructure so that network routing remains consistent.

#### Acceptance Criteria

1. WHEN proxy_manager is available THEN the enhanced cookie method SHALL use proxy_dict_for("requests")
2. WHEN proxies are configured THEN they SHALL be passed to the get_transcript_with_cookies_fixed function
3. WHEN no proxy is available THEN the system SHALL operate with direct connections
4. WHEN proxy errors occur THEN they SHALL be handled gracefully without breaking transcript fetching
5. WHEN using proxies with cookies THEN both authentication methods SHALL work together

### Requirement 9

**User Story:** As a user who has uploaded cookies via the app's cookie upload function, I want the transcript service to automatically load my cookies from S3 storage so that I can access restricted videos without manual cookie configuration.

#### Acceptance Criteria

1. WHEN a user_id is provided THEN the system SHALL attempt to load cookies from `s3://tldw-cookies-bucket/cookies/{user_id}.txt`
2. WHEN loading cookies from S3 THEN it SHALL parse Netscape format cookie files correctly
3. WHEN S3 cookie loading fails THEN it SHALL log the error and fallback to environment/file cookies
4. WHEN cookies are successfully loaded from S3 THEN it SHALL log the number of cookies loaded (without values)
5. WHEN no S3 cookies exist for a user THEN it SHALL operate without user-specific cookies

### Requirement 10

**User Story:** As a transcript processing system, I want YouTubei operations to have strict timeout limits so that the system doesn't hang indefinitely on problematic videos.

#### Acceptance Criteria

1. WHEN get_transcript_via_youtubei is called THEN it SHALL enforce a maximum operation time of 150 seconds
2. WHEN timeout is approaching THEN it SHALL abort current attempts and move to next fallback
3. WHEN Playwright operations exceed navigation timeout THEN they SHALL be terminated gracefully
4. WHEN YouTubei times out THEN it SHALL trigger the circuit breaker appropriately
5. WHEN maximum operation time is reached THEN it SHALL log timeout warnings and return empty string
6. WHEN YouTubei operations approach timeout THEN it SHALL log remaining time warnings
7. WHEN operations are aborted due to timeout THEN it SHALL log the abort reason and elapsed time

### Requirement 11

**User Story:** As a system bypassing YouTube Transcript API limitations, I want direct HTTP requests to properly authenticate with user cookies so that restricted content can be accessed.

#### Acceptance Criteria

1. WHEN making direct HTTP transcript requests THEN it SHALL include proper YouTube headers (User-Agent, Referer)
2. WHEN user cookies are available THEN they SHALL be included in Cookie headers for authentication
3. WHEN cookie authentication fails THEN it SHALL log XML parsing errors as YouTube blocking indicators
4. WHEN transcript list requests succeed THEN it SHALL attempt individual transcript fetches with same authentication
5. WHEN both S3 cookies and environment cookies are available THEN it SHALL prefer S3 cookies for user context

### Requirement 12

**User Story:** As a system protecting against cascading failures, I want proper circuit breaker behavior so that repeated Playwright failures don't overwhelm the system.

#### Acceptance Criteria

1. WHEN 3 consecutive Playwright timeouts occur THEN the circuit breaker SHALL activate for 10 minutes
2. WHEN circuit breaker is active THEN YouTubei operations SHALL be skipped with appropriate logging
3. WHEN a Playwright operation succeeds THEN the failure count SHALL reset to zero
4. WHEN circuit breaker activates THEN it SHALL log clear warnings about the protection
5. WHEN circuit breaker is active THEN the system SHALL continue with remaining fallback methods
6. WHEN circuit breaker activates THEN it SHALL log "Playwright circuit breaker activated - skipping for 10 minutes"
7. WHEN circuit breaker blocks operations THEN they SHALL be skipped with appropriate logging

### Requirement 13

**User Story:** As a developer debugging transcript failures, I want specific error identification so that I can distinguish between different types of YouTube blocking and access issues.

#### Acceptance Criteria

1. WHEN "no element found: line 1, column 0" error occurs THEN it SHALL be identified as YouTube anti-bot blocking
2. WHEN empty XML responses are received THEN they SHALL be logged with response content preview
3. WHEN TimeoutError exceptions occur THEN they SHALL trigger circuit breaker registration
4. WHEN proxy vs direct connection attempts fail THEN they SHALL be logged separately for comparison
5. WHEN authentication vs content issues occur THEN they SHALL be distinguished in error messages

### Requirement 14

**User Story:** As a system administrator deploying fixes, I want to replace existing broken functions with fixed versions so that transcript operations work reliably in production.

#### Acceptance Criteria

1. WHEN deploying fixes THEN get_transcript_with_cookies SHALL be replaced with get_transcript_with_cookies_fixed
2. WHEN deploying fixes THEN get_transcript_via_youtubei SHALL be replaced with the timeout-enforced version
3. WHEN deploying fixes THEN TranscriptService.get_captions_via_api SHALL be updated with the enhanced version
4. WHEN deploying fixes THEN user ID passing SHALL be implemented throughout the pipeline
5. WHEN testing cookie loading THEN the system SHALL verify cookies are being loaded and log cookie names (not values)