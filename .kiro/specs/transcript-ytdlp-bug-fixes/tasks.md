# Implementation Plan

- [x] 1. Fix critical dependency versions and cookie plumbing




  - Pin youtube-transcript-api==0.6.2 in requirements.txt to fix AttributeError
  - Pin yt-dlp==2025.8.11 in requirements.txt for stable behavior
  - Add cookiefile: Optional[str] = None parameter to download_audio_with_fallback function signature
  - Implement cookie file validation helper function _maybe_cookie() to check file exists and has content
  - Add cookiefile to base_opts configuration in both ydl_opts_step1 and ydl_opts_step2
  - Implement resolve_cookiefile(user_id) method in TranscriptService to get per-user cookie path
  - Update TranscriptService._attempt_ytdlp_download to resolve and pass user cookiefile to helper
  - Add structured logging for cookies_used=true/false per download attempt
  - Test cookie parameter reaches yt-dlp configuration correctly
  - _Requirements: 1.2, 1.3, 2.1, 2.2, 2.3_

- [x] 2. Implement stable client selection and enhanced yt-dlp configuration





  - Add extractor_args: {"youtube": {"player_client": ["web"]}} to base_opts in yt_download_helper.py
  - Ensure extractor_args configuration is identical in both step1 and step2 download attempts
  - Update enhanced HTTP headers to include Accept-Language for better bot detection avoidance
  - Remove unstable client variants and use only web client for consistency
  - Test that web client is used consistently across both download steps
  - _Requirements: 3.1, 3.2, 3.4_

- [x] 3. Fix Deepgram Content-Type headers and MIME type mapping




  - Create explicit EXT_MIME_MAP dictionary mapping file extensions to correct MIME types
  - Map .m4a and .mp4 to "audio/mp4", .mp3 to "audio/mpeg"
  - Update _send_to_deepgram method to use explicit mapping before mimetypes.guess_type fallback
  - Add fallback to "application/octet-stream" for unknown file extensions
  - Test Content-Type headers are correct for both m4a and mp3 files sent to Deepgram
  - _Requirements: 6.5_

- [x] 4. Enhance proxy 407 error handling with fast-fail strategy




  - Implement _handle_407_error method in TranscriptService for immediate proxy rotation
  - Add 407 error detection in _attempt_ytdlp_download method similar to transcript fetch
  - Create ALLOW_NO_PROXY_ON_407 environment variable with default false for optional no-proxy fallback
  - Mark proxy sessions as failed immediately on 407 errors to prevent reuse
  - Add structured logging for 407 error handling and proxy rotation events
  - Test 407 errors trigger immediate proxy rotation without retry delays
  - _Requirements: 4.1, 4.3, 4.4, 4.5_

- [x] 5. Improve error message propagation and bot detection




  - Ensure yt-dlp DownloadError messages are preserved and propagated verbatim
  - Implement error message combination with " || " separator for step1 and step2 failures
  - Update _detect_bot_check function to handle combined error messages from both steps
  - Add normalized error string return from helper function for structured logging
  - Ensure TranscriptService logs the single normalized error string in structured logs for simple Kibana/Grafana searches
  - Test bot detection works correctly with combined error messages
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 6. Add health diagnostics and observability enhancements




  - Add EXPOSE_HEALTH_DIAGNOSTICS environment variable to control diagnostic exposure
  - Enhance /healthz endpoint to include yt_dlp_version and ffmpeg_location
  - Add last_download_used_cookies boolean and last_download_client string fields to health response
  - Implement tracking of last download attempt metadata without exposing sensitive data
  - Ensure health endpoint never leaks cookie file paths, contents, or proxy credentials - only booleans and client strings
  - Test health endpoint returns correct diagnostic information without PII or secrets
  - _Requirements: 7.1, 7.4_

- [ ] 7. Clean up code duplications and environment variable consistency










  - Remove duplicate initialization of ProxyManager, ProxyHTTPClient, and UserAgentManager in TranscriptService.__init__
  - Standardize Google OAuth environment variable names between GOOGLE_CLIENT_* and GOOGLE_OAUTH_CLIENT_*
  - Update deployment scripts and App Runner configuration to use consistent variable names
  - Ensure google_auth.py code matches the environment variable names used in deployment
  - Test OAuth integration works with consistent environment variable naming
  - _Requirements: 6.1, 6.3_

- [x] 8. Create comprehensive CI smoke test suite and deployment improvements




  - Implement end-to-end smoke test for transcript path using known public video with captions
  - Create ASR path smoke test using known public video without captions or force_asr flag
  - Add test cases for both step1 (m4a) and step2 (mp3) download scenarios
  - Include one test that runs with cookies and one without cookies for realistic network conditions
  - Mock Deepgram responses to test complete pipeline without external API calls
  - Configure CI to fail build on smoke test failures to prevent regression deployment
  - Update deploy-apprunner.sh to either push unique git SHA tags or call aws apprunner start-deployment to force restart
  - Test smoke tests catch regressions in transcript API, yt-dlp, and Deepgram integration
  - _Requirements: 7.2, 7.3_