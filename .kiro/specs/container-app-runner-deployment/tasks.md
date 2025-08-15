# Implementation Plan

- [x] 1. Update Dockerfile with optimized configuration






  - Replace current Dockerfile with minimal, known-good version using Python 3.11 slim base
  - Add environment variables for Python optimization (PYTHONDONTWRITEBYTECODE, PYTHONUNBUFFERED)
  - Simplify system dependency installation to only include ffmpeg
  - Add non-root user setup: `RUN useradd -m app && chown -R app:app /app` and `USER app`
  - Pin yt-dlp version in requirements.txt (e.g., yt-dlp==2024.08.06) to avoid extractor changes
  - Update Gunicorn CMD with proper configuration and log level
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [ ] 2. Enhance wsgi.py with dev override and ffmpeg path export






  - Add ALLOW_MISSING_DEPS environment variable support (default false for prod safety)
  - Implement _check_binary() function with graceful failure handling
  - Create log_startup_dependencies() function to replace current verification
  - Export FFMPEG_LOCATION environment variable when ffmpeg is available
  - Log exact binary paths and versions used, fail fast if missing in production
  - Include FFMPEG_LOCATION in startup logs for debugging
  - Update import structure to ensure app object is properly exposed
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3_

- [x] 3. Update yt-dlp calls to use explicit ffmpeg location



  - Modify transcript_service.py to include --ffmpeg-location from FFMPEG_LOCATION env (fallback /usr/bin)
  - Add socket timeout configuration to yt-dlp options
  - Ensure consistent proxy and user agent configuration from request chain
  - Add logging before yt-dlp calls: session=<sid> ua_applied=true for debugging
  - Test yt-dlp functionality with explicit ffmpeg path
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 4. Handle apprunner.yaml file migration


  - Check for existing apprunner.yaml file in repository
  - Remove/rename apprunner.yaml so App Runner can't choose source runtime
  - Update any CI/CD references to use ECR image mode deployment
  - Ensure CI deploy path uses ECR image mode with empty Start command (use Dockerfile CMD)
  - Verify apprunner.container.yaml is properly configured for image mode
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 5. Create deployment documentation and scripts


  - Create ECR repository creation commands
  - Write Docker build and push scripts including `aws ecr get-login-password | docker login`
  - Include standard tag and push snippet for ECR deployment
  - Document App Runner configuration: health path /healthz, port 8080, no override start command
  - Create deployment verification checklist
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 6. Add MVP testing for container deployment


  - Create Docker build smoke test (verify ffmpeg present in container)
  - Add wsgi.py dependency check test (passes/fails with ALLOW_MISSING_DEPS scenarios)
  - Create yt-dlp integration test with --ffmpeg-location parameter
  - Add test for /health and /healthz endpoints returning 200 with dependency status
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

- [x] 7. Update health check endpoints with enhanced dependency reporting


  - Modify /health and /healthz endpoints to use new dependency checking
  - Add ffmpeg_location and yt_dlp_version fields to JSON response
  - Return 503 if critical deps missing (unless ALLOW_MISSING_DEPS=true, then 200 with degraded=true)
  - Test health check response format and status codes
  - _Requirements: 7.2, 7.3_

## Final Acceptance Criteria

- [ ] App Runner deploys successfully from ECR image with service healthy on /healthz
- [ ] Startup logs show non-None paths for ffmpeg, ffprobe, and yt-dlp with versions
- [ ] Summarize flow completes for 1-3 public videos:
  - Attempt 1 may bot-check → rotate once → Attempt 2 downloads audio via proxy
  - No "ffmpeg/ffprobe not found" errors in logs
  - Email sent with summary successfully
  - Zero "407 Proxy Authentication Required" errors in logs