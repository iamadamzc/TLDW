# Requirements Document

## Introduction

This feature implements a robust transcript acquisition and summarization pipeline that operates without yt-dlp dependency. The system provides a reliable "always summarize" behavior by implementing a hierarchical fallback strategy for obtaining video transcripts, followed by AI-powered summarization and email delivery. The solution is designed for containerized deployment (App Runner) with optional residential proxy support and integrates with existing authentication and email systems.

## Requirements

### Requirement 1

**User Story:** As a user, I want the system to reliably obtain transcripts from YouTube videos using multiple fallback methods, so that I can receive summaries even when primary caption sources are unavailable.

#### Acceptance Criteria

1. WHEN a video transcript is requested THEN the system SHALL attempt YouTube Transcript API first as the fastest and most reliable method
2. IF YouTube Transcript API fails THEN the system SHALL attempt direct timed-text endpoints without proxy initially
3. IF timed-text endpoints fail without proxy THEN the system SHALL retry with proxy if available
4. IF all caption methods fail THEN the system SHALL attempt UI-agnostic transcript capture via Playwright
5. IF UI-agnostic capture fails AND ASR is enabled THEN the system SHALL extract audio via HLS and transcribe using Deepgram
6. WHEN any method succeeds THEN the system SHALL cache the transcript with appropriate TTL and source metadata

### Requirement 2

**User Story:** As a user, I want the system to process video summarization requests asynchronously, so that I receive immediate feedback and don't experience timeouts during processing.

#### Acceptance Criteria

1. WHEN a summarization request is submitted THEN the system SHALL return HTTP 202 immediately with a job_id
2. WHEN the request is accepted THEN the system SHALL start background processing using a worker thread
3. WHEN processing begins THEN the system SHALL update job status to track progress
4. WHEN processing completes THEN the system SHALL send a single digest email with all video summaries
5. IF processing fails THEN the system SHALL log errors and update job status appropriately

### Requirement 3

**User Story:** As a user, I want to receive well-formatted email summaries with video details, so that I can quickly review content without visiting each video individually.

#### Acceptance Criteria

1. WHEN summaries are ready THEN the system SHALL send one consolidated email per request
2. WHEN building email content THEN the system SHALL include title, thumbnail, video URL, and summary for each video
3. IF a transcript is unavailable THEN the system SHALL include "No transcript available" message instead of summary
4. WHEN generating summaries THEN the system SHALL use explicit parameters to prevent argument confusion
5. WHEN email template renders THEN the system SHALL handle missing fields gracefully without crashes

### Requirement 4

**User Story:** As a system administrator, I want configurable ASR fallback controls, so that I can manage costs and enable premium features appropriately.

#### Acceptance Criteria

1. WHEN ASR fallback is disabled THEN the system SHALL skip audio extraction and Deepgram processing
2. WHEN ASR fallback is enabled THEN the system SHALL only process videos within configured duration limits
3. WHEN ASR processing occurs THEN the system SHALL respect cost guard rails and user quotas
4. WHEN configuration changes THEN the system SHALL apply new settings without requiring restart
5. IF ASR limits are exceeded THEN the system SHALL log the event and skip ASR processing

### Requirement 5

**User Story:** As a developer, I want comprehensive logging and error handling, so that I can troubleshoot issues and monitor system performance effectively.

#### Acceptance Criteria

1. WHEN each transcript method is attempted THEN the system SHALL log the attempt and outcome
2. WHEN a transcript is successfully obtained THEN the system SHALL log the source method used
3. WHEN errors occur THEN the system SHALL log detailed error information without crashing the pipeline
4. WHEN browser automation is used THEN the system SHALL ensure proper cleanup in finally blocks
5. WHEN proxy connectivity issues occur THEN the system SHALL fall back to direct connections gracefully

### Requirement 6

**User Story:** As a user, I want the system to handle various video types and access restrictions, so that I can summarize both public and restricted content when I have appropriate access.

#### Acceptance Criteria

1. WHEN processing restricted videos THEN the system SHALL use provided user cookies for authentication
2. WHEN cookies are available THEN the system SHALL convert them to appropriate format for each method
3. WHEN accessing timed-text endpoints THEN the system SHALL try multiple language variants and caption types
4. WHEN using browser automation THEN the system SHALL handle consent dialogs and UI interactions
5. IF video access is denied THEN the system SHALL log the restriction and continue with other videos

### Requirement 7

**User Story:** As a user, I want the frontend to provide clear feedback during processing, so that I understand the system is working and know when to expect results.

#### Acceptance Criteria

1. WHEN I submit a summarization request THEN the UI SHALL show loading state immediately
2. WHEN the server responds THEN the UI SHALL stop loading regardless of response type
3. WHEN the request is accepted THEN the UI SHALL display confirmation message about email delivery
4. IF the request fails THEN the UI SHALL display appropriate error message
5. WHEN processing multiple videos THEN the UI SHALL indicate that results will be delivered via email

## Non-Functional Requirements (NFRs)

### Performance

- `/api/summarize` must respond 202 within ≤ 500 ms p95 with `{job_id, status:"queued"}`
- Per-video transcript attempt budget ≤ 45 s total:
  - Timed-text: connect 5 s, read 15 s, ≤ 2 attempts, alt host retry
  - YouTubei (Playwright): nav timeout 15 s; try desktop→mobile, no-proxy→proxy; max 4 attempts; always close browser
  - ASR (if enabled): ffmpeg + upload + transcription ≤ 120 s per video (skip if > ASR_MAX_VIDEO_MINUTES)

### Reliability

- Public videos with captions: transcript success rate ≥ 98% (via YouTube Transcript API or timed-text)
- Any video: pipeline must never crash; if no text, return summary string "No transcript available." (email still sends)
- Email delivery: attempt send once per job; if API <200/≥300, log and mark job error without retries

### Resource Limits

- WORKER_CONCURRENCY default 2; queue in-process (ThreadPoolExecutor)
- Playwright launched headless with `--no-sandbox --disable-dev-shm-usage`

### Configuration (Authoritative)

| ENV | Default | Purpose |
|-----|---------|---------|
| ENABLE_ASR_FALLBACK | 0 | Gate ASR for premium only |
| ASR_MAX_VIDEO_MINUTES | 20 | Skip ASR above this length |
| USE_PROXY_FOR_TIMEDTEXT | 0 | Timed-text is no-proxy first |
| PW_NAV_TIMEOUT_MS | 15000 | Playwright navigation timeout |
| WORKER_CONCURRENCY | 2 | Background worker threads |
| RESEND_API_KEY, SENDER_EMAIL | — | Email sending (accept any 2xx) |
| DEEPGRAM_API_KEY | — | ASR provider key |

All settings are hot-reload via env at container start; no code changes required.

### Observability

- Log each per-video decision as: `transcript_source=yt_api|timedtext|youtubei|asr|none`
- Log timing per step (`t_timedtext_ms`, `t_yti_ms`, `t_asr_ms`), and job state `queued|processing|done|error`
- Redact secrets/cookies in logs; never log raw proxy creds or cookie values

### Security & Privacy

- User-provided YouTube cookies are encrypted at rest, TTL 24 h, auto-delete after TTL
- Cookies never leave the container except to the target domains; not included in logs
- No persistent storage of raw audio; temporary WAVs deleted at job end

### Email Contract (Strict)

Input to `EmailService.send_digest_email(to, items)` is a flat list of dicts:
```json
[
  {
    "title": "Video title",
    "thumbnail_url": "https://…jpg", 
    "video_url": "https://www.youtube.com/watch?v=ID",
    "summary": "…or 'No transcript available.'"
  }
]
```

Missing fields must not throw; template renders defaults (title "(Untitled)", empty thumb, # link). Exactly one email per request (not per video).

### Proxy Policy

- Do not use proxy for timed-text by default; only if `USE_PROXY_FOR_TIMEDTEXT=1`
- YouTubei/Playwright: try no-proxy first, then proxy; always short timeouts

### Test Matrix (Must Pass)

- Public video with human captions → `source=yt_api`, email sent
- Public video with auto captions only → `source=timedtext` or `yt_api`, email sent  
- Public video no captions, ASR disabled → `source=none`, summary string is "No transcript available.", email sent
- Public video no captions, ASR enabled → `source=asr`, email sent
- Restricted video with uploaded cookies → one of the sources succeeds; else "No transcript available.", email sent
- YouTube Shorts with captions → treated like any other (no special casing)

### Out-of-Scope (To Prevent Creep)

- No yt-dlp reintroduction; no persistent audio/video downloads
- No non-YouTube sites
- No in-app live rendering of summaries (email-only delivery)
- No webhooks/push notifications beyond the email
- No translation or multi-language summarization (English only, for now)