# Requirements Document

## Introduction

This feature enhances the YouTube video summarization service by adding per-user cookie support and hardening yt-dlp client emulation to overcome bot detection. The system will allow users to provide their own YouTube cookies to bypass bot checks while maintaining backwards compatibility and preserving existing logging and API structures.

## Requirements

### Requirement 1

**User Story:** As a user experiencing bot detection blocks, I want to provide my own YouTube cookies so that I can successfully download and summarize videos that would otherwise be blocked.

#### Acceptance Criteria

1. WHEN a user has a valid cookie file available THEN the system SHALL pass the cookiefile parameter to yt-dlp for authentication
2. WHEN no user cookies are available THEN the system SHALL continue with existing proxy + user agent behavior unchanged
3. WHEN cookies are used THEN the system SHALL log "Using user cookiefile for yt-dlp (user={user_id})" without exposing cookie contents
4. IF COOKIE_S3_BUCKET environment variable is set AND boto3 is available THEN the system SHALL attempt to download cookies from s3://{bucket}/cookies/{user_id}.txt
5. IF S3 cookie download fails OR COOKIE_S3_BUCKET is not set THEN the system SHALL fallback to local directory lookup at {COOKIE_LOCAL_DIR}/{user_id}.txt

### Requirement 2

**User Story:** As a developer debugging bot detection issues, I want to see the actual yt-dlp error messages so that I can identify when bot checks are triggered and implement appropriate retry logic.

#### Acceptance Criteria

1. WHEN yt-dlp raises a DownloadError THEN the system SHALL propagate the original error message verbatim
2. WHEN the error message contains bot detection indicators THEN the _detect_bot_check() function SHALL properly identify it as a bot check
3. WHEN bot detection is identified THEN the system SHALL set status=bot_check in structured logs
4. WHEN yt-dlp fails THEN the system SHALL raise RuntimeError with the original yt-dlp error message preserved

### Requirement 3

**User Story:** As a system administrator, I want improved yt-dlp client emulation so that downloads are less likely to be flagged as bot traffic.

#### Acceptance Criteria

1. WHEN making yt-dlp requests THEN the system SHALL use enhanced HTTP headers including Accept, Accept-Encoding, and Referer
2. WHEN downloading content THEN the system SHALL set concurrent_fragment_downloads=1 to reduce detection risk
3. WHEN extracting video data THEN the system SHALL use multiple player_client variants (ios, web_creator, android) as extractor arguments
4. WHEN making requests THEN the system SHALL disable geo_bypass to avoid suspicious behavior patterns
5. WHEN configuring yt-dlp THEN the system SHALL maintain existing retry counts and timeout settings

### Requirement 4

**User Story:** As a Flask application user, I want the system to automatically detect my user ID so that my personal cookies are used without manual configuration.

#### Acceptance Criteria

1. WHEN current_user_id is explicitly set on TranscriptService THEN the system SHALL use that user ID for cookie lookup
2. WHEN current_user_id is not set AND Flask-Login is available THEN the system SHALL attempt to get user ID from current_user.id
3. WHEN Flask-Login current_user is not authenticated THEN the system SHALL proceed without user-specific cookies
4. WHEN user ID resolution fails THEN the system SHALL log a warning and continue without cookies

### Requirement 5

**User Story:** As a system operator, I want flexible cookie storage options so that I can choose between S3 and local file storage based on deployment needs.

#### Acceptance Criteria

1. WHEN COOKIE_S3_BUCKET environment variable is set THEN the system SHALL prioritize S3 cookie retrieval
2. WHEN S3 download succeeds THEN the system SHALL create a temporary file and clean it up after use
3. WHEN COOKIE_LOCAL_DIR is set THEN the system SHALL use that directory for local cookie files
4. WHEN COOKIE_LOCAL_DIR is not set THEN the system SHALL default to /app/cookies directory
5. WHEN using local cookie files THEN the system SHALL NOT delete persistent local files after use

### Requirement 6

**User Story:** As an API consumer, I want the existing service interface to remain unchanged so that my integration continues to work without modifications.

#### Acceptance Criteria

1. WHEN the feature is deployed THEN all existing API endpoints SHALL return the same response structure
2. WHEN logging occurs THEN the system SHALL maintain existing structured log formats
3. WHEN errors occur THEN the system SHALL preserve existing error handling patterns
4. WHEN the download_audio_with_fallback function is called without cookiefile parameter THEN it SHALL behave identically to the previous version
5. WHEN TranscriptService methods are called THEN they SHALL maintain the same public interface signatures

### Requirement 7

**User Story:** As a system that relies on 2-step fallback logic, I want both steps to be attempted and real error messages preserved so that bot-check detection works properly upstream.

#### Acceptance Criteria

1. WHEN Step 1 (m4a format) fails with DownloadError THEN the system SHALL record the error message but continue to Step 2
2. WHEN Step 2 (mp3 format) also fails THEN the system SHALL raise RuntimeError containing both Step 1 and Step 2 yt-dlp error messages
3. WHEN combining error messages THEN the system SHALL use " || " as separator between Step 1 and Step 2 messages
4. WHEN upstream bot-check detection runs THEN it SHALL receive the complete error message chain for proper detection

### Requirement 8

**User Story:** As a service sending audio files to Deepgram, I want the correct Content-Type header set based on the actual file format so that transcription requests succeed.

#### Acceptance Criteria

1. WHEN sending .m4a files to Deepgram THEN the system SHALL set Content-Type to audio/mp4 or audio/m4a
2. WHEN sending .mp3 files to Deepgram THEN the system SHALL set Content-Type to audio/mp3
3. WHEN file extension cannot be determined THEN the system SHALL fallback to application/octet-stream
4. WHEN determining MIME type THEN the system SHALL use Python's mimetypes.guess_type() function

### Requirement 9

**User Story:** As a security-conscious administrator, I want user cookies to be properly secured and never exposed in logs so that user privacy is maintained.

#### Acceptance Criteria

1. WHEN storing cookies in S3 THEN the system SHALL use SSE-KMS encryption at rest
2. WHEN accessing S3 cookies THEN the system SHALL use least-privilege IAM with s3:GetObject restricted to cookies/* path only
3. WHEN logging cookie-related events THEN the system SHALL never include cookie file contents in any log messages
4. WHEN users want to remove cookies THEN the system SHALL provide a mechanism for cookie deletion
5. WHEN handling cookie files THEN the system SHALL ensure temporary files are properly cleaned up after use
### Requi
rement 10

**User Story:** As a logged-in user, I want a web interface to upload and manage my YouTube cookies so that I can easily provide authentication for video downloads.

#### Acceptance Criteria

1. WHEN accessing /account/cookies THEN the system SHALL require user authentication via login_required decorator
2. WHEN displaying the upload form THEN the system SHALL provide clear instructions for exporting cookies from Chrome/Brave/Edge
3. WHEN a user uploads a file THEN the system SHALL validate it appears to be Netscape-format cookies (contains tabs and starts with comments)
4. WHEN validating uploaded files THEN the system SHALL enforce a 256 KB maximum file size limit
5. WHEN storing uploaded cookies THEN the system SHALL save to local directory ${COOKIE_LOCAL_DIR}/${user_id}.txt
6. IF COOKIE_S3_BUCKET is configured AND boto3 is available THEN the system SHALL also upload to s3://${COOKIE_S3_BUCKET}/cookies/${user_id}.txt
7. WHEN users want to delete cookies THEN the system SHALL provide a delete endpoint that removes both local and S3 copies
8. WHEN logging cookie operations THEN the system SHALL only log user ID and destination path/URI, never cookie contents
9. WHEN registering the blueprint THEN the system SHALL add it to app.py after existing blueprints
10. WHEN using S3 storage THEN the system SHALL require IAM permissions for s3:GetObject, s3:PutObject, and s3:DeleteObject on cookies/* path