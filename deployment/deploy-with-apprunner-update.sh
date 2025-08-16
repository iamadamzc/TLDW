#!/bin/bash

# Complete AWS App Runner Deployment Script
# Builds Docker image, pushes to ECR, and updates App Runner service

set -e  # Exit on any error

# Configuration
AWS_REGION="us-west-2"
AWS_ACCOUNT_ID="528131355234"
ECR_REPOSITORY="tldw"
IMAGE_TAG="$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)"
SERVICE_NAME="tldw-container-app"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}"

echo "=== TL;DW Complete Deployment ==="
echo "AWS Region: ${AWS_REGION}"
echo "ECR Repository: ${ECR_URI}"
echo "Image Tag: ${IMAGE_TAG}"
echo "Service Name: ${SERVICE_NAME}"
echo ""

# Check if AWS CLI is configured
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ AWS CLI not configured or credentials invalid"
    echo "Run: aws configure"
    exit 1
fi

echo "✅ AWS CLI configured"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running"
    echo "Start Docker Desktop and try again"
    exit 1
fi

echo "✅ Docker is running"

# Login to ECR
echo "🔐 Logging into ECR..."
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_URI}

# Create ECR repository if it doesn't exist
echo "📦 Ensuring ECR repository exists..."
aws ecr describe-repositories --repository-names ${ECR_REPOSITORY} --region ${AWS_REGION} > /dev/null 2>&1 || {
    echo "Creating ECR repository: ${ECR_REPOSITORY}"
    aws ecr create-repository --repository-name ${ECR_REPOSITORY} --region ${AWS_REGION}
}

# Build Docker image
echo "🔨 Building Docker image..."
docker build -t ${ECR_REPOSITORY}:${IMAGE_TAG} .

# Tag image for ECR
echo "🏷️  Tagging image for ECR..."
docker tag ${ECR_REPOSITORY}:${IMAGE_TAG} ${ECR_URI}:${IMAGE_TAG}

# Push image to ECR
echo "⬆️  Pushing image to ECR..."
docker push ${ECR_URI}:${IMAGE_TAG}

# Get the image URI for App Runner
IMAGE_URI="${ECR_URI}:${IMAGE_TAG}"

echo "✅ Image pushed successfully: ${IMAGE_URI}"

# Find App Runner service
echo "🔍 Finding App Runner service..."
SERVICE_ARN=$(aws apprunner list-services --region ${AWS_REGION} --query "ServiceSummaryList[?ServiceName=='${SERVICE_NAME}'].ServiceArn" --output text)

if [ -z "$SERVICE_ARN" ]; then
    echo "❌ App Runner service '${SERVICE_NAME}' not found in region ${AWS_REGION}"
    echo "📋 Manual steps needed:"
    echo "1. Go to AWS App Runner console"
    echo "2. Create or find your service"
    echo "3. Set Image URI: ${IMAGE_URI}"
    echo "4. Set Port: 8080"
    echo "5. Set Health Check: /healthz"
    exit 1
fi

echo "✅ Found service: ${SERVICE_ARN}"

# Get current service configuration
echo "📋 Getting current service configuration..."
CURRENT_CONFIG=$(aws apprunner describe-service --service-arn "${SERVICE_ARN}" --region ${AWS_REGION})

# Extract current environment variables (correct fallback to array, not object)
ENV_VARS=$(echo "$CURRENT_CONFIG" | jq -c '.Service.SourceConfiguration.ImageRepository.ImageConfiguration.RuntimeEnvironmentVariables // []')

echo "🔄 Updating App Runner service with new image..."

# Build a safe JSON file for the update call
echo "📝 Creating service configuration for image: ${IMAGE_URI}"
cat > /tmp/source-config.json <<JSON
{
  "ImageRepository": {
    "ImageIdentifier": "${IMAGE_URI}",
    "ImageConfiguration": {
      "Port": "8080",
      "RuntimeEnvironmentVariables": ${ENV_VARS}
    },
    "ImageRepositoryType": "ECR"
  },
  "AutoDeploymentsEnabled": false
}
JSON

# Update the service with new image URI
UPDATE_RESULT=$(aws apprunner update-service \
    --service-arn "${SERVICE_ARN}" \
    --region ${AWS_REGION} \
    --source-configuration file:///tmp/source-config.json 2>&1)

if [ $? -eq 0 ]; then
    echo "✅ App Runner service update initiated successfully"
    OPERATION_ID=$(echo "$UPDATE_RESULT" | jq -r '.OperationId // "unknown"')
    echo "   Operation ID: $OPERATION_ID"
else
    echo "❌ App Runner service update failed:"
    echo "$UPDATE_RESULT"
    rm -f /tmp/source-config.json
    exit 1
fi

# Clean up temp file
rm -f /tmp/source-config.json

# Wait for deployment to complete
echo "⏳ Waiting for deployment to complete..."
echo "   This may take 3-5 minutes..."

# Poll service status
TIMEOUT=600  # 10 minutes timeout
ELAPSED=0
POLL_INTERVAL=15

while [ $ELAPSED -lt $TIMEOUT ]; do
    SERVICE_INFO=$(aws apprunner describe-service --service-arn "${SERVICE_ARN}" --region ${AWS_REGION})
    STATUS=$(echo "$SERVICE_INFO" | jq -r '.Service.Status')
    CURRENT_IMAGE=$(echo "$SERVICE_INFO" | jq -r '.Service.SourceConfiguration.ImageRepository.ImageIdentifier')
    
    echo "   Status: ${STATUS}, Image: ${CURRENT_IMAGE} (${ELAPSED}s elapsed)"
    
    case $STATUS in
        "RUNNING")
            if [ "$CURRENT_IMAGE" = "$IMAGE_URI" ]; then
                echo "✅ Deployment completed successfully!"
                echo "   Service is running with new image: $IMAGE_URI"
                break
            else
                echo "⚠️  Service is running but with old image: $CURRENT_IMAGE"
                echo "   Expected: $IMAGE_URI"
                sleep $POLL_INTERVAL
                ELAPSED=$((ELAPSED + POLL_INTERVAL))
            fi
            ;;
        "OPERATION_IN_PROGRESS")
            sleep $POLL_INTERVAL
            ELAPSED=$((ELAPSED + POLL_INTERVAL))
            ;;
        "CREATE_FAILED"|"UPDATE_FAILED"|"DELETE_FAILED")
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
    echo "⚠️  Deployment timeout after ${TIMEOUT} seconds"
    FINAL_STATUS=$(aws apprunner describe-service --service-arn "${SERVICE_ARN}" --region ${AWS_REGION} --query 'Service.Status' --output text)
    FINAL_IMAGE=$(aws apprunner describe-service --service-arn "${SERVICE_ARN}" --region ${AWS_REGION} --query 'Service.SourceConfiguration.ImageRepository.ImageIdentifier' --output text)
    echo "   Final Status: $FINAL_STATUS"
    echo "   Final Image: $FINAL_IMAGE"
    echo "   Expected Image: $IMAGE_URI"
    echo "Check AWS App Runner console for current status"
    exit 1
fi

# Final verification
echo "🔍 Final verification..."
FINAL_SERVICE_INFO=$(aws apprunner describe-service --service-arn "${SERVICE_ARN}" --region ${AWS_REGION})
FINAL_STATUS=$(echo "$FINAL_SERVICE_INFO" | jq -r '.Service.Status')
FINAL_IMAGE=$(echo "$FINAL_SERVICE_INFO" | jq -r '.Service.SourceConfiguration.ImageRepository.ImageIdentifier')
SERVICE_URL=$(echo "$FINAL_SERVICE_INFO" | jq -r '.Service.ServiceUrl')

if [ "$FINAL_IMAGE" != "$IMAGE_URI" ]; then
    echo "❌ Deployment verification failed!"
    echo "   Service Status: $FINAL_STATUS"
    echo "   Current Image: $FINAL_IMAGE"
    echo "   Expected Image: $IMAGE_URI"
    echo "   The service may not have updated properly"
    exit 1
fi

echo ""
echo "🎉 Deployment completed successfully!"
echo ""
echo "📊 Service Details:"
echo "   Service ARN: ${SERVICE_ARN}"
echo "   Image URI: ${IMAGE_URI}"
echo "   Service URL: https://${SERVICE_URL}"
echo ""
echo "🧪 Test endpoints:"
echo "   Health Check: https://${SERVICE_URL}/healthz"
echo "   Application: https://${SERVICE_URL}/"
echo "   Cookie Upload: https://${SERVICE_URL}/account/cookies"
echo ""
echo "🔍 Monitor logs for:"
echo "   - 'Using user cookiefile for yt-dlp' (cookie success)"
echo "   - 'cookies_used=true' (S3 access working)"
echo "   - No more S3 403 or proxy 407 errors"