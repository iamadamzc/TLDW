# Cookie Feature Deployment Guide

## Overview

This guide covers deploying the per-user cookie functionality for the TL;DW YouTube summarization service.

## Prerequisites

- AWS CLI configured with appropriate permissions
- App Runner service already deployed
- S3 bucket for cookie storage (optional but recommended for production)

## Environment Variables

Add these environment variables to your App Runner service configuration:

### Required
- `DEEPGRAM_API_KEY` - Already configured for ASR functionality

### Optional Cookie Configuration
- `COOKIE_S3_BUCKET` - S3 bucket name for cookie storage (recommended for production)
- `COOKIE_LOCAL_DIR` - Local directory for cookie storage (default: `/app/cookies`)
- `DISABLE_COOKIES` - Emergency kill-switch to disable cookie functionality (default: `false`)

## S3 Setup (Recommended for Production)

### 1. Create S3 Bucket

```bash
# Replace with your desired bucket name
export COOKIE_BUCKET_NAME="your-app-cookies-bucket"
export AWS_REGION="us-west-2"

# Create bucket with encryption
aws s3 mb s3://$COOKIE_BUCKET_NAME --region $AWS_REGION

# Enable default encryption
aws s3api put-bucket-encryption \
  --bucket $COOKIE_BUCKET_NAME \
  --server-side-encryption-configuration '{
    "Rules": [
      {
        "ApplyServerSideEncryptionByDefault": {
          "SSEAlgorithm": "aws:kms"
        }
      }
    ]
  }'

# Block public access
aws s3api put-public-access-block \
  --bucket $COOKIE_BUCKET_NAME \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

### 2. Update IAM Role

Add the cookie access policy to your App Runner instance role:

```bash
# Get your App Runner service ARN and extract the role name
export SERVICE_ARN="your-app-runner-service-arn"
export ROLE_NAME="your-app-runner-instance-role"

# Create the policy (replace ${COOKIE_S3_BUCKET} with actual bucket name)
sed "s/\${COOKIE_S3_BUCKET}/$COOKIE_BUCKET_NAME/g" deployment/cookie-iam-policy.json > /tmp/cookie-policy.json

# Attach the policy
aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "AppRunnerCookieAccess" \
  --policy-document file:///tmp/cookie-policy.json

# Clean up temp file
rm /tmp/cookie-policy.json
```

### 3. Update App Runner Configuration

Add the S3 bucket environment variable to your App Runner service:

```bash
# Update your App Runner service configuration
aws apprunner update-service \
  --service-arn "$SERVICE_ARN" \
  --source-configuration '{
    "ImageRepository": {
      "ImageConfiguration": {
        "RuntimeEnvironmentVariables": {
          "COOKIE_S3_BUCKET": "'$COOKIE_BUCKET_NAME'",
          "COOKIE_LOCAL_DIR": "/app/cookies"
        }
      }
    }
  }'
```

## Local Development Setup

For local development, you can use local file storage:

```bash
# Create local cookie directory
mkdir -p /tmp/cookies
chmod 700 /tmp/cookies

# Set environment variable
export COOKIE_LOCAL_DIR="/tmp/cookies"
```

## Security Considerations

### File Permissions
- Cookie directory: `chmod 700` (owner read/write/execute only)
- Cookie files: `chmod 600` (owner read/write only)

### S3 Security
- Bucket encryption: SSE-KMS enabled by default
- Public access: Completely blocked
- IAM permissions: Least-privilege access to `cookies/*` path only

### Application Security
- Cookie contents never logged
- Temporary files automatically cleaned up
- User isolation: Users can only access their own cookies

## Emergency Procedures

### Kill-Switch Activation
To immediately disable cookie functionality without code deployment:

```bash
# Set the kill-switch environment variable
aws apprunner update-service \
  --service-arn "$SERVICE_ARN" \
  --source-configuration '{
    "ImageRepository": {
      "ImageConfiguration": {
        "RuntimeEnvironmentVariables": {
          "DISABLE_COOKIES": "true"
        }
      }
    }
  }'
```

### Rollback Procedure
To completely remove cookie functionality:

1. Set `DISABLE_COOKIES=true` (immediate effect)
2. Remove `COOKIE_S3_BUCKET` environment variable
3. Deploy previous version of code if needed

### Cookie Cleanup
To remove all stored cookies:

```bash
# Remove all cookies from S3 (CAREFUL!)
aws s3 rm s3://$COOKIE_BUCKET_NAME/cookies/ --recursive

# Remove local cookies (if using local storage)
rm -rf /app/cookies/*
```

## Monitoring and Troubleshooting

### Key Metrics to Monitor
- Cookie upload success/failure rates
- Bot-check detection rates with/without cookies
- S3 access errors
- Cookie staleness warnings

### Log Patterns to Watch
- `Using user cookiefile for yt-dlp (user=X)` - Cookie usage
- `Cookie failure for user X: bot_check` - Potential stale cookies
- `S3 cookie download failed` - S3 access issues
- `Cookie functionality disabled` - Kill-switch activated

### Common Issues

**S3 Access Denied**
- Check IAM policy is correctly attached
- Verify bucket name in environment variable
- Ensure bucket exists and has correct permissions

**Cookie Upload Fails**
- Check local directory permissions
- Verify S3 bucket configuration
- Check application logs for specific errors

**Bot-Check Still Occurring**
- Cookies may be expired/stale
- User needs to re-export fresh cookies
- Check cookie file format validation

## Testing

### Functional Testing
1. Upload a cookie file via `/account/cookies`
2. Attempt to summarize a video that previously failed with bot-check
3. Verify success and check logs for cookie usage

### Security Testing
1. Verify users cannot access other users' cookies
2. Check that cookie contents don't appear in logs
3. Confirm file permissions are correctly set

### Rollback Testing
1. Test kill-switch functionality
2. Verify graceful degradation when cookies disabled
3. Confirm backwards compatibility

## Support

For issues with cookie functionality:
1. Check application logs for specific error messages
2. Verify environment variable configuration
3. Test S3 access permissions
4. Use kill-switch if immediate disable needed