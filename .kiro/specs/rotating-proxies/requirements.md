# Requirements Document

## Introduction

The TL;DW application is experiencing 500 Internal Server Errors when attempting to fetch YouTube video transcripts due to IP blocking from YouTube's servers. This occurs when the App Runner service's IP address gets blocked by YouTube for making too many requests. To resolve this issue, we need to implement a rotating proxy system that distributes requests across multiple IP addresses to avoid detection and blocking.

## Requirements

### Requirement 1

**User Story:** As a user, I want to be able to successfully fetch video transcripts without encountering IP blocking errors, so that I can generate summaries for my YouTube videos.

#### Acceptance Criteria

1. WHEN the application fetches video transcripts THEN it SHALL use rotating proxy servers to distribute requests
2. WHEN a proxy becomes blocked or unavailable THEN the system SHALL automatically switch to the next available proxy
3. WHEN all proxies are temporarily blocked THEN the system SHALL implement exponential backoff and retry logic
4. WHEN transcript fetching succeeds THEN the user SHALL receive their video summaries without errors

### Requirement 2

**User Story:** As a developer, I want a reliable proxy rotation system, so that the application can handle high volumes of transcript requests without being blocked by YouTube.

#### Acceptance Criteria

1. WHEN configuring proxies THEN the system SHALL support multiple proxy providers and types (HTTP/HTTPS/SOCKS5)
2. WHEN a proxy fails THEN the system SHALL mark it as temporarily unavailable and retry after a cooldown period
3. WHEN proxy health is checked THEN the system SHALL validate proxy connectivity and response times
4. IF no proxies are available THEN the system SHALL fall back to direct connections with appropriate rate limiting

### Requirement 3

**User Story:** As a system administrator, I want proxy configuration to be secure and manageable, so that I can easily update proxy settings without code changes.

#### Acceptance Criteria

1. WHEN storing proxy credentials THEN they SHALL be stored securely in AWS Secrets Manager
2. WHEN updating proxy configuration THEN changes SHALL be applied without requiring application restart
3. WHEN monitoring proxy usage THEN the system SHALL log proxy performance and failure rates
4. IF proxy costs exceed budget THEN the system SHALL provide usage monitoring and alerts

### Requirement 4

**User Story:** As a developer, I want the proxy system to be transparent to existing code, so that minimal changes are required to the current transcript fetching logic.

#### Acceptance Criteria

1. WHEN integrating proxy support THEN existing transcript_service.py SHALL require minimal modifications
2. WHEN making HTTP requests THEN the proxy rotation SHALL be handled transparently by a proxy manager
3. WHEN errors occur THEN the system SHALL provide clear error messages distinguishing proxy issues from other failures
4. WHEN testing locally THEN developers SHALL be able to disable proxy usage for development and testing