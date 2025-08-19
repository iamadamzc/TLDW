#!/bin/bash

# Enhanced App Runner Deployment Script with Container-Based Cache Busting
# Builds Docker image with unique tags and forces App Runner service restart
# Avoids git tag pollution by relying solely on container tags

set -e
set -euo pipefail

# Configuration
AWS_REGION="${AWS_REGION:-us-west-2}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-528131355234}"
ECR_REPOSITORY="${ECR_REPOSITORY:-tldw}"
SERVICE_NAME="${SERVICE_NAME:-tldw-container-app}"

# Get current git SHA for container tagging (don't push git tags)
GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
TIMESTAMP=$(date +%s)
IMAGE_TAG="${GIT_SHA}-${TIMESTAMP}"

ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}"
IMAGE_URI="${ECR_URI}:${IMAGE_TAG}"

# Command line options
DRY_RUN=false
WAIT_FOR_COMPLETION=true
DEPLOY_TIMEOUT=600
ROLLBACK_TO=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --no-wait)
            WAIT_FOR_COMPLETION=false
            shift
            ;;
        --timeout)
            DEPLOY_TIMEOUT="$2"
            shift 2
            ;;
        --rollback-to)
            ROLLBACK_TO="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [--dry-run] [--no-wait] [--timeout SECONDS] [--rollback-to IMAGE_URI] [--help]"
            echo "  --dry-run       Show what would be done without executing"
            echo "  --no-wait       Don't wait for deployment completion"
            echo "  --timeout       Deployment timeout in seconds (default: 600)"
            echo "  --rollback-to   Rollback to specific image URI instead of deploying new code"
            echo "  --help          Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  APPRUNNER_SERVICE_ARN   App Runner service ARN (required)"
            echo "  AWS_REGION             AWS region (default: us-west-2)"
            echo "  ECR_REPOSITORY         ECR repository name (default: tldw)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Cleanup function with rollback support
cleanup() {
    local exit_code=$?
    rm -f ./update-config.json
    rm -f ./rollback-config.json
    
    # If deployment failed and we have rollback info, show rollback instructions
    if [[ $exit_code -ne 0 && -n "${PREVIOUS_IMAGE_URI:-}" ]]; then
        echo ""
        echo "🔄 ROLLBACK INSTRUCTIONS:"
        echo "   To rollback to the previous version, run:"
        echo "   aws apprunner update-service \\"
        echo "     --service-arn \"${APPRUNNER_SERVICE_ARN}\" \\"
        echo "     --region \"${AWS_REGION}\" \\"
        echo "     --source-configuration '{\"ImageRepository\":{\"ImageIdentifier\":\"${PREVIOUS_IMAGE_URI}\",\"ImageRepositoryType\":\"ECR\"}}'"
        echo ""
        echo "   Or use the rollback script:"
        echo "   ./deploy-apprunner.sh --rollback-to \"${PREVIOUS_IMAGE_URI}\""
    fi
    
    exit $exit_code
}
trap cleanup EXIT INT TERM

echo "=== Enhanced App Runner Deployment with Container Cache Busting ==="
echo "AWS Region: ${AWS_REGION}"
echo "ECR Repository: ${ECR_URI}"
echo "Container Tag: ${IMAGE_TAG}"
echo "Image URI: ${IMAGE_URI}"
echo "Dry Run: ${DRY_RUN}"
echo ""

# One-time migration map for environment variables during rollout
echo "🔄 Applying environment variable migration..."
if [[ -n "${GOOGLE_OAUTH_CLIENT_ID:-}" && -z "${GOOGLE_CLIENT_ID:-}" ]]; then
    export GOOGLE_CLIENT_ID="$GOOGLE_OAUTH_CLIENT_ID"
    echo "   Migrated GOOGLE_OAUTH_CLIENT_ID -> GOOGLE_CLIENT_ID"
fi

if [[ -n "${GOOGLE_OAUTH_CLIENT_SECRET:-}" && -z "${GOOGLE_CLIENT_SECRET:-}" ]]; then
    export GOOGLE_CLIENT_SECRET="$GOOGLE_OAUTH_CLIENT_SECRET"
    echo "   Migrated GOOGLE_OAUTH_CLIENT_SECRET -> GOOGLE_CLIENT_SECRET"
fi
echo ""

# Preflight checks
echo "🔍 Running preflight checks..."

# Check required environment variables
if [[ -z "${APPRUNNER_SERVICE_ARN:-}" ]]; then
    echo "❌ APPRUNNER_SERVICE_ARN environment variable is required"
    echo "   Set it to your App Runner service ARN"
    exit 1
fi

# Check AWS CLI
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ AWS CLI not configured or credentials invalid"
    exit 1
fi
echo "✅ AWS CLI configured"

# Check Docker
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running"
    exit 1
fi
echo "✅ Docker is running"

# Check jq
if ! command -v jq > /dev/null 2>&1; then
    echo "❌ 'jq' is required but not installed"
    exit 1
fi
echo "✅ jq is available"

# Verify service exists
echo "🔍 Verifying App Runner service..."
if aws apprunner describe-service --service-arn "${APPRUNNER_SERVICE_ARN}" --region "${AWS_REGION}" > /dev/null 2>&1; then
    echo "✅ App Runner service found: ${APPRUNNER_SERVICE_ARN}"
else
    echo "❌ App Runner service not found or not accessible: ${APPRUNNER_SERVICE_ARN}"
    exit 1
fi

# Login to ECR
echo "🔐 Logging into ECR..."
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${ECR_URI}"

# Ensure ECR repository exists
echo "📦 Ensuring ECR repository exists..."
aws ecr describe-repositories --repository-names "${ECR_REPOSITORY}" --region "${AWS_REGION}" > /dev/null 2>&1 || {
    echo "Creating ECR repository: ${ECR_REPOSITORY}"
    aws ecr create-repository --repository-name "${ECR_REPOSITORY}" --region "${AWS_REGION}"
}

# Handle rollback mode
if [[ -n "$ROLLBACK_TO" ]]; then
    echo "🔄 ROLLBACK MODE: Rolling back to image: ${ROLLBACK_TO}"
    IMAGE_URI="$ROLLBACK_TO"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        echo "🔄 [DRY RUN] Would rollback to image: ${ROLLBACK_TO}"
        echo "⏳ [DRY RUN] Would wait for rollback completion"
        echo "🏥 [DRY RUN] Would verify rollback with health check"
        exit 0
    fi
    
    # Skip build and push for rollback
    echo "⏭️  Skipping build and push for rollback operation"
    
elif [[ "$DRY_RUN" == "true" ]]; then
    echo "🔨 [DRY RUN] Would build Docker image with unique tag: ${IMAGE_TAG}"
    echo "⬆️  [DRY RUN] Would push image to ECR: ${IMAGE_URI}"
    echo "🔄 [DRY RUN] Would force App Runner deployment restart"
    echo "⏳ [DRY RUN] Would wait for deployment completion"
    echo "🏥 [DRY RUN] Would verify deployment with health check"
    exit 0
fi

# Build and push new container image with unique tag (skip for rollback)
if [[ -z "$ROLLBACK_TO" ]]; then
    echo "🔨 Building Docker image with container tag: ${IMAGE_TAG}..."
    docker build \
        --build-arg YTDLP_VERSION=2025.8.11 \
        --build-arg CACHE_BUSTER="${IMAGE_TAG}" \
        -t "${ECR_REPOSITORY}:${IMAGE_TAG}" .

    echo "🏷️  Tagging image for ECR..."
    docker tag "${ECR_REPOSITORY}:${IMAGE_TAG}" "${IMAGE_URI}"

    echo "⬆️  Pushing image to ECR..."
    docker push "${IMAGE_URI}"

    if [ $? -ne 0 ]; then
        echo "❌ Docker push failed. Aborting deployment."
        exit 1
    fi

    echo "✅ Successfully pushed image: ${IMAGE_URI}"
else
    echo "⏭️  Skipping build and push for rollback to: ${IMAGE_URI}"
fi

# Force App Runner deployment restart with new image
echo "🔄 Forcing App Runner deployment restart..."

# Get current service configuration to preserve settings
echo "📋 Getting current service configuration..."
CURRENT_CONFIG=$(aws apprunner describe-service --service-arn "${APPRUNNER_SERVICE_ARN}" --region "${AWS_REGION}")

# Store previous image URI for rollback instructions
PREVIOUS_IMAGE_URI=$(echo "$CURRENT_CONFIG" | jq -r '.Service.SourceConfiguration.ImageRepository.ImageIdentifier')
echo "📝 Previous image: ${PREVIOUS_IMAGE_URI}"

# Extract current environment variables and secrets
ENV_VARS=$(echo "$CURRENT_CONFIG" | jq -c '.Service.SourceConfiguration.ImageRepository.ImageConfiguration.RuntimeEnvironmentVariables // {}')
SECRETS=$(echo "$CURRENT_CONFIG" | jq -c '.Service.SourceConfiguration.ImageRepository.ImageConfiguration.RuntimeEnvironmentSecrets // {}')

# Create update configuration
cat > ./update-config.json <<EOF
{
  "ImageRepository": {
    "ImageIdentifier": "${IMAGE_URI}",
    "ImageConfiguration": {
      "Port": "8080",
      "RuntimeEnvironmentVariables": ${ENV_VARS},
      "RuntimeEnvironmentSecrets": ${SECRETS}
    },
    "ImageRepositoryType": "ECR"
  },
  "AutoDeploymentsEnabled": false
}
EOF

if [[ -n "$ROLLBACK_TO" ]]; then
    echo "🔄 Starting App Runner rollback to image: ${IMAGE_URI}"
else
    echo "🚀 Starting App Runner deployment with image: ${IMAGE_URI}"
fi

# Update the service to force restart
UPDATE_RESULT=$(aws apprunner update-service \
    --service-arn "${APPRUNNER_SERVICE_ARN}" \
    --region "${AWS_REGION}" \
    --source-configuration file://update-config.json 2>&1)

if [ $? -eq 0 ]; then
    echo "✅ App Runner service update initiated successfully"
    OPERATION_ID=$(echo "$UPDATE_RESULT" | jq -r '.OperationId // "unknown"')
    echo "   Operation ID: $OPERATION_ID"
else
    echo "❌ App Runner service update failed:"
    echo "$UPDATE_RESULT"
    exit 1
fi

# Wait for deployment to complete
if [[ "$WAIT_FOR_COMPLETION" == "true" ]]; then
    echo "⏳ Waiting for deployment to complete (timeout: ${DEPLOY_TIMEOUT}s)..."
    
    elapsed=0
    poll_interval=15
    last_status=""
    
    while [ $elapsed -lt $DEPLOY_TIMEOUT ]; do
        service_info=$(aws apprunner describe-service --service-arn "${APPRUNNER_SERVICE_ARN}" --region "${AWS_REGION}")
        status=$(echo "$service_info" | jq -r '.Service.Status')
        current_image=$(echo "$service_info" | jq -r '.Service.SourceConfiguration.ImageRepository.ImageIdentifier')
        
        # Only print status if it changed
        if [[ "$status" != "$last_status" ]]; then
            echo "   Status: $status (${elapsed}s elapsed)"
            last_status="$status"
        fi
        
        case $status in
            "RUNNING")
                if [[ "$current_image" == "$IMAGE_URI" ]]; then
                    echo "✅ Service is running with new image: $IMAGE_URI"
                    break
                else
                    echo "⚠️  Service running but with different image:"
                    echo "   Current: $current_image"
                    echo "   Expected: $IMAGE_URI"
                fi
                ;;
            "OPERATION_IN_PROGRESS")
                # Continue waiting
                ;;
            "CREATE_FAILED"|"UPDATE_FAILED"|"DELETE_FAILED")
                echo "❌ Deployment failed with status: $status"
                
                # Get failure details
                echo "🔍 Getting failure details..."
                failure_info=$(aws apprunner describe-service --service-arn "${APPRUNNER_SERVICE_ARN}" --region "${AWS_REGION}" 2>/dev/null)
                if [[ -n "$failure_info" ]]; then
                    failure_reason=$(echo "$failure_info" | jq -r '.Service.Status // "unknown"')
                    echo "   Failure reason: $failure_reason"
                fi
                
                echo ""
                echo "💡 Troubleshooting steps:"
                echo "   1. Check App Runner service logs in AWS Console"
                echo "   2. Verify the container image exists and is accessible"
                echo "   3. Check environment variables and secrets configuration"
                echo "   4. Ensure the service has proper IAM permissions"
                
                exit 1
                ;;
        esac
        
        sleep $poll_interval
        elapsed=$((elapsed + poll_interval))
    done
    
    if [ $elapsed -ge $DEPLOY_TIMEOUT ]; then
        echo "⚠️  Deployment timeout after ${DEPLOY_TIMEOUT} seconds"
        exit 1
    fi
else
    echo "⏭️  Skipping deployment wait (--no-wait specified)"
fi

# Verify deployment with health check
echo "🏥 Verifying deployment..."
sleep 30  # Give service time to fully start

# Get service URL
FINAL_SERVICE_INFO=$(aws apprunner describe-service --service-arn "${APPRUNNER_SERVICE_ARN}" --region "${AWS_REGION}")
SERVICE_URL=$(echo "$FINAL_SERVICE_INFO" | jq -r '.Service.ServiceUrl')

if [[ -n "$SERVICE_URL" && "$SERVICE_URL" != "null" ]]; then
    HEALTH_URL="https://${SERVICE_URL}/healthz"
    
    echo "🔍 Testing health endpoint: $HEALTH_URL"
    
    if curl -fsS --connect-timeout 10 --max-time 30 "$HEALTH_URL" > /tmp/health-response.json 2>/dev/null; then
        echo "✅ Health check passed"
        
        # Show basic health info if available
        if [[ -f /tmp/health-response.json ]]; then
            status=$(jq -r '.status // "unknown"' /tmp/health-response.json 2>/dev/null)
            echo "   Health status: $status"
        fi
        
        rm -f /tmp/health-response.json
    else
        echo "⚠️  Health check failed or timed out"
        echo "   This may indicate the service is still starting up"
        echo "   Check the service manually: $HEALTH_URL"
    fi
else
    echo "⚠️  Could not determine service URL"
fi

echo ""
echo "🎉 Deployment completed successfully!"
echo ""
echo "📊 Deployment Summary:"
echo "   Container Tag: ${IMAGE_TAG}"
echo "   Image URI: ${IMAGE_URI}"
echo "   Service ARN: ${APPRUNNER_SERVICE_ARN}"
if [[ -n "$SERVICE_URL" && "$SERVICE_URL" != "null" ]]; then
    echo "   Service URL: https://${SERVICE_URL}"
    echo ""
    echo "🧪 Test endpoints:"
    echo "   Health Check: https://${SERVICE_URL}/healthz"
    echo "   Application: https://${SERVICE_URL}/"
fi

echo ""
echo "✅ New code is now running with container tag: ${IMAGE_TAG}"