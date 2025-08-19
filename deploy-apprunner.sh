#!/bin/bash
# Enhanced App Runner Deployment Script with Container-Based Cache Busting
# Builds Docker image with unique tags and forces App Runner service restart
# Avoids git tag pollution by relying solely on container tags

set -euo pipefail
export AWS_PAGER=""

# Configuration
AWS_REGION="${AWS_REGION:-us-west-2}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-528131355234}"
ECR_REPOSITORY="${ECR_REPOSITORY:-tldw}"
SERVICE_NAME="${SERVICE_NAME:-tldw-container-app}"

# Auto-detect App Runner service ARN if not provided
if [[ -z "${APPRUNNER_SERVICE_ARN:-}" ]]; then
  echo "🔍 Auto-detecting App Runner service ARN..."
  APPRUNNER_SERVICE_ARN=$(aws apprunner list-services \
    --region "${AWS_REGION}" \
    --query "ServiceSummaryList[?ServiceName=='${SERVICE_NAME}'].ServiceArn" \
    --output text 2>/dev/null || echo "")
  if [[ -n "$APPRUNNER_SERVICE_ARN" && "$APPRUNNER_SERVICE_ARN" != "None" ]]; then
    echo "✅ Found existing App Runner service: ${SERVICE_NAME}"
    echo "   Service ARN: ${APPRUNNER_SERVICE_ARN}"
  else
    echo "❌ Could not auto-detect App Runner service ARN for service: ${SERVICE_NAME}"
    echo "   Please set APPRUNNER_SERVICE_ARN environment variable manually"
    exit 1
  fi
fi

# Tag for image
GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
TIMESTAMP=$(date +%s)
IMAGE_TAG="${GIT_SHA}-${TIMESTAMP}"

REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
ECR_URI="${REGISTRY}/${ECR_REPOSITORY}"
IMAGE_URI="${ECR_URI}:${IMAGE_TAG}"

# CLI options
DRY_RUN=false
WAIT_FOR_COMPLETION=true
DEPLOY_TIMEOUT=600
ROLLBACK_TO=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run) DRY_RUN=true; shift ;;
    --no-wait) WAIT_FOR_COMPLETION=false; shift ;;
    --timeout) DEPLOY_TIMEOUT="$2"; shift 2 ;;
    --rollback-to) ROLLBACK_TO="$2"; shift 2 ;;
    --help)
      echo "Usage: $0 [--dry-run] [--no-wait] [--timeout SECONDS] [--rollback-to IMAGE_URI] [--help]"
      echo "  --dry-run       Show what would be done without executing"
      echo "  --no-wait       Don't wait for deployment completion"
      echo "  --timeout       Deployment timeout in seconds (default: 600)"
      echo "  --rollback-to   Roll back to a specific image URI (e.g., ${ECR_URI}:abc123)"
      echo ""
      echo "Env:"
      echo "  APPRUNNER_SERVICE_ARN   (required unless auto-detected by SERVICE_NAME)"
      echo "  AWS_REGION              (default: us-west-2)"
      echo "  ECR_REPOSITORY          (default: tldw)"
      echo "  SERVICE_NAME            (default: tldw-container-app)"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

cleanup() {
  local exit_code=$?
  rm -f ./update-config.json ./rollback-config.json
  if [[ $exit_code -ne 0 && -n "${PREVIOUS_IMAGE_URI:-}" ]]; then
    echo ""
    echo "🔄 ROLLBACK INSTRUCTIONS:"
    echo "   aws apprunner update-service --service-arn \"${APPRUNNER_SERVICE_ARN}\" --region \"${AWS_REGION}\" \\"
    echo "     --source-configuration '{\"ImageRepository\":{\"ImageIdentifier\":\"${PREVIOUS_IMAGE_URI}\",\"ImageRepositoryType\":\"ECR\"}}'"
    echo ""
    echo "   Or: ./deploy-apprunner.sh --rollback-to \"${PREVIOUS_IMAGE_URI}\""
  fi
  exit $exit_code
}
trap cleanup EXIT INT TERM

echo "=== Enhanced App Runner Deployment (Container Cache Busting) ==="
echo "AWS Region: ${AWS_REGION}"
echo "ECR Repository: ${ECR_URI}"
echo "Container Tag: ${IMAGE_TAG}"
echo "Image URI: ${IMAGE_URI}"
echo "Dry Run: ${DRY_RUN}"
echo ""

# One-time env var migration (backwards compatible)
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

# Preflight
echo "🔍 Running preflight checks..."
aws sts get-caller-identity >/dev/null 2>&1 || { echo "❌ AWS CLI not configured"; exit 1; }
echo "✅ AWS CLI configured"
docker info >/dev/null 2>&1 || { echo "❌ Docker is not running"; exit 1; }
echo "✅ Docker is running"
command -v jq >/dev/null || { echo "❌ 'jq' is required but not installed"; exit 1; }
echo "✅ jq is available"

echo "🔍 Verifying App Runner service..."
aws apprunner describe-service --service-arn "${APPRUNNER_SERVICE_ARN}" --region "${AWS_REGION}" >/dev/null 2>&1 \
  || { echo "❌ App Runner service not found: ${APPRUNNER_SERVICE_ARN}"; exit 1; }
echo "✅ App Runner service found"

# ECR login (to registry host)
echo "🔐 Logging into ECR..."
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${REGISTRY}"

# Ensure repository exists
echo "📦 Ensuring ECR repository exists..."
aws ecr describe-repositories --repository-names "${ECR_REPOSITORY}" --region "${AWS_REGION}" >/dev/null 2>&1 \
  || { echo "Creating ECR repository: ${ECR_REPOSITORY}"; aws ecr create-repository --repository-name "${ECR_REPOSITORY}" --region "${AWS_REGION}" >/dev/null; }

# Rollback path
if [[ -n "$ROLLBACK_TO" ]]; then
  echo "🔄 ROLLBACK MODE: ${ROLLBACK_TO}"
  IMAGE_URI="$ROLLBACK_TO"
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "🔄 [DRY RUN] Would rollback to: ${ROLLBACK_TO}"
    exit 0
  fi
else
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "🔨 [DRY RUN] Would build image: ${IMAGE_URI}"
    echo "⬆️  [DRY RUN] Would push image to ECR"
    echo "🚀 [DRY RUN] Would update App Runner to this image"
    exit 0
  fi

  echo "🔨 Building Docker image: ${IMAGE_URI}..."
  docker build \
    --build-arg YTDLP_VERSION=2025.8.11 \
    --build-arg CACHE_BUSTER="${IMAGE_TAG}" \
    -t "${ECR_REPOSITORY}:${IMAGE_TAG}" .

  echo "🏷️  Tagging image for ECR..."
  docker tag "${ECR_REPOSITORY}:${IMAGE_TAG}" "${IMAGE_URI}"

  echo "⬆️  Pushing image to ECR..."
  docker push "${IMAGE_URI}" >/dev/null || { echo "❌ Docker push failed"; exit 1; }
  echo "✅ Pushed: ${IMAGE_URI}"

  # (Nice) capture digest for logs
  DIGEST=$(aws ecr describe-images --repository-name "${ECR_REPOSITORY}" --image-ids imageTag="${IMAGE_TAG}" --region "${AWS_REGION}" \
    | jq -r '.imageDetails[0].imageDigest // empty')
  [[ -n "$DIGEST" ]] && echo "🧾 Image digest: ${DIGEST}"
fi

echo "🔄 Preparing App Runner update..."

# Get current service config to preserve settings
CURRENT_CONFIG=$(aws apprunner describe-service --service-arn "${APPRUNNER_SERVICE_ARN}" --region "${AWS_REGION}")

# Save previous image for rollback instructions
PREVIOUS_IMAGE_URI=$(echo "$CURRENT_CONFIG" | jq -r '.Service.SourceConfiguration.ImageRepository.ImageIdentifier')
echo "📝 Previous image: ${PREVIOUS_IMAGE_URI}"

# Preserve env vars, secrets, and port (arrays not objects)
ENV_VARS=$(echo "$CURRENT_CONFIG" | jq -c '.Service.SourceConfiguration.ImageRepository.ImageConfiguration.RuntimeEnvironmentVariables // []')
SECRETS=$(echo "$CURRENT_CONFIG" | jq -c '.Service.SourceConfiguration.ImageRepository.ImageConfiguration.RuntimeEnvironmentSecrets // []')
PORT=$(echo "$CURRENT_CONFIG" | jq -r '.Service.SourceConfiguration.ImageRepository.ImageConfiguration.Port // "8080"')
AUTO_DEPLOY=$(echo "$CURRENT_CONFIG" | jq '.Service.SourceConfiguration.AutoDeploymentsEnabled // false')

cat > ./update-config.json <<EOF
{
  "ImageRepository": {
    "ImageIdentifier": "${IMAGE_URI}",
    "ImageConfiguration": {
      "Port": "${PORT}",
      "RuntimeEnvironmentVariables": ${ENV_VARS},
      "RuntimeEnvironmentSecrets": ${SECRETS}
    },
    "ImageRepositoryType": "ECR"
  },
  "AutoDeploymentsEnabled": ${AUTO_DEPLOY}
}
EOF

if [[ -n "$ROLLBACK_TO" ]]; then
  echo "🔄 Starting App Runner rollback to: ${IMAGE_URI}"
else
  echo "🚀 Starting App Runner deployment with image: ${IMAGE_URI}"
fi

UPDATE_RESULT=$(aws apprunner update-service \
  --service-arn "${APPRUNNER_SERVICE_ARN}" \
  --region "${AWS_REGION}" \
  --source-configuration file://update-config.json 2>&1)

if [[ $? -eq 0 ]]; then
  echo "✅ App Runner service update initiated"
  SVC_ARN=$(echo "$UPDATE_RESULT" | jq -r '.Service.ServiceArn // empty')
  [[ -n "$SVC_ARN" ]] && echo "   Service: $SVC_ARN"
else
  echo "❌ App Runner service update failed:"
  echo "$UPDATE_RESULT"
  exit 1
fi

# Wait loop
if [[ "$WAIT_FOR_COMPLETION" == "true" ]]; then
  echo "⏳ Waiting for deployment (timeout: ${DEPLOY_TIMEOUT}s)..."
  elapsed=0
  poll_interval=15
  last_status=""

  while [[ $elapsed -lt $DEPLOY_TIMEOUT ]]; do
    service_info=$(aws apprunner describe-service --service-arn "${APPRUNNER_SERVICE_ARN}" --region "${AWS_REGION}")
    status=$(echo "$service_info" | jq -r '.Service.Status')
    current_image=$(echo "$service_info" | jq -r '.Service.SourceConfiguration.ImageRepository.ImageIdentifier')

    if [[ "$status" != "$last_status" ]]; then
      echo "   Status: $status (${elapsed}s)"
      last_status="$status"
    fi

    case "$status" in
      RUNNING)
        if [[ "$current_image" == "$IMAGE_URI" ]]; then
          echo "✅ Service is RUNNING with new image: $IMAGE_URI"
          break
        else
          echo "⚠️  RUNNING but image mismatch:"
          echo "   Current:  $current_image"
          echo "   Expected: $IMAGE_URI"
        fi
        ;;
      OPERATION_IN_PROGRESS) ;;
      CREATE_FAILED|UPDATE_FAILED|DELETE_FAILED)
        echo "❌ Deployment failed with status: $status"
        exit 1
        ;;
    esac

    sleep $poll_interval
    elapsed=$((elapsed + poll_interval))
  done

  if [[ $elapsed -ge $DEPLOY_TIMEOUT ]]; then
    echo "⚠️  Deployment timeout after ${DEPLOY_TIMEOUT}s"
    exit 1
  fi
else
  echo "⏭️  Skipping wait (--no-wait)"
fi

# Health verification with small retry loop
echo "🏥 Verifying deployment..."
sleep 10

FINAL_SERVICE_INFO=$(aws apprunner describe-service --service-arn "${APPRUNNER_SERVICE_ARN}" --region "${AWS_REGION}")
SERVICE_URL=$(echo "$FINAL_SERVICE_INFO" | jq -r '.Service.ServiceUrl')

if [[ -n "$SERVICE_URL" && "$SERVICE_URL" != "null" ]]; then
  HEALTH_URL="https://${SERVICE_URL}/healthz"
  echo "🔍 Health endpoint: $HEALTH_URL"
  ok=false
  for i in {1..10}; do
    if curl -fsS --connect-timeout 10 --max-time 30 "$HEALTH_URL" >/tmp/health.json 2>/dev/null; then
      ok=true; break
    fi
    sleep 6
  done
  if $ok; then
    echo "✅ Health check passed"
    status_val=$(jq -r '.status // empty' /tmp/health.json 2>/dev/null)
    [[ -n "$status_val" ]] && echo "   Health status: $status_val"
    rm -f /tmp/health.json
  else
    echo "⚠️  Health check failed or timed out (service may still be starting)"
    echo "   Check manually: $HEALTH_URL"
  fi
else
  echo "⚠️  Could not determine service URL"
fi

echo ""
echo "🎉 Deployment completed!"
echo "📊 Summary:"
echo "   Image URI: ${IMAGE_URI}"
echo "   Service ARN: ${APPRUNNER_SERVICE_ARN}"
if [[ -n "$SERVICE_URL" && "$SERVICE_URL" != "null" ]]; then
  echo "   Service URL: https://${SERVICE_URL}"
  echo "   Health:      https://${SERVICE_URL}/healthz"
fi
echo "✅ New code is now running with container tag: ${IMAGE_TAG}"
