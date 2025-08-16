# Implementation Plan

- [ ] 1. Create unified deployment script foundation



  - Create new `deploy.sh` script with proper shebang and error handling (`set -euo pipefail`)
  - Implement command-line argument parsing with all required options (--service-name, --region, --ecr-repo, --force-latest, --force-restart, --dry-run, --tail, --json, --cleanup-old, --prune-images, --deploy-timeout, --health-timeout, --health-retries, --help)
  - Set up global configuration variables and environment variable overrides (SERVICE_NAME, AWS_REGION, ECR_REPOSITORY)
  - Initialize deployment state tracking with associative array for service_arn, previous/target image tags and digests
  - Add standardized exit codes (0=success, 10=build failure, 11=push failure, 12=update failure, 13=health failure, 14=timeout, 15=rollback failure, 20=preflight failure)
  - Create lightweight lock file mechanism to prevent concurrent deployments of the same tag
  - _Requirements: 1.1, 1.4, 8.3, 8.4_

- [ ] 2. Implement comprehensive preflight validation system





  - Create `preflight_checks()` function that validates Docker daemon connectivity
  - Add AWS CLI configuration validation with proper error messages and setup instructions
  - Implement ECR repository access verification and automatic repository creation
  - Add service configuration alignment check (port 8080, health path /healthz)
  - Create IAM permissions validation for ECR and App Runner operations
  - Implement secrets accessibility verification (instance role has secretsmanager:GetSecretValue for OXYLABS_PROXY_CONFIG ARN)
  - Add structured logging with `log_deployment_event()` function supporting both human-readable and JSON output
  - _Requirements: 5.2, 5.3, 5.4, 5.8, 5.9_

- [-] 3. Build image management system with unique tagging

  - Implement git commit hash detection with timestamp fallback for image tagging
  - Add platform correctness check: set DOCKER_DEFAULT_PLATFORM=linux/amd64 or use docker buildx build --platform linux/amd64 for ARM laptops
  - Create Docker build process with proper error handling and build context optimization
  - Add ECR login functionality with retry logic and clear error messages
  - Implement image tagging strategy (commit hash + latest) with proper ECR URI construction
  - Create image push functionality with progress indication and error recovery
  - Add digest retrieval and verification functions for both ECR and App Runner
  - Implement `verify_image_digest()` function to compare ECR digest with deployed digest
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 5.5_

- [ ] 4. Create service state detection and management
  - Implement `detect_service_state()` function to determine if service exists and its current status
  - Add explicit handling for PAUSED and DELETED service states with clear remediation messages (resume or re-create)
  - Create service creation logic with proper IAM role configuration and secrets management
  - Add service update logic with normalized environment variables and secrets arrays
  - Implement `update_service_with_normalized_config()` to handle App Runner's strict update payload requirements (normalize env/secrets to arrays of {Name,Value} for App Runner updates)
  - Create AutoDeployments management with save/disable/restore functionality for immutable tag deployments
  - Add `manage_auto_deployments()` function with proper state preservation
  - _Requirements: 1.1, 1.2, 1.3, 4.1, 4.2, 4.3, 4.6, 4.7_

- [ ] 5. Implement deployment verification and waiting logic
  - Create `wait_for_deployment_complete()` function that polls service status and digest verification
  - Implement proper wait logic requiring both Status=RUNNING and digest match before proceeding
  - Add timeout handling with configurable timeout periods (--deploy-timeout flag) and clear timeout reporting
  - Create deployment status monitoring with progress indicators and elapsed time tracking
  - Implement `force_deployment_restart()` function: if --force-restart or deploying :latest, call start-deployment after update-service
  - Add deployment completion verification with comprehensive status checking
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.7, 2.7_

- [ ] 6. Build comprehensive health validation system
  - Create `validate_deployment_health()` function with HTTP health endpoint testing
  - Implement port/path mismatch detection (404 for /healthz, connection refused for port 8080)
  - Add JSON health response parsing and dependency validation
  - Create `validate_health_dependencies()` function: assert dependencies.ffmpeg.available and dependencies.yt_dlp.available are true and proxy_config_readable is true
  - Implement health check retry logic with configurable attempts (--health-retries flag) and timeout (--health-timeout flag)
  - Add automatic log streaming on health failures with `stream_recent_logs_on_failure()`
  - Create health validation failure handling with comprehensive error output: service URL, target tag, target digest, deployed digest, last 20 lines of app logs, and likely cause analysis
  - _Requirements: 7.1, 7.2, 7.3, 7.6, 7.7, 3.9, 3.10_

- [ ] 7. Implement automatic rollback system
  - Create `rollback_deployment()` function that reverts to previous image tag and digest
  - Implement previous image state capture: capture previous tag+digest before update to ensure deterministic rollback
  - Add rollback trigger logic for health check failures and deployment timeouts
  - Create rollback verification: after rollback, re-run digest+health gates to ensure rollback success
  - Implement rollback status reporting and success/failure indication
  - Add rollback failure handling with appropriate exit codes
  - _Requirements: 3.8, 15 exit code_

- [ ] 8. Add logging, observability, and output formatting
  - Implement structured logging system supporting both human-readable and JSON formats
  - Create App Runner log streaming functionality with `stream_apprunner_logs()` for --tail option
  - Add deployment summary output with service URL, image tag, digest, and elapsed time
  - Implement `show_deployment_summary()` function with comprehensive deployment information
  - Create machine-readable JSON output for CI/CD integration (--json flag)
  - Add dry-run mode that shows planned actions without execution
  - _Requirements: 5.7, 5.10, 8.1, 8.5_

- [ ] 9. Create cleanup and migration functionality
  - Implement old script detection and archival with `--cleanup-old` option
  - Add ECR image pruning functionality with configurable retention (default: keep last 10): never prune the digest currently deployed or designated rollback digest
  - Create migration guidance and documentation updates
  - Implement configuration preservation from old scripts during migration
  - Add cleanup verification and reporting
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [ ] 10. Add comprehensive error handling and user experience features
  - Implement specific error handling for each failure scenario with actionable messages
  - Add AWS error parsing and solution suggestions for common App Runner issues
  - Create Docker build failure analysis with common fix suggestions
  - Implement network connectivity troubleshooting for ECR and App Runner operations
  - Add parameter validation and help text generation
  - Create usage examples and common workflow documentation
  - _Requirements: 5.1, 5.6, 8.2_

- [ ] 11. Create comprehensive testing suite
  - Write unit tests for all major functions (preflight checks, image management, service detection)
  - Create integration tests for end-to-end deployment scenarios
  - Add mock AWS API response testing for error conditions
  - Implement dry-run testing to verify script logic without actual deployments
  - Create rollback scenario testing with simulated failures
  - Add performance testing for deployment timing and resource usage
  - _Requirements: All requirements validation_

- [ ] 12. Update documentation and finalize deployment process
  - Update README.md with new deployment process documentation
  - Create deployment troubleshooting guide with common issues and solutions
  - Add CI/CD integration examples for GitHub Actions and other platforms
  - Create migration guide from old deployment scripts
  - Update any existing documentation references to point to new unified script
  - Add deployment best practices and security considerations documentation
  - _Requirements: 6.5, comprehensive documentation_