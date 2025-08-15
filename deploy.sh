#!/bin/bash

# AWS App Runner Container Deployment Script
# Builds Docker image and pushes to ECR for App Runner deployment

set -e  # Exit on any error

# Configuration
AWS_REGION="us-west-2"
AWS_ACCOUNT_ID="528131355234"
ECR_REPOSITORY="tldw"
IMAGE_TAG="latest"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}"

echo "=== TL;DW Container Deployment ==="
echo "AWS Region: ${AWS_REGION}"
echo "ECR Repository: ${ECR_URI}"
echo "Image Tag: ${IMAGE_TAG}"
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

echo ""
echo "🎉 Deployment successful!"
echo ""
echo "📋 App Runner Configuration:"
echo "   Image URI: ${IMAGE_URI}"
echo "   Port: 8080"
echo "   Health Check: /healthz"
echo "   Start Command: (leave blank - uses Dockerfile CMD)"
echo ""
echo "🔗 Next Steps:"
echo "1. Go to AWS App Runner console"
echo "2. Update service to use container source"
echo "3. Set Image URI: ${IMAGE_URI}"
echo "4. Set Port: 8080"
echo "5. Set Health Check: /healthz"
echo "6. Deploy the service"
echo ""
echo "🧪 Test endpoints after deployment:"
echo "   Health: https://your-app-url/healthz"
echo "   App: https://your-app-url/"