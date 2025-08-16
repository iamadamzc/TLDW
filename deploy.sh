#!/bin/bash

# Unified AWS App Runner Deployment Script
# Builds Docker image, pushes to ECR, and updates App Runner service
# Consolidates build, push, and service management into a single reliable process

set -euo pipefail

# Cleanup function for trap
cleanup() {
    local exit_code=$?
    echo ""
    if [[ $exit_code -ne 0 ]]; then
        echo "⚠️  Script interrupted or failed (exit code: $exit_code)"
        echo "🧹 Cleaning up temporary files..."
    fi
    rm -f ./update-config.json
    exit $exit_code
}

# Set trap to cleanup on exit
trap cleanup EXIT INT TERM

# Configuration
AWS_REGION="us-west-2"
AWS_ACCOUNT_ID="528131355234"
ECR_REPOSITORY="tldw"
SERVICE_NAME="tldw-container-app"

# Generate unique image tag based on git commit or timestamp
IMAGE_TAG="$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}"

# Command line flags
DRY_RUN=false
FORCE_RESTART=false
WAIT_FOR_COMPLETION=true

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force-restart)
            FORCE_RESTART=true
            shift
            ;;
        --no-wait)
            WAIT_FOR_COMPLETION=false
            shift
            ;;
        --help)
            echo "Usage: $0 [--dry-run] [--force-restart] [--no-wait] [--help]"
            echo "  --dry-run       Show what would be done without executing"
            echo "  --force-restart Force App Runner service restart"
            echo "  --no-wait       Don't wait for deployment completion"
            echo "  --help          Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "=== Unified TL;DW App Runner Deployment (Fixed) ==="
echo "AWS Region: ${AWS_REGION}"
echo "ECR Repository: ${ECR_URI}"
echo "Image Tag: ${IMAGE_TAG}"
echo "Service Name: ${SERVICE_NAME}"
echo "Dry Run: ${DRY_RUN}"
echo ""

# Preflight checks
echo "🔍 Running preflight checks..."

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

# Check if jq is installed
if ! command -v jq > /dev/null 2>&1; then
    echo "❌ 'jq' is required but not installed"
    echo "Install with: brew install jq (macOS) or apt-get install jq (Linux) or choco install jq (Windows)"
    exit 1
fi
echo "✅ jq is available"

# Check if service exists
SERVICE_ARN=$(aws apprunner list-services --region ${AWS_REGION} --query "ServiceSummaryList[?ServiceName=='${SERVICE_NAME}'].ServiceArn" --output text 2>/dev/null || echo "")
if [[ -n "$SERVICE_ARN" && "$SERVICE_ARN" != "None" ]]; then
    echo "✅ Found existing App Runner service: ${SERVICE_NAME}"
    SERVICE_EXISTS=true
else
    echo "ℹ️  App Runner service '${SERVICE_NAME}' not found - will provide manual setup instructions"
    SERVICE_EXISTS=false
fi

# Login to ECR
echo "🔐 Logging into ECR..."
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_URI}

# Create ECR repository if it doesn't exist
echo "📦 Ensuring ECR repository exists..."
aws ecr describe-repositories --repository-names ${ECR_REPOSITORY} --region ${AWS_REGION} > /dev/null 2>&1 || {
    echo "Creating ECR repository: ${ECR_REPOSITORY}"
    aws ecr create-repository --repository-name ${ECR_REPOSITORY} --region ${AWS_REGION}
}

# Build and push image
if [[ "$DRY_RUN" == "true" ]]; then
    echo "🔨 [DRY RUN] Would build Docker image with tag: ${IMAGE_TAG}"
    echo "🏷️  [DRY RUN] Would tag image for ECR: ${ECR_URI}:${IMAGE_TAG}"
    echo "⬆️  [DRY RUN] Would push image to ECR"
else
    # Build Docker image
    echo "🔨 Building Docker image..."
    docker build -t ${ECR_REPOSITORY}:${IMAGE_TAG} .

    # Tag image for ECR (both unique tag and latest)
    echo "🏷️  Tagging image for ECR..."
    docker tag ${ECR_REPOSITORY}:${IMAGE_TAG} ${ECR_URI}:${IMAGE_TAG}
    docker tag ${ECR_REPOSITORY}:${IMAGE_TAG} ${ECR_URI}:latest

    # Push both tags to ECR
    echo "⬆️  Pushing image to ECR..."
    docker push ${ECR_URI}:${IMAGE_TAG}
    docker push ${ECR_URI}:latest
fi

# Get the image URI for App Runner
IMAGE_URI="${ECR_URI}:${IMAGE_TAG}"

# Create or update App Runner service
if [[ "$SERVICE_EXISTS" == "true" ]]; then
    echo ""
    echo "🔄 Updating existing App Runner service..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        echo "🔄 [DRY RUN] Would update App Runner service with image: ${IMAGE_URI}"
        echo "⏳ [DRY RUN] Would wait for deployment to complete"
        echo "🏥 [DRY RUN] Would verify health check"
    else
        # Get current service configuration to preserve environment variables
        echo "📋 Getting current service configuration..."
        CURRENT_CONFIG=$(aws apprunner describe-service --service-arn "${SERVICE_ARN}" --region ${AWS_REGION})
        
        # Extract current environment variables as arrays (App Runner update requires arrays of {Name,Value} objects)
        ENV_VARS=$(echo "$CURRENT_CONFIG" | jq -c '[.Service.SourceConfiguration.ImageRepository.ImageConfiguration.RuntimeEnvironmentVariables | to_entries[]? | {Name: .key, Value: .value}] // []')
        SECRETS=$(echo "$CURRENT_CONFIG" | jq -c '[.Service.SourceConfiguration.ImageRepository.ImageConfiguration.RuntimeEnvironmentSecrets | to_entries[]? | {Name: .key, Value: .value}] // []')
        
        # Update the service with new image URI
        echo "🔄 Updating service with new image: ${IMAGE_URI}"
        
        # Create update configuration (use current directory for Windows compatibility)
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
        
        echo "📄 Created update configuration for image: ${IMAGE_URI}"
        
        # Update the service (use current directory path for Windows compatibility)
        UPDATE_RESULT=$(aws apprunner update-service \
            --service-arn "${SERVICE_ARN}" \
            --region ${AWS_REGION} \
            --source-configuration file://update-config.json 2>&1)
        
        if [ $? -eq 0 ]; then
            echo "✅ App Runner service update initiated successfully"
            OPERATION_ID=$(echo "$UPDATE_RESULT" | jq -r '.OperationId // "unknown"')
            echo "   Operation ID: $OPERATION_ID"
            
            # Verify the service is actually updating with the correct image
            sleep 5  # Give AWS a moment to process the update
            UPDATED_IMAGE=$(aws apprunner describe-service --service-arn "${SERVICE_ARN}" --region ${AWS_REGION} --query 'Service.SourceConfiguration.ImageRepository.ImageIdentifier' --output text)
            if [[ "$UPDATED_IMAGE" == "$IMAGE_URI" ]]; then
                echo "✅ Confirmed: Service is updating to correct image: $IMAGE_URI"
            else
                echo "❌ Warning: Service image mismatch!"
                echo "   Expected: $IMAGE_URI"
                echo "   Actual: $UPDATED_IMAGE"
                echo "   The update may have failed - check AWS console"
            fi
        else
            echo "❌ App Runner service update failed:"
            echo "$UPDATE_RESULT"
            exit 1
        fi
        
        # Clean up temp file
        rm -f ./update-config.json
        
        # Wait for deployment to complete (unless --no-wait is specified)
        if [[ "$WAIT_FOR_COMPLETION" == "true" ]]; then
            echo "⏳ Waiting for deployment to complete..."
            echo "   This may take 3-5 minutes... (use --no-wait to skip)"
            
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
        else
            echo "⏭️  Skipping deployment wait (--no-wait specified)"
            echo "   Check AWS App Runner console to monitor deployment progress"
        fi
        
        # Get final service information
        FINAL_SERVICE_INFO=$(aws apprunner describe-service --service-arn "${SERVICE_ARN}" --region ${AWS_REGION})
        SERVICE_URL=$(echo "$FINAL_SERVICE_INFO" | jq -r '.Service.ServiceUrl')
        
        # Force restart if requested
        if [[ "$FORCE_RESTART" == "true" ]]; then
            echo "🔄 Forcing service restart..."
            aws apprunner start-deployment --service-arn "${SERVICE_ARN}" --region ${AWS_REGION}
            echo "✅ Service restart initiated"
        fi
    fi
else
    # Create new App Runner service
    echo ""
    echo "🆕 Creating new App Runner service: ${SERVICE_NAME}"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        echo "🆕 [DRY RUN] Would create App Runner service with image: ${IMAGE_URI}"
    else
        # Define required IAM role ARN for ECR access
        ECR_ACCESS_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/AppRunnerECRAccessRole"
        INSTANCE_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/AppRunnerInstanceRole"
        
        # Create service configuration with default environment variables and secrets
        cat > ./create-config.json <<EOF
{
  "ServiceName": "${SERVICE_NAME}",
  "SourceConfiguration": {
    "ImageRepository": {
      "ImageIdentifier": "${IMAGE_URI}",
      "ImageRepositoryType": "ECR",
      "ImageConfiguration": {
        "Port": "8080",
        "RuntimeEnvironmentVariables": [
          {"Name": "PORT", "Value": "8080"},
          {"Name": "FFMPEG_LOCATION", "Value": "/usr/bin"},
          {"Name": "USE_PROXIES", "Value": "true"},
          {"Name": "PROXY_COUNTRY", "Value": "us"},
          {"Name": "ALLOW_MISSING_DEPS", "Value": "true"},
          {"Name": "COOKIE_LOCAL_DIR", "Value": "/app/cookies"},
          {"Name": "COOKIE_S3_BUCKET", "Value": "tldw-cookies-bucket"}
        ],
        "RuntimeEnvironmentSecrets": [
          {"Name": "OXYLABS_PROXY_CONFIG", "Value": "arn:aws:secretsmanager:${AWS_REGION}:${AWS_ACCOUNT_ID}:secret:tldw-oxylabs-proxy-config-mkbzlM"},
          {"Name": "RESEND_API_KEY", "Value": "arn:aws:secretsmanager:${AWS_REGION}:${AWS_ACCOUNT_ID}:secret:TLDW-RESEND-API-KEY-5O5Kdx"},
          {"Name": "OPENAI_API_KEY", "Value": "arn:aws:secretsmanager:${AWS_REGION}:${AWS_ACCOUNT_ID}:secret:TLDW-OPENAI-API-KEY-5rNo6a"},
          {"Name": "GOOGLE_OAUTH_CLIENT_SECRET", "Value": "arn:aws:secretsmanager:${AWS_REGION}:${AWS_ACCOUNT_ID}:secret:TLDW-GOOGLE-OAUTH-CLIENT-SECRET-LmUrPI"},
          {"Name": "GOOGLE_OAUTH_CLIENT_ID", "Value": "arn:aws:secretsmanager:${AWS_REGION}:${AWS_ACCOUNT_ID}:secret:TLDW-GOOGLE-OAUTH-CLIENT-ID-8Z22IN"},
          {"Name": "SESSION_SECRET", "Value": "arn:aws:secretsmanager:${AWS_REGION}:${AWS_ACCOUNT_ID}:secret:TLDW-SESSION-SECRET-hJDTQ1"},
          {"Name": "DEEPGRAM_API_KEY", "Value": "arn:aws:secretsmanager:${AWS_REGION}:${AWS_ACCOUNT_ID}:secret:TLDW-DEEPGRAM-API-KEY-6gvcFv"}
        ]
      }
    },
    "AutoDeploymentsEnabled": false,
    "AuthenticationConfiguration": {
      "AccessRoleArn": "${ECR_ACCESS_ROLE_ARN}"
    }
  },
  "InstanceConfiguration": {
    "Cpu": "1024",
    "Memory": "2048",
    "InstanceRoleArn": "${INSTANCE_ROLE_ARN}"
  },
  "HealthCheckConfiguration": {
    "Protocol": "HTTP",
    "Path": "/healthz",
    "Interval": 10,
    "Timeout": 5,
    "HealthyThreshold": 1,
    "UnhealthyThreshold": 3
  }
}
EOF
        
        echo "📄 Created service configuration for image: ${IMAGE_URI}"
        
        # Create the service
        CREATE_RESULT=$(aws apprunner create-service \
            --region ${AWS_REGION} \
            --cli-input-json file://create-config.json 2>&1)
        
        if [ $? -eq 0 ]; then
            echo "✅ App Runner service creation initiated successfully"
            SERVICE_ARN=$(echo "$CREATE_RESULT" | jq -r '.Service.ServiceArn')
            OPERATION_ID=$(echo "$CREATE_RESULT" | jq -r '.OperationId // "unknown"')
            echo "   Service ARN: $SERVICE_ARN"
            echo "   Operation ID: $OPERATION_ID"
        else
            echo "❌ App Runner service creation failed:"
            echo "$CREATE_RESULT"
            rm -f ./create-config.json
            exit 1
        fi
        
        # Clean up temp file
        rm -f ./create-config.json
        
        # Wait for service creation to complete
        echo "⏳ Waiting for service creation to complete..."
        echo "   This may take 5-10 minutes for initial service creation..."
        
        TIMEOUT=900  # 15 minutes timeout for creation
        ELAPSED=0
        POLL_INTERVAL=20
        
        while [ $ELAPSED -lt $TIMEOUT ]; do
            SERVICE_INFO=$(aws apprunner describe-service --service-arn "${SERVICE_ARN}" --region ${AWS_REGION})
            STATUS=$(echo "$SERVICE_INFO" | jq -r '.Service.Status')
            
            echo "   Status: ${STATUS} (${ELAPSED}s elapsed)"
            
            case $STATUS in
                "RUNNING")
                    echo "✅ Service creation completed successfully!"
                    echo "   Service is running with image: $IMAGE_URI"
                    break
                    ;;
                "OPERATION_IN_PROGRESS")
                    sleep $POLL_INTERVAL
                    ELAPSED=$((ELAPSED + POLL_INTERVAL))
                    ;;
                "CREATE_FAILED"|"UPDATE_FAILED"|"DELETE_FAILED")
                    echo "❌ Service creation failed with status: ${STATUS}"
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
            echo "⚠️  Service creation timeout after ${TIMEOUT} seconds"
            FINAL_STATUS=$(aws apprunner describe-service --service-arn "${SERVICE_ARN}" --region ${AWS_REGION} --query 'Service.Status' --output text)
            echo "   Final Status: $FINAL_STATUS"
            echo "Check AWS App Runner console for current status"
            exit 1
        fi
    fi
fi

echo ""
echo "🎉 Deployment completed successfully!"
echo ""
echo "📊 Deployment Summary:"
echo "   Image Tag: ${IMAGE_TAG}"
echo "   Image URI: ${IMAGE_URI}"
if [[ "$DRY_RUN" != "true" ]]; then
    # Get final service information
    FINAL_SERVICE_INFO=$(aws apprunner describe-service --service-arn "${SERVICE_ARN}" --region ${AWS_REGION})
    SERVICE_URL=$(echo "$FINAL_SERVICE_INFO" | jq -r '.Service.ServiceUrl')
    DEPLOYED_DIGEST=$(echo "$FINAL_SERVICE_INFO" | jq -r '.Service.DeployedImageDigest // "unknown"')
    
    echo "   Service URL: https://${SERVICE_URL}"
    echo "   Deployed Digest: ${DEPLOYED_DIGEST}"
    echo ""
    
    # Perform health check validation
    echo "🏥 Performing health check validation..."
    HEALTH_URL="https://${SERVICE_URL}/healthz"
    
    if curl -fsS --connect-timeout 10 --max-time 30 "$HEALTH_URL" > /tmp/health-response.json 2>/dev/null; then
        echo "✅ Health check passed"
        
        # Validate dependencies from health response
        if command -v jq > /dev/null 2>&1 && [[ -f /tmp/health-response.json ]]; then
            FFMPEG_AVAILABLE=$(jq -r '.dependencies.ffmpeg.available // false' /tmp/health-response.json 2>/dev/null)
            YTDLP_AVAILABLE=$(jq -r '.dependencies.yt_dlp.available // false' /tmp/health-response.json 2>/dev/null)
            PROXY_READABLE=$(jq -r '.secrets.proxy_config_readable // false' /tmp/health-response.json 2>/dev/null)
            
            if [[ "$FFMPEG_AVAILABLE" == "true" && "$YTDLP_AVAILABLE" == "true" ]]; then
                echo "✅ Critical dependencies available (ffmpeg: $FFMPEG_AVAILABLE, yt-dlp: $YTDLP_AVAILABLE)"
            else
                echo "⚠️  Dependency issues detected (ffmpeg: $FFMPEG_AVAILABLE, yt-dlp: $YTDLP_AVAILABLE)"
            fi
            
            if [[ "$PROXY_READABLE" == "true" ]]; then
                echo "✅ Proxy configuration accessible"
            else
                echo "⚠️  Proxy configuration may not be accessible (could cause 407 errors)"
            fi
        fi
        
        rm -f /tmp/health-response.json
    else
        echo "⚠️  Health check failed or timed out"
        echo "   URL: $HEALTH_URL"
        echo "   This may indicate the service is still starting up"
    fi
    
    echo ""
    echo "🧪 Test endpoints:"
    echo "   Health Check: https://${SERVICE_URL}/healthz"
    echo "   Application: https://${SERVICE_URL}/"
else
    echo ""
    echo "📋 Manual App Runner Setup Required:"
    echo "   Image URI: ${IMAGE_URI}"
    echo "   Port: 8080"
    echo "   Health Check: /healthz"
    echo "   Start Command: (leave blank - uses Dockerfile CMD)"
    echo ""
    echo "🔗 Manual Steps:"
    echo "1. Go to AWS App Runner console"
    echo "2. Create or update service to use container source"
    echo "3. Set Image URI: ${IMAGE_URI}"
    echo "4. Set Port: 8080"
    echo "5. Set Health Check: /healthz"
    echo "6. Deploy the service"
fi