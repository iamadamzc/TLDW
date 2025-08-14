# Design Document

## Overview

This design addresses the 500 Internal Server Error in the TL;DW application by implementing proper API key management through AWS Secrets Manager and App Runner configuration. The solution involves creating secrets for OpenAI and Resend API keys, configuring proper IAM permissions, and updating the apprunner.yaml file to inject these secrets as environment variables.

## Architecture

### Current Problem Analysis

The application is failing because:
1. `summarizer.py` expects `OPENAI_API_KEY` environment variable but it's not available in App Runner
2. `email_service.py` expects `RESEND_API_KEY` environment variable but it's not available in App Runner  
3. When these keys are missing, API calls fail and cause unhandled exceptions leading to 500 errors
4. The try/catch in `routes.py` catches these exceptions but only returns a generic "500" response

### Solution Architecture

**AWS Secrets Manager Integration**
- Store API keys as individual secrets in AWS Secrets Manager
- Use descriptive secret names for easy identification
- Configure proper IAM permissions for App Runner to access secrets

**App Runner Configuration**
- Update `apprunner.yaml` to reference secrets using ARN format
- Map secrets to environment variable names expected by the application
- Ensure proper secret injection during service startup

**Application Layer**
- Verify that existing code properly handles environment variables
- Add better error handling and logging for missing API keys
- Implement graceful degradation when services are unavailable

## Components and Interfaces

### AWS Secrets Manager Configuration

#### Secret Structure
Each API key will be stored as a separate secret:

**OpenAI Secret:**
- Secret Name: `tldw-openai-api-key`
- Secret Value: `[OPENAI_API_KEY_VALUE]` (provided separately)
- Region: us-west-2 (matching App Runner service region)

**Resend Secret:**
- Secret Name: `tldw-resend-api-key`  
- Secret Value: `[RESEND_API_KEY_VALUE]` (provided separately)
- Region: us-west-2 (matching App Runner service region)

#### IAM Permissions
App Runner service role needs permissions to access secrets:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "secretsmanager:GetSecretValue"
            ],
            "Resource": [
                "arn:aws:secretsmanager:us-west-2:528131355234:secret:tldw-openai-api-key-*",
                "arn:aws:secretsmanager:us-west-2:528131355234:secret:tldw-resend-api-key-*"
            ]
        }
    ]
}
```

### App Runner Configuration

#### Updated apprunner.yaml Structure
```yaml
version: 1.0
runtime: python3
build:
  commands:
    build:
      - pip install -r requirements.txt
run:
  command: gunicorn --bind 0.0.0.0:8080 --workers 1 app:app
  network:
    port: 8080
  secrets:
    - name: OPENAI_API_KEY
      value-from: arn:aws:secretsmanager:us-west-2:528131355234:secret:tldw-openai-api-key-XXXXXX
    - name: RESEND_API_KEY
      value-from: arn:aws:secretsmanager:us-west-2:528131355234:secret:tldw-resend-api-key-XXXXXX
```

### Application Integration Points

#### Summarizer Service Integration
Current code in `summarizer.py`:
```python
self.openai_api_key = os.environ.get("OPENAI_API_KEY", "")
```

This will now receive the actual API key from the injected environment variable.

#### Email Service Integration  
Current code in `email_service.py`:
```python
resend_api_key = os.environ.get("RESEND_API_KEY")
```

This will now receive the actual API key from the injected environment variable.

#### Error Handling Enhancement
Add validation in both services to check for empty/missing keys:
```python
if not self.openai_api_key:
    raise ValueError("OPENAI_API_KEY environment variable is required")
```

## Data Models

### Secret Configuration Model
```yaml
Secret:
  name: string (descriptive identifier)
  value: string (actual API key)
  region: string (AWS region)
  arn: string (full ARN for reference)
```

### Environment Variable Mapping
```yaml
EnvironmentVariable:
  name: string (variable name in application)
  source: string (secrets manager ARN)
  required: boolean (whether app can function without it)
```

### App Runner Secrets Configuration
```yaml
SecretsConfig:
  secrets: array of SecretReference
  
SecretReference:
  name: string (environment variable name)
  value-from: string (secrets manager ARN)
```

## Error Handling

### Missing API Key Scenarios

1. **Secret Not Found in AWS**
   - Detection: App Runner deployment fails with secret access error
   - Resolution: Verify secret exists and ARN is correct

2. **Invalid API Key Format**
   - Detection: API calls return authentication errors
   - Resolution: Verify API key value in secret is correct

3. **IAM Permission Issues**
   - Detection: App Runner can't access secrets during startup
   - Resolution: Update App Runner service role with proper permissions

4. **Environment Variable Not Injected**
   - Detection: Application logs show empty environment variables
   - Resolution: Verify apprunner.yaml secrets configuration syntax

### Application-Level Error Handling

#### Enhanced Error Messages
Instead of generic 500 errors, provide specific error responses:
```python
try:
    # API call logic
except AuthenticationError:
    return {"error": "API authentication failed", "code": "AUTH_ERROR"}, 500
except Exception as e:
    logger.error(f"Unexpected error: {str(e)}")
    return {"error": "Internal server error", "code": "INTERNAL_ERROR"}, 500
```

#### Graceful Degradation
- If OpenAI API is unavailable, return informative error message
- If email service is unavailable, continue with summarization but skip email
- Log all API failures for debugging

## Testing Strategy

### Secret Configuration Testing

1. **AWS Secrets Manager Validation**
   - Verify secrets are created with correct names and values
   - Test secret retrieval using AWS CLI
   - Validate IAM permissions allow access

2. **App Runner Configuration Testing**
   - Validate apprunner.yaml syntax
   - Test secret injection during deployment
   - Verify environment variables are available in running container

### Application Integration Testing

1. **API Key Validation**
   - Test OpenAI API calls with injected key
   - Test Resend API calls with injected key
   - Verify both services authenticate successfully

2. **Error Handling Testing**
   - Test behavior with invalid API keys
   - Test behavior with missing environment variables
   - Verify appropriate error messages are returned

### End-to-End Testing

1. **Complete User Flow**
   - Test video summarization from start to finish
   - Verify email notifications are sent successfully
   - Confirm no 500 errors occur during normal operation

2. **Deployment Testing**
   - Deploy with new configuration
   - Verify service starts successfully
   - Test all endpoints respond correctly

## Implementation Approach

### Phase 1: Create AWS Secrets
- Create OpenAI API key secret in AWS Secrets Manager
- Create Resend API key secret in AWS Secrets Manager
- Document the ARNs for configuration reference

### Phase 2: Configure IAM Permissions
- Update App Runner service role with secrets access permissions
- Test permissions using AWS CLI or console

### Phase 3: Update App Runner Configuration
- Modify apprunner.yaml to include secrets configuration
- Deploy updated configuration to App Runner
- Verify environment variables are injected correctly

### Phase 4: Enhance Error Handling
- Add API key validation in application services
- Improve error messages and logging
- Test error scenarios and recovery

This design ensures secure API key management while maintaining application functionality and providing clear error handling for troubleshooting.