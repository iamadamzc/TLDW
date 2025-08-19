# Health Endpoints Guide

## Overview

The application provides comprehensive health endpoints with gated diagnostics for monitoring system status while maintaining security best practices.

## Available Endpoints

### 1. `/healthz` - Primary Health Check

**Purpose**: Main health endpoint for App Runner and load balancers

**Basic Response** (default, diagnostics disabled):
```json
{
  "status": "healthy"
}
```

**Enhanced Response** (when `EXPOSE_HEALTH_DIAGNOSTICS=true`):
```json
{
  "status": "healthy",
  "yt_dlp_version": "2025.8.11",
  "ffmpeg_available": true,
  "proxy_in_use": false,
  "last_download_used_cookies": false,
  "last_download_client": "android",
  "timestamp": "2025-01-19T10:30:00.000Z"
}
```

### 2. `/health/yt-dlp` - yt-dlp Specific Diagnostics

**Purpose**: Focused diagnostics for yt-dlp functionality

**Response**:
```json
{
  "version": "2025.8.11",
  "proxy_in_use": false,
  "status": "available"
}
```

**Error Response**:
```json
{
  "status": "error",
  "error": "yt-dlp import failed"
}
```

### 3. `/health/live` - Liveness Probe

**Purpose**: Simple liveness check (always returns 200 if process running)

**Response**:
```json
{
  "status": "ok",
  "timestamp": "2025-01-19T10:30:00.000Z"
}
```

### 4. `/health/ready` - Readiness Probe

**Purpose**: Readiness check including proxy health

**Response**:
```json
{
  "status": "ready",
  "proxy_healthy": true
}
```

## Security Features

### Gated Diagnostics

**Default Behavior** (Production Safe):
- `EXPOSE_HEALTH_DIAGNOSTICS=false` (default)
- Only basic status information exposed
- No version numbers, paths, or system details

**Enhanced Diagnostics** (Development/Debug):
- `EXPOSE_HEALTH_DIAGNOSTICS=true`
- Detailed system information available
- Still no sensitive data (credentials, file paths)

### Data Protection

**Never Exposed**:
- File paths (e.g., `/usr/bin/ffmpeg`)
- Proxy credentials or URLs
- Cookie file contents or paths
- Environment variable values
- Internal configuration details

**Safe to Expose**:
- Boolean flags (`ffmpeg_available`, `proxy_in_use`)
- Version numbers (`yt_dlp_version`)
- Status strings (`healthy`, `available`)
- Timestamps (UTC ISO format)

## Environment Variables

### Required
None - all endpoints work with defaults

### Optional
```bash
# Diagnostic information control (default: false for security)
EXPOSE_HEALTH_DIAGNOSTICS=false

# Proxy configuration (for proxy status)
OXYLABS_PROXY_CONFIG='{"provider":"oxylabs",...}'

# Debug mode for detailed error messages
DEBUG_HEALTHZ=false
```

## Usage Examples

### App Runner Health Check
```yaml
# apprunner.yaml
health_check:
  protocol: HTTP
  path: /healthz
  interval: 30
  timeout: 5
  healthy_threshold: 2
  unhealthy_threshold: 5
```

### Kubernetes Probes
```yaml
# deployment.yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
```

### Monitoring Integration
```bash
# Basic health check
curl -f https://your-service.com/healthz

# yt-dlp specific monitoring
curl https://your-service.com/health/yt-dlp | jq '.version'

# Enable diagnostics for debugging
export EXPOSE_HEALTH_DIAGNOSTICS=true
curl https://your-service.com/healthz | jq '.yt_dlp_version'
```

## Monitoring Alerts

### Recommended Alerts

1. **Service Down**
   - Endpoint: `/healthz`
   - Condition: HTTP status != 200
   - Severity: Critical

2. **yt-dlp Issues**
   - Endpoint: `/health/yt-dlp`
   - Condition: `status != "available"`
   - Severity: Warning

3. **Proxy Problems**
   - Endpoint: `/health/ready`
   - Condition: `proxy_healthy == false`
   - Severity: Warning

### Grafana Dashboard Queries

```promql
# Health status
up{job="tldw-service"}

# yt-dlp availability
probe_success{instance="https://your-service.com/health/yt-dlp"}

# Response time
probe_duration_seconds{instance="https://your-service.com/healthz"}
```

## Troubleshooting

### Common Issues

1. **Health check fails**
   - Check if service is running
   - Verify port accessibility
   - Check application logs

2. **Diagnostics not showing**
   - Verify `EXPOSE_HEALTH_DIAGNOSTICS=true`
   - Check environment variable is set correctly
   - Restart service after changing environment

3. **yt-dlp errors**
   - Check `/health/yt-dlp` for specific error
   - Verify yt-dlp installation
   - Check container build process

### Debug Mode

Enable detailed error information:
```bash
export DEBUG_HEALTHZ=true
export EXPOSE_HEALTH_DIAGNOSTICS=true
```

**Warning**: Only use debug mode in development - may expose sensitive information.

## Testing

Run the test suite to verify health endpoints:
```bash
python test_health_endpoints.py
```

**Expected Output**:
```
✅ Basic health endpoint works without exposing diagnostics
✅ Health endpoint exposes diagnostics when enabled
✅ /health/yt-dlp endpoint works correctly
✅ No sensitive data exposed in health endpoints
```

## Best Practices

### Production Deployment
- Keep `EXPOSE_HEALTH_DIAGNOSTICS=false`
- Use `/healthz` for load balancer health checks
- Monitor `/health/yt-dlp` for application-specific issues
- Set up alerts for all endpoints

### Development/Debugging
- Enable `EXPOSE_HEALTH_DIAGNOSTICS=true` temporarily
- Use enhanced diagnostics to troubleshoot issues
- Disable diagnostics before deploying to production

### Security
- Never log health endpoint responses in production
- Regularly audit what information is exposed
- Use separate monitoring credentials if needed
- Implement rate limiting on health endpoints if public