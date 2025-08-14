# Design Document

## Overview

This design addresses the App Runner service creation failure caused by missing Instance Role configuration. The error "Instance Role have to be provided if passing in RuntimeEnvironmentSecrets" occurs because App Runner requires an IAM role with Secrets Manager permissions when the apprunner.yaml file references secrets. This design provides a complete solution for creating and configuring the Instance Role during App Runner service creation.

## Architecture

### Current Problem Analysis

The App Runner service creation is failing because:
1. The apprunner.yaml file correctly references AWS Secrets Manager secrets
2. App Runner requires an Instance Role to access external AWS services
3. No Instance Role is configured during service creation
4. The service fails validation before deployment begins

### Solution Architecture

**Two-Phase Approach:**
1. **Phase 1**: Ensure IAM resources are properly configured
2. **Phase 2**: Create App Runner service with Instance Role from the start

**Key Components:**
- IAM Policy with minimal Secrets Manager permissions
- IAM Role that App Runner can assume
- App Runner service configuration with Instance Role ARN
- Verification and troubleshooting procedures

## Components and Interfaces

### IAM Policy Configuration

#### Secrets Access Policy
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": [
        "arn:aws:secretsmanager:us-west-2:528131355234:secret:TLDW-SESSION-SECRET-hJDTQ1",
        "arn:aws:secretsmanager:us-west-2:528131355234:secret:TLDW-GOOGLE-OAUTH-CLIENT-ID-8Z22IN",
        "arn:aws:secretsmanager:us-west-2:528131355234:secret:TLDW-GOOGLE-OAUTH-CLIENT-SECRET-LmUrPI",
        "arn:aws:secretsmanager:us-west-2:528131355234:secret:TLDW-OPENAI-API-KEY-5rNo6a",
        "arn:aws:secretsmanager:us-west-2:528131355234:secret:TLDW-RESEND-API-KEY-5O5Kdx",
        "arn:aws:secretsmanager:us-west-2:528131355234:secret:TLDW-DEEPGRAM-API-KEY-6gvcFv"
      ]
    }
  ]
}
```

#### Trust Policy for App Runner
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "tasks.apprunner.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

### App Runner Service Configuration

#### Service Creation with Instance Role
The App Runner service must be created with the Instance Role specified:
- **Instance Role ARN**: `arn:aws:iam::528131355234:role/TLDW-AppRunner-Instance-Role`
- **Configuration Method**: AWS Console or AWS CLI
- **Timing**: Must be set during initial service creation

#### Configuration Method: AWS CLI Only

All configuration will be done via AWS CLI commands for consistency and automation:

```bash
aws apprunner create-service \
  --service-name tldw-app \
  --source-configuration '{
    "CodeRepository": {
      "RepositoryUrl": "https://github.com/iamadamzc/TLDW",
      "SourceCodeVersion": {
        "Type": "BRANCH",
        "Value": "main"
      },
      "CodeConfiguration": {
        "ConfigurationSource": "REPOSITORY"
      }
    },
    "AutoDeploymentsEnabled": true
  }' \
  --instance-configuration '{
    "InstanceRoleArn": "arn:aws:iam::528131355234:role/TLDW-AppRunner-Instance-Role"
  }' \
  --region us-west-2
```

## Data Models

### IAM Resource Model

#### Policy Resource
- **Name**: `TLDW-AppRunner-Secrets-Access-Policy`
- **Type**: Customer managed policy
- **Permissions**: Specific Secrets Manager access
- **Scope**: Limited to TLDW secrets only

#### Role Resource
- **Name**: `TLDW-AppRunner-Instance-Role`
- **Type**: Service role for App Runner
- **Trust Relationship**: App Runner tasks service
- **Attached Policies**: Secrets access policy

### App Runner Service Model

#### Service Configuration
- **Service Name**: `tldw-app`
- **Source**: GitHub repository with automatic deployment
- **Runtime**: Python 3 (managed runtime)
- **Instance Role**: Required for secrets access
- **Configuration File**: `apprunner.yaml` with secrets references

## Error Handling

### Common Configuration Errors

1. **Missing Instance Role**
   - **Error**: "Instance Role have to be provided if passing in RuntimeEnvironmentSecrets"
   - **Cause**: No Instance Role specified during service creation
   - **Resolution**: Delete service and recreate with Instance Role ARN

2. **Incorrect Trust Policy**
   - **Error**: App Runner cannot assume the role
   - **Cause**: Wrong service principal in trust policy
   - **Resolution**: Update trust policy to use `tasks.apprunner.amazonaws.com`

3. **Insufficient Permissions**
   - **Error**: Access denied when retrieving secrets
   - **Cause**: Policy doesn't include required secret ARNs
   - **Resolution**: Update policy with correct secret ARNs

4. **Service in Invalid State**
   - **Error**: "Service does not exist or is in an invalid state"
   - **Cause**: Previous failed service creation
   - **Resolution**: Delete failed service completely before recreating

### Validation Steps

1. **Verify IAM Resources**
   ```bash
   aws iam get-role --role-name TLDW-AppRunner-Instance-Role
   aws iam list-attached-role-policies --role-name TLDW-AppRunner-Instance-Role
   ```

2. **Test Secret Access**
   ```bash
   aws secretsmanager get-secret-value --secret-id TLDW-SESSION-SECRET-hJDTQ1
   ```

3. **Verify Service Configuration**
   ```bash
   aws apprunner describe-service --service-arn <service-arn>
   ```

## Testing Strategy

### Pre-Creation Testing
1. **IAM Resource Validation**
   - Verify policy exists and has correct permissions
   - Verify role exists and can be assumed by App Runner
   - Test secret access with the role

2. **Configuration File Testing**
   - Validate apprunner.yaml syntax
   - Verify secret ARNs are correct
   - Test local application startup

### Post-Creation Testing
1. **Service Creation Validation**
   - Verify service creates without errors
   - Check that Instance Role is properly attached
   - Monitor deployment logs for success

2. **Runtime Testing**
   - Verify application starts successfully
   - Test that secrets are loaded as environment variables
   - Validate application functionality

### Rollback Strategy
1. **Service Deletion**
   - Delete failed App Runner service completely
   - Verify no orphaned resources remain

2. **Clean Recreation**
   - Recreate service with corrected configuration
   - Monitor deployment from start to finish

## Implementation Approach

### Phase 1: Verify IAM Configuration
- Confirm IAM policy and role exist with correct configuration
- Update trust policy if needed (use `tasks.apprunner.amazonaws.com`)
- Test permissions manually

### Phase 2: Clean Service Recreation
- Delete any existing failed App Runner services
- Create new service with Instance Role specified from the start
- Monitor deployment for success

### Phase 3: Validation and Documentation
- Verify application functionality
- Document the complete setup process
- Create troubleshooting guide

This design ensures that the App Runner service is created correctly with proper IAM permissions from the beginning, avoiding the "Instance Role have to be provided" error.