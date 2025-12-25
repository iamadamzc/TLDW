# Environment Variable Migration Guide

## Overview

This guide helps migrate from the previous transcript service configuration to the enhanced version. All changes maintain backward compatibility, but new features require additional configuration.

## Migration Checklist

- [ ] Review existing environment variables
- [ ] Add new optional enhancement variables
- [ ] Update proxy configuration format
- [ ] Configure cookie directory settings
- [ ] Set up circuit breaker parameters
- [ ] Enable performance monitoring
- [ ] Validate configuration

## Existing Variables (No Changes Required)

These variables continue to work exactly as before:

### Core Application
```bash
FLASK_ENV=production
DATABASE_URL=sqlite:///instance/tldw.db
SECRET_KEY=<your-secret-key>
```

### API Keys (Unchanged)
```bash
OPENAI_API_KEY=<your-openai-key>
DEEPGRAM_API_KEY=<your-deepgram-key>
YOUTUBE_API_KEY=<your-youtube-key>
RESEND_API_KEY=<your-resend-key>
```

### Google OAuth (Unchanged)
```bash
GOOGLE_CLIENT_ID=<your-client-id>
GOOGLE_CLIENT_SECRET=<your-client-secret>
```

## New Optional Variables

### Cookie Management Enhancement
```bash
# Cookie directory (defaults to /app/cookies in production)
COOKIE_DIR=/app/cookies

# Enable user-specific cookie loading from S3 (optional)
USER_COOKIES_S3_BUCKET=tldw-user-cookies
ENABLE_USER_COOKIE_PREFERENCE=true
```

### Circuit Breaker Configuration
```bash
# Circuit breaker failure threshold (default: 5)
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5

# Circuit breaker recovery timeout in seconds (default: 60)
CIRCUIT_BREAKER_RECOVERY_TIMEOUT=60

# Enable circuit breaker logging (default: true)
ENABLE_CIRCUIT_BREAKER_LOGGING=true
```

### Retry Configuration
```bash
# Maximum retry attempts for network operations (default: 3)
MAX_RETRY_ATTEMPTS=3

# Retry backoff factor (default: 2)
RETRY_BACKOFF_FACTOR=2

# Enable retry with jitter (default: true)
ENABLE_RETRY_JITTER=true
```

### Performance Monitoring
```bash
# Enable performance metrics collection (default: false)
ENABLE_PERFORMANCE_METRICS=true

# Metrics collection interval in seconds (default: 30)
METRICS_COLLECTION_INTERVAL=30

# Enable structured logging (default: true)
ENABLE_STRUCTURED_LOGGING=true
```

### Multi-Client Profile Configuration
```bash
# Enable multi-client profile support (default: true)
ENABLE_MULTI_CLIENT_PROFILES=true

# Default client profile (desktop|mobile, default: desktop)
DEFAULT_CLIENT_PROFILE=desktop

# Enable profile switching on failure (default: true)
ENABLE_PROFILE_SWITCHING=true
```

### DOM Fallback Configuration
```bash
# Enable DOM fallback when network interception fails (default: true)
ENABLE_DOM_FALLBACK=true

# DOM polling timeout in seconds (default: 5)
DOM_FALLBACK_TIMEOUT=5

# DOM polling interval in milliseconds (default: 500)
DOM_POLLING_INTERVAL=500
```

## Proxy Configuration Migration

### Previous Format (Still Supported)
```bash
# Old environment variable format (deprecated but functional)
PROXY_ENDPOINT=rotating-residential.oxylabs.io:8000
PROXY_USERNAME=customer-username
PROXY_PASSWORD=customer-password
```

### New Format (Recommended)
```bash
# AWS Secrets Manager secret name
PROXY_SECRET_NAME=tldw-proxy-config

# Secret content (JSON format):
{
  "proxy_endpoint": "rotating-residential.oxylabs.io:8000",
  "proxy_username": "customer-username", 
  "proxy_password": "customer-password"
}
```

### Migration Steps
1. **Create AWS Secrets Manager secret**:
```bash
aws secretsmanager create-secret \
  --name tldw-proxy-config \
  --secret-string '{"proxy_endpoint":"rotating-residential.oxylabs.io:8000","proxy_username":"customer-username","proxy_password":"customer-password"}'
```

2. **Update environment variable**:
```bash
# Remove old variables (optional, they still work)
unset PROXY_ENDPOINT PROXY_USERNAME PROXY_PASSWORD

# Add new variable
export PROXY_SECRET_NAME=tldw-proxy-config
```

3. **Verify migration**:
```bash
# Test proxy configuration
curl -X GET https://your-app.awsapprunner.com/health/proxy
```

## Development vs Production Configuration

### Development Environment
```bash
# Local development settings
FLASK_ENV=development
COOKIE_DIR=./test_cookies
ENABLE_PERFORMANCE_METRICS=false
CIRCUIT_BREAKER_FAILURE_THRESHOLD=10  # Higher threshold for testing
```

### Production Environment
```bash
# Production settings
FLASK_ENV=production
COOKIE_DIR=/app/cookies
ENABLE_PERFORMANCE_METRICS=true
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5   # Lower threshold for stability
```

## Configuration Validation

### Validation Script
Create a validation script to check your configuration:

```bash
#!/bin/bash
# validate_config.sh

echo "Validating transcript service configuration..."

# Check required variables
required_vars=("OPENAI_API_KEY" "DEEPGRAM_API_KEY" "YOUTUBE_API_KEY")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "ERROR: $var is not set"
        exit 1
    fi
done

# Check cookie directory
if [ ! -d "$COOKIE_DIR" ]; then
    echo "WARNING: COOKIE_DIR ($COOKIE_DIR) does not exist"
    mkdir -p "$COOKIE_DIR"
    echo "Created COOKIE_DIR: $COOKIE_DIR"
fi

# Check proxy configuration
if [ -n "$PROXY_SECRET_NAME" ]; then
    echo "Using AWS Secrets Manager for proxy config: $PROXY_SECRET_NAME"
elif [ -n "$PROXY_ENDPOINT" ]; then
    echo "Using legacy proxy environment variables"
else
    echo "No proxy configuration found (optional)"
fi

# Validate numeric configurations
if [ -n "$CIRCUIT_BREAKER_FAILURE_THRESHOLD" ]; then
    if ! [[ "$CIRCUIT_BREAKER_FAILURE_THRESHOLD" =~ ^[0-9]+$ ]]; then
        echo "ERROR: CIRCUIT_BREAKER_FAILURE_THRESHOLD must be a number"
        exit 1
    fi
fi

echo "Configuration validation complete!"
```

### Run Validation
```bash
chmod +x validate_config.sh
./validate_config.sh
```

## Feature Flags for Gradual Migration

You can enable enhancements gradually using feature flags:

### Phase 1: Basic Enhancements
```bash
ENABLE_ENHANCED_STORAGE_STATE=true
ENABLE_DETERMINISTIC_INTERCEPTION=true
ENABLE_COMPLETE_HTTP_ADAPTERS=true
```

### Phase 2: Advanced Features
```bash
ENABLE_MULTI_CLIENT_PROFILES=true
ENABLE_ENHANCED_COOKIE_INTEGRATION=true
ENABLE_DOM_FALLBACK=true
```

### Phase 3: Full Monitoring
```bash
ENABLE_CIRCUIT_BREAKER_INTEGRATION=true
ENABLE_PERFORMANCE_METRICS=true
ENABLE_PROXY_HEALTH_MONITORING=true
```

## Rollback Configuration

If you need to rollback to previous behavior:

```bash
# Disable all enhancements
ENABLE_ENHANCED_FEATURES=false

# Use legacy interception method
USE_LEGACY_INTERCEPTION=true

# Disable new retry logic
USE_LEGACY_RETRY_LOGIC=true

# Disable circuit breaker
ENABLE_CIRCUIT_BREAKER=false
```

## Testing Your Migration

### 1. Configuration Test
```bash
# Test basic functionality
curl -X POST http://localhost:5000/api/summarize \
  -H "Content-Type: application/json" \
  -d '{"video_ids": ["dQw4w9WgXcQ"]}'
```

### 2. Enhancement Test
```bash
# Test with user cookies (if configured)
curl -X POST http://localhost:5000/api/summarize \
  -H "Content-Type: application/json" \
  -d '{"video_ids": ["dQw4w9WgXcQ"], "user_id": "test-user"}'
```

### 3. Health Check Test
```bash
# Test enhanced health endpoints
curl http://localhost:5000/health
curl http://localhost:5000/healthz
curl http://localhost:5000/health/ready
```

## Common Migration Issues

### Issue 1: Cookie Directory Permissions
```bash
# Fix permissions
sudo chown -R app:app $COOKIE_DIR
sudo chmod -R 755 $COOKIE_DIR
```

### Issue 2: Secrets Manager Access
```bash
# Verify IAM permissions
aws secretsmanager get-secret-value --secret-id tldw-proxy-config
```

### Issue 3: Playwright Dependencies
```bash
# Install missing dependencies
playwright install chromium
playwright install-deps
```

### Issue 4: Circuit Breaker Too Sensitive
```bash
# Increase failure threshold
export CIRCUIT_BREAKER_FAILURE_THRESHOLD=10
export CIRCUIT_BREAKER_RECOVERY_TIMEOUT=120
```

## Support and Troubleshooting

If you encounter issues during migration:

1. **Check logs** for configuration validation errors
2. **Run validation script** to verify setup
3. **Test with feature flags** to isolate issues
4. **Use rollback configuration** if needed
5. **Review troubleshooting guide** for specific error patterns

For additional help, see the detailed troubleshooting procedures documentation.