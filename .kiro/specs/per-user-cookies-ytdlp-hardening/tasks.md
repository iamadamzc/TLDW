# Implementation Plan

- [x] 1. Implement complete cookie-enabled ASR download system


  - Add cookiefile parameter to download_audio_with_fallback function signature in yt_download_helper.py
  - Implement enhanced HTTP headers with Accept, Accept-Encoding, and Referer for hardening
  - Configure concurrent_fragment_downloads=1 and geo_bypass=False for bot detection avoidance
  - Add extractor_args with multiple player_client variants (ios, web_creator, android)
  - Modify error handling to preserve Step 1 errors and combine with Step 2 errors using " || " separator
  - Add current_user_id property to TranscriptService class for explicit user ID injection
  - Implement _resolve_current_user_id method with Flask-Login fallback logic
  - Create _get_user_cookiefile method with S3-first, local-fallback storage strategy
  - Add S3 cookie download functionality with boto3 client and temporary file management
  - Implement local cookie file lookup with configurable directory path
  - Modify _attempt_ytdlp_download method to resolve user cookies and pass to helper
  - Add proper cleanup of temporary S3-downloaded cookie files in finally blocks
  - Ensure backwards compatibility when no cookies are available
  - Create comprehensive unit and integration tests for cookie-enabled download flow
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3, 5.4, 5.5, 6.4, 7.1, 7.2, 7.3, 7.4, 9.3_



- [ ] 2. Enhance Deepgram integration with correct Content-Type headers
  - Create explicit MIME type mapping for common audio formats (.m4a, .mp4, .mp3)
  - Modify _send_to_deepgram method to use explicit mapping before mimetypes.guess_type fallback
  - Add fallback to application/octet-stream for unknown file types


  - Write unit tests for Content-Type header generation based on file extensions
  - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [ ] 3. Create complete cookie upload and management system
  - Create cookies_routes.py blueprint with /account/cookies URL prefix
  - Implement GET /account/cookies route with upload form and user instructions
  - Add POST /account/cookies route with file upload, validation, and storage
  - Create DELETE /account/cookies/delete route for cookie removal
  - Add Netscape format validation with tab and comment detection plus expiry checking
  - Implement 256 KB file size limit enforcement
  - Add dual storage to local directory and S3 (when configured) with security built-in
  - Implement S3 upload with explicit ServerSideEncryption='aws:kms' parameter
  - Create local directory with chmod 700 permissions for security
  - Add proper error handling for S3 access failures with local fallback
  - Create cookie cleanup functionality for both local and S3 storage
  - Import and register cookies_routes blueprint in app.py after existing blueprints


  - Ensure Flask-Login integration works correctly with cookie routes
  - Add application startup validation for cookie storage directories
  - Write comprehensive unit tests for upload validation, storage operations, and security
  - _Requirements: 9.1, 9.4, 9.5, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9_

- [ ] 4. Add comprehensive error handling and monitoring system
  - Implement cookie staleness detection when bot-checks occur with cookies present
  - Add automatic cookie flagging as "stale" in storage to skip usage until re-upload
  - Add warning logs for repeated cookie failures suggesting re-upload
  - Ensure all cookie-related logs exclude cookie file contents
  - Add structured logging for cookie resolution success/failure rates

  - Create granular monitoring metrics for bot-check detection rates with/without cookies
  - Track Step 1 vs Step 2 success rates separately for performance analysis
  - Monitor cookie-present vs cookie-absent download success rates
  - Add DISABLE_COOKIES environment variable as emergency kill-switch
  - Write tests for error scenarios, log content validation, and bot-check regression testing
  - _Requirements: 2.1, 2.2, 2.3, 9.3_

- [x] 5. Create deployment configuration and security hardening




  - Add boto3 to requirements.txt for S3 cookie support
  - Create least-privilege IAM policy restricting access to s3:GetObject/PutObject/DeleteObject on cookies/{user_id}.txt paths only
  - Block S3 bucket listing permissions unless specifically needed
  - Add environment variable configuration for COOKIE_S3_BUCKET, COOKIE_LOCAL_DIR, and DISABLE_COOKIES
  - Update deployment scripts with optional cookie storage environment variables
  - Document rollback procedure and emergency kill-switch usage
  - Create deployment rollback drill documentation
  - _Requirements: 5.1, 9.1, 9.2, 10.10_

- [ ] 6. Implement comprehensive testing and validation suite



  - Create unit tests for cookie resolution with mocked S3 and local storage
  - Add integration tests for end-to-end cookie upload to video download flow
  - Implement security tests for access control and content filtering
  - Create performance tests for cookie resolution impact on request latency and S3 fetch caching needs
  - Add regression tests for bot-check detection with simulated yt-dlp output containing known bot-check phrases
  - Test combined error message handling with and without cookies present
  - Write tests for cookie expiry scenarios and graceful fallback behavior
  - Add tests for emergency kill-switch functionality (DISABLE_COOKIES=true)
  - Create load tests to verify cookie resolution doesn't become a bottleneck
  - _Requirements: All requirements validation through comprehensive test coverage_