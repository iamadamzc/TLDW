# Implementation Plan

- [x] 1. Investigate and identify the root cause of secret validation error


  - Examine the current OXYLABS_PROXY_CONFIG environment variable value in App Runner
  - Check the actual secret ARN format being used vs. expected format
  - Verify the secret exists in AWS Secrets Manager with the expected name
  - Test secret accessibility with the current IAM instance role permissions
  - Identify if the ARN is being modified or corrupted in the application code
  - Document the exact error and the problematic secret reference
  - _Requirements: 2.1, 2.2, 2.3_



- [ ] 2. Fix the malformed secret ARN configuration
  - Correct the secret ARN format to meet AWS naming requirements (alphanumeric and -/_+=.@! only)
  - Update the App Runner service configuration with the corrected secret ARN
  - Verify the secret name matches the actual secret in AWS Secrets Manager
  - Test secret retrieval with the corrected ARN format
  - Update deployment scripts to use the correct secret ARN format
  - Validate that the corrected ARN resolves the ValidationException
  - _Requirements: 1.1, 1.2, 2.4, 2.5_


- [ ] 3. Enhance proxy_manager.py with robust secret validation
  - Add secret ARN format validation before attempting retrieval
  - Implement comprehensive error handling for different secret failure scenarios
  - Add detailed logging for secret retrieval attempts (ARN only, not content)
  - Create fallback behavior when secrets are inaccessible
  - Add secret content validation to ensure proper JSON format
  - Implement retry logic for transient secret retrieval failures
  - _Requirements: 1.3, 3.1, 3.2, 5.1, 5.2_

- [ ] 4. Add secret validation to deployment preflight checks
  - Create validate_secret_configuration() function in deploy.sh
  - Validate all secret ARN formats before deployment
  - Test secret accessibility with the instance role during preflight
  - Provide clear error messages for secret format and permission issues
  - Fail deployment early if critical secrets are inaccessible
  - Add secret validation to the comprehensive preflight check suite



  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [ ] 5. Improve health check endpoint secret validation
  - Update /healthz endpoint to test actual secret retrieval, not just configuration
  - Add comprehensive secret validation reporting in health check response
  - Distinguish between secret format errors, permission errors, and content errors
  - Test proxy configuration JSON parsing and field validation
  - Add proxy connectivity testing if feasible (without exposing credentials)
  - Provide actionable troubleshooting information in health check output
  - _Requirements: 1.5, 3.3, 3.4, 3.5, 5.3, 5.4, 5.5_

- [ ] 6. Create comprehensive secret validation utility
  - Implement SecretValidator class with ARN format validation
  - Add methods for testing secret accessibility and content validation
  - Create validation reporting with detailed error messages and suggested fixes
  - Add support for validating multiple secrets in batch
  - Implement secure logging that never exposes secret values
  - Add unit tests for all validation scenarios
  - _Requirements: 3.1, 3.2, 3.5_

- [ ] 7. Test and verify the complete fix
  - Deploy the corrected secret configuration to App Runner
  - Verify the health check reports proxy_config_readable as true
  - Test actual proxy authentication with yt-dlp operations
  - Confirm that 407 authentication errors are resolved
  - Validate that video downloads work correctly through the proxy
  - Run comprehensive end-to-end testing of proxy functionality
  - _Requirements: 1.4, 5.4, 5.5_

- [ ] 8. Add monitoring and alerting for secret validation
  - Add metrics for secret validation success/failure rates
  - Implement logging for secret validation attempts and results
  - Create alerts for secret validation failures
  - Add monitoring for proxy authentication success rates
  - Implement health check monitoring for secret-related issues
  - Document troubleshooting procedures for secret validation failures
  - _Requirements: 3.5, 4.5_

- [ ] 9. Update deployment process with enhanced secret validation
  - Integrate secret validation into the unified deployment script
  - Add --validate-secrets flag for comprehensive secret checking
  - Update deployment documentation with secret validation procedures
  - Add secret validation to the deployment verification process
  - Create troubleshooting guide for common secret configuration issues
  - Test deployment script secret validation with various error scenarios
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [ ] 10. Create comprehensive testing suite for secret validation
  - Write unit tests for secret ARN format validation
  - Create integration tests for secret retrieval with AWS Secrets Manager
  - Add tests for proxy configuration parsing and validation
  - Implement mock testing for various secret failure scenarios
  - Create end-to-end tests for proxy authentication functionality
  - Add performance tests for secret validation operations
  - _Requirements: All requirements validation_