# Implementation Plan

- [x] 1. Update dependencies and Docker configuration


  - Add playwright==1.46.0 to requirements.txt
  - Update Dockerfile to install Chromium browser with dependencies
  - Ensure COOKIE_DIR environment variable and directory creation
  - _Requirements: 6.1, 6.2, 6.3, 6.4_



- [ ] 2. Enhance proxy_manager.py with Playwright support
  - Add playwright_proxy() method to return Playwright-compatible proxy configuration
  - Add is_production_environment() method for environment detection
  - Parse proxy URL components for Playwright server/username/password format


  - In production: hard-fail if no proxy configured; in development: warn and allow direct connection
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 8.1, 8.2, 8.3, 8.4_

- [ ] 3. Update cookie_generator.py for proper storage state location
  - Modify STORAGE_STATE path to use COOKIE_DIR environment variable


  - Default to /app/cookies when COOKIE_DIR is not set
  - Add logging when storage_state is successfully saved
  - Handle errors during storage_state save operations
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_


- [ ] 4. Implement core Playwright transcript extraction method
  - Add _get_transcript_via_playwright() async method to TranscriptService
  - Implement browser launch with storage_state, proxy, and user agent configuration
  - Add production environment validation that fails fast on missing proxy
  - Navigate to YouTube video URLs with domcontentloaded wait
  - _Requirements: 1.1, 1.2, 2.1, 2.3, 3.1, 3.2, 3.3_


- [ ] 5. Implement network request interception and JSON parsing
  - Set up Playwright request interception for /youtubei/v1/get_transcript URLs
  - Wait up to 15 seconds for transcript XHR after page load, with 120s navigation timeout
  - Implement _extract_cues_from_youtubei() method to parse JSON responses
  - Transform YouTubei JSON to standard [{text, start, duration}, ...] format
  - Handle two YouTube URL formats: www.youtube.com/watch?v= then m.youtube.com/watch?v=
  - _Requirements: 1.3, 1.4, 9.1, 9.2, 9.3, 13.1, 13.2, 13.3_


- [ ] 6. Add comprehensive error handling and logging
  - Implement error classification for three main types: authentication_missing, navigation_timeout, response_parsing_error
  - Add detailed logging for browser launch, navigation, and transcript capture
  - Log performance metrics with operation, success status, and duration
  - Handle missing storage_state with clear remediation instructions

  - Log proxy configuration with masked credentials, target URLs, and timing
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 11.1, 11.2, 11.3, 14.1, 14.2, 14.3, 14.4, 14.5_

- [ ] 7. Decouple circuit breaker from ASR processing
  - Modify circuit breaker to only affect Playwright operations
  - Ensure ASR processing always runs when all transcript methods fail, regardless of circuit breaker state


  - Update circuit breaker logging to clarify it only blocks Playwright
  - Verify orchestrator truly runs ASR even when Playwright breaker is open
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 15.1, 15.2, 15.3, 15.4, 15.5_

- [ ] 8. Integrate Playwright as primary transcript method
  - Update get_transcript() method to call Playwright first



  - Implement proper fallback order: Playwright → youtube-transcript-api → timedtext → ASR
  - Ensure existing transcript methods remain as fallbacks
  - Add feature flag ENABLE_PLAYWRIGHT_PRIMARY for rollback capability
  - _Requirements: 1.1, 1.6, 10.1, 10.2, 10.3, 10.4, 10.5_

- [ ] 9. Add comprehensive testing and validation
  - Write unit tests for Playwright configuration and JSON parsing
  - Test production environment proxy validation
  - Test circuit breaker behavior with Playwright failures
  - Verify ASR processing is never blocked by circuit breaker
  - Test end-to-end Playwright transcript extraction flow
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

- [ ] 10. Update deployment configuration and documentation
  - Update deployment scripts to handle new Playwright dependencies
  - Add environment variable documentation for COOKIE_DIR and feature flags
  - Create setup instructions for local development with Playwright
  - Document cookie generation process with proper storage location
  - _Requirements: 6.1, 6.2, 6.3, 12.1, 12.2, 12.3, 12.4, 12.5_