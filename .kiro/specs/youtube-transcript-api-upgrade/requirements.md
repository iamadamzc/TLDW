# Requirements Document

## Introduction

This spec covers upgrading the TL;DW codebase from youtube-transcript-api version 0.6.2 to version 1.2.2. The API has changed significantly between versions, requiring updates to all transcript fetching code to use the new API structure.

## Requirements

### Requirement 1: Update Library Version

**User Story:** As a developer, I want to use the latest version of youtube-transcript-api (1.2.2) so that I have access to the most recent features and bug fixes.

#### Acceptance Criteria

1. WHEN the requirements.txt file is updated THEN youtube-transcript-api SHALL be set to version 1.2.2
2. WHEN the application starts THEN it SHALL successfully import the new API without errors
3. WHEN checking the installed version THEN it SHALL report 1.2.2

### Requirement 2: Update API Usage in Core Services

**User Story:** As a system, I want to use the correct API methods from youtube-transcript-api 1.2.2 so that transcript fetching continues to work properly.

#### Acceptance Criteria

1. WHEN transcript_service.py uses the API THEN it SHALL use the new instance-based methods (list() and fetch())
2. WHEN the API is called THEN it SHALL NOT use the deprecated static methods (get_transcript, list_transcripts)
3. WHEN transcript fetching fails THEN the system SHALL provide clear error messages about the new API structure

### Requirement 3: Update Test Files

**User Story:** As a developer, I want all test files to use the correct API so that testing continues to work with the new version.

#### Acceptance Criteria

1. WHEN test_api.py runs THEN it SHALL successfully fetch transcripts using the new API
2. WHEN other test files run THEN they SHALL use the correct API methods
3. WHEN tests fail THEN they SHALL provide clear information about API usage

### Requirement 4: Maintain Proxy and Cookie Support

**User Story:** As a system, I want to continue using proxies and cookies with the new API so that restricted video access is maintained.

#### Acceptance Criteria

1. WHEN using proxies THEN the new API SHALL accept proxy configuration
2. WHEN using cookies THEN the new API SHALL accept cookie files or headers
3. WHEN both are used together THEN they SHALL work without conflicts

### Requirement 5: Backward Compatibility Handling

**User Story:** As a system, I want graceful handling of API differences so that the upgrade doesn't break existing functionality.

#### Acceptance Criteria

1. WHEN the old API methods are referenced THEN the system SHALL provide clear migration guidance
2. WHEN errors occur THEN they SHALL indicate whether it's an API version issue
3. WHEN debugging THEN logs SHALL clearly show which API version is being used

### Requirement 6: Update Documentation and Examples

**User Story:** As a developer, I want updated documentation and examples so that I understand how to use the new API.

#### Acceptance Criteria

1. WHEN viewing code comments THEN they SHALL reflect the new API usage
2. WHEN looking at example files THEN they SHALL demonstrate correct 1.2.2 usage
3. WHEN troubleshooting THEN documentation SHALL provide migration guidance