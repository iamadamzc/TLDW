# Enhanced Deployment Script Guide

## Overview

The enhanced `deploy-apprunner.sh` script provides container-based cache busting for AWS App Runner deployments, ensuring that new code is always deployed without relying on git tag pollution.

## Key Features

### Container-Based Cache Busting

**Problem Solved**: App Runner sometimes caches previous deployments, preventing new code from running.

**Solution**: Generate unique container image tags using git SHA and timestamp:
```bash
GIT_SHA=$(git rev-parse --short HEAD)
TIMESTAMP=$(date +%s)
IMAGE_TAG="${GIT_SHA}-${TIMESTAMP}"
```

**Benefits**:
- ✅ Forces App Runner to pull new image
- ✅ No git repository pollution with deployment tags
- ✅ Traceable deployments with git SHA
- ✅ Unique tags prevent caching issues

### Deployment Process

1. **Build**: Create Docker image with unique tag
2. **Push**: Upload to ECR with unique identifier
3. **Update**: Force App Runner service restart with new image
4. **Verify**: Health check validation and deployment confirmation

## Usage

### Basic Deployment
```bash
export APPRUNNER_SERVICE_ARN="arn:aws:apprunner:us-west-2:123456789012:service/my-service/abcd1234"
./deploy-apprunner.sh
```

### Dry Run (Test Without Execution)
```bash
./deploy-apprunner.sh --dry-run
```

### Quick Deployment (No Wait)
```bash
./deploy-apprunner.sh --no-wait
```

### Custom Timeout
```bash
./deploy-apprunner.sh --timeout 900  # 15 minutes
```

## Environment Variables

### Required
```bash
# App Runner service ARN (required)
export APPRUNNER_SERVICE_ARN="arn:aws:apprunner:region:account:service/name/id"
```

### Optional
```bash
# AWS configuration (defaults provided)
export AWS_REGION="us-west-2"              # Default: us-west-2
export AWS_ACCOUNT_ID="123456789012"       # Default: 528131355234
export ECR_REPOSITORY="my-app"             # Default: tldw
export SERVICE_NAME="my-service"           # Default: tldw-container-app
```

## Command Line Options

| Option | Description | Example |
|--------|-------------|---------|
| `--dry-run` | Show what would be done without executing | `./deploy-apprunner.sh --dry-run` |
| `--no-wait` | Don't wait for deployment completion | `./deploy-apprunner.sh --no-wait` |
| `--timeout SECONDS` | Set deployment timeout | `./deploy-apprunner.sh --timeout 900` |
| `--help` | Show help message | `./deploy-apprunner.sh --help` |

## Deployment Verification

### Automatic Checks
1. **Image Verification**: Confirms App Runner is using the new image
2. **Health Check**: Tests `/healthz` endpoint after deployment
3. **Status Monitoring**: Tracks deployment progress with status updates
4. **Error Detection**: Fails fast on deployment errors

### Manual Verification
```bash
# Check service status
aws apprunner describe-service --service-arn "$APPRUNNER_SERVICE_ARN"

# Test health endpoint
curl https://your-service.region.awsapprunner.com/healthz

# Check logs
aws logs tail /aws/apprunner/your-service/application --follow
```

## Error Handling

### Common Issues and Solutions

1. **"APPRUNNER_SERVICE_ARN environment variable is required"**
   ```bash
   export APPRUNNER_SERVICE_ARN="your-service-arn"
   ```

2. **"AWS CLI not configured"**
   ```bash
   aws configure
   # or
   export AWS_ACCESS_KEY_ID="your-key"
   export AWS_SECRET_ACCESS_KEY="your-secret"
   ```

3. **"Docker is not running"**
   - Start Docker Desktop
   - Verify with: `docker info`

4. **"ECR push failed"**
   - Check AWS permissions
   - Verify ECR repository exists
   - Check network connectivity

5. **"Deployment timeout"**
   - Increase timeout: `--timeout 900`
   - Check App Runner console for details
   - Verify service configuration

### Exit Codes
- `0`: Success
- `1`: General error (missing requirements, configuration issues)
- `2`: AWS CLI error
- `3`: Docker error
- `4`: Deployment failure

## Comparison with Previous Approach

### Old Approach (Problematic)
```bash
# Created git tags for each deployment
git tag "deploy-$(date +%s)"
git push origin "deploy-$(date +%s)"

# Relied on App Runner auto-deployment
# Often failed due to caching issues
```

**Problems**:
- ❌ Polluted git repository with deployment tags
- ❌ App Runner caching prevented new deployments
- ❌ No reliable way to force restart
- ❌ Difficult to track which code was deployed

### New Approach (Enhanced)
```bash
# Container-based unique tagging
IMAGE_TAG="${GIT_SHA}-${TIMESTAMP}"
docker build -t "$ECR_REPOSITORY:$IMAGE_TAG" .
docker push "$ECR_URI:$IMAGE_TAG"

# Force App Runner update with new image
aws apprunner update-service --source-configuration file://config.json
```

**Benefits**:
- ✅ Clean git repository (no deployment tags)
- ✅ Guaranteed cache busting with unique images
- ✅ Reliable deployment restart mechanism
- ✅ Traceable deployments with git SHA
- ✅ Health check validation

## CI/CD Integration

### GitHub Actions
```yaml
name: Deploy to App Runner
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-west-2
      
      - name: Deploy to App Runner
        env:
          APPRUNNER_SERVICE_ARN: ${{ secrets.APPRUNNER_SERVICE_ARN }}
        run: ./deploy-apprunner.sh
```

### GitLab CI
```yaml
deploy:
  stage: deploy
  image: docker:latest
  services:
    - docker:dind
  before_script:
    - apk add --no-cache aws-cli jq curl
  script:
    - ./deploy-apprunner.sh
  variables:
    APPRUNNER_SERVICE_ARN: $APPRUNNER_SERVICE_ARN
  only:
    - main
```

## Monitoring and Alerting

### CloudWatch Metrics
Monitor these metrics for deployment health:
- App Runner service status
- Deployment duration
- Health check success rate
- Error rates post-deployment

### Recommended Alerts
```bash
# Deployment failure alert
aws cloudwatch put-metric-alarm \
  --alarm-name "AppRunner-Deployment-Failure" \
  --alarm-description "Alert when App Runner deployment fails" \
  --metric-name "DeploymentStatus" \
  --namespace "AWS/AppRunner" \
  --statistic "Sum" \
  --period 300 \
  --threshold 1 \
  --comparison-operator "GreaterThanOrEqualToThreshold"
```

## Best Practices

### Development
- Always test with `--dry-run` first
- Use meaningful commit messages (included in image tags)
- Keep deployments small and frequent
- Monitor health checks after deployment

### Production
- Set appropriate timeout values (`--timeout 600`)
- Use CI/CD for automated deployments
- Monitor deployment metrics
- Have rollback procedures ready

### Security
- Use IAM roles instead of access keys when possible
- Rotate AWS credentials regularly
- Limit ECR repository access
- Monitor deployment logs for sensitive data

## Troubleshooting

### Debug Mode
Enable verbose output for troubleshooting:
```bash
set -x  # Add to script for debug mode
./deploy-apprunner.sh --dry-run
```

### Common Log Messages
- `✅ Successfully pushed image`: ECR push completed
- `✅ App Runner service update initiated`: Deployment started
- `✅ Service is running with new image`: Deployment successful
- `⚠️ Health check failed`: Service may still be starting

### Recovery Procedures
If deployment fails:
1. Check App Runner console for detailed error messages
2. Verify service configuration and permissions
3. Test health endpoint manually
4. Consider rolling back to previous image if needed

## Testing

Validate the deployment script:
```bash
python test_deployment_script_content.py
```

Expected output:
```
🎉 All tests passed! Deployment script is properly configured.
📝 Key features verified:
   - Container-based cache busting (no git tag pollution)
   - Unique image tags with git SHA and timestamp
   - App Runner service integration
   - Proper error handling and cleanup
```