#!/bin/bash
# Staging deployment script for structured JSON logging migration
# This script deploys to staging with minimal logging enabled for validation

set -euo pipefail
export AWS_PAGER=""

# Staging configuration
AWS_REGION="${AWS_REGION:-us-west-2}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-528131355234}"
ECR_REPOSITORY="${ECR_REPOSITORY:-tldw}"
SERVICE_NAME="${SERVICE_NAME:-tldw-container-app-staging}"

echo "=== Staging Deployment for Structured JSON Logging ==="
echo "Service: ${SERVICE_NAME}"
echo "Region: ${AWS_REGION}"
echo ""

# Validate staging environment variables
echo "🔍 Validating staging environment configuration..."

# Required staging environment variables for minimal logging
STAGING_ENV_VARS=(
    "USE_MINIMAL_LOGGING=true"
    "LOG_LEVEL=DEBUG"
    "CLOUDWATCH_LOG_GROUP=/aws/apprunner/tldw-transcript-service-staging"
    "RATE_LIMIT_PER_KEY=5"
    "RATE_LIMIT_WINDOW_SEC=60"
    "FFMPEG_STDERR_TAIL_LINES=40"
    "PERF_METRICS_ENABLED=true"
)

echo "Staging environment variables:"
for env_var in "${STAGING_ENV_VARS[@]}"; do
    echo "  - $env_var"
done
echo ""

# Create staging CloudWatch log group if it doesn't exist
echo "📊 Setting up staging CloudWatch log group..."
STAGING_LOG_GROUP="/aws/apprunner/tldw-transcript-service-staging"

if ! aws logs describe-log-groups \
    --log-group-name-prefix "$STAGING_LOG_GROUP" \
    --region "$AWS_REGION" \
    --query "logGroups[?logGroupName=='$STAGING_LOG_GROUP']" \
    --output text | grep -q "$STAGING_LOG_GROUP"; then
    
    echo "Creating staging log group: $STAGING_LOG_GROUP"
    aws logs create-log-group \
        --log-group-name "$STAGING_LOG_GROUP" \
        --region "$AWS_REGION"
    
    # Set 7-day retention for staging (cost optimization)
    aws logs put-retention-policy \
        --log-group-name "$STAGING_LOG_GROUP" \
        --retention-in-days 7 \
        --region "$AWS_REGION"
    
    echo "✅ Staging log group created with 7-day retention"
else
    echo "✅ Staging log group already exists"
fi

# Deploy to staging using main deployment script
echo "🚀 Deploying to staging environment..."
export SERVICE_NAME="$SERVICE_NAME"

# Call main deployment script with staging configuration
./deploy-apprunner.sh --timeout 600

echo ""
echo "🎉 Staging deployment completed!"
echo "📊 Monitor logs: aws logs tail $STAGING_LOG_GROUP --follow --region $AWS_REGION"
echo "🔍 Health check: Check service URL /healthz endpoint"
echo ""
echo "Next steps:"
echo "1. Validate JSON log format in CloudWatch"
echo "2. Test CloudWatch Logs Insights queries"
echo "3. Verify job correlation and stage timing"
echo "4. Run integration tests"
echo "5. Proceed to production deployment if validation passes"