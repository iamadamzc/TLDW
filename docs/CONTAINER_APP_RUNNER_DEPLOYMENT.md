# Container-Based App Runner Deployment Guide

This guide covers the migration from source-based to container-based App Runner deployment for the TL;DW application.

## Prerequisites

- AWS CLI configured with appropriate permissions
- Docker Desktop running
- ECR repository access

## Quick Deployment

### 1. Build and Push to ECR

Use the provided deployment script:

```bash
./deploy.sh
```

This script will:
- Create ECR repository if it doesn't exist
- Build Docker image with ffmpeg and dependencies
- Push to ECR with proper tagging

### 2. Manual ECR Commands (Alternative)

If you prefer manual deployment:

```bash
# Set variables
AWS_REGION="us-west-2"
AWS_ACCOUNT_ID="528131355234"
ECR_REPOSITORY="tldw"

# Create repository
aws ecr create-repository --repository-name tldw-app --region $AWS_REGION || true

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build and tag
docker build -t tldw-app:latest .
docker tag tldw-app:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/tldw-app:latest

# Push
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/tldw-app:latest
```

## App Runner Configuration

### Service Settings

When configuring App Runner service:

- **Source**: Container registry (ECR)
- **Image URI**: `528131355234.dkr.ecr.us-west-2.amazonaws.com/tldw:latest`
- **Port**: `8080`
- **Health check path**: `/healthz`
- **Start command**: Leave empty (uses Dockerfile CMD)

### Environment Variables

The container automatically sets:
- `FFMPEG_LOCATION=/usr/bin`
- `ALLOW_MISSING_DEPS=false`
- `PYTHONDONTWRITEBYTECODE=1`
- `PYTHONUNBUFFERED=1`

### Secrets Configuration

App Runner secrets (configured via console or CLI):
- `SESSION_SECRET`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `OPENAI_API_KEY`
- `RESEND_API_KEY`
- `DEEPGRAM_API_KEY`
- `OXYLABS_PROXY_CONFIG`

## Container Features

### Dependencies Included
- ✅ ffmpeg and ffprobe at `/usr/bin`
- ✅ yt-dlp pinned to version 2024.8.6
- ✅ Python dependencies from requirements.txt
- ✅ curl for health checks

### Security Features
- ✅ Non-root user (`app`)
- ✅ Minimal base image (python:3.11-slim)
- ✅ Proper file permissions

### Health Monitoring
- ✅ Built-in Docker health check every 30s
- ✅ App Runner health check at `/healthz`
- ✅ Dependency status reporting

## Development Override

For development environments, set:
```bash
ALLOW_MISSING_DEPS=true
```

This allows the application to start even if some dependencies are missing, with degraded functionality warnings.

## Verification Steps

### 1. Container Build Test
```bash
docker build -t tldw-test .
docker run --rm tldw-test python -c "import yt_dlp; print('yt-dlp OK')"
```

### 2. Health Check Test
After deployment, verify:
```bash
curl https://your-app-url/healthz
```

Expected response:
```json
{
  "status": "healthy",
  "dependencies": {
    "ffmpeg": {"available": true, "path": "/usr/bin/ffmpeg"},
    "yt_dlp": {"available": true, "version": "2024.8.6"}
  },
  "ffmpeg_location": "/usr/bin"
}
```

### 3. End-to-End Test
1. Access application URL
2. Attempt video summarization
3. Check logs for:
   - ✅ Non-None paths for ffmpeg, ffprobe, yt-dlp
   - ✅ No "ffmpeg not found" errors
   - ✅ Successful proxy rotation on bot-check
   - ✅ Email delivery confirmation

## Troubleshooting

### Common Issues

**Build Failures:**
- Ensure Docker is running
- Check network connectivity for base image pull
- Verify requirements.txt is valid

**Deployment Failures:**
- Verify ECR permissions
- Check AWS CLI configuration
- Ensure repository exists

**Runtime Issues:**
- Check App Runner logs for startup errors
- Verify health check endpoint returns 200
- Confirm all secrets are properly configured

### Logs Analysis

Key startup log patterns:
```
STARTUP: ffmpeg at /usr/bin/ffmpeg
STARTUP: ffprobe at /usr/bin/ffprobe  
STARTUP: yt-dlp module OK (version=2024.8.6)
STARTUP: FFMPEG_LOCATION=/usr/bin
STARTUP: Environment ready for application startup
```

### Performance Monitoring

Monitor these metrics:
- Container startup time (should be < 30s)
- Health check response time (should be < 5s)
- yt-dlp success rate (should be > 90% with proxy rotation)
- Memory usage (should be < 1GB under normal load)

## Migration Checklist

- [x] Dockerfile updated with ffmpeg and non-root user
- [x] wsgi.py enhanced with dev overrides and logging
- [x] yt-dlp calls use explicit ffmpeg location
- [x] apprunner.yaml removed to prevent source runtime
- [x] deploy.sh script configured for ECR
- [x] Documentation created for container deployment
- [ ] End-to-end testing completed
- [ ] Production deployment verified