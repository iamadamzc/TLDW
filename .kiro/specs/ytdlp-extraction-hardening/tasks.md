# Implementation Plan

- [x] 1. Expand extraction failure detection patterns in yt_download_helper.py


  - Update _detect_extraction_failure() function to include new YouTube error patterns
  - Add case-insensitive checks for: "unable to extract yt initial data", "failed to parse json", "unable to extract player version", "failed to extract any player response"
  - Maintain existing patterns for backward compatibility
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 2. Implement mandatory A/B testing logic in download_audio_with_retry()


  - **Force attempt 2 with use_cookies=false when _detect_extraction_failure() returns true, even when cookies are fresh**
  - Add 1-2 second randomized sleep between attempt 1 and attempt 2 to reduce throttling (import time and random)
  - Ensure any extraction failure triggers no-cookie retry regardless of cookie freshness status
  - _Requirements: 2.1, 2.2, 2.5_

- [x] 3. Enhance error message formatting and logging in download_audio_with_retry()

  - Raise single final RuntimeError with format: "Attempt 1: <msg> | Attempt 2: <msg> - consider updating yt-dlp"
  - Always emit standardized log keys: Attempt 1: yt_dlp_attempt=1 use_cookies=<true|false> reason=<normal|stale_cookiefile|environment_disabled>
  - Always emit standardized log keys: Attempt 2: yt_dlp_attempt=2 use_cookies=false retry_reason=<extraction_failure|cookie_invalid>
  - _Requirements: 2.6, 4.1, 4.2, 4.3, 4.4, 4.5, 4.8_

- [x] 4. Enhance startup logging with yt-dlp version information in app.py


  - Add structured JSON logging for yt-dlp version in _check_dependencies() function
  - Ensure version information is easily correlatable with extraction failures in logs
  - Maintain existing dependency checking structure while adding version visibility
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 5. Implement DISABLE_COOKIES environment flag support

  - Add check for DISABLE_COOKIES=true environment variable in download_audio_with_retry()
  - Skip all cookie usage when flag is set, logging reason=environment_disabled
  - Ensure canary testing capability without code changes
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 6. Update structured logging in transcript_service._log_structured()


  - Standardize log keys for unified attempt logging: yt_dlp_attempt, use_cookies, reason (attempt 1), retry_reason (attempt 2)
  - Ensure lowercase values for boolean and enum fields for consistent grep/alerting
  - Support exact reason values: normal, stale_cookiefile, environment_disabled, extraction_failure, cookie_invalid
  - _Requirements: 4.8, 6.4_

- [x] 7. Create unit tests for extraction failure detection


  - Test _detect_extraction_failure() with all new error patterns
  - Verify case-insensitive matching works correctly
  - Test that existing patterns continue to work
  - _Requirements: 11.1_

- [x] 8. Create unit tests for stale cookie handling

  - Test that cookies older than 12 hours trigger reason=stale_cookiefile logging
  - Verify that stale cookies result in use_cookies=false for attempt 1
  - Test _check_cookie_freshness() function behavior
  - _Requirements: 11.2_

- [ ] 9. Create integration test for mandatory A/B testing flow


  - Mock attempt 1 failure with "failed to parse json" error
  - Verify attempt 2 runs with use_cookies=false and retry_reason=extraction_failure
  - Test complete flow from extraction failure detection through retry
  - _Requirements: 11.3_

