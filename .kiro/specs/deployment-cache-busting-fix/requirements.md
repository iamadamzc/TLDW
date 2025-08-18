# Requirements Document

## Introduction

This feature addresses a critical deployment issue where Docker caching prevents dependency updates from being applied during AWS App Runner deployments. The root cause is that Docker reuses cached layers for the yt-dlp update command, leading to silent deployment failures where new code appears to deploy successfully but actually runs with stale dependencies that fail health checks.

## Requirements

### Requirement 1

**User Story:** As a DevOps engineer, I want Docker builds to invalidate cache for dependency updates on every deployment, so that critical library updates are always applied to new container images.

#### Acceptance Criteria

1. WHEN a deployment is triggered THEN the Docker build SHALL use a unique cache-busting argument to force dependency layer rebuilds
2. WHEN the docker build command runs THEN it SHALL pass the git commit hash as a CACHE_BUSTER build argument
3. WHEN the Dockerfile processes the yt-dlp update RUN command THEN it SHALL incorporate the cache-busting argument to ensure the command string is unique for each build

### Requirement 2

**User Story:** As a DevOps engineer, I want the Dockerfile to accept and use cache-busting arguments, so that dependency update layers are rebuilt on every deployment regardless of command similarity.

#### Acceptance Criteria

1. WHEN the Dockerfile is built THEN it SHALL accept a CACHE_BUSTER build argument
2. WHEN the yt-dlp update RUN command executes THEN it SHALL echo the CACHE_BUSTER value to make the command unique
3. WHEN Docker processes the RUN command THEN it SHALL not use cached layers due to the unique cache-busting content

### Requirement 3

**User Story:** As a system administrator, I want the health check endpoint to validate proxy connectivity when proxies are enabled, so that deployment failures are detected early and explicitly rather than silently.

#### Acceptance Criteria

1. WHEN the /healthz endpoint is called AND proxies are enabled THEN the system SHALL test proxy connectivity
2. WHEN proxy connectivity test fails THEN the health check SHALL return HTTP 503 status code
3. WHEN proxy connectivity test succeeds THEN the health check SHALL include proxy status in the response
4. WHEN proxy connectivity cannot be tested due to errors THEN the health check SHALL fail with appropriate error messaging
5. WHEN proxies are disabled THEN the health check SHALL skip proxy testing and proceed normally

### Requirement 4

**User Story:** As a DevOps engineer, I want deployment failures to be explicit and loud, so that I can quickly identify and resolve issues instead of having silent failures that appear successful.

#### Acceptance Criteria

1. WHEN App Runner performs health checks on a new deployment THEN unhealthy containers SHALL be rejected with clear failure signals
2. WHEN proxy connectivity fails during health checks THEN the deployment SHALL fail fast rather than timing out silently
3. WHEN health check failures occur THEN the error messages SHALL provide actionable diagnostic information
4. WHEN a deployment is aborted due to health check failures THEN the system SHALL maintain the previous stable version