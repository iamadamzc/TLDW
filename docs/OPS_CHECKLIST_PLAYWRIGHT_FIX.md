# Ops Checklist: Playwright Fix Deployment Verification

## Overview

This checklist provides manual commands and CloudWatch filters to verify that the three critical fixes are active in production after deploying the `playwright-fix-2025-08-24T1` version.

## Critical Fixes to Verify

1. **Storage State Path Load**: Verify `/app/cookies/youtube_session.json` is being loaded
2. **Playwright Proxy Usage**: Confirm Playwright is using proxy (`via_proxy=True`)
3. **ASR Circuit Breaker Bypass**: Ensure ASR continues even when Playwright circuit breaker is active

## Deployment Verification Commands

### 1. Deploy with Tagged Image

```bash
# Deploy the new version
./deploy-apprunner.sh

# Verify the deployed tag is correct
echo "Expected tag format: playwright-fix-YYYYMMDD-HHMMSS"
```

### 2. Health Check Verification

```bash
# Get service URL from AWS
SERVICE_URL=$(aws apprunner describe-service \
  --service-arn "arn:aws:apprunner:us-west-2:528131355234:service/tldw-container-app/..." \
  --region us-west-2 \
  --query 'Service.ServiceUrl' \
  --output text)

# Test health endpoint
curl -s "https://${SERVICE_URL}/healthz" | jq '.'

# Test detailed health endpoint
curl -s "https://${SERVICE_URL}/health" | jq '.'
```

### 3. Version Verification

```bash
# Check logs for version markers
aws logs filter-log-events \
  --log-group-name "/aws/apprunner/tldw-container-app/application" \
  --region us-west-2 \
  --start-time $(date -d '10 minutes ago' +%s)000 \
  --filter-pattern "playwright-fix-2025-08-24T1" \
  --query 'events[*].[timestamp,message]' \
  --output table
```

## CloudWatch Log Filters

### Filter 1: Version Verification

**Purpose**: Confirm the correct version is running

```bash
# CloudWatch Insights Query
fields @timestamp, @message
| filter @message like /TranscriptService version: playwright-fix-2025-08-24T1/
| sort @timestamp desc
| limit 20
```

**Manual AWS CLI Command**:
```bash
aws logs filter-log-events \
  --log-group-name "/aws/apprunner/tldw-container-app/application" \
  --region us-west-2 \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --filter-pattern "TranscriptService version: playwright-fix-2025-08-24T1" \
  --query 'events[*].[timestamp,message]' \
  --output table
```

### Filter 2: Storage State Validation

**Purpose**: Verify `/app/cookies/youtube_session.json` is being loaded

```bash
# CloudWatch Insights Query
fields @timestamp, @message
| filter @message like /Using Playwright storage_state at \/app\/cookies\/youtube_session.json/
| sort @timestamp desc
| limit 20
```

**Manual AWS CLI Command**:
```bash
aws logs filter-log-events \
  --log-group-name "/aws/apprunner/tldw-container-app/application" \
  --region us-west-2 \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --filter-pattern "Using Playwright storage_state at /app/cookies/youtube_session.json" \
  --query 'events[*].[timestamp,message]' \
  --output table
```

### Filter 3: Proxy Usage Verification

**Purpose**: Confirm Playwright is using proxy (`via_proxy=True`)

```bash
# CloudWatch Insights Query
fields @timestamp, @message
| filter @message like /youtubei_attempt.*via_proxy=True/
| sort @timestamp desc
| limit 20
```

**Manual AWS CLI Command**:
```bash
aws logs filter-log-events \
  --log-group-name "/aws/apprunner/tldw-container-app/application" \
  --region us-west-2 \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --filter-pattern "youtubei_attempt" \
  --query 'events[?contains(message, `via_proxy=True`)][timestamp,message]' \
  --output table
```

### Filter 4: ASR Fallback Continuation

**Purpose**: Verify ASR continues when circuit breaker is active

```bash
# CloudWatch Insights Query
fields @timestamp, @message
| filter @message like /Playwright circuit breaker active - continuing to ASR fallback/
| sort @timestamp desc
| limit 20
```

**Manual AWS CLI Command**:
```bash
aws logs filter-log-events \
  --log-group-name "/aws/apprunner/tldw-container-app/application" \
  --region us-west-2 \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --filter-pattern "Playwright circuit breaker active - continuing to ASR fallback" \
  --query 'events[*].[timestamp,message]' \
  --output table
```

### Filter 5: App Boot Version

**Purpose**: Verify app startup shows correct version

```bash
# CloudWatch Insights Query
fields @timestamp, @message
| filter @message like /App boot version: playwright-fix-2025-08-24T1/
| sort @timestamp desc
| limit 20
```

**Manual AWS CLI Command**:
```bash
aws logs filter-log-events \
  --log-group-name "/aws/apprunner/tldw-container-app/application" \
  --region us-west-2 \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --filter-pattern "App boot version: playwright-fix-2025-08-24T1" \
  --query 'events[*].[timestamp,message]' \
  --output table
```

## Verification Checklist

### Pre-Deployment
- [ ] Confirm current App Runner service status is RUNNING
- [ ] Note current image tag for rollback reference
- [ ] Verify AWS CLI is configured and authenticated

### During Deployment
- [ ] Deploy script completes successfully
- [ ] New image tag follows format: `playwright-fix-YYYYMMDD-HHMMSS`
- [ ] App Runner service transitions to RUNNING state
- [ ] Health check endpoint returns 200 OK

### Post-Deployment Verification

#### Version Confirmation
- [ ] **Filter 1**: Version logs show `playwright-fix-2025-08-24T1`
- [ ] **Filter 5**: App boot logs show correct version

#### Critical Fix #1: Storage State Path
- [ ] **Filter 2**: Logs show "Using Playwright storage_state at /app/cookies/youtube_session.json"
- [ ] No "storage_state missing" warnings in recent logs

#### Critical Fix #2: Proxy Usage
- [ ] **Filter 3**: Logs show `youtubei_attempt` with `via_proxy=True`
- [ ] Proxy configuration is active in production

#### Critical Fix #3: ASR Fallback
- [ ] **Filter 4**: Logs show "continuing to ASR fallback" (when circuit breaker is active)
- [ ] No "skipping ASR" messages in recent logs

### Functional Testing
- [ ] Submit a test transcript request
- [ ] Verify transcript is returned successfully
- [ ] Check logs for proper method progression (playwright → yt_api → timedtext → asr)

## Rollback Procedure

If verification fails, rollback using the previous image:

```bash
# Get previous image from deployment logs or AWS console
PREVIOUS_IMAGE="528131355234.dkr.ecr.us-west-2.amazonaws.com/tldw:previous-tag"

# Rollback
./deploy-apprunner.sh --rollback-to "${PREVIOUS_IMAGE}"
```

## Troubleshooting

### No Version Logs Found
- Check if the service has restarted since deployment
- Verify log group name and region are correct
- Increase time range in filters

### Storage State Missing
- Check if `/app/cookies/youtube_session.json` exists in container
- Verify `COOKIE_DIR` environment variable is set to `/app/cookies`
- Run `python cookie_generator.py` if needed

### Proxy Not Active
- Verify `OXYLABS_PROXY_CONFIG` secret is configured
- Check proxy health endpoint: `/health/ready`
- Review proxy manager initialization logs

### ASR Still Being Skipped
- Check circuit breaker status in logs
- Verify ASR is not disabled via `ASR_DISABLED` environment variable
- Confirm Deepgram API key is configured

## Success Criteria

✅ **Deployment is successful when:**
1. All 5 CloudWatch filters return expected log entries
2. Health endpoints return 200 OK
3. Version markers show `playwright-fix-2025-08-24T1`
4. Test transcript requests complete successfully
5. No critical errors in application logs

## Contact Information

- **Deployment Issues**: Check App Runner console and CloudWatch logs
- **Application Issues**: Review `/health` endpoint for diagnostic information
- **Rollback**: Use the rollback procedure above with previous image tag

---

**Document Version**: 1.0  
**Last Updated**: 2025-08-24  
**Deployment Tag**: `playwright-fix-2025-08-24T1`
