# Requirements Document

## Introduction

The App Runner service creation is failing with the error "Instance Role have to be provided if passing in RuntimeEnvironmentSecrets." The apprunner.yaml file is correctly configured with secrets references, but the AWS App Runner service needs to be configured with an Instance Role that has permissions to access AWS Secrets Manager. This feature will configure the App Runner service with the proper Instance Role during service creation.

## Requirements

### Requirement 1

**User Story:** As a developer, I want to create an App Runner service with an Instance Role configured, so that the service can access AWS Secrets Manager secrets during deployment.

#### Acceptance Criteria

1. WHEN creating an App Runner service THEN an Instance Role SHALL be specified in the service configuration
2. WHEN the Instance Role is configured THEN the service SHALL have permission to access the specified Secrets Manager secrets
3. WHEN the service is created with the Instance Role THEN the deployment SHALL not fail with "Instance Role have to be provided" error
4. WHEN the service accesses secrets THEN it SHALL successfully retrieve values from AWS Secrets Manager

### Requirement 2

**User Story:** As a developer, I want the Instance Role to have minimal required permissions, so that the service follows security best practices with least privilege access.

#### Acceptance Criteria

1. WHEN the Instance Role is created THEN it SHALL only have `secretsmanager:GetSecretValue` permission
2. WHEN defining permissions THEN the role SHALL only access the specific TLDW secrets (not all secrets)
3. WHEN the role is assumed THEN it SHALL only be assumable by the App Runner service
4. IF additional AWS services are needed THEN permissions SHALL be added incrementally

### Requirement 3

**User Story:** As a developer, I want to configure the Instance Role during App Runner service creation, so that the service is properly configured from the start.

#### Acceptance Criteria

1. WHEN creating the App Runner service THEN the Instance Role ARN SHALL be specified in the service configuration
2. WHEN using automatic deployment THEN the Instance Role SHALL be configured in the initial service creation
3. WHEN the service is created THEN it SHALL immediately have access to the required secrets
4. IF the service creation fails THEN clear error messages SHALL indicate any missing permissions or configuration

### Requirement 4

**User Story:** As a developer, I want clear documentation of the Instance Role setup process, so that I can understand and troubleshoot the configuration.

#### Acceptance Criteria

1. WHEN setting up the Instance Role THEN step-by-step instructions SHALL be provided
2. WHEN troubleshooting access issues THEN common problems and solutions SHALL be documented
3. WHEN the setup is complete THEN verification steps SHALL confirm proper configuration
4. IF changes are needed THEN the process for updating the Instance Role SHALL be documented