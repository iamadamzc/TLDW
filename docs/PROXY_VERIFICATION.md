# Proxy Configuration Verification Guide

This guide explains how to verify that the rotating proxy system is properly configured and working in the TL;DW application.

## Quick Verification Steps

### 1. Check Health Endpoint

Visit your App Runner URL with `/health` endpoint:
```
https://your-app-runner-url.region.awsapprunner.com/health
```

Expected response should include:
```json
{
  "status": "healthy",
  "message": "TL;DW API is running",
  "proxy_enabled": true,
  "proxy_status": {
    "enabled": true,
    "active_sessions": 0,
    "total_requests": 0,
    "total_failures": 0,
    "blocked_sessions": 0,
    "success_rate": 100.0
  }
}
```

### 2. Check Environment Variables

The following environment variables should be configured in App Runner:

- `USE_PROXIES=true`
- `OXYLABS_PROXY_CONFIG` (should reference the AWS Secrets Manager ARN)

### 3. Verify AWS Secrets Manager Access

The application should be able to access the `tldw-oxylabs-proxy-config` secret containing:
```json
{
  "host": "pr.oxylabs.io",
  "port": 7777,
  "username": "customer-tldw__BwTQx-cc-US",
  "password": "b6AXONDdSBHA3U_",
  "session_ttl_minutes": 10,
  "max_requests_per_second": 2,
  "jitter_ms": 250
}
```

## Testing Proxy Functionality

### 1. Test Transcript Fetching

Try fetching a transcript for a YouTube video through the application. Check the logs for:

```
INFO - ProxyManager initialized with Oxylabs proxy
INFO - Created new proxy session [session_id] for video [video_id]
INFO - Request success: video_id=[video_id], session_id=[session_id], status=200
```

### 2. Monitor for Blocking Detection

If YouTube blocking occurs, you should see logs like:
```
WARNING - YouTube blocking detected for video [video_id], session [session_id]
INFO - Retrying transcript fetch for [video_id] with rotated session [new_session_id]
```

### 3. Check Session Statistics

The proxy manager maintains statistics that can be accessed via the health endpoint or logs:
- Active sessions count
- Success rate percentage
- Blocked sessions count
- Total requests processed

## Troubleshooting

### Common Issues

1. **Proxy not enabled**
   - Check `USE_PROXIES` environment variable is set to "true"
   - Verify App Runner configuration includes the environment variable

2. **AWS Secrets Manager access denied**
   - Check App Runner IAM role has `secretsmanager:GetSecretValue` permission
   - Verify the secret ARN is correct in the IAM policy

3. **Proxy connection failures**
   - Verify Oxylabs credentials are correct in the secret
   - Check network connectivity from App Runner to Oxylabs servers
   - Review proxy configuration format in the secret

4. **High blocking rates**
   - Monitor success rates in proxy statistics
   - Check if rate limiting is properly configured
   - Verify session rotation is working correctly

### Log Analysis

Look for these key log patterns:

**Successful proxy initialization:**
```
INFO - ProxyManager initialized with Oxylabs proxy
INFO - Loaded proxy config: pr.oxylabs.io:7777
```

**Session management:**
```
INFO - Created new proxy session [session_id] for video [video_id]
INFO - Reusing session [session_id] for video [video_id]
INFO - Rotating session [old_session_id] for video [video_id]
```

**Request success:**
```
INFO - Request success: video_id=[video_id], session_id=[session_id], url=[url], status=200
```

**Blocking detection:**
```
WARNING - YouTube blocking detected for video [video_id]: HTTP 403 - YouTube blocking detected
INFO - Falling back to ASR for video [video_id] due to blocking
```

## Performance Monitoring

### Key Metrics to Monitor

1. **Success Rate**: Should be ≥95% for first/second attempts
2. **Blocking Rate**: Should be <2% after rotation
3. **Session Reuse**: Sessions should be reused within 10-minute TTL
4. **Response Times**: Should be <30 seconds for transcript fetching

### Expected Behavior

- New sessions created for each unique video_id
- Sessions reused for the same video_id within 10 minutes
- Automatic rotation on YouTube blocking detection
- Fallback to ASR when transcript fetching fails after rotation
- Rate limiting: ≤2 requests/second with ±250ms jitter per session

## Success Criteria

The proxy system is working correctly when:

✅ Health endpoint shows `proxy_enabled: true` and valid proxy status
✅ Transcript fetching succeeds for most videos without blocking
✅ Session rotation occurs automatically on blocking detection
✅ Success rate remains ≥95% across varied video content
✅ Application logs show proper proxy session management
✅ No persistent "500 Internal Server Error" responses due to IP blocking