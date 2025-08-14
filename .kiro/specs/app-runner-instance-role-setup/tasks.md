# Implementation Plan

- [x] 1. Verify and update IAM trust policy for App Runner


  - Check current trust policy for the TLDW-AppRunner-Instance-Role
  - Update trust policy to use correct service principal (tasks.apprunner.amazonaws.com)
  - Verify the policy attachment is correct
  - _Requirements: 2.3, 3.1_

- [x] 2. Delete any existing failed App Runner services


  - List all App Runner services to identify failed or invalid services
  - Delete any existing tldw-app service that is in failed state
  - Verify complete cleanup of App Runner resources
  - _Requirements: 3.3, 4.3_

- [x] 3. Create App Runner service with Instance Role via CLI


  - Use AWS CLI to create App Runner service with proper Instance Role configuration
  - Configure automatic deployment from GitHub repository
  - Specify the correct Instance Role ARN in the service configuration
  - Set up proper source code configuration for repository deployment
  - _Requirements: 1.1, 1.2, 3.1, 3.2_

- [ ] 4. Verify service creation and deployment



  - Check that the App Runner service was created successfully
  - Monitor the initial deployment process for any errors
  - Verify that the Instance Role is properly attached to the service
  - Confirm that secrets are accessible during deployment
  - _Requirements: 1.3, 1.4, 3.3_

- [ ] 5. Test application functionality and secret access
  - Verify that the deployed application starts successfully
  - Test that all environment variables are loaded from Secrets Manager
  - Check the health endpoint responds correctly
  - Validate that the application functions as expected
  - _Requirements: 1.4, 2.1, 2.2_

- [ ] 6. Document the complete CLI-based setup process
  - Create step-by-step CLI commands for the entire setup
  - Document troubleshooting steps for common issues
  - Include verification commands to check configuration
  - Provide rollback procedures if needed
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [ ] 7. Clean up temporary files and validate final configuration
  - Remove local policy.json and trust-policy.json files
  - Verify the final App Runner service configuration
  - Test the complete deployment pipeline from GitHub push to running service
  - Confirm all requirements are met and service is production-ready
  - _Requirements: 3.3, 4.3_