# Requirements Document

## Introduction

This feature consolidates the current three deployment scripts into a single, reliable deployment process that properly handles App Runner service updates and image recognition. The solution addresses issues with multiple confusing scripts, App Runner not recognizing new images, and services not restarting properly after deployments.

## Requirements

### Requirement 1

**User Story:** As a developer, I want a single deployment script that handles both new service creation and existing service updates, so that I don't have to choose between multiple confusing scripts.

#### Acceptance Criteria

1. WHEN I run the deployment script THEN it SHALL automatically detect if an App Runner service exists
2. WHEN the service doesn't exist THEN the script SHALL create a new service with proper configuration
3. WHEN the service exists THEN the script SHALL update the existing service with the new image
4. WHEN the deployment completes THEN there SHALL be only one script to maintain and use
5. WHEN I need to deploy THEN I SHALL not need to remember which script to use for which scenario

### Requirement 2

**User Story:** As a developer, I want the deployment script to use unique image tags based on git commits, so that App Runner can properly recognize and deploy new images.

#### Acceptance Criteria

1. WHEN building a Docker image THEN the script SHALL tag it with the current git commit hash
2. WHEN no git repository exists THEN the script SHALL use a timestamp-based tag as fallback
3. WHEN pushing to ECR THEN the script SHALL push both the commit-tagged image and update the latest tag
4. WHEN updating App Runner THEN it SHALL reference the specific commit-tagged image URI
5. WHEN App Runner checks for updates THEN it SHALL recognize the new image due to the unique tag
6. WHEN deployment completes THEN the script SHALL verify DeployedImageDigest equals ECR imageDigest for the target tag before declaring success
7. WHEN --force-latest flag is used THEN the script SHALL trigger start-deployment after update-service

### Requirement 3

**User Story:** As a developer, I want the deployment script to properly update App Runner services and wait for completion, so that I know when the deployment is actually finished and working.

#### Acceptance Criteria

1. WHEN updating an App Runner service THEN the script SHALL use the correct AWS API call with proper parameters
2. WHEN the update is initiated THEN the script SHALL wait for the deployment to complete
3. WHEN waiting for deployment THEN the script SHALL poll the service status every 15 seconds
4. WHEN the deployment completes THEN the script SHALL verify the service is running with the correct image
5. WHEN the deployment fails THEN the script SHALL provide clear error messages and exit with proper status codes
6. WHEN the deployment times out THEN the script SHALL report the timeout and current status
7. WHEN deployment is considered successful THEN describe-service SHALL report Status=RUNNING and DeployedImageDigest equals the ECR digest for the target tag
8. WHEN health verification fails THEN the script SHALL update the service back to the previous image tag and repeat the wait + health sequence
9. WHEN the script fails deployment THEN it SHALL fail if /healthz indicates missing critical dependencies (ffmpeg/yt-dlp) or returns non-200
10. WHEN health fails THEN the script SHALL print the first 50 lines of recent App Runner logs for quick triage

### Requirement 4

**User Story:** As a developer, I want the deployment script to handle AutoDeployments configuration properly, so that App Runner behaves predictably during updates.

#### Acceptance Criteria

1. WHEN creating a new service THEN AutoDeployments SHALL be enabled for automatic ECR updates
2. WHEN updating an existing service THEN AutoDeployments SHALL be temporarily disabled during manual updates
3. WHEN the manual update completes THEN AutoDeployments SHALL be re-enabled if it was previously enabled
4. WHEN AutoDeployments is disabled THEN App Runner SHALL not interfere with manual image updates
5. WHEN AutoDeployments is enabled THEN App Runner SHALL automatically deploy future ECR pushes to the same tag
6. WHEN using manual commit-tag deploys THEN the script SHALL set AutoDeploymentsEnabled=false, then restore to its prior boolean after successful validation
7. WHEN AutoDeployments is relied upon THEN it SHALL only be used for a stable tag (e.g., :latest); manual updates SHALL pin to an immutable tag

### Requirement 5

**User Story:** As a developer, I want comprehensive error handling and logging throughout the deployment process, so that I can quickly identify and fix issues when deployments fail.

#### Acceptance Criteria

1. WHEN any step fails THEN the script SHALL provide clear, actionable error messages
2. WHEN AWS CLI is not configured THEN the script SHALL detect this and provide setup instructions
3. WHEN Docker is not running THEN the script SHALL detect this and provide startup instructions
4. WHEN ECR login fails THEN the script SHALL provide authentication troubleshooting steps
5. WHEN the Docker build fails THEN the script SHALL show the build error and suggest common fixes
6. WHEN App Runner operations fail THEN the script SHALL show the AWS error and suggest solutions
7. WHEN the script succeeds THEN it SHALL provide a summary with service URL and test endpoints
8. WHEN preflight checks run THEN the script SHALL verify Docker daemon, AWS creds/region, ECR login, and service health path alignment
9. WHEN the script verifies secrets THEN it SHALL confirm the instance role policy includes secretsmanager:GetSecretValue for the ARN referenced by OXYLABS_PROXY_CONFIG, and warn/fail if mismatched
10. WHEN outputting results THEN the script SHALL show the deployed tag, deployed digest, and service URL; with --tail flag, stream logs until healthy

### Requirement 6

**User Story:** As a developer, I want the deployment script to clean up old deployment scripts and provide migration guidance, so that the codebase is simplified and maintainable.

#### Acceptance Criteria

1. WHEN the new script is implemented THEN it SHALL identify the old deployment scripts
2. WHEN old scripts exist THEN the new script SHALL offer to archive or remove them
3. WHEN migrating THEN the script SHALL preserve any custom configuration from old scripts
4. WHEN cleanup is complete THEN only the new unified script SHALL remain active
5. WHEN documentation is updated THEN it SHALL reference only the new deployment process
6. WHEN ECR cleanup is enabled THEN the script SHALL optionally prune ECR images older than N versions (configurable)

### Requirement 7

**User Story:** As a developer, I want the deployment script to validate the deployment was successful, so that I can be confident the application is working correctly.

#### Acceptance Criteria

1. WHEN deployment completes THEN the script SHALL test the health check endpoint
2. WHEN the health check passes THEN the script SHALL report successful deployment
3. WHEN the health check fails THEN the script SHALL provide troubleshooting guidance
4. WHEN testing endpoints THEN the script SHALL verify the service URL is accessible
5. WHEN validation completes THEN the script SHALL provide next steps for further testing
6. WHEN validating health THEN the script SHALL GET https://<service-url>/healthz and fail if status != healthy or dependencies.ffmpeg/yt_dlp.available == false
7. WHEN validating secrets THEN the script SHALL confirm the configured proxy secret is readable by the service (without exposing secret values)

### Requirement 8

**User Story:** As a developer, I want advanced deployment options and observability features, so that I can handle different deployment scenarios and debug issues effectively.

#### Acceptance Criteria

1. WHEN using --dry-run flag THEN the script SHALL print the steps and JSON payloads (redacting secrets) without applying changes
2. WHEN service name is known THEN the script SHALL detect ARN and region automatically via describe-service to reduce user input errors
3. WHEN using environment variables THEN the script SHALL allow overriding service name/region/ECR repo via flags and environment variables (SERVICE_NAME, AWS_REGION, ECR_REPO)
4. WHEN the script exits THEN it SHALL use distinct exit codes: build failures (10), push failures (11), update failures (12), health failures (13), timeout (14)
5. WHEN using --json flag THEN the script SHALL emit machine-readable status output (useful for CI/CD)