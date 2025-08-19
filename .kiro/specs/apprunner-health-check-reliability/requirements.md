# Requirements Document

## Introduction

The App Runner deployment is consistently failing health checks on the `/healthz` endpoint, causing deployment failures. The current health check implementation is too complex and performs expensive operations (proxy connectivity tests, dependency checks) that can timeout or fail during the critical deployment window. We need a reliable, fast health check that ensures App Runner deployments succeed while maintaining comprehensive health monitoring through separate endpoints.

## Requirements

### Requirement 1

**User Story:** As a DevOps engineer, I want App Runner deployments to succeed consistently, so that I can deploy updates without manual intervention or rollback procedures.

#### Acceptance Criteria

1. WHEN App Runner performs a health check on `/healthz` THEN the endpoint SHALL respond within 2 seconds
2. WHEN the Flask application is running THEN `/healthz` SHALL return HTTP 200 status
3. WHEN `/healthz` is called during deployment THEN it SHALL NOT perform expensive operations like proxy connectivity tests
4. WHEN `/healthz` is called THEN it SHALL only verify that the Flask application process is responsive

### Requirement 2

**User Story:** As a system administrator, I want detailed health information available through dedicated endpoints, so that I can monitor system health without impacting deployment reliability.

#### Acceptance Criteria

1. WHEN I access `/health/live` THEN the system SHALL return basic liveness information
2. WHEN I access `/health/ready` THEN the system SHALL return readiness status including proxy health
3. WHEN I access `/health/detailed` THEN the system SHALL return comprehensive health information including dependencies
4. WHEN any health endpoint fails THEN it SHALL include correlation IDs for debugging

### Requirement 3

**User Story:** As a developer, I want health check failures to be easily debuggable, so that I can quickly identify and resolve deployment issues.

#### Acceptance Criteria

1. WHEN a health check fails THEN the system SHALL log structured error information with correlation IDs
2. WHEN deployment health checks are performed THEN the system SHALL log the specific checks being performed
3. WHEN health endpoints are accessed THEN response times SHALL be logged for performance monitoring
4. WHEN health checks encounter errors THEN error details SHALL be available in application logs

### Requirement 4

**User Story:** As a platform engineer, I want health checks to be configurable for different environments, so that I can optimize for deployment speed in production and detailed monitoring in development.

#### Acceptance Criteria

1. WHEN `DEPLOYMENT_MODE=apprunner` environment variable is set THEN `/healthz` SHALL use minimal checks only
2. WHEN `HEALTH_CHECK_TIMEOUT` is configured THEN all health operations SHALL respect this timeout
3. WHEN `ENABLE_DETAILED_HEALTH` is false THEN expensive health checks SHALL be skipped
4. WHEN environment variables are missing THEN the system SHALL use safe defaults that prioritize deployment success

### Requirement 5

**User Story:** As a monitoring system, I want health endpoints to provide consistent response formats, so that I can reliably parse and alert on health status.

#### Acceptance Criteria

1. WHEN any health endpoint is called THEN it SHALL return JSON with a consistent schema
2. WHEN health status is "healthy" THEN HTTP status SHALL be 200
3. WHEN health status is "degraded" THEN HTTP status SHALL be 200 with degraded flag
4. WHEN health status is "unhealthy" THEN HTTP status SHALL be 503 with retry headers
5. WHEN health endpoints return errors THEN they SHALL include machine-readable error codes