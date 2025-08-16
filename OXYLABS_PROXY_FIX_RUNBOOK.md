# Oxylabs Proxy 407 Authentication Fix - Deployment Runbook

## Problem Summary

The application was experiencing consistent 407 Proxy Authentication Required errors when using Oxylabs proxy services. Root cause: **double URL-encoding** of credentials due to storing URL-encoded values in AWS Secrets Manager, which were then encoded again by the application.

## Solution Implemented

Added automatic credential normalization in `proxy_manager.py` that:
- Detects URL-encoded credentials (containing `%XX` sequences)
- Safely decodes them once before applying proper URL encoding
- Maintains backward compatibility with raw credentials
- Provides clear diagnostic logging

## Deployment Steps

### 1. Update Oxylabs Secret with RAW Credentials

**CRITICAL**: Store credentials in their raw, unencoded form in AWS Secrets Manager.

```bash
# Replace with your actual credentials - these are examples
aws secretsmanager put-secret-value \
  --region us-west-2 \
  --secret-id tldw-oxylabs-proxy-config-mkbzlM \
  --secret-string '{
    "username": "new_user_LDKZF",
    "password": "319z8jZt4KkHgR+",
    "geo_enabled": true,
    "country": "us",
    "session_ttl_minutes": 30,
    "timeout_seconds": 15
  }'
```

**Key Points:**
- Store the password as `319z8jZt4KkHgR+` (with the actual plus sign)
- Do NOT store as `319z8jZt4KkHgR%2B` (URL-encoded)
- Username should be raw: `new_user_LDKZF` (not `new%5Fuser%5FLDKZF`)

### 2. Deploy the Updated Code

```bash
# Deploy with force restart to pick up new secret values
./deploy.sh --force-restart --tail
```

### 3. Verify the Fix

#### Check Health Endpoint
```bash
# Replace with your actual service URL
curl -s https://your-service-url/healthz | jq .
```

**Expected Response:**
```json
{
  "proxy_connectivity": {
    "status": "success",
    "response_code": 200,
    "proxy_ip": "xxx.xxx.xxx.xxx"
  },
  "proxy_config": {
    "status": "configured",
    "looks_percent_encoded_password": false
  }
}
```

#### Check Application Logs
Look for these success indicators:
```
✅ SUCCESS: "ProxyManager initialized with Oxylabs proxy"
✅ SUCCESS: Proxy connectivity test shows status: "success"
✅ SUCCESS: No "407 Proxy Authentication Required" errors
✅ SUCCESS: yt-dlp downloads succeed with "yt_step1_ok" or "yt_step1_fail_step2_ok"
```

#### Test Video Summarization
Try summarizing a known working video to confirm end-to-end functionality.

## Troubleshooting

### If You Still See 407 Errors

1. **Check if normalization is working:**
   ```bash
   # Look for these log messages
   grep "Detected percent-encoded proxy" /path/to/logs
   ```

2. **Verify secret format:**
   ```bash
   aws secretsmanager get-secret-value \
     --region us-west-2 \
     --secret-id tldw-oxylabs-proxy-config-mkbzlM \
     --query SecretString --output text | jq .
   ```

3. **Check health diagnostics:**
   ```bash
   curl -s https://your-service-url/healthz?DEBUG_HEALTHZ=true | jq .proxy_config
   ```

### Common Issues

**Issue**: `looks_percent_encoded_password: true` in health check
**Solution**: The secret still contains URL-encoded values. Update with raw credentials.

**Issue**: Still getting 407 after deployment
**Solution**: 
1. Verify the secret was updated correctly
2. Ensure App Runner picked up the new secret (may need service restart)
3. Check logs for normalization messages

**Issue**: Proxy connectivity test fails with different error
**Solution**: Verify Oxylabs account status and IP whitelist settings

## Validation Commands

### Test Normalization Function
```bash
# Run the test suite to verify normalization works
python test_proxy_normalization.py
```

### Check Proxy Session Creation
```bash
# Look for successful session creation in logs
grep "Created new proxy session" /path/to/logs
```

### Monitor Success Rate
```bash
# Check for successful yt-dlp operations
grep "yt_step1_ok\|yt_step1_fail_step2_ok" /path/to/logs
```

## Rollback Plan

If issues occur, you can temporarily disable proxies:
```bash
# Set environment variable to disable proxies
aws apprunner update-service \
  --service-arn your-service-arn \
  --source-configuration '{
    "AutoDeploymentsEnabled": false,
    "CodeRepository": {
      "RepositoryUrl": "your-repo-url",
      "SourceCodeVersion": {
        "Type": "BRANCH",
        "Value": "main"
      },
      "CodeConfiguration": {
        "ConfigurationSource": "API",
        "CodeConfigurationValues": {
          "Runtime": "PYTHON_3_11",
          "BuildCommand": "pip install -r requirements.txt",
          "StartCommand": "gunicorn --bind 0.0.0.0:8000 wsgi:app",
          "RuntimeEnvironmentVariables": {
            "USE_PROXIES": "false"
          }
        }
      }
    }
  }'
```

## Success Metrics

- ✅ Health check shows `proxy_connectivity.status == "success"`
- ✅ No 407 errors in application logs
- ✅ yt-dlp downloads succeed consistently
- ✅ Video summarization works end-to-end
- ✅ `looks_percent_encoded_password: false` in health diagnostics

## Files Modified

- `proxy_manager.py`: Added `_normalize_credential()` function and integration
- `test_proxy_normalization.py`: Test suite for validation
- `OXYLABS_PROXY_FIX_RUNBOOK.md`: This deployment guide

## Technical Details

The fix handles these encoding scenarios:
- `%2B` → `+` (plus sign)
- `%5F` → `_` (underscore) 
- `%40` → `@` (at symbol)
- `%3A` → `:` (colon)
- `%21` → `!` (exclamation)

Raw credentials are preserved unchanged, ensuring backward compatibility.
