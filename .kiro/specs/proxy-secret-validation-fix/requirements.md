# Requirements Document

## Introduction

This feature addresses the proxy configuration secret validation error that prevents the application from accessing the Oxylabs proxy configuration. The health check shows a ValidationException indicating the secret name format is invalid, which causes proxy functionality to fail and results in 407 authentication errors during video downloads.

## Requirements

### Requirement 1

**User Story:** As a system administrator, I want the proxy configuration secret to be accessible with a valid name format, so that the application can authenticate with the proxy service without 407 errors.

#### Acceptance Criteria

1. WHEN the application attempts to read the proxy configuration secret THEN it SHALL use a valid secret name format
2. WHEN the secret name is validated THEN it SHALL contain only alphanumeric characters and allowed special characters (-/_+=.@!)
3. WHEN the secret is successfully retrieved THEN the proxy configuration SHALL be available for yt-dlp operations
4. WHEN proxy authentication works THEN video downloads SHALL not receive 407 authentication errors
5. WHEN the health check runs THEN it SHALL report proxy_config_readable as true

### Requirement 2

**User Story:** As a developer, I want to identify and fix the root cause of the secret name validation error, so that I can ensure the correct secret ARN is being used.

#### Acceptance Criteria

1. WHEN investigating the secret name error THEN the system SHALL identify which secret ARN is being used
2. WHEN the secret ARN is examined THEN it SHALL be verified against the actual secret in AWS Secrets Manager
3. WHEN the secret name format is incorrect THEN it SHALL be corrected to match AWS naming requirements
4. WHEN environment variables reference secrets THEN they SHALL use the correct ARN format
5. WHEN the App Runner service configuration is updated THEN it SHALL reference the corrected secret ARN

### Requirement 3

**User Story:** As a system operator, I want comprehensive validation of all secret configurations, so that I can prevent similar issues with other secrets.

#### Acceptance Criteria

1. WHEN validating secret configurations THEN the system SHALL check all secret ARNs for proper format
2. WHEN secret ARNs are malformed THEN the system SHALL provide clear error messages with correction guidance
3. WHEN secrets are inaccessible THEN the system SHALL distinguish between permission issues and name format issues
4. WHEN the health check validates secrets THEN it SHALL test accessibility of all required secrets
5. WHEN secret validation fails THEN the system SHALL provide actionable troubleshooting information

### Requirement 4

**User Story:** As a deployment engineer, I want the deployment script to validate secret configurations before deployment, so that I can catch secret issues early in the deployment process.

#### Acceptance Criteria

1. WHEN running preflight checks THEN the deployment script SHALL validate all secret ARN formats
2. WHEN secret ARNs are invalid THEN the deployment SHALL fail with clear error messages
3. WHEN secrets are inaccessible THEN the deployment SHALL distinguish between format and permission issues
4. WHEN updating App Runner configuration THEN the deployment SHALL ensure all secret references are valid
5. WHEN deployment completes THEN all secrets SHALL be verified as accessible through health checks

### Requirement 5

**User Story:** As a system administrator, I want to ensure the proxy configuration secret contains valid proxy credentials, so that the application can successfully authenticate with the Oxylabs proxy service.

#### Acceptance Criteria

1. WHEN the proxy secret is retrieved THEN it SHALL contain valid JSON with required proxy configuration fields
2. WHEN proxy credentials are validated THEN they SHALL include host, port, username, and password
3. WHEN proxy configuration is applied THEN yt-dlp SHALL successfully authenticate with the proxy
4. WHEN proxy authentication succeeds THEN video downloads SHALL complete without 407 errors
5. WHEN the health check tests proxy connectivity THEN it SHALL verify actual proxy authentication (not just secret accessibility)