# Implementation Plan

- [x] 1. Fix Playwright API Usage in YouTubei Service





  - Replace all `locator.is_visible(timeout=...)` calls with proper `locator.wait_for(state="visible", timeout=...)` 
  - Update consent wall detection, expander clicks, and menu interactions to use correct wait API
  - Add error logging for wait failures to identify selector issues
  - _Requirements: 1.1_

- [x] 2. Implement Fast-Path Caption Extraction





  - [x] 2.1 Add caption tracks extraction from ytInitialPlayerResponse


    - Create `_extract_captions_from_player_response()` method to read captionTracks from page JavaScript
    - Implement track selection logic (prefer non-ASR English, fallback to first available)
    - Add this extraction immediately after page load, before any DOM interaction
    - _Requirements: 1.2, 1.3_

  - [x] 2.2 Create HTTP-based transcript fetching helper

    - Implement `_fetch_transcript_xml_via_requests()` method with proxy support
    - Respect `ENFORCE_PROXY_ALL` environment variable for proxy enforcement
    - Add proper error handling and logging for HTTP failures
    - _Requirements: 1.6_

- [x] 3. Implement Deterministic DOM Selectors





  - Replace unreliable overflow menu detection with title-row menu selectors
  - Create `_open_transcript_via_title_menu()` method using `TITLE_ROW_MENU` and `SHOW_TRANSCRIPT_ITEM` constants
  - Add dropdown state verification before clicking transcript option
  - Update main DOM interaction flow to use deterministic path
  - _Requirements: 1.4_

- [x] 4. Enhance Direct POST Fallback with Real Context





  - [x] 4.1 Extract real API context from page


    - Implement extraction of `INNERTUBE_API_KEY` and `INNERTUBE_CONTEXT` from ytcfg
    - Create `_extract_transcript_params()` method to get params from captured requests or DOM
    - Add validation to ensure all required context is available before POST
    - _Requirements: 1.5_

  - [x] 4.2 Implement authenticated direct POST request


    - Create `_make_direct_transcript_request()` with proper authentication headers
    - Add JSON response parsing to extract transcript text from API response
    - Implement proxy support for direct POST requests
    - _Requirements: 1.5, 1.6_

- [x] 5. Add XML Content Validation to Transcript Service





  - [x] 5.1 Implement content validation helpers


    - Create XML validation functions to check content before parsing
    - Add early blocking detection for HTML/consent/captcha responses
    - Implement `_validate_and_parse_xml()` method replacing direct `ET.fromstring()` calls
    - _Requirements: 3.1, 3.3_

  - [x] 5.2 Update timedtext parsing with validation


    - Replace `ET.fromstring()` calls in `_fetch_timedtext_xml()` with validation wrapper
    - Add retry logic with cookies when blocking is detected
    - Update error logging to include specific validation failure types
    - _Requirements: 3.1, 3.2, 3.3_

- [x] 6. Implement Cookie Propagation Throughout Pipeline





  - Update `_execute_transcript_pipeline()` to ensure cookie headers are passed to all stages
  - Modify all downstream HTTP fetch helpers to receive propagated cookies: timedtext calls, `_fetch_transcript_xml_via_requests()`, direct POST requests, and FFmpeg fallback requests
  - Update timedtext, YouTubei, and ASR stage entrypoints to accept and forward cookie parameters
  - Add logging to track cookie usage across different extraction methods
  - _Requirements: 1.6, 3.2_

- [x] 7. Enforce Proxy Compliance in FFmpeg Service





  - [x] 7.1 Add proxy enforcement to requests fallback


    - Implement proxy availability check in `_requests_streaming_fallback()`
    - Block execution when `ENFORCE_PROXY_ALL=1` and no proxy available
    - Add `requests_fallback_blocked` logging for blocked operations
    - _Requirements: 2.1, 2.2_

  - [x] 7.2 Update FFmpeg timeout configuration


    - Change `FFMPEG_TIMEOUT` constant from 120 to 60 seconds
    - Confirm all `subprocess.run()` calls (ffmpeg and ffprobe) read `FFMPEG_TIMEOUT` from config, not hardcoded values
    - Ensure timeout is consistently applied across all FFmpeg operations
    - Add timeout exceeded logging with context information
    - _Requirements: 2.3, 2.4_

- [x] 8. Fix FFmpeg Header Placement and Audio Validation





  - [x] 8.1 Correct FFmpeg command header placement


    - Move `-headers` parameter to immediately before `-i` in command construction
    - Ensure CRLF formatting is maintained in header strings
    - Test header placement with various audio URL types
    - _Requirements: 2.5_

  - [x] 8.2 Enhance audio file validation


    - Always run `_validate_audio_with_ffprobe()` regardless of file size
    - Delete tiny files (<1MB) even if ffprobe validation passes to prevent HTML bodies from being accepted
    - Add duration validation to detect zero-length or corrupted audio
    - Delete invalid files and return appropriate error codes
    - _Requirements: 2.5_

- [x] 9. Implement Fast-Fail YouTubei to ASR Transition





  - Add timeout detection in YouTubei wrapper calls
  - Implement immediate ASR transition when navigation timeouts occur
  - Add `youtubei_nav_timeout_short_circuit` logging for fast-fail events
  - Prevent retry loops on the same failed extraction path
  - _Requirements: 3.4, 5.1_

- [x] 10. Add ASR Playback Triggering





  - [x] 10.1 Implement video playback initiation


    - Add `_trigger_asr_playback()` method to start video playback
    - Use keyboard shortcuts (`k` key) and video element clicks
    - Add `asr_playback_initiated` logging before HLS capture
    - _Requirements: 3.5, 3.6_

  - [x] 10.2 Update ASR HLS capture flow


    - Call playback triggering immediately after page navigation
    - Ensure HLS/MPD listeners are active before playback starts
    - Add error handling for playback initiation failures
    - _Requirements: 3.5, 3.6_

- [x] 11. Add Comprehensive Reliability Logging





  - Implement logging events tied to specific requirements: `youtubei_captiontracks_shortcircuit` (Req 1.3), `requests_fallback_blocked` (Req 2.1), content validation events (Req 3.3), `asr_playback_initiated` (Req 3.6)
  - Add structured logging for caption track shortcuts, proxy blocks, and validation failures
  - Create log event definitions for new reliability events with proper context fields
  - Ensure logging provides sufficient context for troubleshooting without duplication
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 12. Create Reliability Configuration Management




  - [x] 12.1 Implement configuration data class


    - Create `ReliabilityConfig` with all timeout and feature flag settings
    - Add environment variable loading with sensible defaults
    - Implement configuration validation and error handling
    - _Requirements: 5.5_

  - [x] 12.2 Update services to use centralized configuration


    - Modify YouTubei, FFmpeg, and Transcript services to use config object instead of duplicated constants
    - Ensure FFmpeg timeout, YouTubei hard timeout, and all feature flags are loaded from config
    - Replace hardcoded constants with config references to prevent drift
    - Ensure backward compatibility with existing environment variables
    - Add configuration logging for debugging deployment issues
    - _Requirements: 5.5_

- [x] 13. Write Comprehensive Tests for Reliability Fixes





  - [x] 13.1 Create unit tests for individual components


    - Test Playwright API fixes with mocked page interactions
    - Test content validation with various response types
    - Test proxy enforcement logic with different configuration scenarios
    - _Requirements: All requirements validation_

  - [x] 13.2 Create integration tests for end-to-end pipeline


    - Test complete transcript extraction with reliability fixes enabled
    - Test fallback behavior between different extraction methods
    - Test logging output matches expected events for each scenario
    - _Requirements: All requirements validation_

- [-] 14. Update Documentation and Deployment



  - Update service documentation to reflect reliability improvements
  - Add troubleshooting guide for new logging events
  - Update deployment scripts to include new environment variables
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_