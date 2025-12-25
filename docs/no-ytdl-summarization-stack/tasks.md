# Implementation Plan

## Deployment Strategy
Ship in one PR with feature flags for operational safety:
- **Phase 1**: YouTube API + timed-text + async jobs (ENABLE_YT_API=1, ENABLE_TIMEDTEXT=1)
- **Phase 2**: YouTubei Playwright capture (ENABLE_YOUTUBEI=1, short timeouts)
- **Phase 3**: ASR fallback (ENABLE_ASR_FALLBACK=1, duration caps)

All paths implemented behind env toggles for zero-downtime config changes.

- [x] 1. Set up enhanced transcript service foundation with feature flags


  - Create enhanced TranscriptService class with hierarchical fallback structure behind env flags
  - Add feature flags: ENABLE_YT_API=1, ENABLE_TIMEDTEXT=1, ENABLE_YOUTUBEI=0, ENABLE_ASR_FALLBACK=0
  - Implement comprehensive logging with source attribution and timing metrics
  - Add configuration validation for ASR and email services
  - Create HTTP session with retry logic for timed-text requests
  - _Requirements: 1.1, 1.6, 4.1, 4.4, 5.1, 5.2_



- [ ] 2. Implement YouTube Transcript API as first tier
  - Add get_captions_via_api method using youtube-transcript-api library
  - Implement language fallback logic (en, en-US, es)
  - Add error handling for TranscriptsDisabled and NoTranscriptFound exceptions


  - Write unit tests for API method with various video types
  - _Requirements: 1.1, 5.3_

- [ ] 3. Enhance timed-text endpoints with resilience
  - Refactor existing get_captions_via_timedtext with no-proxy-first strategy
  - Add retry logic with exponential backoff for connection timeouts


  - Implement multiple host fallback (youtube.com → video.google.com)
  - Add comprehensive timeout controls per NFR specifications (5s connect, 15s read)
  - Write unit tests for timed-text method with timeout and retry scenarios
  - _Requirements: 1.2, 1.3, 5.3_

- [ ] 4. Implement UI-agnostic YouTubei transcript capture with safety controls
  - Enhance existing get_transcript_via_youtubei with no-proxy-first strategy
  - Add YouTube reachability preflight check (generate_204 endpoint)
  - Implement Playwright circuit breaker (skip after 3 consecutive timeouts for 10 minutes)


  - Add desktop→mobile URL fallback with 15s navigation timeout
  - Implement cookie format conversion for Playwright compatibility
  - Add scroll-to-transcript logic to handle dynamic UI loading
  - Ensure proper browser cleanup in finally blocks with semaphore concurrency control
  - Write unit tests for YouTubei capture with various UI scenarios and circuit breaker logic
  - _Requirements: 1.4, 5.5, 6.1, 6.2, 6.4_




- [ ] 5. Create ASR fallback system with HLS audio extraction
  - Implement ASRAudioExtractor class with HLS stream interception
  - Add Playwright-based audio URL capture from network responses
  - Integrate ffmpeg audio extraction to WAV format with proper cleanup
  - Implement Deepgram API integration for audio transcription
  - Add cost control guards (duration limits, quotas) per NFR specifications
  - Write unit tests for ASR system with mocked audio extraction and API calls


  - _Requirements: 1.5, 4.2, 4.3_

- [ ] 6. Implement async job processing system with concurrency controls
  - Create JobManager class with ThreadPoolExecutor for background processing
  - Add semaphore-based concurrency control to prevent browser/CPU saturation
  - Implement job status tracking with queued→processing→done→error states
  - Add job submission endpoint returning immediate 202 responses within 500ms



  - Create job status query endpoint for monitoring job progress
  - Add per-video error isolation so individual failures don't stop entire job
  - Write unit tests for job lifecycle and concurrent job handling
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [ ] 7. Enhance VideoSummarizer with bullet-proof parameter validation
  - Refactor summarize_video method with keyword-only transcript_text and video_id parameters


  - Add strict input validation to check for empty/invalid transcript text
  - Implement graceful handling returning "No transcript available" for empty input
  - Add comprehensive error handling to prevent pipeline crashes
  - Ensure LLM is never called with empty text to avoid API costs
  - Write unit tests for summarizer with various input scenarios including edge cases
  - _Requirements: 3.2, 5.4_




- [ ] 8. Update EmailService for consolidated digest delivery with fault tolerance
  - Refactor send_digest_email to accept flat list of video items with strict schema
  - Update email template to handle missing fields gracefully with default values
  - Implement single email per job (not per video) consolidation
  - Add HTML escaping and responsive email template design
  - Ensure email template never crashes on malformed data (title="(Untitled)", url="#")
  - Add single-attempt email delivery (no retries) with proper error logging
  - Write unit tests for email service with various item configurations and edge cases
  - _Requirements: 3.1, 3.3, 3.4_

- [ ] 9. Integrate enhanced transcript service into job workflow
  - Update _run_summarize_job to use new hierarchical transcript acquisition
  - Add per-video error handling that doesn't stop entire job processing
  - Implement transcript source logging for observability
  - Add timing metrics collection for performance monitoring
  - Write integration tests for complete job workflow
  - _Requirements: 1.6, 2.5, 5.1, 5.2_

- [ ] 10. Update API routes with async job processing
  - Refactor /api/summarize endpoint to use JobManager for immediate 202 responses
  - Add proper request validation for video_ids parameter
  - Implement job status endpoint /api/jobs/<job_id> for progress tracking
  - Add comprehensive error handling and user feedback messages
  - Write unit tests for API endpoints with various request scenarios
  - _Requirements: 2.1, 2.2, 7.1, 7.2, 7.3_

- [x] 11. Add configuration management and validation



  - Implement ConfigValidator class for ASR and email configuration validation
  - Add environment variable validation on service startup
  - Create configuration documentation with default values and validation rules
  - Add runtime configuration checks for ASR enablement
  - Write unit tests for configuration validation with various env scenarios
  - _Requirements: 4.1, 4.4, 5.4_

- [x] 12. Implement comprehensive error handling and logging



  - Add structured logging for transcript attempts with source attribution
  - Implement job-level error handling with partial success support
  - Add performance metrics logging (timing, success rates)
  - Ensure proper cleanup of resources (browsers, temp files) in error scenarios
  - Write unit tests for error handling and resource cleanup
  - _Requirements: 5.1, 5.2, 5.3, 5.5_

- [ ] 13. Add security enhancements for cookie and credential handling


  - Implement secure cookie storage with encryption at rest
  - Add TTL enforcement with automatic cleanup after 24 hours
  - Ensure cookies are only sent to YouTube domains
  - Add log redaction to prevent credential exposure
  - Write unit tests for security features and credential protection
  - _Requirements: 6.1, 6.2, 6.3_

- [x] 14. Create comprehensive test suite



  - Implement test matrix scenarios (public videos, restricted videos, ASR cases)
  - Add performance tests for 202 response time and per-video processing budgets
  - Create integration tests for complete pipeline with various video types
  - Add reliability tests for external service failures and proxy issues
  - Write end-to-end tests for email delivery and job completion
  - _Requirements: All requirements validation_

- [x] 15. Add monitoring and observability features



  - Implement TranscriptMetrics class for structured performance logging
  - Add health check endpoints with dependency status reporting
  - Create job completion metrics with success/failure rates
  - Add alerting for critical failures and performance degradation
  - Write unit tests for monitoring and metrics collection
  - _Requirements: 5.1, 5.2_

- [x] 16. Update frontend for async job processing



  - Modify handleSummarize function to handle 202 responses properly
  - Update UI to show job submission confirmation instead of processing spinner
  - Add proper error handling for various API response scenarios
  - Implement user feedback messages for job status and email delivery
  - Write frontend tests for async job submission and error handling
  - _Requirements: 7.1, 7.4, 7.5_

## Configuration Reference

### Feature Flags (Operational Safety)
```bash
# Phase 1 - Core captions (ship first)
ENABLE_YT_API=1              # YouTube Transcript API
ENABLE_TIMEDTEXT=1           # Direct timed-text endpoints

# Phase 2 - UI capture (enable after Phase 1 stable)
ENABLE_YOUTUBEI=0            # Playwright YouTubei capture

# Phase 3 - ASR fallback (enable for premium users)
ENABLE_ASR_FALLBACK=0        # HLS audio → Deepgram

# Performance & Safety Controls
PW_NAV_TIMEOUT_MS=15000      # Playwright navigation timeout
USE_PROXY_FOR_TIMEDTEXT=0    # No-proxy first for timed-text
ASR_MAX_VIDEO_MINUTES=20     # Skip ASR above duration
WORKER_CONCURRENCY=2         # Background job threads
```

### Reliability Features
- **Circuit breaker**: Auto-skip Playwright after 3 consecutive timeouts (10min cooldown)
- **Preflight check**: Ping YouTube reachability before browser automation
- **Semaphore control**: Prevent browser/CPU saturation with concurrency limits
- **Per-video isolation**: Individual video failures don't stop entire job
- **Graceful degradation**: Always send email even with partial failures