# App Runner Quick Start Guide

## TL;DR - Fix Deployment Issues

The previous App Runner deployments were failing due to **mixed runtime syntax** in `apprunner.yaml`. This has been fixed.

## Quick Fix Applied

### ❌ Before (Broken Configuration)
```yaml
version: 1.0
runtime: docker
build:
  commands:
    build:
      - echo "Building with Docker"
run:
  runtime-version: latest
  command: gunicorn --bind 0.0.0.0:8000 --workers 1 app:app
  network:
    port: 8000
    env: PORT
```

### ✅ After (Fixed Configuration)
```yaml
version: 1.0
runtime: docker
build:
  dockerfile: Dockerfile
```

## Two Deployment Options

### Option 1: Docker Runtime (Current apprunner.yaml)
- **File**: `apprunner.yaml`
- **Port**: 8000
- **Build**: Uses Dockerfile
- **Best for**: Full control over environment

### Option 2: Python Runtime (Recommended)
- **File**: `apprunner-python-runtime.yaml`
- **Port**: 8080
- **Build**: Managed Python environment
- **Best for**: Faster deployments, less maintenance

## Switch to Python Runtime

To use the recommended Python runtime:

1. **Backup current config**:
   ```bash
   mv apprunner.yaml apprunner-docker.yaml.backup
   ```

2. **Use Python runtime**:
   ```bash
   mv apprunner-python-runtime.yaml apprunner.yaml
   ```

3. **Deploy**: App Runner will automatically use the new configuration

## What Was Fixed

1. **✅ Cleaned up codebase** - Removed 11 unused/test files
2. **✅ Fixed requirements.txt** - Corrected malformed dependencies
3. **✅ Fixed Docker config** - Proper Docker runtime syntax
4. **✅ Updated Dockerfile** - Uses real app files, not test files
5. **✅ Added Python option** - Alternative runtime configuration
6. **✅ Tested locally** - Both configurations validated

## Environment Variables Needed

```bash
SESSION_SECRET=your-session-secret
GOOGLE_OAUTH_CLIENT_ID=your-google-client-id
GOOGLE_OAUTH_CLIENT_SECRET=your-google-client-secret
OPENAI_API_KEY=your-openai-key
DATABASE_URL=your-database-url
RESEND_API_KEY=your-resend-key
```

## Health Check

Both configurations expose a health check endpoint:
- **URL**: `/health`
- **Response**: `{"status": "healthy", "message": "TL;DW API is running"}`
- **Docker**: Available on port 8000
- **Python**: Available on port 8080

## Troubleshooting

If deployment still fails:

1. **Check logs** in App Runner console
2. **Verify** environment variables are set
3. **Ensure** GitHub connection is working
4. **Test locally** using the commands in DEPLOYMENT.md

## Next Steps

1. Deploy with the fixed configuration
2. Test the application functionality
3. Set up custom domain if needed
4. Monitor performance and scaling