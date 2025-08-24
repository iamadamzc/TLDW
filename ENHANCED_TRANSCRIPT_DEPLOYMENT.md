# Enhanced Transcript API Cookie Integration - Deployment Guide

## Overview

This document describes the deployment configuration for the enhanced transcript API with S3 cookie integration, timeout protection, and circuit breaker functionality.

## Environment Variables

### Required for S3 Cookie Support

```bash
# S3 Cookie Storage
COOKIE_S3_BUCKET=tldw-cookies-bucket

# AWS credentials (via IAM role or environment)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1
```

### Optional Configuration

```bash
# Timeout Configuration
YOUTUBEI_HARD_TIMEOUT=150  # seconds (default: 150)
PLAYWRIGHT_NAVIGATION_TIMEOUT=60  # seconds (default: 60)

# Feature Flags
ENABLE_S3_COOKIES=true  # Enable S3 cookie loading (default: true if boto3 available)
ENABLE_TIMEOUT_PROTECTION=true  # Enable timeout enforcement (default: true)

# Legacy Cookie Support (fallback)
COOKIE_DIR=/app/cookies  # Local cookie directory
COOKIES_HEADER="session_token=abc123; user_id=456"  # Direct cookie header
```

## IAM Permissions

### S3 Cookie Access Policy

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject"
            ],
            "Resource": "arn:aws:s3:::tldw-cookies-bucket/cookies/*"
        }
    ]
}
```

### Minimal IAM Role for App Runner

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject"
            ],
            "Resource": "arn:aws:s3:::tldw-cookies-bucket/cookies/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "secretsmanager:GetSecretValue"
            ],
            "Resource": "arn:aws:secretsmanager:*:*:secret:tldw/*"
        }
    ]
}
```

## S3 Bucket Setup

### Create S3 Bucket

```bash
aws s3 mb s3://tldw-cookies-bucket
```

### Enable Server-Side Encryption

```bash
aws s3api put-bucket-encryption \
    --bucket tldw-cookies-bucket \
    --server-side-encryption-configuration '{
        "Rules": [
            {
                "ApplyServerSideEncryptionByDefault": {
                    "SSEAlgorithm": "aws:kms"
                }
            }
        ]
    }'
```

### Set Bucket Policy (Optional - for additional security)

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Deny",
            "Principal": "*",
            "Action": "s3:ListBucket",
            "Resource": "arn:aws:s3:::tldw-cookies-bucket"
        },
        {
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::ACCOUNT-ID:role/tldw-app-runner-role"
            },
            "Action": [
                "s3:GetObject"
            ],
            "Resource": "arn:aws:s3:::tldw-cookies-bucket/cookies/*"
        }
    ]
}
```

## Health Check Enhancements

### New Health Check Endpoints

The `/healthz` endpoint now includes additional diagnostic information:

```json
{
    "cookie_loading": {
        "s3_available": true,
        "s3_bucket_configured": true,
        "boto3_available": true,
        "current_user_id": null,
        "environment_cookies_available": false
    },
    "timeout_protection": {
        "circuit_breaker_status": "closed",
        "circuit_breaker_failure_count": 0,
        "circuit_breaker_last_failure": null,
        "timeout_enforcement_enabled": true
    }
}
```

### Monitoring Alerts

Set up alerts for:

1. **Circuit Breaker Activation**: `circuit_breaker_status == "open"`
2. **S3 Cookie Failures**: Monitor application logs for S3 cookie loading errors
3. **Timeout Events**: Monitor logs for `timeout_event` entries
4. **High Failure Rates**: Monitor `circuit_breaker_failure_count` increases

## Deployment Steps

### 1. Update App Runner Configuration

```bash
# Update environment variables in App Runner
aws apprunner update-service \
    --service-arn arn:aws:apprunner:region:account:service/tldw-backend \
    --source-configuration '{
        "ImageRepository": {
            "ImageConfiguration": {
                "RuntimeEnvironmentVariables": {
                    "COOKIE_S3_BUCKET": "tldw-cookies-bucket",
                    "YOUTUBEI_HARD_TIMEOUT": "150",
                    "PLAYWRIGHT_NAVIGATION_TIMEOUT": "60"
                }
            }
        }
    }'
```

### 2. Deploy New Container Image

```bash
# Build and push new image
make build
make deploy

# Or using the deployment script
./deploy-apprunner.sh --timeout 600
```

### 3. Verify Deployment

```bash
# Check health endpoint
curl https://your-app-url/healthz | jq '.cookie_loading, .timeout_protection'

# Check application logs
aws logs tail /aws/apprunner/tldw-backend --follow
```

## Testing Cookie Integration

### Upload Test Cookies

1. Log into the application
2. Navigate to `/account/cookies`
3. Upload a Netscape format cookie file
4. Verify cookies are stored in S3: `s3://tldw-cookies-bucket/cookies/{user_id}.txt`

### Test Transcript Fetching

```bash
# Test with user context
curl -X POST https://your-app-url/api/summarize \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer your-token" \
    -d '{"video_ids": ["test_video_id"]}'
```

## Rollback Procedures

### Emergency Rollback

If issues occur, you can disable features via environment variables:

```bash
# Disable S3 cookies (use environment cookies only)
COOKIE_S3_BUCKET=""

# Disable timeout protection (use legacy timeouts)
YOUTUBEI_HARD_TIMEOUT="0"

# Disable circuit breaker
# (Not recommended - circuit breaker prevents cascading failures)
```

### Full Rollback

```bash
# Deploy previous container image
aws apprunner update-service \
    --service-arn arn:aws:apprunner:region:account:service/tldw-backend \
    --source-configuration '{
        "ImageRepository": {
            "ImageIdentifier": "previous-image-tag"
        }
    }'
```

## Performance Considerations

### S3 Cookie Loading

- **Latency**: S3 cookie loading adds ~100-500ms per request
- **Caching**: Consider implementing application-level cookie caching for high-traffic users
- **Fallback**: Environment cookies provide zero-latency fallback

### Timeout Protection

- **Resource Usage**: Timeout protection reduces resource consumption from hanging operations
- **Success Rate**: May slightly reduce success rate for slow operations, but prevents system overload

### Circuit Breaker

- **Availability**: Improves overall system availability by preventing cascading failures
- **Recovery**: Automatically recovers after 10 minutes of no failures

## Troubleshooting

### Common Issues

1. **S3 Access Denied**
   - Check IAM permissions
   - Verify bucket name and region
   - Check AWS credentials

2. **Circuit Breaker Always Open**
   - Check Playwright installation
   - Verify network connectivity to YouTube
   - Review timeout settings

3. **Cookies Not Loading**
   - Verify cookie file format (Netscape)
   - Check S3 bucket and key path
   - Review application logs for S3 errors

### Debug Commands

```bash
# Check S3 cookie access
aws s3 ls s3://tldw-cookies-bucket/cookies/

# Test S3 permissions
aws s3 cp s3://tldw-cookies-bucket/cookies/123.txt -

# Check application health
curl https://your-app-url/healthz | jq
```

## Security Notes

1. **Cookie Encryption**: Cookies are encrypted at rest in S3 using KMS
2. **Access Control**: IAM policies restrict access to cookie paths only
3. **Logging**: Cookie values are never logged, only cookie names
4. **Cleanup**: Temporary files are automatically cleaned up
5. **Least Privilege**: IAM roles follow least privilege principle