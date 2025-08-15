# Implementation Plan

- [x] 1. Enhance ProxySession for sticky session support


  - Update ProxySession class to generate deterministic session IDs from sanitized video_id (sanitize to [A-Za-z0-9], cap at 16 chars)
  - Implement sticky username builder with geo-enabled toggle: omit -cc-<country> segment entirely when geo disabled or unspecified
  - Add URL encoding for username and password credentials
  - Hardcode residential entrypoint pr.oxylabs.io:7777 in proxy URL construction
  - Add credential redaction in logging (log session ID, never password or full URL)
  - Add unit test for both geo-enabled and non-geo username variants
  - Add unit test for session ID truncation behavior
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 2.1, 2.2, 2.3, 2.4, 2.5_



- [ ] 2. Update ProxyManager for AWS Secrets Manager integration
  - Modify _load_proxy_config to retrieve SUBUSER from AWS Secrets Manager
  - Add geo_enabled capability detection from proxy configuration
  - Update get_session_for_video to use enhanced ProxySession with sticky URLs
  - Implement session rotation with new session ID generation for retries
  - Add 407 error handling: fail fast with guidance log (hint="check URL-encoding or secret password")
  - Add optional one-time secrets refresh after 407 before final failure (keeps MVP resilient)


  - Add proxy configuration validation and error handling
  - _Requirements: 2.1, 2.2, 2.3, 2.5, 3.4_

- [ ] 3. Enhance UserAgentManager for consistent header application
  - Add get_transcript_headers method returning User-Agent and Accept-Language headers


  - Ensure get_yt_dlp_user_agent returns identical User-Agent string as transcript headers
  - Update existing methods to maintain backward compatibility
  - Add error handling for User-Agent generation failures
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_



- [ ] 4. Implement discovery gate in YouTubeService
  - Add caption availability checking in get_video_details method
  - Return has_captions boolean from videos.list.contentDetails.caption field
  - Update video details response to include caption availability
  - Add error handling for API failures during caption checking
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 5. Update TranscriptService with sticky session workflow

  - Modify get_transcript to implement discovery gate (skip transcript if has_captions=false)
  - Update _get_existing_transcript_with_proxy to use sticky sessions and User-Agent headers
  - Add 15-second hard timeout for transcript HTTP calls (mirror yt-dlp timeout)
  - Implement single retry logic with session rotation for bot detection/403/429 errors
  - Add 407 proxy authentication error handling (fail fast, no retry)
  - Add idempotency guard (in-memory lock per video_id) to prevent concurrent fetching
  - Ensure ASR fallback uses same session as transcript attempt

  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.3, 4.4_

- [ ] 6. Enhance yt-dlp integration with proxy and User-Agent support
  - Update _transcribe_audio method to accept and use ProxySession parameter
  - Add sticky proxy URL to yt-dlp configuration via --proxy parameter
  - Apply User-Agent to yt-dlp via --user-agent parameter (same as transcript)
  - Add --socket-timeout 15 for hard timeout enforcement

  - Implement environment proxy collision detection and warning
  - _Requirements: 5.4, 5.5, 6.1, 6.2, 6.3, 6.4, 3.6_

- [ ] 7. Implement structured logging with credential redaction
  - Update _log_structured method to include session ID, latency_ms, and ua_applied status
  - Add error status codes: proxy_407, bot_check, blocked_403, blocked_429, timeout

  - Implement credential redaction (log only sticky username, never password/full URL)
  - Add logging for transcript and yt-dlp operations with identical session IDs
  - Include latency tracking for performance monitoring
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

- [ ] 8. Add environment variable collision handling
  - Implement _handle_env_proxy_collision function to detect HTTP_PROXY/HTTPS_PROXY


  - Add warning logging when environment proxy variables are ignored
  - Configure requests sessions to explicitly ignore environment proxies when sticky proxy provided
  - Update both transcript HTTP requests and yt-dlp to use explicit proxy configuration
  - _Requirements: 6.1, 6.2, 6.3, 6.4_



- [ ] 9. Implement error classification and retry logic
  - Add bot detection pattern matching in response content
  - Implement single retry with session rotation for 403/429/bot-check errors



  - Add fail-fast handling for 407 proxy authentication errors (no retry)
  - Update timeout handling with 15-second hard defaults
  - Add proper error logging with specific status codes
  - _Requirements: 3.1, 3.2, 3.3, 3.5, 3.6_

- [ ] 10. Create unit tests for sticky session functionality (MVP-focused)
  - Test sticky username builder with and without -cc-<country> segment
  - Test URL encoding of credentials and session ID truncation (16 char limit)
  - Test User-Agent header generation and yt-dlp parameter consistency
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [ ] 11. Create integration tests for end-to-end workflow (MVP-focused)
  - Test one E2E happy path (transcript → yt-dlp with same session)
  - Test one bot-check rotate path (first fails, second succeeds)
  - Test one 407 fail-fast path (no retry, immediate failure with guidance log)
  - _Requirements: 8.1, 8.5, 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ] 12. Add smoke test and acceptance testing for Definition of Done
  - Create one-shot smoke test: GET https://ipinfo.io twice with same sessid (same IP), then different sessid (different IP)
  - Run acceptance test across 3 videos with complete workflow
  - Verify zero 407 Proxy Authentication Required errors occur
  - Validate logs show identical session IDs for transcript and yt-dlp per video
  - Confirm all logs include ua_applied=true and latency_ms values
  - _Requirements: 8.1, 8.5, 9.1, 9.2, 9.3, 9.4, 9.5_