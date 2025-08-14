# API Key Setup Guide for TL;DW App Runner Deployment

This guide explains how to configure API keys for the TL;DW application in AWS App Runner using AWS Secrets Manager.

## Overview

The TL;DW application requires two API keys to function properly:
- **OpenAI API Key**: For AI-powered video summarization
- **Resend API Key**: For sending email digests to users

These keys must be securely stored in AWS Secrets Manager and referenced in the App Runner configuration.

## Step 1: Create Secrets in AWS Secrets Manager

### Using AWS CLI

```bash
# Create OpenAI API key secret
aws secretsmanager create-secret \
    --name "TLDW-OPENAI-API-KEY" \
    --description "OpenAI API Key for TLDW" \
    --secret-string "your-openai-api-key-here" \
    --region us-west-2

# Create Resend API key secret
aws secretsmanager create-secret \
    --name "TLDW-RESEND-API-KEY" \
    --description "Resend API Key for TLDW" \
    --secret-string "your-resend-api-key-here" \
    --region us-west-2
```

### Using AWS Console

1. Navigate to AWS Secrets Manager in the AWS Console
2. Click "Store a new secret"
3. Select "Other type of secret"
4. Choose "Plaintext" and enter your API key
5. Name the secret (e.g., "TLDW-OPENAI-API-KEY")
6. Add a description
7. Click "Next" and complete the creation process
8. Repeat for the second API key

## Step 2: Note the Secret ARNs

After creating the secrets, note their ARNs. They will look like:
```
arn:aws:secretsmanager:us-west-2:528131355234:secret:TLDW-OPENAI-API-KEY-5rNo6a
arn:aws:secretsmanager:us-west-2:528131355234:secret:TLDW-RESEND-API-KEY-5O5Kdx
```

## Step 3: Configure App Runner IAM Role

Your App Runner service needs permission to access these secrets. Add this policy to your App Runner instance role:

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
                "arn:aws:secretsmanager:us-west-2:528131355234:secret:TLDW-OPENAI-API-KEY-*",
                "arn:aws:secretsmanager:us-west-2:528131355234:secret:TLDW-RESEND-API-KEY-*"
            ]
        }
    ]
}
```

## Step 4: Update apprunner.yaml Configuration

Add the secrets configuration to your `apprunner.yaml` file:

```yaml
version: 1.0
runtime: python311
build:
  commands:
    build:
      - python3 -m pip install --target /app -r requirements.txt
run:
  command: python3 -m gunicorn --bind 0.0.0.0:8080 --workers 1 app:app
  network:
    port: 8080
  secrets:
    - name: OPENAI_API_KEY
      value-from: arn:aws:secretsmanager:us-west-2:528131355234:secret:TLDW-OPENAI-API-KEY-5rNo6a
    - name: RESEND_API_KEY
      value-from: arn:aws:secretsmanager:us-west-2:528131355234:secret:TLDW-RESEND-API-KEY-5O5Kdx
    # ... other secrets
```

**Important**: Replace the ARNs with your actual secret ARNs from Step 2.

## Step 5: Deploy and Test

1. Commit your updated `apprunner.yaml` file
2. Deploy to App Runner (automatic if using GitHub integration)
3. Monitor the deployment logs for any errors
4. Test the application functionality

## Troubleshooting

### Common Issues and Solutions

#### 1. CREATE_FAILED Status
**Symptoms**: App Runner service fails to start with CREATE_FAILED status
**Causes**: 
- Invalid secret ARNs in apprunner.yaml
- Missing IAM permissions
- Incorrect YAML syntax

**Solutions**:
- Verify secret ARNs are correct and complete
- Check IAM role has secretsmanager:GetSecretValue permission
- Validate YAML syntax

#### 2. 500 Internal Server Error
**Symptoms**: Application starts but returns 500 errors when summarizing
**Causes**:
- Environment variables not injected properly
- Invalid API keys
- Service initialization failures

**Solutions**:
- Check App Runner logs for specific error messages
- Verify secrets contain valid API keys
- Test API keys locally using the test script

#### 3. Authentication Errors
**Symptoms**: "OpenAI authentication failed" or "Resend authentication failed" errors
**Causes**:
- Invalid or expired API keys
- API keys not properly injected as environment variables

**Solutions**:
- Verify API keys are valid and active
- Check secret values in AWS Secrets Manager
- Ensure ARNs in apprunner.yaml are correct

### Diagnostic Commands

#### Check if secrets exist:
```bash
aws secretsmanager list-secrets --region us-west-2 --query "SecretList[?contains(Name, 'TLDW')].{Name:Name,ARN:ARN}"
```

#### Get secret value (for testing):
```bash
aws secretsmanager get-secret-value --secret-id "TLDW-OPENAI-API-KEY" --region us-west-2
```

#### Test API keys locally:
```bash
python test-api-keys.py
```

### App Runner Logs

To view App Runner logs:
1. Go to AWS App Runner console
2. Select your service
3. Click on "Logs" tab
4. Check both "Deployment logs" and "Application logs"

Look for these log messages:
- ✅ `OpenAI client initialized successfully`
- ✅ `Email service initialized successfully`
- ❌ `OPENAI_API_KEY environment variable is required but not set`
- ❌ `RESEND_API_KEY environment variable is required but not set`

## API Key Rotation

To rotate API keys without downtime:

1. **Update the secret value** in AWS Secrets Manager:
   ```bash
   aws secretsmanager update-secret \
       --secret-id "TLDW-OPENAI-API-KEY" \
       --secret-string "new-api-key-value" \
       --region us-west-2
   ```

2. **Restart the App Runner service**:
   - Go to App Runner console
   - Select your service
   - Click "Deploy" to trigger a new deployment
   - The service will restart with the new secret values

3. **Verify the update**:
   - Test the application functionality
   - Check logs for successful initialization

## Security Best Practices

1. **Never commit API keys to version control**
2. **Use least-privilege IAM policies** - only grant access to specific secrets
3. **Rotate API keys regularly** - especially if they may have been compromised
4. **Monitor secret access** - use CloudTrail to track secret usage
5. **Use different secrets for different environments** (dev, staging, prod)

## Support

If you continue to experience issues:
1. Check the troubleshooting section above
2. Review App Runner application logs
3. Verify all configuration steps were completed correctly
4. Test API keys locally using the provided test script

For additional help, ensure you have:
- Complete error messages from App Runner logs
- Confirmation that secrets exist and have correct values
- Verification that IAM permissions are properly configured