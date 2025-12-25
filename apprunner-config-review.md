# App Runner Service Configuration Review

**Service:** tldw-container-app  
**Status:** ✅ RUNNING  
**URL:** https://wy2vvma4cw.us-west-2.awsapprunner.com/  
**ARN:** arn:aws:apprunner:us-west-2:528131355234:service/tldw-container-app/81cfdc5538c04039bddfedb791e69e6f

## Runtime Environment Variables

### Application Config
- `PORT`: 8080
- `COOKIE_DIR`: /app/cookies
- `COOKIE_LOCAL_DIR`: /app/cookies
- `COOKIE_S3_BUCKET`: tldw-cookies-bucket
- `FFMPEG_LOCATION`: /usr/bin
- `SENDER_EMAIL`: noreply@resend.dev
- `FORCE_UPDATE`: 2025-08-16-05-40

### Feature Flags
- `ENABLE_ASR_FALLBACK`: 1 ✅ (ASR fallback enabled)
- `ENABLE_PLAYWRIGHT_PRIMARY`: true ✅ (Playwright enabled for YouTubei)
- `ALLOW_MISSING_DEPS`: true
- `USE_PROXIES`: true ✅ (Proxy usage enabled)
- `ENFORCE_PROXY_ALL`: 1 ✅ (All requests use proxy)
- `USE_PROXY_FOR_TIMEDTEXT`: 1 ✅ (Timedtext uses proxy)

### Proxy Configuration
- `PROXY_SECRET_NAME`: tldw-oxylabs-proxy-config
- `OXY_DISABLE_GEO`: true

### Playwright Settings
- `PW_NAV_TIMEOUT_MS`: 120000 (120 seconds)

## Runtime Environment Secrets (from Secrets Manager)

- `DEEPGRAM_API_KEY`: arn:aws:secretsmanager:us-west-2:528131355234:secret:...
- `SESSION_SECRET`: arn:aws:secretsmanager:us-west-2:528131355234:secret:TLDW-SESSION-SECRET-hJDTQ1
- (Additional secrets truncated in output)

## Analysis for Transcript Extraction Fixes

### ✅ Compatible Settings
1. **Playwright enabled** (`ENABLE_PLAYWRIGHT_PRIMARY: true`) - Good for YouTubei DOM fixes
2. **ASR fallback enabled** (`ENABLE_ASR_FALLBACK: 1`) - Works with our pipeline
3. **Reasonable navigation timeout** (120s) - Compatible with our robust navigation

### 🔍 Considerations
1. **Proxy enforcement** (`ENFORCE_PROXY_ALL: 1`) - All stages will use proxy
   - YouTubei: Will use proxy ✅
   - Timedtext: Will use proxy ✅ (`USE_PROXY_FOR_TIMEDTEXT: 1`)
   - Our fixes handle proxy scenarios

2. **Navigation timeout** (120s) - Higher than our implemented timeouts:
   - Our networkidle: 15s timeout
   - Our domcontentloaded fallback: 30s timeout
   - **This is fine** - our shorter timeouts will trigger first, then fall back

### ❌ No Conflicts Found

All environment variables are compatible with our transcript extraction fixes:
- YouTubei deterministic DOM sequence
- Robust navigation with fallbacks
- Timedtext TypeError protection
- Cache list format support

**Ready to deploy!**
