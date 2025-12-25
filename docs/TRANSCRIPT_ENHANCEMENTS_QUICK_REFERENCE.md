# Transcript Service Enhancements Quick Reference

## New Features Summary

### 🔄 Enhanced Storage State Management
- Automatic loading of `${COOKIE_DIR}/youtube_session.json`
- Netscape cookie conversion with `--from-netscape` flag
- GDPR consent bypass for authenticated sessions

### 🎯 Deterministic Network Interception
- Route-based interception using `page.route()`
- Future resolution pattern (no more fixed waits)
- 20-25 second timeout with fallback

### 📱 Multi-Client Profile System
- Desktop profile: Chrome Windows 10, 1920×1080
- Mobile profile: Android Chrome, 390×844
- Attempt sequence: desktop(no-proxy → proxy) → mobile(no-proxy → proxy)

### 🍪 Enhanced Cookie Integration
- User-specific cookie preference (S3 → env → file)
- Timed-text method cookie parameters
- Debug logging for cookie source tracking

### 🔄 Circuit Breaker Integration
- Tenacity retry wrapper with exponential backoff + jitter
- Circuit breaker hooks for failure/success recording
- Skip logic when breaker is open

### 🌐 DOM Fallback Implementation
- DOM polling after network route timeout
- 3-5 second transcript line selector polling
- Text extraction when network is blocked

### 🔧 Proxy-Enforced FFmpeg
- Proxy environment variables for ffmpeg subprocess
- Immediate failure detection for broken proxies
- External IP verification

### 📊 Comprehensive Metrics
- Structured event emission for circuit breaker states
- Stage duration logging with success/failure tracking
- Dashboard integration with p50/p95 metrics

## Quick Commands

### Cookie Management
```bash
# Convert Netscape cookies to storage state
python cookie_generator.py --from-netscape /path/to/cookies.txt

# Warm up storage state
python cookie_generator.py --warm-up

# Check storage state
ls -la $COOKIE_DIR/youtube_session.json
```

### Health Checks
```bash
# Basic health
curl http://localhost:5000/health

# Detailed health
curl http://localhost:5000/healthz

# Component status
curl http://localhost:5000/health/ready
```

### Configuration Validation
```bash
# Validate configuration
python config_validator.py

# Check environment variables
env | grep -E "(COOKIE_DIR|CIRCUIT_BREAKER|PROXY)"
```

### Troubleshooting
```bash
# Check recent logs
tail -f /var/log/app.log

# Filter for specific features
grep "circuit_breaker\|storage_state\|dom_fallback" /var/log/app.log

# Test specific components
python test_deterministic_interception_validation.py
python test_multi_client_profiles.py
python test_circuit_breaker_integration.py
```

## Key Environment Variables

### Required (Unchanged)
```bash
OPENAI_API_KEY=<your-key>
DEEPGRAM_API_KEY=<your-key>
YOUTUBE_API_KEY=<your-key>
```

### New Optional Variables
```bash
# Cookie management
COOKIE_DIR=/app/cookies
USER_COOKIES_S3_BUCKET=tldw-user-cookies

# Circuit breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT=60

# Performance monitoring
ENABLE_PERFORMANCE_METRICS=true
METRICS_COLLECTION_INTERVAL=30

# Feature flags
ENABLE_MULTI_CLIENT_PROFILES=true
ENABLE_DOM_FALLBACK=true
ENABLE_CIRCUIT_BREAKER_INTEGRATION=true
```

## Common Issues & Quick Fixes

### Storage State Not Loading
```bash
# Check file permissions
chmod 644 $COOKIE_DIR/youtube_session.json

# Regenerate if corrupted
python cookie_generator.py --warm-up
```

### Circuit Breaker Stuck Open
```bash
# Reset manually
curl -X POST http://localhost:5000/admin/reset-circuit-breaker

# Increase threshold
export CIRCUIT_BREAKER_FAILURE_THRESHOLD=10
```

### Network Interception Failing
```bash
# Reinstall Playwright
playwright install chromium --force

# Enable DOM fallback
export ENABLE_DOM_FALLBACK=true
```

### Proxy Issues
```bash
# Test proxy connectivity
curl -x $http_proxy https://httpbin.org/ip

# Check proxy environment
python -c "from proxy_manager import ProxyManager; print(ProxyManager().proxy_env_for_subprocess())"
```

## Migration Checklist

- [ ] Review existing environment variables (all unchanged)
- [ ] Add new optional enhancement variables
- [ ] Update proxy configuration to use AWS Secrets Manager
- [ ] Configure cookie directory settings
- [ ] Set up circuit breaker parameters
- [ ] Enable performance monitoring
- [ ] Test health endpoints
- [ ] Validate transcript extraction with enhancements
- [ ] Monitor structured logs for new events

## Rollback Commands

### Emergency Rollback
```bash
export ENABLE_ENHANCED_FEATURES=false
export USE_LEGACY_INTERCEPTION=true
export ENABLE_CIRCUIT_BREAKER=false
systemctl restart tldw-app
```

### Partial Rollback
```bash
export ENABLE_DOM_FALLBACK=false
export ENABLE_MULTI_CLIENT_PROFILES=false
# Keep working features enabled
```

For detailed information, see the complete documentation guides.