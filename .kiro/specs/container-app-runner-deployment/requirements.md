# Requirements Document

## Introduction

This feature migrates the TL;DW application from source-based App Runner deployment to container-based deployment. The migration ensures ffmpeg availability, proper Gunicorn configuration, and includes development overrides for missing dependencies. This addresses deployment reliability issues and provides better control over the runtime environment.

## Requirements

### Requirement 1

**User Story:** As a DevOps engineer, I want to disable source-based App Runner deployment, so that the application uses container-based deployment instead.

#### Acceptance Criteria

1. WHEN the repository contains apprunner.yaml THEN the system SHALL rename it to apprunner.container.yaml or remove it
2. WHEN CI/CD references apprunner.yaml THEN the system SHALL update those references accordingly
3. WHEN App Runner attempts deployment THEN it SHALL NOT try to use the managed Python runtime

### Requirement 2

**User Story:** As a developer, I want a Dockerfile with ffmpeg and proper Gunicorn configuration, so that the application can process audio files and serve requests reliably.

#### Acceptance Criteria

1. WHEN the Docker image is built THEN it SHALL include ffmpeg and ffprobe binaries
2. WHEN the container starts THEN it SHALL use Gunicorn with proper worker configuration
3. WHEN the application needs audio processing THEN ffmpeg SHALL be available at /usr/bin
4. WHEN Gunicorn starts THEN it SHALL bind to 0.0.0.0:8080 with 2 workers and 4 threads per worker
5. WHEN requests are processed THEN the timeout SHALL be set to 120 seconds

### Requirement 3

**User Story:** As a developer, I want a wsgi.py with dependency checks and dev overrides, so that I can run the application even when some dependencies are missing during development.

#### Acceptance Criteria

1. WHEN ALLOW_MISSING_DEPS environment variable is set to "true" THEN the system SHALL log warnings for missing dependencies and continue startup
2. WHEN ALLOW_MISSING_DEPS is not set or "false" THEN the system SHALL exit with an error for missing dependencies
3. WHEN ffmpeg is available THEN the system SHALL set FFMPEG_LOCATION environment variable to /usr/bin
4. WHEN the application starts THEN it SHALL check for ffmpeg, ffprobe, and yt-dlp availability
5. WHEN dependency checks pass THEN the system SHALL log the binary paths and versions

### Requirement 4

**User Story:** As a developer, I want the Flask/FastAPI app properly exposed in wsgi.py, so that Gunicorn can serve the application correctly.

#### Acceptance Criteria

1. WHEN Gunicorn starts THEN it SHALL find the app object at wsgi:app import path
2. WHEN the wsgi module is imported THEN it SHALL expose the main application as 'app'
3. WHEN startup dependency checks run THEN they SHALL execute before the application serves requests

### Requirement 5

**User Story:** As a developer, I want yt-dlp calls to use explicit ffmpeg paths and proxy configuration, so that audio processing works reliably in the containerized environment.

#### Acceptance Criteria

1. WHEN yt-dlp is invoked THEN it SHALL include --ffmpeg-location parameter with the correct path
2. WHEN yt-dlp is invoked THEN it SHALL include --user-agent parameter with appropriate user agent
3. WHEN yt-dlp is invoked THEN it SHALL include --proxy parameter with sticky proxy URL
4. WHEN yt-dlp is invoked THEN it SHALL include --socket-timeout parameter set to 15 seconds

### Requirement 6

**User Story:** As a DevOps engineer, I want clear deployment steps for App Runner image mode, so that I can successfully deploy the containerized application.

#### Acceptance Criteria

1. WHEN deploying to ECR THEN the system SHALL create the repository if it doesn't exist
2. WHEN building the Docker image THEN it SHALL be tagged appropriately for ECR
3. WHEN configuring App Runner THEN it SHALL use Image repository as source with ECR image
4. WHEN App Runner starts THEN it SHALL bind to port 8080
5. WHEN health checks run THEN they SHALL use /healthz or /health endpoint

### Requirement 7

**User Story:** As a QA engineer, I want acceptance criteria for successful deployment, so that I can verify the migration worked correctly.

#### Acceptance Criteria

1. WHEN App Runner deploys THEN it SHALL complete successfully without source runtime errors
2. WHEN the application starts THEN startup logs SHALL show non-None paths for ffmpeg, ffprobe, and yt-dlp
3. WHEN accessing the health endpoint THEN it SHALL return HTTP 200 status
4. WHEN a summarize operation runs THEN it SHALL handle YouTube bot-check with proxy rotation
5. WHEN audio download occurs THEN it SHALL use proxy without "ffmpeg not found" errors
6. WHEN ASR processing completes THEN it SHALL successfully send email notifications