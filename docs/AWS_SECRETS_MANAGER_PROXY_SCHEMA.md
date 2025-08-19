# AWS Secrets Manager Proxy Secret Schema Fix

## Problem

The production logs show `proxy_secret_missing_provider` errors, indicating that the AWS Secrets Manager secret is missing the required "provider" field, causing ProxyManager to crash on initialization.

## Solution Overview

This fix provides comprehensive tools to validate and fix AWS Secrets Manager proxy secrets:

1. **Validation Script**: `validate_proxy_secret.py` - Interactive validation and fixing
2. **Deployment Script**: `deployment/fix-proxy-secret-schema.sh` - Automated validation and quick fixes
3. **Enhanced ProxyManager**: Graceful degradation when secrets are malformed
4. **Comprehensive Testing**: Validation of all functionality

## Required Secret Schema

The proxy secret in AWS Secrets Manager must include all required fields:

```json
{
  "provider": "oxylabs",
  "host": "pr.oxylabs.io",
  "port": 60000,
  "username": "your-username",
  "password": "your-password",
  "protocol": "http"
}
```

### Required Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `provider` | string | Proxy provider name | `"oxylabs"` |
| `host` | string | Proxy hostname (no protocol) | `"pr.oxylabs.io"` |
| `port` | integer | Proxy port number | `60000` |
| `username` | string | Proxy username | `"customer-username"` |
| `password` | string | Proxy password (RAW, not URL-encoded) | `"customer-password"` |
| `protocol` | string | Proxy protocol | `"http"` |

### Optional Fields

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `geo_enabled` | boolean | Enable geo-targeting | `false` |
| `country` | string | Country code for geo-targeting | `null` |
| `version` | integer | Secret schema version | `1` |

## Validation Tools

### 1. Python Validation Script

**Interactive validation and fixing:**
```bash
# Validate a secret
python validate_proxy_secret.py validate my-proxy-secret

# Validate and fix interactively
python validate_proxy_secret.py validate my-proxy-secret --fix

# Show example secret format
python validate_proxy_secret.py example

# List potential proxy secrets
python validate_proxy_secret.py list
```

**Features:**
- ✅ Comprehensive schema validation
- ✅ Interactive fixing of missing fields
- ✅ Secure handling (masks sensitive data)
- ✅ AWS integration with proper error handling
- ✅ Example secret generation

### 2. Bash Deployment Script

**Quick validation and fixes:**
```bash
# List proxy secrets
./deployment/fix-proxy-secret-schema.sh list

# Validate a secret
./deployment/fix-proxy-secret-schema.sh validate oxylabs-proxy-secret

# Quick fix: add missing provider field
./deployment/fix-proxy-secret-schema.sh quick-fix oxylabs-proxy-secret oxylabs

# Create example secret file
./deployment/fix-proxy-secret-schema.sh example
```

**Features:**
- ✅ Fast validation without Python dependencies
- ✅ Quick fix for common missing provider issue
- ✅ Colored output for easy reading
- ✅ Comprehensive error checking

## Fixing Existing Secrets

### Method 1: Interactive Python Script (Recommended)

```bash
# Validate and fix interactively
python validate_proxy_secret.py validate oxylabs-proxy-secret --fix
```

This will:
1. Retrieve the current secret
2. Identify missing fields
3. Prompt for missing values (with masked password input)
4. Update the secret in AWS
5. Verify the fix

### Method 2: Quick Fix Script

```bash
# Add missing provider field only
./deployment/fix-proxy-secret-schema.sh quick-fix oxylabs-proxy-secret oxylabs
```

### Method 3: Manual AWS CLI

```bash
# Get current secret
aws secretsmanager get-secret-value --secret-id oxylabs-proxy-secret

# Update with provider field
aws secretsmanager update-secret --secret-id oxylabs-proxy-secret \
  --secret-string '{
    "provider": "oxylabs",
    "host": "pr.oxylabs.io",
    "port": 60000,
    "username": "your-username",
    "password": "your-password",
    "protocol": "http"
  }'
```

### Method 4: AWS Console

1. Go to AWS Secrets Manager
2. Find your proxy secret (e.g., `oxylabs-proxy-secret`)
3. Click "Retrieve secret value"
4. Click "Edit"
5. Add the missing `"provider": "oxylabs"` field
6. Save changes

## Environment Variables

Configure the tools with environment variables:

```bash
# AWS region (default: us-west-2)
export AWS_REGION=us-west-2

# Default secret name for validation
export PROXY_SECRET_NAME=oxylabs-proxy-secret
```

## Validation Examples

### Valid Secret
```bash
$ python validate_proxy_secret.py validate oxylabs-proxy-secret
✅ Secret schema is valid!
📋 Secret contains all required fields:
   ✅ provider: oxylabs
   ✅ host: pr.oxylabs.io
   ✅ port: 60000
   ✅ username: cu***er
   ✅ password: ***
   ✅ protocol: http
```

### Invalid Secret (Missing Provider)
```bash
$ python validate_proxy_secret.py validate oxylabs-proxy-secret
❌ Secret schema is invalid!
🚨 Missing required fields: ['provider']
💡 This will cause 'proxy_secret_missing_provider' errors in production
🔧 To fix this issue, run:
   python validate_proxy_secret.py validate oxylabs-proxy-secret --fix
```

## Integration with ProxyManager

The enhanced ProxyManager (from Task 2) now handles malformed secrets gracefully:

```python
# ProxyManager graceful degradation
proxy_manager = ProxyManager(secret_dict, logger)

if proxy_manager.in_use:
    # Proxy configured successfully
    proxies = proxy_manager.proxies_for(video_id)
else:
    # Graceful degradation to no-proxy mode
    proxies = {}
```

**Benefits:**
- ✅ **Service doesn't crash** on malformed secrets
- ✅ **Graceful degradation** to direct requests
- ✅ **Clear logging** of validation issues
- ✅ **Health endpoints** show proxy status

## Monitoring and Verification

### Health Endpoint Checks
```bash
# Check proxy status in health endpoint
curl https://your-service.com/healthz

# Expected response (with diagnostics enabled):
{
  "status": "healthy",
  "proxy_in_use": true,  # Should be true after fix
  "yt_dlp_version": "2025.8.11"
}
```

### Log Monitoring
```bash
# Should see successful proxy initialization
grep "ProxyManager initialized successfully" /var/log/app.log

# Should NOT see missing provider errors
grep "proxy_secret_missing_provider" /var/log/app.log
```

### Proxy Authentication
```bash
# Should NOT see 407 errors (proxy auth failures)
grep "407 Proxy Authentication Required" /var/log/app.log
```

## Testing

### Validation Script Tests
```bash
python test_proxy_secret_validation.py
```

**Expected Output:**
```
🎉 All tests passed! Proxy secret validation is working correctly.
📝 Key features verified:
   - Valid secret schema detection
   - Missing provider field detection (fixes production issue)
   - Multiple missing fields detection
   - Empty field value detection
   - Example secret creation
   - AWS integration (mocked)
   - Error handling for edge cases
```

### ProxyManager Integration Tests
```bash
python test_proxy_manager_resilience.py
```

## Troubleshooting

### Common Issues

1. **"Secret not found"**
   ```bash
   # List all secrets to find the correct name
   ./deployment/fix-proxy-secret-schema.sh list
   ```

2. **"Access denied"**
   ```bash
   # Check IAM permissions for Secrets Manager
   aws iam get-user-policy --user-name your-user --policy-name SecretsManagerPolicy
   ```

3. **"Invalid JSON"**
   ```bash
   # Validate JSON format
   aws secretsmanager get-secret-value --secret-id your-secret | jq '.SecretString | fromjson'
   ```

4. **"Still getting proxy errors after fix"**
   ```bash
   # Restart the application to pick up new secret
   # Check health endpoint for proxy_in_use status
   curl https://your-service.com/healthz
   ```

### Required IAM Permissions

The user/role needs these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:UpdateSecret",
        "secretsmanager:ListSecrets"
      ],
      "Resource": [
        "arn:aws:secretsmanager:*:*:secret:*proxy*",
        "arn:aws:secretsmanager:*:*:secret:*oxylabs*"
      ]
    }
  ]
}
```

## Security Considerations

### Data Protection
- ✅ **Passwords are masked** in all output
- ✅ **Usernames are partially masked** for security
- ✅ **No sensitive data in logs** during validation
- ✅ **Secure input** for password fields (hidden input)

### Access Control
- ✅ **IAM permissions** required for secret access
- ✅ **Region-specific** secret access
- ✅ **Audit trail** in CloudTrail for secret updates

### Best Practices
- ✅ **Validate before deploy** to production
- ✅ **Test in staging** environment first
- ✅ **Monitor logs** after secret updates
- ✅ **Use least privilege** IAM policies

## Deployment Checklist

Before deploying the fix:

1. **Backup current secret** (if needed)
2. **Validate current secret** with validation script
3. **Fix missing fields** using interactive script
4. **Test in staging** environment
5. **Deploy to production**
6. **Monitor health endpoints** and logs
7. **Verify proxy functionality** is working

After deployment:

1. **Check health endpoints** show `proxy_in_use: true`
2. **Monitor logs** for successful proxy initialization
3. **Verify no 407 errors** in proxy authentication
4. **Test video downloads** work correctly