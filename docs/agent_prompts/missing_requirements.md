### Requirement 9: S3 Cookie Storage Integration

**User Story:** As a user who has uploaded cookies via the app's cookie upload function, I want the transcript service to automatically load my cookies from S3 storage so that I can access restricted videos without manual cookie configuration.

#### Acceptance Criteria

1. WHEN a user_id is provided THEN the system SHALL attempt to load cookies from `s3://tldw-cookies-bucket/cookies/{user_id}.txt`
2. WHEN loading cookies from S3 THEN it SHALL parse Netscape format cookie files correctly
3. WHEN S3 cookie loading fails THEN it SHALL log the error and fallback to environment/file cookies
4. WHEN cookies are successfully loaded from S3 THEN it SHALL log the number of cookies loaded (without values)
5. WHEN no S3 cookies exist for a user THEN it SHALL operate without user-specific cookies

### Requirement 10: YouTubei Timeout Protection

**User Story:** As a transcript processing system, I want YouTubei operations to have strict timeout limits so that the system doesn't hang indefinitely on problematic videos.

#### Acceptance Criteria

1. WHEN get_transcript_via_youtubei is called THEN it SHALL enforce a maximum operation time of 150 seconds
2. WHEN timeout is approaching THEN it SHALL abort current attempts and move to next fallback
3. WHEN Playwright operations exceed navigation timeout THEN they SHALL be terminated gracefully
4. WHEN YouTubei times out THEN it SHALL trigger the circuit breaker appropriately
5. WHEN maximum operation time is reached THEN it SHALL log timeout warnings and return empty string

### Requirement 11: Direct HTTP Cookie Authentication

**User Story:** As a system bypassing YouTube Transcript API limitations, I want direct HTTP requests to properly authenticate with user cookies so that restricted content can be accessed.

#### Acceptance Criteria

1. WHEN making direct HTTP transcript requests THEN it SHALL include proper YouTube headers (User-Agent, Referer)
2. WHEN user cookies are available THEN they SHALL be included in Cookie headers for authentication
3. WHEN cookie authentication fails THEN it SHALL log XML parsing errors as YouTube blocking indicators
4. WHEN transcript list requests succeed THEN it SHALL attempt individual transcript fetches with same authentication
5. WHEN both S3 cookies and environment cookies are available THEN it SHALL prefer S3 cookies for user context

### Requirement 12: Circuit Breaker Integration

**User Story:** As a system protecting against cascading failures, I want proper circuit breaker behavior so that repeated Playwright failures don't overwhelm the system.

#### Acceptance Criteria

1. WHEN 3 consecutive Playwright timeouts occur THEN the circuit breaker SHALL activate for 10 minutes
2. WHEN circuit breaker is active THEN YouTubei operations SHALL be skipped with appropriate logging
3. WHEN a Playwright operation succeeds THEN the failure count SHALL reset to zero
4. WHEN circuit breaker activates THEN it SHALL log clear warnings about the protection
5. WHEN circuit breaker is active THEN the system SHALL continue with remaining fallback methods

### Requirement 13: Enhanced Error Detection

**User Story:** As a developer debugging transcript failures, I want specific error identification so that I can distinguish between different types of YouTube blocking and access issues.

#### Acceptance Criteria

1. WHEN "no element found: line 1, column 0" error occurs THEN it SHALL be identified as YouTube anti-bot blocking
2. WHEN empty XML responses are received THEN they SHALL be logged with response content preview
3. WHEN TimeoutError exceptions occur THEN they SHALL trigger circuit breaker registration
4. WHEN proxy vs direct connection attempts fail THEN they SHALL be logged separately for comparison
5. WHEN authentication vs content issues occur THEN they SHALL be distinguished in error messages

Recommended Changes to Existing Requirements
Requirement 1 - Add S3 Integration
Add this acceptance criteria:
6. WHEN loading cookies THEN it SHALL first attempt S3 bucket loading with load_user_cookies_from_s3(user_id)
7. WHEN S3 cookies are found THEN they SHALL take precedence over environment/file cookies
Requirement 3 - Add Timeout Logging
Add this acceptance criteria:
6. WHEN YouTubei operations approach timeout THEN it SHALL log remaining time warnings
7. WHEN operations are aborted due to timeout THEN it SHALL log the abort reason and elapsed time
Requirement 6 - Add Circuit Breaker Errors
Add this acceptance criteria:
6. WHEN circuit breaker activates THEN it SHALL log "Playwright circuit breaker activated - skipping for 10 minutes"
7. WHEN circuit breaker blocks operations THEN they SHALL be skipped with appropriate logging