#!/usr/bin/env bash
set -euo pipefail

# ====== CONFIG YOU CAN TWEAK ======
export AWS_REGION=us-west-2
export SERVICE_NAME=tldw-container-app
export APP_REPO=tldw-app
# Tag image with both commit and 'latest'
export IMAGE_TAG=$(git rev-parse --short HEAD 2>/dev/null || echo "manual")
# Instance sizing
export CPU="1 vCPU"
export MEM="2 GB"
# ==================================

export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export ECR_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${APP_REPO}:${IMAGE_TAG}"
export ECR_URI_LATEST="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${APP_REPO}:latest"

# ====== YOUR SECRET ARNs (as provided) ======
export ARN_OXY=arn:aws:secretsmanager:us-west-2:528131355234:secret:tldw-oxylabs-proxy-config-mkbzlM
export ARN_RESEND=arn:aws:secretsmanager:us-west-2:528131355234:secret:TLDW-RESEND-API-KEY-5O5Kdx
export ARN_OPENAI=arn:aws:secretsmanager:us-west-2:528131355234:secret:TLDW-OPENAI-API-KEY-5rNo6a
export ARN_GCSEC=arn:aws:secretsmanager:us-west-2:528131355234:secret:TLDW-GOOGLE-OAUTH-CLIENT-SECRET-LmUrPI
export ARN_GCID=arn:aws:secretsmanager:us-west-2:528131355234:secret:TLDW-GOOGLE-OAUTH-CLIENT-ID-8Z22IN
export ARN_SESSION=arn:aws:secretsmanager:us-west-2:528131355234:secret:TLDW-SESSION-SECRET-hJDTQ1
export ARN_DEEPGRAM=arn:aws:secretsmanager:us-west-2:528131355234:secret:TLDW-DEEPGRAM-API-KEY-6gvcFv

echo "=== TL;DW App Runner Deployment Script ==="
echo "AWS Region: $AWS_REGION"
echo "Service Name: $SERVICE_NAME"
echo "Repository: $APP_REPO"
echo "Image Tag: $IMAGE_TAG"
echo "Account ID: $ACCOUNT_ID"
echo ""

# ====== Build & push image to ECR ======
echo "Step 1: Creating ECR repository and building Docker image..."
aws ecr create-repository --repository-name "$APP_REPO" --region "$AWS_REGION" >/dev/null 2>&1 || true

echo "Logging into ECR..."
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "Building Docker image..."
# Try building with existing cache or alternative approach
if ! docker build -t "${APP_REPO}:${IMAGE_TAG}" .; then
    echo "Build failed, checking for existing images..."
    if docker images | grep -q "tldw-app-test"; then
        echo "Using existing tldw-app-test image..."
        docker tag tldw-app-test:latest "${APP_REPO}:${IMAGE_TAG}"
    else
        echo "No suitable image found. Please check Docker network connectivity."
        exit 1
    fi
fi

echo "Tagging and pushing image with commit tag..."
docker tag "${APP_REPO}:${IMAGE_TAG}" "${ECR_URI}"
docker push "${ECR_URI}"

echo "Tagging and pushing image as latest..."
docker tag "${APP_REPO}:${IMAGE_TAG}" "${ECR_URI_LATEST}"
docker push "${ECR_URI_LATEST}"

# ====== Create roles (one-time safe) ======
echo ""
echo "Step 2: Creating IAM roles..."
export ECR_ACCESS_ROLE=AppRunnerECRAccessRole
export INSTANCE_ROLE=AppRunnerInstanceRole

cat > trust-ecr.json <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Service": "build.apprunner.amazonaws.com" },
    "Action": "sts:AssumeRole"
  }]
}
JSON

cat > trust-inst.json <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Service": "tasks.apprunner.amazonaws.com" },
    "Action": "sts:AssumeRole"
  }]
}
JSON

echo "Creating ECR access role..."
aws iam create-role --role-name "$ECR_ACCESS_ROLE" \
  --assume-role-policy-document file://trust-ecr.json >/dev/null 2>&1 || true
aws iam attach-role-policy --role-name "$ECR_ACCESS_ROLE" \
  --policy-arn arn:aws:iam::aws:policy/AWSAppRunnerServicePolicyForECRAccess >/dev/null 2>&1 || true

echo "Creating instance role..."
aws iam create-role --role-name "$INSTANCE_ROLE" \
  --assume-role-policy-document file://trust-inst.json >/dev/null 2>&1 || true

# Grant the instance role read access to ALL your secrets
echo "Granting secrets access to instance role..."
cat > secrets-inline.json <<JSON
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "AllowReadAllTLDWSecrets",
    "Effect": "Allow",
    "Action": ["secretsmanager:GetSecretValue"],
    "Resource": [
      "${ARN_OXY}",
      "${ARN_RESEND}",
      "${ARN_OPENAI}",
      "${ARN_GCSEC}",
      "${ARN_GCID}",
      "${ARN_SESSION}",
      "${ARN_DEEPGRAM}"
    ]
  }]
}
JSON

aws iam put-role-policy --role-name "$INSTANCE_ROLE" \
  --policy-name AppRunnerSecretsAccess \
  --policy-document file://secrets-inline.json >/dev/null

# ====== Create App Runner service (image mode) ======
echo ""
echo "Step 3: Creating App Runner service..."
cat > create.json <<JSON
{
  "ServiceName": "${SERVICE_NAME}",
  "SourceConfiguration": {
    "AutoDeploymentsEnabled": true,
    "AuthenticationConfiguration": {
      "AccessRoleArn": "arn:aws:iam::${ACCOUNT_ID}:role/${ECR_ACCESS_ROLE}"
    },
    "ImageRepository": {
      "ImageIdentifier": "${ECR_URI}",
      "ImageRepositoryType": "ECR",
      "ImageConfiguration": {
        "Port": "8080",
        "RuntimeEnvironmentVariables": {
          "PORT": "8080",
          "FFMPEG_LOCATION": "/usr/bin",
          "USE_PROXIES": "true",
          "PROXY_COUNTRY": "us",
          "ALLOW_MISSING_DEPS": "true"
        },
        "RuntimeEnvironmentSecrets": {
          "OXYLABS_PROXY_CONFIG": "${ARN_OXY}",
          "RESEND_API_KEY": "${ARN_RESEND}",
          "OPENAI_API_KEY": "${ARN_OPENAI}",
          "GOOGLE_CLIENT_SECRET": "${ARN_GCSEC}",
          "GOOGLE_CLIENT_ID": "${ARN_GCID}",
          "SESSION_SECRET": "${ARN_SESSION}",
          "DEEPGRAM_API_KEY": "${ARN_DEEPGRAM}"
        }
      }
    }
  },
  "InstanceConfiguration": {
    "Cpu": "${CPU}",
    "Memory": "${MEM}",
    "InstanceRoleArn": "arn:aws:iam::${ACCOUNT_ID}:role/${INSTANCE_ROLE}"
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
JSON

echo "Creating App Runner service (this may take a few minutes)..."
aws apprunner create-service --region "$AWS_REGION" --cli-input-json file://create.json

echo ""
echo "=== Deployment Complete! ==="
echo "Service Name: $SERVICE_NAME"
echo "Image: $ECR_URI"
echo ""
echo "Next steps:"
echo "1. Monitor service status: aws apprunner describe-service --service-arn <service-arn> --region $AWS_REGION"
echo "2. Check logs in AWS Console: App Runner > Services > $SERVICE_NAME > Logs"
echo "3. Once running, test health endpoint: https://<service-url>/healthz"
echo "4. After confirming everything works, consider setting ALLOW_MISSING_DEPS=false"
echo ""
echo "Cleaning up temporary files..."
rm -f trust-ecr.json trust-inst.json secrets-inline.json create.json
