# Playwright Transcript Pipeline Setup Guide

This guide covers the setup and deployment of the Playwright-first transcript pipeline for TL;DW.

## Overview

The Playwright transcript pipeline uses browser automation to intercept YouTube's internal `/youtubei/v1/get_transcript` API calls, providing higher success rates than traditional transcript extraction methods.

### Pipeline Order
1. **Playwright** (Primary) - Network interception of YouTubei API
2. **YouTube Transcript API** - Library-based extraction
3. **Timedtext** - Direct HTTP requests to YouTube endpoints
4. **ASR** - Audio extraction + Deepgram transcription (always available)

## Prerequisites

### Dependencies
- Python 3.11+
- Playwright 1.47.0+
- Chromium browser (installed via Playwright)

### Environment Variables
```bash
# Required
COOKIE_DIR=/app/cookies                    # Storage location for session files
PROXY_SECRET_NAME=proxy-secret            # AWS Secrets Manager proxy config

# Optional
ENABLE_PLAYWRIGHT_PRIMARY=true            # Enable/disable Playwright (default: true)
ENVIRONMENT=production                    # Environment detection for proxy enforcement
PLAYWRIGHT_HEADLESS=true                  # Run browser in headless mode
PLAYWRIGHT_TIMEOUT_MS=120000              # Navigation timeout (default: 2 minutes)
```

## Local Development Setup

### 1. Install Dependencies
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers
python -m playwright install --with-deps chromium
```

### 2. Set Environment Variables
```bash
# Set cookie directory (adjust path as needed)
export COOKIE_DIR=/path/to/your/cookies

# For development, you can disable proxy requirement
export ENVIRONMENT=development
```

### 3. Generate High-Quality Session
```bash
# Generate YouTube session with proper cookies
python cookie_generator.py

# Verify the session file was created
ls -l "$COOKIE_DIR/youtube_session.json"
```

### 4. Test Configuration
```bash
# Run validation tests
python test_playwright_transcript.py

# Test with a real video (optional)
python -c "
from transcript_service import TranscriptService
service = TranscriptService()
result = service.get_transcript('dQw4w9WgXcQ')  # Rick Roll video
print(f'Success: {bool(result)}')
print(f'Length: {len(result)} chars')
"
```

### 5. Run Application
```bash
python app.py
```

## Production Deployment

### Docker Configuration

The Dockerfile is already configured for Playwright:

```dockerfile
# Uses official Playwright Python image
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

# Installs Chromium with dependencies
RUN playwright install --with-deps chromium

# Sets up cookie directory
ENV COOKIE_DIR=/app/cookies
RUN mkdir -p ${COOKIE_DIR}
```

### AWS App Runner Deployment

1. **Build and Push Container**
```bash
# Build image
docker build -t tldw-app .

# Tag for ECR
docker tag tldw-app:latest <account>.dkr.ecr.<region>.amazonaws.com/tldw-app:latest

# Push to ECR
docker push <account>.dkr.ecr.<region>.amazonaws.com/tldw-app:latest
```

2. **Configure Secrets Manager**

Ensure proxy configuration is available in AWS Secrets Manager:
```json
{
  "provider": "oxylabs",
  "host": "pr.oxylabs.io",
  "port": 7777,
  "username": "customer-username",
  "password": "raw-password-not-url-encoded"
}
```

3. **Deploy via App Runner**
```bash
# Use existing deployment script
./deploy-apprunner.sh
```

### Environment Configuration

#### Required Environment Variables in Production
- `COOKIE_DIR=/app/cookies` (set in Dockerfile)
- `ENVIRONMENT=production` (auto-detected via AWS_REGION)
- `PROXY_SECRET_NAME=proxy-secret` (AWS Secrets Manager)

#### Optional Configuration
- `ENABLE_PLAYWRIGHT_PRIMARY=true` (feature flag for rollback)
- `PLAYWRIGHT_TIMEOUT_MS=120000` (adjust if needed)

## Cookie Management

### Generating Session Cookies

The `cookie_generator.py` script creates high-quality YouTube sessions:

```bash
# Set cookie directory
export COOKIE_DIR=/app/cookies

# Generate session (requires proxy for production-like behavior)
python cookie_generator.py
```

### Session File Location

- **Local Development**: `$COOKIE_DIR/youtube_session.json`
- **Production**: `/app/cookies/youtube_session.json`

### Session File Format

The session file contains Playwright storage state with cookies:
```json
{
  "cookies": [
    {
      "name": "CONSENT",
      "value": "YES+...",
      "domain": ".youtube.com",
      ...
    }
  ],
  "origins": [...]
}
```

## Monitoring and Troubleshooting

### Key Metrics to Monitor

- Playwright transcript success rate
- Circuit breaker activation frequency
- Storage state file availability
- Proxy connection success rate

### Common Issues

#### 1. Missing Storage State File
**Error**: `Playwright storage_state missing at /app/cookies/youtube_session.json`

**Solution**:
```bash
# Generate new session
python cookie_generator.py

# Verify file exists
ls -l "$COOKIE_DIR/youtube_session.json"
```

#### 2. Proxy Configuration Missing in Production
**Error**: `Proxy configuration required in production environment`

**Solution**:
- Verify AWS Secrets Manager contains proxy configuration
- Check `PROXY_SECRET_NAME` environment variable
- Ensure IAM permissions for Secrets Manager access

#### 3. Browser Launch Failures
**Error**: `Failed to launch Chromium browser`

**Solution**:
```bash
# Reinstall Playwright browsers
python -m playwright install --with-deps chromium

# Check Docker base image includes Playwright
# Should use: mcr.microsoft.com/playwright/python:v1.47.0-jammy
```

#### 4. Circuit Breaker Activation
**Log**: `Playwright circuit breaker activated - skipping for 10 minutes`

**Behavior**: 
- Playwright operations are skipped
- Other transcript methods (API, timedtext) continue
- ASR processing remains available

**Recovery**: Circuit breaker automatically resets after 10 minutes or on successful operation

### Performance Tuning

#### Timeout Configuration
```bash
# Increase navigation timeout for slow networks
export PLAYWRIGHT_TIMEOUT_MS=180000  # 3 minutes

# Adjust circuit breaker recovery time (default: 10 minutes)
# This is hardcoded but can be made configurable if needed
```

#### Resource Optimization
- Playwright runs in headless mode by default
- Browser instances are properly cleaned up after each operation
- Storage state is reused across requests for efficiency

## Rollback Strategy

### Disable Playwright
```bash
# Disable Playwright as primary method
export ENABLE_PLAYWRIGHT_PRIMARY=false

# Restart application
# Pipeline will use: YouTube API → Timedtext → ASR
```

### Emergency Rollback
If Playwright causes issues:

1. **Immediate**: Set `ENABLE_PLAYWRIGHT_PRIMARY=false` in App Runner
2. **Code Rollback**: Deploy previous version without Playwright changes
3. **Gradual Re-enable**: Test with small percentage of traffic

## Health Checks

### Application Health Endpoint
```bash
# Check overall health
curl https://your-app.com/healthz

# Response includes Playwright status
{
  "status": "healthy",
  "playwright": {
    "enabled": true,
    "storage_state_exists": true,
    "circuit_breaker_status": "closed"
  }
}
```

### Manual Validation
```bash
# Test Playwright configuration
python test_playwright_transcript.py

# Test specific video
curl -X POST https://your-app.com/api/summarize \
  -H "Content-Type: application/json" \
  -d '{"video_ids": ["dQw4w9WgXcQ"]}'
```

## Security Considerations

### Credential Protection
- Proxy credentials are masked in logs
- Storage state files contain session cookies (protect access)
- AWS Secrets Manager used for proxy configuration

### Network Security
- All production requests use authenticated proxies
- Direct connections blocked in production environment
- Browser automation uses realistic user agents and headers

## Support and Maintenance

### Regular Maintenance
1. **Weekly**: Check storage state file freshness
2. **Monthly**: Regenerate session cookies if success rates decline
3. **Quarterly**: Update Playwright version and browser

### Monitoring Alerts
- Circuit breaker activation frequency > 10% of requests
- Storage state file missing for > 1 hour
- Playwright success rate < 70%

For additional support, check application logs for detailed error messages and performance metrics.