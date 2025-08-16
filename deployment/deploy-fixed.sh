#!/bin/bash

# Fixed AWS App Runner Deployment Script
# Addresses issues with image tag recognition and service restart

set -e  # Exit on any error

# Configuration
AWS_REGION="us-west-2"
AWS_ACCOUNT_ID="528131355234"
ECR_REPOSITORY="tldw"
SERVICE_NAME="tldw-container-app"

# Generate unique image tag using git commit + timestamp for guaranteed uniqueness
GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "manual")
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
IMAGE_TAG="${GIT_COMMIT}-${TIMESTAMP}"

ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}"
IMAGE_URI="${ECR_URI}:${IMAGE_TAG}"

echo "=== TL;DW Fixed Deployment ==="
echo "AWS Region: ${AWS_REGION}"
echo "ECR Repository: ${ECR_URI}"
echo "Image Tag: ${IMAGE_TAG}"
echo "Service Name: ${SERVICE_NAME}"
echo "Full Image URI: ${IMAGE_URI}"
echo ""

# Validate prerequisites
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ AWS CLI not configured or credentials invalid"
    exit 1
fi

if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running"
    exit 1
fi

echo "✅ Prerequisites validated"

# Build and push image
echo ""
echo "🔨 Building and pushing Docker image..."

# Login to ECR
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_URI}

# Ensure ECR repository exists
aws ecr describe-repositories --repository-names ${ECR_REPOSITORY} --region ${AWS_REGION} > /dev/null 2>&1 || {
    echo "Creating ECR repository: ${ECR_REPOSITORY}"
    aws ecr create-repository --repository-name ${ECR_REPOSITORY} --region ${AWS_REGION}
}

# Build image
docker build -t ${ECR_REPOSITORY}:${IMAGE_TAG} .

# Tag and push with unique tag
docker tag ${ECR_REPOSITORY}:${IMAGE_TAG} ${IMAGE_URI}
docker push ${IMAGE_URI}

# Also tag and push as latest for fallback
docker tag ${ECR_REPOSITORY}:${IMAGE_TAG} ${ECR_URI}:latest
docker push ${ECR_URI}:latest

echo "✅ Image pushed: ${IMAGE_URI}"

# Find App Runner service
echo ""
echo "🔍 Finding App Runner service..."
SERVICE_ARN=$(aws apprunner list-services --region ${AWS_REGION} --query "ServiceSummaryList[?ServiceName=='${SERVICE_NAME}'].ServiceArn" --output text)

if [ -z "$SERVICE_ARN" ]; then
    echo "❌ App Runner service '${SERVICE_NAME}' not found"
    echo ""
    echo "📋 To create the service, run:"
    echo "   ./deployment/deploy-apprunner.sh"
    echo ""
    echo "Or manually create with these settings:"
    echo "   Image URI: ${IMAGE_URI}"
    echo "   Port: 8080"
    echo "   Health Check: /healthz"
    exit 1
fi

echo "✅ Found service: ${SERVICE_ARN}"

# Get current service configuration to preserve environment variables and secrets
echo ""
echo "📋 Getting current service configuration..."
CURRENT_CONFIG=$(aws apprunner describe-service --service-arn "${SERVICE_ARN}" --region ${AWS_REGION})

# Extract current configuration
CURRENT_IMAGE=$(echo "$CURRENT_CONFIG" | jq -r '.Service.SourceConfiguration.ImageRepository.ImageIdentifier')
ENV_VARS=$(echo "$CURRENT_CONFIG" | jq -c '.Service.SourceConfiguration.ImageRepository.ImageConfiguration.RuntimeEnvironmentVariables // {}')
ENV_SECRETS=$(echo "$CURRENT_CONFIG" | jq -c '.Service.SourceConfiguration.ImageRepository.ImageConfiguration.RuntimeEnvironmentSecrets // {}')
CURRENT_PORT=$(echo "$CURRENT_CONFIG" | jq -r '.Service.SourceConfiguration.ImageRepository.ImageConfiguration.Port // "8080"')

echo "Current image: ${CURRENT_IMAGE}"
echo "New image: ${IMAGE_URI}"

if [ "$CURRENT_IMAGE" = "$IMAGE_URI" ]; then
    echo "⚠️  Warning: Image URI is the same as current. This may not trigger a restart."
    echo "   Current: $CURRENT_IMAGE"
    echo "   New: $IMAGE_URI"
fi

# Create update configuration with the new image
echo ""
echo "🔄 Updating App Runner service..."

# Create temporary config file
cat > /tmp/update-config.json <<JSON
{
  "ImageRepository": {
    "ImageIdentifier": "${IMAGE_URI}",
    "ImageConfiguration": {
      "Port": "${CURRENT_PORT}",
      "RuntimeEnvironmentVariables": ${ENV_VARS},
      "RuntimeEnvironmentSecrets": ${ENV_SECRETS}
    },
    "ImageRepositoryType": "ECR"
  },
  "AutoDeploymentsEnabled": false
}
JSON

echo "Configuration prepared. Updating service..."

# Update the service
UPDATE_RESULT=$(aws apprunner update-service \
    --service-arn "${SERVICE_ARN}" \
    --region ${AWS_REGION} \
    --source-configuration file:///tmp/update-config.json 2>&1)

if [ $? -eq 0 ]; then
    echo "✅ App Runner service update initiated"
    OPERATION_ID=$(echo "$UPDATE_RESULT" | jq -r '.OperationId // "unknown"')
    echo "   Operation ID: $OPERATION_ID"
else
    echo "❌ App Runner service update failed:"
    echo "$UPDATE_RESULT"
    rm -f /tmp/update-config.json
    exit 1
fi

# Clean up temp file
rm -f /tmp/update-config.json

# Force restart by calling start-deployment if update doesn't trigger restart
echo ""
echo "🚀 Ensuring deployment restart..."
RESTART_RESULT=$(aws apprunner start-deployment --service-arn "${SERVICE_ARN}" --region ${AWS_REGION} 2>&1)

if [ $? -eq 0 ]; then
    echo "✅ Deployment restart initiated"
    DEPLOYMENT_ID=$(echo "$RESTART_RESULT" | jq -r '.DeploymentId // "unknown"')
    echo "   Deployment ID: $DEPLOYMENT_ID"
else
    echo "⚠️  Could not force restart (this is sometimes normal):"
    echo "$RESTART_RESULT"
fi

# Wait for deployment to complete
echo ""
echo "⏳ Waiting for deployment to complete..."
echo "   This typically takes 3-5 minutes..."

TIMEOUT=600  # 10 minutes
ELAPSED=0
POLL_INTERVAL=20

while [ $ELAPSED -lt $TIMEOUT ]; do
    SERVICE_INFO=$(aws apprunner describe-service --service-arn "${SERVICE_ARN}" --region ${AWS_REGION})
    STATUS=$(echo "$SERVICE_INFO" | jq -r '.Service.Status')
    RUNNING_IMAGE=$(echo "$SERVICE_INFO" | jq -r '.Service.SourceConfiguration.ImageRepository.ImageIdentifier')
    
    echo "   Status: ${STATUS} | Image: ${RUNNING_IMAGE} | Elapsed: ${ELAPSED}s"
    
    case $STATUS in
        "RUNNING")
            if [ "$RUNNING_IMAGE" = "$IMAGE_URI" ]; then
                echo ""
                echo "🎉 Deployment completed successfully!"
                break
            else
                echo "   ⚠️  Service running but image not updated yet..."
                sleep $POLL_INTERVAL
                ELAPSED=$((ELAPSED + POLL_INTERVAL))
            fi
            ;;
        "OPERATION_IN_PROGRESS")
            sleep $POLL_INTERVAL
            ELAPSED=$((ELAPSED + POLL_INTERVAL))
            ;;
        "CREATE_FAILED"|"UPDATE_FAILED"|"DELETE_FAILED")
            echo ""
            echo "❌ Deployment failed with status: ${STATUS}"
            echo "Check AWS App Runner console for details"
            exit 1
            ;;
        *)
            sleep $POLL_INTERVAL
            ELAPSED=$((ELAPSED + POLL_INTERVAL))
            ;;
    esac
done

if [ $ELAPSED -ge $TIMEOUT ]; then
    echo ""
    echo "⚠️  Deployment timeout after ${TIMEOUT} seconds"
    FINAL_STATUS=$(aws apprunner describe-service --service-arn "${SERVICE_ARN}" --region ${AWS_REGION} --query 'Service.Status' --output text)
    FINAL_IMAGE=$(aws apprunner describe-service --service-arn "${SERVICE_ARN}" --region ${AWS_REGION} --query 'Service.SourceConfiguration.ImageRepository.ImageIdentifier' --output text)
    echo "   Final Status: $FINAL_STATUS"
    echo "   Final Image: $FINAL_IMAGE"
    echo "   Expected: $IMAGE_URI"
    echo ""
    echo "The deployment may still be in progress. Check the AWS console."
    exit 1
fi

# Final verification and service info
echo ""
echo "🔍 Final verification..."
FINAL_SERVICE_INFO=$(aws apprunner describe-service --service-arn "${SERVICE_ARN}" --region ${AWS_REGION})
FINAL_STATUS=$(echo "$FINAL_SERVICE_INFO" | jq -r '.Service.Status')
FINAL_IMAGE=$(echo "$FINAL_SERVICE_INFO" | jq -r '.Service.SourceConfiguration.ImageRepository.ImageIdentifier')
SERVICE_URL=$(echo "$FINAL_SERVICE_INFO" | jq -r '.Service.ServiceUrl')

echo ""
echo "🎉 Deployment Summary:"
echo "   Status: ${FINAL_STATUS}"
echo "   Image: ${FINAL_IMAGE}"
echo "   URL: https://${SERVICE_URL}"
echo ""

if [ "$FINAL_IMAGE" != "$IMAGE_URI" ]; then
    echo "⚠️  Warning: Service image doesn't match expected"
    echo "   Expected: $IMAGE_URI"
    echo "   Actual: $FINAL_IMAGE"
    echo "   The service may still be updating"
else
    echo "✅ Image verification successful"
fi

echo ""
echo "🧪 Test your deployment:"
echo "   Health Check: https://${SERVICE_URL}/healthz"
echo "   Application: https://${SERVICE_URL}/"
echo ""
echo "🔍 Monitor in AWS Console:"
echo "   App Runner > Services > ${SERVICE_NAME} > Logs"