# Transcript Service Enhancements Troubleshooting Guide

## Overview

This guide provides troubleshooting procedures for the enhanced transcript service features. Issues are organized by feature area with specific diagnostic steps and solutions.

## General Diagnostic Steps

### 1. Check Application Health
```bash
# Basic health check
curl http://localhost:5000/health

# Detailed component health
curl http://localhost:5000/healthz

# Check specific components
curl http://localhost:5000/health/ready
curl http://localhost:5000/health/live
```

### 2. Review Application Logs
```bash
# Check recent logs
tail -f /var/log/app.log

# Filter for specific components
grep "transcript_service" /var/log/app.log
grep "circuit_breaker" /var/log/app.log
grep "storage_state" /var/log/app.log
```

### 3. Validate Configuration
```bash
# Run configuration validation
python config_validator.py

# Check environment variables
env | grep -E "(COOKIE_DIR|CIRCUIT_BREAKER|PROXY)"
```

## Feature-Specific Troubleshooting

### 1. Enhanced Storage State Management

#### Issue: Storage state file not loading
**Symptoms:**
- GDPR consent wall appears on YouTube
- Authentication cookies not present
- Warning logs about missing storage state

**Diagnostic Steps:**
```bash
# Check file existence and permissions
ls -la $COOKIE_DIR/youtube_session.json

# Validate JSON format
python -m json.tool $COOKIE_DIR/youtube_session.json

# Check file size (should be > 100 bytes)
wc -c $COOKIE_DIR/youtube_session.json
```

**Solutions:**
```bash
# Fix permissions
chmod 644 $COOKIE_DIR/youtube_session.json

# Regenerate storage state
python cookie_generator.py --warm-up

# Convert from Netscape if available
python cookie_generator.py --from-netscape $COOKIE_DIR/cookies.txt
```#### I
ssue: Netscape conversion failing
**Symptoms:**
- Conversion script exits with error
- Invalid storage state format
- Playwright context creation fails

**Diagnostic Steps:**
```bash
# Check Netscape file format
head -5 $COOKIE_DIR/cookies.txt

# Validate cookie format
grep -c "youtube.com" $COOKIE_DIR/cookies.txt

# Check conversion logs
python cookie_generator.py --from-netscape $COOKIE_DIR/cookies.txt --verbose
```

**Solutions:**
```bash
# Fix Netscape file format (ensure proper headers)
echo "# Netscape HTTP Cookie File" > temp_cookies.txt
cat $COOKIE_DIR/cookies.txt >> temp_cookies.txt
mv temp_cookies.txt $COOKIE_DIR/cookies.txt

# Manual conversion with error handling
python cookie_generator.py --from-netscape $COOKIE_DIR/cookies.txt --ignore-errors
```

### 2. Deterministic Network Interception

#### Issue: Network interception timing out
**Symptoms:**
- YouTubei stage consistently fails
- 20-25 second timeouts in logs
- No transcript data captured

**Diagnostic Steps:**
```bash
# Check Playwright browser installation
playwright install --dry-run chromium

# Test basic navigation
python -c "
import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto('https://youtube.com')
        print('Navigation successful')
        await browser.close()

asyncio.run(test())
"

# Check network route setup
grep "route.*youtubei" /var/log/app.log
```

**Solutions:**
```bash
# Reinstall Playwright browsers
playwright install chromium --force

# Clear browser cache
rm -rf ~/.cache/ms-playwright

# Increase timeout for slow networks
export YOUTUBEI_TIMEOUT=35

# Enable DOM fallback
export ENABLE_DOM_FALLBACK=true
```

#### Issue: Route interception not working
**Symptoms:**
- No route matches in logs
- Future never resolves
- Network requests not captured

**Diagnostic Steps:**
```bash
# Check route pattern matching
grep "route.*pattern" /var/log/app.log

# Verify URL patterns
curl -s "https://www.youtube.com/youtubei/v1/get_transcript" | head

# Test route setup
python test_deterministic_interception_validation.py
```

**Solutions:**
```bash
# Update route patterns for new YouTube URLs
# Check for URL format changes in logs

# Use broader route matching
export USE_BROAD_ROUTE_MATCHING=true

# Enable request logging for debugging
export DEBUG_ROUTE_MATCHING=true
```

### 3. Multi-Client Profile System

#### Issue: Profile switching not working
**Symptoms:**
- Only desktop profile attempts logged
- Mobile profile never tried
- User-Agent not changing between attempts

**Diagnostic Steps:**
```bash
# Check profile configuration
grep "profile.*desktop\|mobile" /var/log/app.log

# Verify User-Agent changes
grep "User-Agent" /var/log/app.log | tail -10

# Test profile switching logic
python test_multi_client_profiles.py
```

**Solutions:**
```bash
# Enable profile switching
export ENABLE_PROFILE_SWITCHING=true

# Verify profile definitions
python -c "
from transcript_service import PROFILES
print(PROFILES)
"

# Reset browser contexts
export FORCE_NEW_BROWSER_CONTEXT=true
```

#### Issue: Browser context creation failing
**Symptoms:**
- Context creation errors in logs
- Memory issues with multiple contexts
- Browser launch failures

**Diagnostic Steps:**
```bash
# Check available memory
free -h

# Monitor browser processes
ps aux | grep chromium

# Check browser launch logs
grep "browser.*launch" /var/log/app.log
```

**Solutions:**
```bash
# Increase memory limits
export PLAYWRIGHT_MEMORY_LIMIT=2048

# Reduce concurrent contexts
export MAX_CONCURRENT_CONTEXTS=2

# Enable context cleanup
export ENABLE_CONTEXT_CLEANUP=true
```

### 4. Enhanced Cookie Integration

#### Issue: User cookies not loading from S3
**Symptoms:**
- Fallback to environment cookies
- S3 access errors in logs
- User-specific content not accessible

**Diagnostic Steps:**
```bash
# Check S3 bucket access
aws s3 ls s3://$USER_COOKIES_S3_BUCKET/

# Test S3 permissions
aws s3 cp test.txt s3://$USER_COOKIES_S3_BUCKET/test.txt

# Check cookie loading logs
grep "cookie_source" /var/log/app.log
```

**Solutions:**
```bash
# Fix S3 permissions
aws s3api put-bucket-policy --bucket $USER_COOKIES_S3_BUCKET --policy file://s3-policy.json

# Verify IAM role permissions
aws sts get-caller-identity

# Test cookie loading
python -c "
from transcript_service import EnhancedCookieManager
cm = EnhancedCookieManager()
cookies = cm.get_cookies_for_request('test-user')
print(f'Loaded {len(cookies)} cookies')
"
```

#### Issue: Timed-text requests failing with cookies
**Symptoms:**
- 403 Forbidden errors on timed-text endpoints
- Cookie headers not being sent
- Member-only content not accessible

**Diagnostic Steps:**
```bash
# Check cookie format in requests
grep "Cookie:" /var/log/app.log

# Test timed-text endpoint directly
curl -H "Cookie: CONSENT=YES+..." "https://www.youtube.com/api/timedtext?v=VIDEO_ID"

# Verify cookie threading
grep "timed.*text.*cookie" /var/log/app.log
```

**Solutions:**
```bash
# Verify cookie format
python -c "
cookies = {'CONSENT': 'YES+cb.20210328-17-p0.en+FX+667'}
print('; '.join([f'{k}={v}' for k, v in cookies.items()]))
"

# Enable cookie debugging
export DEBUG_COOKIE_HEADERS=true

# Test with known working cookies
export FALLBACK_COOKIES="CONSENT=YES+cb.20210328-17-p0.en+FX+667"
```##
# 5. Circuit Breaker Integration

#### Issue: Circuit breaker stuck open
**Symptoms:**
- All transcript attempts skipped
- "Circuit breaker open" messages in logs
- No recovery after timeout period

**Diagnostic Steps:**
```bash
# Check circuit breaker state
grep "circuit_breaker.*state" /var/log/app.log | tail -5

# Check failure count and timing
grep "circuit_breaker.*failure" /var/log/app.log

# Verify recovery timeout
echo $CIRCUIT_BREAKER_RECOVERY_TIMEOUT
```

**Solutions:**
```bash
# Reset circuit breaker manually
curl -X POST http://localhost:5000/admin/reset-circuit-breaker

# Increase recovery timeout
export CIRCUIT_BREAKER_RECOVERY_TIMEOUT=300

# Increase failure threshold
export CIRCUIT_BREAKER_FAILURE_THRESHOLD=10

# Disable circuit breaker temporarily
export ENABLE_CIRCUIT_BREAKER=false
```

#### Issue: Circuit breaker not activating
**Symptoms:**
- Continuous failures without circuit breaker activation
- No circuit breaker state changes in logs
- Resource waste on failing operations

**Diagnostic Steps:**
```bash
# Check failure recording
grep "record_failure" /var/log/app.log

# Verify circuit breaker integration
python test_circuit_breaker_integration.py

# Check threshold configuration
echo "Threshold: $CIRCUIT_BREAKER_FAILURE_THRESHOLD"
```

**Solutions:**
```bash
# Lower failure threshold
export CIRCUIT_BREAKER_FAILURE_THRESHOLD=3

# Enable circuit breaker logging
export ENABLE_CIRCUIT_BREAKER_LOGGING=true

# Verify integration points
grep "circuit_breaker" transcript_service.py
```

### 6. DOM Fallback Implementation

#### Issue: DOM fallback not triggering
**Symptoms:**
- Network timeout but no DOM attempt
- Missing DOM fallback logs
- Transcript extraction fails completely

**Diagnostic Steps:**
```bash
# Check DOM fallback configuration
echo $ENABLE_DOM_FALLBACK

# Verify timeout settings
echo $DOM_FALLBACK_TIMEOUT

# Check DOM selector logs
grep "dom.*selector" /var/log/app.log
```

**Solutions:**
```bash
# Enable DOM fallback
export ENABLE_DOM_FALLBACK=true

# Increase DOM timeout
export DOM_FALLBACK_TIMEOUT=10

# Test DOM selectors
python test_dom_fallback_implementation.py
```

#### Issue: DOM selectors not finding content
**Symptoms:**
- DOM fallback triggered but no content found
- Empty transcript returned
- Selector timeout errors

**Diagnostic Steps:**
```bash
# Check current DOM selectors
grep "selector.*transcript" transcript_service.py

# Test selectors manually
python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto('https://www.youtube.com/watch?v=VIDEO_ID')
    elements = page.query_selector_all('[data-testid=\"transcript-line\"]')
    print(f'Found {len(elements)} transcript elements')
    browser.close()
"
```

**Solutions:**
```bash
# Update DOM selectors for current YouTube layout
# Check YouTube page source for new selectors

# Increase polling interval
export DOM_POLLING_INTERVAL=1000

# Enable selector debugging
export DEBUG_DOM_SELECTORS=true
```

### 7. Proxy-Enforced FFmpeg Audio Extraction

#### Issue: FFmpeg not using proxy
**Symptoms:**
- Direct connections in network logs
- Geo-blocked content still failing
- External IP not changing with proxy

**Diagnostic Steps:**
```bash
# Check proxy environment variables
env | grep -i proxy

# Test proxy with curl
curl -x $http_proxy https://httpbin.org/ip

# Check FFmpeg command construction
grep "ffmpeg.*proxy" /var/log/app.log
```

**Solutions:**
```bash
# Verify proxy environment setup
python -c "
from proxy_manager import ProxyManager
pm = ProxyManager()
env = pm.proxy_env_for_subprocess()
print(env)
"

# Test proxy connectivity
export http_proxy=http://user:pass@proxy:port
export https_proxy=http://user:pass@proxy:port
curl https://httpbin.org/ip

# Enable proxy debugging
export DEBUG_PROXY_ENV=true
```

#### Issue: FFmpeg header formatting errors
**Symptoms:**
- "No trailing CRLF" errors
- Header parsing failures
- Authentication failures with cookies

**Diagnostic Steps:**
```bash
# Check header format in logs
grep "headers.*CRLF" /var/log/app.log

# Verify header construction
python test_ffmpeg_header_hygiene.py

# Check cookie masking
grep "Cookie:" /var/log/app.log | head -5
```

**Solutions:**
```bash
# Fix header formatting
python -c "
headers = {'Cookie': 'test=value', 'User-Agent': 'test'}
header_string = '\\r\\n'.join([f'{k}: {v}' for k, v in headers.items()]) + '\\r\\n'
print(repr(header_string))
"

# Verify parameter order
grep "ffmpeg.*-headers.*-i" /var/log/app.log

# Enable header debugging (with masking)
export DEBUG_FFMPEG_HEADERS=true
```

### 8. Performance and Monitoring Issues

#### Issue: Metrics not being collected
**Symptoms:**
- No performance metrics in logs
- Dashboard showing no data
- Missing structured events

**Diagnostic Steps:**
```bash
# Check metrics configuration
echo $ENABLE_PERFORMANCE_METRICS

# Verify metrics collection
grep "stage_duration_ms" /var/log/app.log

# Check structured logging
grep "structured_event" /var/log/app.log
```

**Solutions:**
```bash
# Enable metrics collection
export ENABLE_PERFORMANCE_METRICS=true

# Reduce collection interval
export METRICS_COLLECTION_INTERVAL=10

# Test metrics emission
python validate_task_10_implementation.py
```

#### Issue: High memory usage
**Symptoms:**
- Memory usage growing over time
- Browser context leaks
- Out of memory errors

**Diagnostic Steps:**
```bash
# Monitor memory usage
watch -n 5 'free -h && ps aux | grep chromium | wc -l'

# Check context cleanup
grep "context.*cleanup" /var/log/app.log

# Monitor browser processes
ps aux | grep chromium
```

**Solutions:**
```bash
# Enable context cleanup
export ENABLE_CONTEXT_CLEANUP=true

# Reduce context lifetime
export CONTEXT_MAX_AGE=300

# Limit concurrent contexts
export MAX_CONCURRENT_CONTEXTS=2

# Force garbage collection
export FORCE_GC_AFTER_EXTRACTION=true
```

## Emergency Procedures

### 1. Complete Service Rollback
```bash
# Disable all enhancements
export ENABLE_ENHANCED_FEATURES=false
export USE_LEGACY_INTERCEPTION=true
export ENABLE_CIRCUIT_BREAKER=false

# Restart service
systemctl restart tldw-app
```

### 2. Partial Feature Rollback
```bash
# Disable specific problematic features
export ENABLE_DOM_FALLBACK=false
export ENABLE_MULTI_CLIENT_PROFILES=false

# Keep working features
export ENABLE_ENHANCED_STORAGE_STATE=true
export ENABLE_COMPLETE_HTTP_ADAPTERS=true
```

### 3. Debug Mode Activation
```bash
# Enable comprehensive debugging
export DEBUG_MODE=true
export DEBUG_ROUTE_MATCHING=true
export DEBUG_COOKIE_HEADERS=true
export DEBUG_PROXY_ENV=true
export DEBUG_DOM_SELECTORS=true

# Increase log verbosity
export LOG_LEVEL=DEBUG
```

## Getting Help

### Log Collection for Support
```bash
# Collect relevant logs
grep -A 5 -B 5 "ERROR\|CRITICAL" /var/log/app.log > error_logs.txt
grep "circuit_breaker\|storage_state\|dom_fallback" /var/log/app.log > feature_logs.txt

# System information
uname -a > system_info.txt
python --version >> system_info.txt
playwright --version >> system_info.txt
```

### Configuration Export
```bash
# Export current configuration
env | grep -E "(COOKIE|CIRCUIT|PROXY|ENABLE)" > current_config.txt

# Test configuration
python config_validator.py > config_validation.txt
```

For additional support, include these files with your support request along with a description of the issue and steps to reproduce.