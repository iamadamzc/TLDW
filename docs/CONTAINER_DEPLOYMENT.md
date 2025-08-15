# TL;DW Container Deployment Guide

This guide covers deploying TL;DW to AWS App Runner using container-based deployment.

## Prerequisites

- AWS CLI configured with appropriate permissions
- Docker Desktop installed and running
- ECR repository access (will be created automatically)

## Quick Deployment

### Option 1: Using Make (Recommended)

```bash
# Build and test locally
make build
make test

# Deploy to ECR
make deploy
```

### Option 2: Using Deploy Script

```bash
# Make script executable (if not already)
chmod +x deploy.sh

# Deploy to ECR
./deploy.sh
```

## Manual Steps

### 1. Build and Push Container

```bash
# Login to ECR
aws ecr get-login-password --region us-west-2 | \
  docker login --username AWS --password-stdin \
  528131355234.dkr.ecr.us-west-2.amazonaws.com

# Build image
docker build -t tldw:latest .

# Tag for ECR
docker tag tldw:latest \
  528131355234.dkr.ecr.us-west-2.amazonaws.com/tldw:latest

# Push to ECR
docker push 528131355234.dkr.ecr.us-west-2.amazonaws.com/tldw:latest
```

### 2. Configure App Runner Service

1. Go to AWS App Runner console
2. Select your service
3. Choose "Edit configuration"
4. Change source to "Container registry"
5. Set configuration:
   - **Image URI**: `528131355234.dkr.ecr.us-west-2.amazonaws.com/tldw:latest`
   - **Port**: `8080`
   - **Start command**: (leave blank - uses Dockerfile CMD)
   - **Environment variables**: (copy from existing service)

### 3. Configure Health Check

- **Health check path**: `/healthz`
- **Health check interval**: 20 seconds
- **Health check timeout**: 10 seconds
- **Healthy threshold**: 3
- **Unhealthy threshold**: 5

## Container Features

### Dependency Verification

The container includes multiple layers of dependency checking:

1. **Build-time verification**: Dockerfile tests ffmpeg/ffprobe during build
2. **Startup verification**: wsgi.py checks all dependencies before starting
3. **Runtime health checks**: /healthz endpoint reports dependency status

### Logging

Container startup logs include:

```
=== TL;DW Container Startup Verification ===
✅ yt-dlp: available at /usr/local/bin/yt-dlp
✅ ffmpeg: ffmpeg version 4.3.6 (at /usr/bin/ffmpeg)
✅ ffprobe: ffprobe version 4.3.6 (at /usr/bin/ffprobe)
✅ yt-dlp module: 2024.08.06
✅ All critical dependencies verified - starting application
=== End Startup Verification ===
```

### Health Check Response

GET `/healthz` returns:

```json
{
  "status": "healthy",
  "message": "TL;DW API is running",
  "proxy_enabled": true,
  "dependencies": {
    "ffmpeg": {
      "available": true,
      "path": "/usr/bin/ffmpeg",
      "version": "ffmpeg version 4.3.6"
    },
    "ffprobe": {
      "available": true,
      "path": "/usr/bin/ffprobe", 
      "version": "ffprobe version 4.3.6"
    },
    "yt_dlp": {
      "available": true,
      "version": "2024.08.06"
    }
  }
}
```

## Testing

### Local Testing

```bash
# Test dependencies locally (may fail without ffmpeg)
make test-local

# Test in container
make test
```

### Production Testing

After deployment:

1. **Health check**: `curl https://your-app-url/healthz`
2. **Bot-check retry**: Process a video that triggers bot detection
3. **ASR functionality**: Verify audio download and transcription works

## Troubleshooting

### Build Failures

- Check Docker is running: `docker info`
- Check AWS credentials: `aws sts get-caller-identity`
- Check ECR permissions: `aws ecr describe-repositories`

### Startup Failures

- Check container logs in App Runner console
- Look for dependency verification messages
- Verify all environment variables are set

### Runtime Issues

- Check `/healthz` endpoint for dependency status
- Monitor App Runner logs for proxy/ASR errors
- Verify bot-check detection and session rotation

## Environment Variables

The container requires these environment variables (configured in App Runner):

- `SESSION_SECRET`
- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `OPENAI_API_KEY`
- `RESEND_API_KEY`
- `DEEPGRAM_API_KEY`
- `OXYLABS_PROXY_CONFIG`
- `USE_PROXIES=true`

## File Structure

```
.
├── Dockerfile                 # Container definition with dependency verification
├── wsgi.py                   # WSGI entrypoint with startup checks
├── deploy.sh                 # ECR deployment script
├── Makefile                  # Deployment commands
├── apprunner.container.yaml  # Container config (reference only)
├── test_dependencies.py     # Dependency test script
└── CONTAINER_DEPLOYMENT.md  # This guide
```

## Success Criteria

✅ Container builds without errors  
✅ All dependencies verified at build time  
✅ Application starts successfully  
✅ Health check returns 200  
✅ Bot-check detection and session rotation works  
✅ ASR functionality processes audio successfully