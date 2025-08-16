# Requirements Document

## Introduction

This feature focuses on cleaning up code duplications, standardizing environment variable naming conventions, and improving overall code maintainability across the TLDW application. The goal is to eliminate redundant code, ensure consistent naming patterns, and improve the developer experience without affecting existing functionality.

## Requirements

### Requirement 1

**User Story:** As a developer, I want consistent environment variable naming across all application components, so that configuration is predictable and deployment is reliable.

#### Acceptance Criteria

1. WHEN reviewing OAuth configuration THEN all files SHALL use consistent `GOOGLE_OAUTH_CLIENT_*` environment variable names
2. WHEN deploying the application THEN deployment scripts SHALL use the same environment variable names as the application code
3. WHEN configuring App Runner THEN the configuration SHALL match the environment variable names expected by the application
4. IF any inconsistent variable names exist THEN they SHALL be updated to use the standard format

### Requirement 2

**User Story:** As a developer, I want to eliminate duplicate code initializations, so that the codebase is more maintainable and less prone to bugs.

#### Acceptance Criteria

1. WHEN examining service classes THEN each manager or client SHALL be initialized exactly once
2. WHEN reviewing TranscriptService THEN ProxyManager, ProxyHTTPClient, and UserAgentManager SHALL have single initialization points
3. IF duplicate initializations exist THEN they SHALL be removed while preserving functionality
4. WHEN refactoring initialization code THEN all existing functionality SHALL continue to work unchanged

### Requirement 3

**User Story:** As a developer, I want consistent import patterns and code organization, so that the codebase follows established conventions.

#### Acceptance Criteria

1. WHEN reviewing import statements THEN duplicate imports SHALL be eliminated
2. WHEN examining class structures THEN initialization patterns SHALL be consistent across similar classes
3. WHEN refactoring code THEN existing API contracts SHALL be preserved
4. IF code organization improvements are made THEN they SHALL not break existing functionality

### Requirement 4

**User Story:** As a developer, I want comprehensive tests to verify cleanup changes, so that refactoring doesn't introduce regressions.

#### Acceptance Criteria

1. WHEN cleanup changes are made THEN automated tests SHALL verify environment variable consistency
2. WHEN refactoring initialization code THEN tests SHALL confirm no duplicate initializations exist
3. WHEN updating configuration THEN OAuth integration SHALL continue to work correctly
4. IF any cleanup breaks functionality THEN the changes SHALL be reverted and fixed