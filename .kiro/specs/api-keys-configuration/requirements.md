# Requirements Document

## Introduction

The TL;DW Flask application is experiencing 500 Internal Server Errors when users attempt to summarize videos. The root cause is missing API keys (OpenAI and Resend) in the AWS App Runner environment. While the API keys are available, they need to be properly configured in AWS Secrets Manager and referenced in the App Runner configuration to be accessible as environment variables within the running application.

## Requirements

### Requirement 1

**User Story:** As a user, I want to be able to summarize videos without encountering 500 Internal Server Errors, so that I can use the core functionality of the TL;DW application.

#### Acceptance Criteria

1. WHEN a user clicks the "summarize" button THEN the application SHALL successfully process the request without 500 errors
2. WHEN the summarizer service attempts to access the OpenAI API THEN the OPENAI_API_KEY environment variable SHALL be available and valid
3. WHEN the email service attempts to send notifications THEN the RESEND_API_KEY environment variable SHALL be available and valid
4. WHEN API calls are made to external services THEN they SHALL authenticate successfully using the provided keys

### Requirement 2

**User Story:** As a developer, I want API keys to be securely stored in AWS Secrets Manager, so that sensitive credentials are not exposed in code or configuration files.

#### Acceptance Criteria

1. WHEN storing API keys THEN they SHALL be created as secrets in AWS Secrets Manager
2. WHEN creating secrets THEN they SHALL use descriptive names that clearly identify their purpose
3. WHEN accessing secrets THEN the App Runner service SHALL have proper IAM permissions to retrieve them
4. IF secrets are updated THEN the App Runner service SHALL be able to access the new values after restart

### Requirement 3

**User Story:** As a developer, I want the apprunner.yaml configuration to properly reference the API key secrets, so that they are injected as environment variables in the running application.

#### Acceptance Criteria

1. WHEN the App Runner service starts THEN the apprunner.yaml SHALL contain proper secrets configuration
2. WHEN referencing secrets THEN the ARN format SHALL be correct and point to existing secrets
3. WHEN the application code accesses environment variables THEN os.environ.get() SHALL return the actual API key values
4. WHEN secrets are injected THEN they SHALL be available to both the summarizer and email services

### Requirement 4

**User Story:** As a developer, I want clear documentation of the API key setup process, so that I can troubleshoot issues and maintain the configuration over time.

#### Acceptance Criteria

1. WHEN setting up API keys THEN step-by-step instructions SHALL be provided for creating secrets in AWS
2. WHEN configuring App Runner THEN the exact apprunner.yaml syntax SHALL be documented with examples
3. WHEN troubleshooting API key issues THEN diagnostic steps SHALL be available to verify configuration
4. IF API keys need to be rotated THEN the process SHALL be documented for updating secrets without service downtime