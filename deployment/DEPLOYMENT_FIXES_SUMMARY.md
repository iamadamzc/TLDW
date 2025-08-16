# Deployment Fixes Summary

## Issues Addressed

Based on deployment logs showing:
- S3 cookie access 403 Forbidden errors
- Proxy authentication 407 errors  
- yt-dlp bot detection failures

## High-Impact Fixes Applied

### 1. yt-dlp Configuration Hardening
**File:** `yt_download_helper.py`
- ✅ Fixed `throttled_rate` → `ratelimit` (correct yt-dlp option name)
- ✅ Added cookiefile existence guard before adding to options
- ✅ Enhanced with `forceipv4`, `http_chunk_size`, and `ratelimit` options
- ✅ Removed `android` from player_client list (keeping `ios`, `web_creator`)

### 2. Cookie Logging Closure Fix
**File:** `transcript_service.py`
- ✅ Fixed closure confusion by computing `cookies_used_flag` before `_log_adapter` definition
- ✅ Removed fragile late-binding reference to `cookiefile` in logging
- ✅ Added cookie source logging (s3 vs local) for better metrics

### 3. S3 IAM Permissions Fix
**Files:** `deployment/cookie-iam-policy.json`, `deployment/enable-cookies.sh`
- ✅ Added missing `kms:Decrypt` permission for SSE-KMS encrypted buckets
- ✅ Enhanced error logging with specific S3 path and permission hints
- ✅ Added ClientError handling with specific 403/AccessDenied detection

### 4. Proxy Authentication Validation
**File:** `transcript_service.py`
- ✅ Added proxy URL credential validation and sanitized logging
- ✅ Warning when proxy URL missing authentication credentials
- ✅ Better debugging for 407 proxy authentication errors

### 5. Deployment Script Improvements
**File:** `deployment/fix-deployment-issues.sh`
- ✅ Added `jq` dependency check to prevent JSON parse errors
- ✅ Automatic detection of current COOKIE_S3_BUCKET from App Runner config
- ✅ Comprehensive IAM policy update with KMS permissions

### 6. Code Cleanup
**File:** `transcript_service.py`
- ✅ Removed unused `import yt_dlp` to keep image lean
- ✅ Added template variable documentation for IAM policy file

## Deployment Steps

### Immediate Fix (for current deployment)
```bash
# Run the quick fix script to update IAM permissions
chmod +x deployment/fix-deployment-issues.sh
./deployment/fix-deployment-issues.sh
```

### Full Deployment (with code changes)
```bash
# Deploy updated code with all fixes
# Then run the fix script to ensure IAM permissions are correct
./deployment/fix-deployment-issues.sh
```

## Expected Log Improvements

### Before Fixes
```
S3 cookie download failed for user 1: An error occurred (403) when calling the HeadObject operation: Forbidden
ERROR: [youtube] NvtsM8Nk72c: HTTP Error 403: Forbidden
407 Proxy Authentication Required
```

### After Fixes
```
Using user cookiefile for yt-dlp (user=1)
Cookie source: s3 for user 1
Using sticky proxy for yt-dlp download: session_123 - http://user:***@host:port
STRUCTURED_LOG step=ytdlp cookies_used=true status=ok
```

## Monitoring Points

### Success Indicators
- `Using user cookiefile for yt-dlp (user=X)` - Cookie resolution working
- `Cookie source: s3` or `Cookie source: local` - Storage backend working
- `cookies_used=true` in structured logs - Cookies being passed to yt-dlp
- No more 403 S3 errors in logs

### Failure Indicators to Watch
- `S3 cookie download failed` with permission hints
- `missing authentication credentials` for proxy issues
- `Cookie failure for user X: bot_check` for stale cookies

## Emergency Procedures

### Kill-Switch
```bash
# Immediately disable cookie functionality
aws apprunner update-service --service-arn $SERVICE_ARN \
  --source-configuration '{"ImageRepository":{"ImageConfiguration":{"RuntimeEnvironmentVariables":{"DISABLE_COOKIES":"true"}}}}'
```

### Rollback
1. Set `DISABLE_COOKIES=true` (immediate effect)
2. Remove `COOKIE_S3_BUCKET` environment variable  
3. Deploy previous code version if needed

## Testing Checklist

- [ ] S3 bucket accessible with new IAM permissions
- [ ] Cookie upload works at `/account/cookies` 
- [ ] Video summarization succeeds with cookies
- [ ] Structured logs show `cookies_used=true`
- [ ] No 403 S3 errors in application logs
- [ ] No 407 proxy authentication errors
- [ ] Bot-check detection still works when cookies fail

## Files Modified

- `yt_download_helper.py` - yt-dlp hardening and cookiefile guard
- `transcript_service.py` - Cookie logging fixes and proxy validation
- `deployment/cookie-iam-policy.json` - Added KMS permissions
- `deployment/enable-cookies.sh` - Updated IAM policy with KMS
- `deployment/fix-deployment-issues.sh` - New quick-fix script
- `deployment/cookie-deployment-guide.md` - Enhanced troubleshooting