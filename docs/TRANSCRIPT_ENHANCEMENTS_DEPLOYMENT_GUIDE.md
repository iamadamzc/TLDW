# Transcript Service Enhancements Deployment Guide

## Pre-Deployment Checklist

### 1. Environment Validation
- [ ] Verify Python 3.11+ is available
- [ ] Confirm Playwright dependencies are installed
- [ ] Check ffmpeg availability for ASR processing
- [ ] Validate proxy configuration in AWS Secrets Manager
- [ ] Ensure S3 bucket access for user cookies (if using)

### 2. Configuration Review
- [ ] Review `COOKIE_DIR` configuration (defaults to `/app/cookies`)
- [ ] Validate proxy settings in secrets manager
- [ ] Check circuit breaker timeout configurations
- [ ] Verify Deepgram API key for ASR fallback
- [ ] Confirm OpenAI API key for summarization

### 3. Dependency Installation
```bash
# Install enhanced dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Verify ffmpeg installation
ffmpeg -version
```

## Deployment Steps

### 1. Container Build
```bash
# Build enhanced container
make build

# Test container locally
make test

# Validate health endpoints
curl http://localhost:5000/health
curl http://localhost:5000/healthz
```

### 2. Environment Variables

#### Required Variables
```bash
# Core application
FLASK_ENV=production
DATABASE_URL=sqlite:///instance/tldw.db

# Cookie management
COOKIE_DIR=/app/cookies

# API keys (stored in AWS Secrets Manager)
OPENAI_API_KEY=<from-secrets-manager>
DEEPGRAM_API_KEY=<from-secrets-manager>
YOUTUBE_API_KEY=<from-secrets-manager>

# Proxy configuration (stored in AWS Secrets Manager)
PROXY_SECRET_NAME=tldw-proxy-config
```

#### Optional Enhancement Variables
```bash
# Circuit breaker configuration
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT=60

# Retry configuration
MAX_RETRY_ATTEMPTS=3
RETRY_BACKOFF_FACTOR=2

# Performance monitoring
ENABLE_PERFORMANCE_METRICS=true
METRICS_COLLECTION_INTERVAL=30

# User cookie S3 integration
USER_COOKIES_S3_BUCKET=tldw-user-cookies
```

### 3. AWS Secrets Manager Configuration

#### Proxy Configuration
```json
{
  "proxy_endpoint": "rotating-residential.oxylabs.io:8000",
  "proxy_username": "customer-username",
  "proxy_password": "customer-password"
}
```

#### API Keys Configuration
```json
{
  "openai_api_key": "sk-...",
  "deepgram_api_key": "...",
  "youtube_api_key": "..."
}
```

### 4. Container Deployment
```bash
# Deploy to AWS App Runner
./deploy-apprunner.sh

# With enhanced options
./deploy-apprunner.sh --timeout 900 --health-check-path /health
```

### 5. Post-Deployment Validation

#### Health Check Validation
```bash
# Basic health
curl https://your-app.awsapprunner.com/health

# Detailed health with components
curl https://your-app.awsapprunner.com/healthz

# Live/ready checks
curl https://your-app.awsapprunner.com/health/live
curl https://your-app.awsapprunner.com/health/ready
```

#### Feature Validation
```bash
# Test transcript extraction
curl -X POST https://your-app.awsapprunner.com/api/summarize \
  -H "Content-Type: application/json" \
  -d '{"video_ids": ["dQw4w9WgXcQ"], "user_id": "test-user"}'

# Check job status
curl https://your-app.awsapprunner.com/api/jobs/{job_id}
```

## Configuration Migration

### From Previous Version

#### 1. Cookie Directory Migration
```bash
# If using custom cookie directory
export COOKIE_DIR=/custom/path/cookies

# Ensure directory exists and has proper permissions
mkdir -p $COOKIE_DIR
chmod 755 $COOKIE_DIR
```

#### 2. Netscape Cookie Conversion
```bash
# Convert existing Netscape cookies
python cookie_generator.py --from-netscape /path/to/cookies.txt

# Verify storage state creation
ls -la $COOKIE_DIR/youtube_session.json
```

#### 3. Proxy Configuration Update
```bash
# Update secrets manager with new proxy format
aws secretsmanager update-secret \
  --secret-id tldw-proxy-config \
  --secret-string '{"proxy_endpoint": "...", "proxy_username": "...", "proxy_password": "..."}'
```

## Monitoring Setup

### 1. CloudWatch Logs
- Enhanced structured logging provides better filtering
- Circuit breaker state changes are logged as structured events
- Stage duration metrics are available for dashboard creation

### 2. Application Metrics
```bash
# Key metrics to monitor
- transcript_stage_duration_ms{stage, proxy_used, profile}
- circuit_breaker_state_changes{from_state, to_state}
- proxy_health_checks{status, masked_username}
- storage_state_load_attempts{success, fallback_used}
```

### 3. Alerting Rules
```yaml
# Circuit breaker open alert
- alert: CircuitBreakerOpen
  expr: circuit_breaker_state == "open"
  for: 5m
  annotations:
    summary: "Transcript service circuit breaker is open"

# High failure rate alert  
- alert: HighTranscriptFailureRate
  expr: rate(transcript_failures_total[5m]) > 0.1
  for: 2m
  annotations:
    summary: "High transcript extraction failure rate"
```

## Rollback Procedures

### 1. Quick Rollback
```bash
# Rollback to previous container version
aws apprunner update-service \
  --service-arn $SERVICE_ARN \
  --source-configuration ImageRepository='{
    "ImageIdentifier": "previous-image-tag",
    "ImageConfiguration": {...}
  }'
```

### 2. Configuration Rollback
```bash
# Disable enhancements via environment variables
export ENABLE_ENHANCED_FEATURES=false
export USE_LEGACY_INTERCEPTION=true

# Redeploy with legacy configuration
./deploy-apprunner.sh --legacy-mode
```

### 3. Data Rollback
```bash
# Restore previous cookie format if needed
cp $COOKIE_DIR/cookies.txt.backup $COOKIE_DIR/cookies.txt
rm $COOKIE_DIR/youtube_session.json
```

## Performance Tuning

### 1. Circuit Breaker Tuning
```bash
# Adjust failure threshold based on traffic
CIRCUIT_BREAKER_FAILURE_THRESHOLD=10  # Higher for high-traffic

# Adjust recovery timeout
CIRCUIT_BREAKER_RECOVERY_TIMEOUT=120  # Longer for stability
```

### 2. Retry Configuration
```bash
# Tune retry attempts based on success rates
MAX_RETRY_ATTEMPTS=2  # Reduce for faster failures
RETRY_BACKOFF_FACTOR=1.5  # Reduce for faster retries
```

### 3. Resource Allocation
```bash
# Increase memory for browser contexts
export PLAYWRIGHT_MEMORY_LIMIT=2048

# Adjust worker processes
export GUNICORN_WORKERS=4
export GUNICORN_THREADS=2
```

## Troubleshooting

### Common Issues

#### 1. Storage State Loading Failures
```bash
# Check file permissions
ls -la $COOKIE_DIR/youtube_session.json

# Validate JSON format
python -m json.tool $COOKIE_DIR/youtube_session.json

# Check conversion logs
grep "storage_state" /var/log/app.log
```

#### 2. Circuit Breaker Stuck Open
```bash
# Check failure patterns
grep "circuit_breaker" /var/log/app.log | tail -20

# Reset circuit breaker (if needed)
curl -X POST https://your-app.awsapprunner.com/admin/reset-circuit-breaker
```

#### 3. Proxy Connection Issues
```bash
# Validate proxy configuration
curl -x proxy-endpoint:port https://httpbin.org/ip

# Check proxy health metrics
grep "proxy_health" /var/log/app.log
```

#### 4. DOM Fallback Not Working
```bash
# Check Playwright browser installation
playwright install --dry-run chromium

# Validate DOM selectors
grep "dom_fallback" /var/log/app.log
```

For additional troubleshooting, see the detailed troubleshooting guide.