# Implementation Plan

- [x] 1. Create AWS Secrets Manager secrets for API keys



  - Create OpenAI API key secret named `tldw-openai-api-key` in AWS Secrets Manager
  - Create Resend API key secret named `tldw-resend-api-key` in AWS Secrets Manager
  - Document the generated ARNs for use in App Runner configuration
  - _Requirements: 2.1, 2.2_

- [ ] 2. Update App Runner service IAM role permissions
  - Add secretsmanager:GetSecretValue permission to App Runner instance role
  - Scope permissions to specific secret ARNs for security
  - Test permissions using AWS CLI to verify access


  - _Requirements: 2.3_

- [ ] 3. Update apprunner.yaml with secrets configuration
  - Add secrets section to apprunner.yaml with proper ARN references
  - Map OPENAI_API_KEY environment variable to OpenAI secret ARN


  - Map RESEND_API_KEY environment variable to Resend secret ARN
  - Validate YAML syntax and App Runner configuration format
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 4. Enhance error handling in summarizer service


  - Add validation check for empty OPENAI_API_KEY in summarizer.py
  - Implement specific error handling for OpenAI authentication failures
  - Add logging for API key validation and OpenAI API call failures
  - Return informative error messages instead of generic 500 responses
  - _Requirements: 1.1, 1.2_



- [ ] 5. Enhance error handling in email service
  - Add validation check for empty RESEND_API_KEY in email_service.py
  - Implement specific error handling for Resend authentication failures
  - Add logging for email service failures and API key validation


  - Implement graceful degradation when email service is unavailable
  - _Requirements: 1.1, 1.3_

- [ ] 6. Update routes.py error handling
  - Improve exception handling in summarize_videos function
  - Add specific error responses for different failure types
  - Implement logging for better debugging of API failures
  - Return structured error responses with error codes and messages
  - _Requirements: 1.1, 4.3_

- [ ] 7. Test API key configuration locally
  - Set up local environment variables with the API keys for testing


  - Test OpenAI API integration with actual API key
  - Test Resend email service with actual API key
  - Verify both services authenticate and function correctly
  - _Requirements: 1.4_

- [ ] 8. Deploy and validate App Runner configuration
  - Deploy updated apprunner.yaml configuration to App Runner service
  - Verify environment variables are properly injected during startup
  - Test complete video summarization flow end-to-end
  - Confirm 500 errors are resolved and application functions correctly
  - _Requirements: 1.1, 3.4_

- [ ] 9. Create API key setup documentation
  - Document step-by-step process for creating secrets in AWS Secrets Manager
  - Document apprunner.yaml configuration syntax with examples
  - Create troubleshooting guide for common API key configuration issues
  - Document API key rotation process for future maintenance
  - _Requirements: 4.1, 4.2, 4.4_