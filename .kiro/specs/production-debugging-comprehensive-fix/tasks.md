# Implementation Plan

- [x] 1. Enhance Dockerfile with yt-dlp version management and build-time logging


  - Add ARG YTDLP_VERSION=2025.8.11 to Dockerfile with pinned default (CI sets explicit value, override with latest only when needed)
  - Implement conditional pip install logic for latest vs pinned yt-dlp versions
  - Add build-time version logging with python -c "import yt_dlp; print('yt-dlp version:', yt_dlp.version.__version__)"
  - Add FFmpeg availability check during build with ffmpeg -version verification
  - Test Docker build works with both YTDLP_VERSION=latest and specific pinned version
  - _Requirements: 2.1, 2.3, 2.5_

- [x] 2. Implement resilient ProxyManager with graceful secret handling


  - Add _validate_secret_schema method to check for required fields: provider, host, port, username, password, protocol
  - Modify ProxyManager.__init__ to catch exceptions and continue with in_use=False on secret failures
  - Read secret name from environment variable (no hardcoding) and include it in logs as non-secret identifier
  - Implement comprehensive logging for missing fields without exposing sensitive data
  - Add graceful degradation when AWS Secrets Manager secret is malformed or missing provider field
  - Test ProxyManager handles missing provider field and continues service startup
  - _Requirements: 1.1, 1.2, 1.4, 1.5_

- [x] 3. Harden yt-dlp configuration with multi-client support and network resilience





  - Update yt_download_helper.py to use extractor_args with multiple player clients: ["android", "web", "web_safari"]
  - Add network resilience settings: retries=2, socket_timeout=10, nocheckcertificate=True
  - Implement enhanced HTTP headers with User-Agent and Accept-Language for bot detection avoidance
  - Ensure identical configuration in both step1 and step2 download attempts
  - Test multi-client configuration prevents "Failed to extract any player response" errors
  - _Requirements: 2.2, 2.4_

- [x] 4. Create comprehensive health endpoints with gated diagnostics




  - Implement enhanced /healthz endpoint with EXPOSE_HEALTH_DIAGNOSTICS environment variable gating
  - Add /health/yt-dlp specific endpoint for yt-dlp diagnostics
  - Include yt_dlp_version, ffmpeg_available boolean, proxy_in_use, last_download_used_cookies in diagnostics
  - Ensure health endpoints never expose file paths or sensitive information
  - Default EXPOSE_HEALTH_DIAGNOSTICS to false for production security
  - _Requirements: 4.1, 4.2, 4.4_

- [x] 5. Enhance deployment script with container-based cache busting





  - Update deploy-apprunner.sh to use container image tagging instead of git tags (don't push git tags for cache-bust)
  - Implement docker build and push with unique GIT_SHA-TIMESTAMP tags
  - Add aws apprunner start-deployment call to force service restart
  - Include deployment verification with health check after restart
  - Test deployment script ensures new code is running, not cached versions
  - _Requirements: 5.1, 5.2, 5.3_

- [x] 6. Improve error message propagation and comprehensive logging







  - Ensure yt-dlp DownloadError messages are preserved and propagated verbatim
  - Implement error message combination with " || " separator for step1 and step2 failures
  - Update _detect_bot_check function to handle combined error messages from both steps
  - Add normalized error string return from helper function for structured logging
  - Cap single log line ≤10k chars to avoid jumbo lines in App Runner logs
  - Track download attempt metadata including cookies_used, client_used, proxy_used without sensitive data
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 7. Fix AWS Secrets Manager proxy secret schema





  - Update AWS Secrets Manager documentation to include required "provider" field in proxy secret JSON
  - Create deployment script to validate existing proxy secrets have all required fields
  - Add example proxy secret JSON with provider, host, port, username, password, protocol fields
  - Test ProxyManager works correctly with updated secret schema
  - Ensure backwards compatibility with existing secrets that have provider field
  - _Requirements: 1.3_

- [x] 8. Clean up code duplications and standardize environment variables








  - Remove duplicate initialization of ProxyManager, ProxyHTTPClient, and UserAgentManager in TranscriptService.__init__
  - Standardize Google OAuth environment variable names between GOOGLE_CLIENT_* and GOOGLE_OAUTH_CLIENT_*
  - Add one-time migration map in deploy script (export GOOGLE_CLIENT_ID="$GOOGLE_CLIENT_ID") to bridge old→new during rollout
  - Update deployment scripts and App Runner configuration to use consistent variable names
  - Ensure google_auth.py code matches the environment variable names used in deployment
  - Test OAuth integration works with consistent environment variable naming
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 9. Implement Content-Type header fixes for Deepgram uploads




  - Create explicit EXT_MIME_MAP dictionary mapping file extensions to correct MIME types
  - Map .m4a and .mp4 to "audio/mp4", .mp3 to "audio/mpeg"
  - Update _send_to_deepgram method to use explicit mapping before mimetypes.guess_type fallback
  - Add fallback to "application/octet-stream" for unknown file extensions
  - Test Content-Type headers are correct for both m4a and mp3 files sent to Deepgram
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 10. Create comprehensive CI smoke test suite with fixtures


  - Implement end-to-end smoke test using stored caption fixtures instead of live YouTube videos
  - Create ASR path smoke test using tiny test MP4 fixture with mocked Deepgram responses
  - Add test cases for both step1 (m4a) and step2 (mp3) download scenarios using fixtures
  - Include cookie scenario testing with fixture files for realistic conditions
  - Configure CI to fail build on smoke test failures to prevent regression deployment
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 11. Add cookie freshness logging and download attempt tracking


  - Implement cookie file mtime and account logging at download start without exposing contents
  - Add last_download_meta tracking in application state for health endpoint exposure
  - Create DownloadAttempt dataclass to track comprehensive download metadata
  - Ensure cookie usage is logged as boolean without exposing file paths or contents
  - Test download attempt metadata is available in health endpoints without sensitive data
  - _Requirements: 4.3, 4.5_

- [ ] 12. Implement backwards compatibility validation and testing



  - Ensure all existing API endpoints return identical response structures after fixes
  - Validate download_audio_with_fallback behaves identically when no cookiefile provided
  - Test transcript service maintains same public interface signatures
  - Verify existing structured log formats are maintained with enhancements
  - Create regression test suite to catch any backwards compatibility breaks
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_