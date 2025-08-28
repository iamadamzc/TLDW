# Implementation Plan

- [x] 1. Implement DOM helper methods in TranscriptService





  - Add _try_consent() method with resilient consent dialog selectors
  - Add _expand_description() method with hierarchical "more" button selectors  
  - Add _open_transcript() method with hardened selectors including case-insensitive aria-label*="transcript" and generic "button inside ytd-transcript-search-panel-renderer" fallback
  - Add panel-open confirmation by waiting for ytd-transcript-search-panel-renderer to appear after clicking transcript button
  - Implement proper timeout handling and error logging for each helper
  - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 2. Enhance route interception setup and management





  - Modify _get_transcript_via_playwright() to set up route interception BEFORE DOM interactions
  - Implement Future-based route capture with (url, body) result handling
  - Add proper route cleanup with unroute() after capture completion
  - Implement 25-second timeout for route capture with proper error logging
  - _Requirements: 5.1, 5.2, 5.3, 12.1_

- [x] 3. Integrate DOM interaction sequence into main Playwright method





  - Update _get_transcript_via_playwright() to call DOM helpers in sequence
  - Implement scroll-and-retry logic when transcript button is not found initially
  - Add proper error handling that returns None for fallback to next transcript method
  - Maintain existing proxy/cookie behavior and browser launch configuration
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 6.1, 6.2, 6.3, 6.4, 8.1, 8.2, 8.3, 8.4_

- [x] 4. Implement HTTP response validation with DOM fallback





  - Add 6-second timeout for waiting for HTTP response after route capture
  - Validate response status code and log youtubei_direct_fetch_failed for non-200 status
  - When response timeout expires, immediately try DOM fallback scraping from transcript panel
  - Parse JSON response and return transcript data using existing _extract_cues_from_youtubei() method
  - _Requirements: 5.4, 5.5, 12.2_

- [x] 5. Add comprehensive structured logging with metrics tags





  - Log "youtubei_dom: expanded description via [selector]" when description expansion succeeds
  - Log "youtubei_dom: clicked transcript launcher ([selector])" when transcript button is clicked
  - Log "youtubei_route_captured url=[url]" when route interception captures request
  - Include metrics tags cookie_source=user|env and proxy_mode=on|off in start/end logs for filtering by root cause
  - Add warning logs for failures without verbose dumps or stack traces
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 13.1, 13.2, 13.3, 13.4, 13.5_

- [x] 6. Implement graceful degradation and error handling





  - Ensure DOM helper methods never throw exceptions that break the transcript pipeline
  - Skip description expansion gracefully when expander is not found
  - Skip consent handling gracefully when no consent dialog is present
  - Return None from main method when DOM interactions fail completely
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 14.4_

- [x] 7. Add unit tests for DOM helper methods





  - Test _try_consent() with mock page showing consent dialog present and absent scenarios
  - Test _expand_description() with mock page showing expander exists and missing scenarios  
  - Test _open_transcript() with mock page showing button found and not found scenarios
  - Test timeout handling and error scenarios for all DOM helper methods
  - _Requirements: 10.1, 10.2, 10.3_

- [x] 8. Add integration tests for route interception and retry logic















  - Test route interception setup and Future-based capture mechanism
  - Test scroll-and-retry logic when transcript button is not initially visible
  - Test complete DOM interaction sequence with successful transcript extraction
  - Test failure paths where DOM interactions timeout or elements are not found
  - _Requirements: 10.4, 10.5_

- [x] 9. Add validation tests with specific video IDs





  - Create test that validates DOM interactions work with video ID rNxC16mlO60
  - Verify expected log messages are generated during DOM interaction sequence
  - Test that transcript JSON is successfully extracted and returned
  - Add test for videos with collapsed descriptions to verify expansion works
  - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

- [x] 10. Implement DOM fallback scraping helper





  - Add ~30-line _scrape_transcript_from_panel() method as deterministic Plan B when route capture fails
  - Extract transcript text directly from ytd-transcript-search-panel-renderer DOM elements
  - Use this as immediate fallback when HTTP response timeout expires (6s) instead of bailing to next method
  - Parse DOM-scraped transcript into standard [{text, start, duration}, ...] format
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 11. Ensure backward compatibility and integration





  - Verify DOM enhancements do not change existing method signatures
  - Ensure existing error handling and circuit breaker behavior is preserved
  - Confirm fallback order remains: Playwright → youtube-transcript-api → timedtext → ASR
  - Test that DOM interaction failures properly trigger fallback to next transcript method
  - _Requirements: 14.1, 14.2, 14.3, 14.4, 15.1, 15.2, 15.3, 15.4, 15.5_