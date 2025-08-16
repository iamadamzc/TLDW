#!/bin/bash

# Enable cookie functionality for TL;DW App Runner service
# Usage: ./enable-cookies.sh [S3_BUCKET_NAME]

set -e

# Configuration
SERVICE_NAME="${SERVICE_NAME:-tldw-service}"
AWS_REGION="${AWS_REGION:-us-west-2}"
COOKIE_BUCKET_NAME="${1:-}"

echo "=== TL;DW Cookie Feature Deployment ==="

# Check if AWS CLI is configured
if ! aws sts get-caller-identity >/dev/null 2>&1; then
    echo "❌ AWS CLI not configured. Please run 'aws configure' first."
    exit 1
fi

# Get App Runner service ARN
echo "🔍 Finding App Runner service..."
SERVICE_ARN=$(aws apprunner list-services --region "$AWS_REGION" --query "ServiceSummaryList[?ServiceName=='$SERVICE_NAME'].ServiceArn" --output text)

if [ -z "$SERVICE_ARN" ]; then
    echo "❌ App Runner service '$SERVICE_NAME' not found in region $AWS_REGION"
    exit 1
fi

echo "✅ Found service: $SERVICE_ARN"

# Setup S3 bucket if provided
if [ -n "$COOKIE_BUCKET_NAME" ]; then
    echo "🪣 Setting up S3 bucket: $COOKIE_BUCKET_NAME"
    
    # Create bucket if it doesn't exist
    if ! aws s3 ls "s3://$COOKIE_BUCKET_NAME" >/dev/null 2>&1; then
        echo "📦 Creating S3 bucket..."
        aws s3 mb "s3://$COOKIE_BUCKET_NAME" --region "$AWS_REGION"
        
        # Enable encryption
        echo "🔒 Enabling encryption..."
        aws s3api put-bucket-encryption \
            --bucket "$COOKIE_BUCKET_NAME" \
            --server-side-encryption-configuration '{
                "Rules": [
                    {
                        "ApplyServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "aws:kms"
                        }
                    }
                ]
            }'
        
        # Block public access
        echo "🚫 Blocking public access..."
        aws s3api put-public-access-block \
            --bucket "$COOKIE_BUCKET_NAME" \
            --public-access-block-configuration \
                BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
    else
        echo "✅ S3 bucket already exists"
    fi
    
    # Get the instance role ARN from the service
    echo "🔑 Updating IAM permissions..."
    INSTANCE_ROLE_ARN=$(aws apprunner describe-service --service-arn "$SERVICE_ARN" --query 'Service.InstanceConfiguration.InstanceRoleArn' --output text)
    
    if [ "$INSTANCE_ROLE_ARN" != "None" ] && [ -n "$INSTANCE_ROLE_ARN" ]; then
        ROLE_NAME=$(echo "$INSTANCE_ROLE_ARN" | cut -d'/' -f2)
        
        # Create IAM policy
        POLICY_JSON=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCookieOperations",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::$COOKIE_BUCKET_NAME/cookies/*"
      ]
    }
  ]
}
EOF
)
        
        # Apply the policy
        echo "$POLICY_JSON" | aws iam put-role-policy \
            --role-name "$ROLE_NAME" \
            --policy-name "AppRunnerCookieAccess" \
            --policy-document file:///dev/stdin
        
        echo "✅ IAM policy applied to role: $ROLE_NAME"
    else
        echo "⚠️  No instance role found. You may need to manually configure IAM permissions."
    fi
fi

# Update App Runner service with environment variables
echo "🚀 Updating App Runner service configuration..."

# Get current service configuration
CURRENT_CONFIG=$(aws apprunner describe-service --service-arn "$SERVICE_ARN")

# Build environment variables
ENV_VARS='"PORT": "8080", "FFMPEG_LOCATION": "/usr/bin", "USE_PROXIES": "true", "PROXY_COUNTRY": "us", "ALLOW_MISSING_DEPS": "true", "COOKIE_LOCAL_DIR": "/app/cookies"'

if [ -n "$COOKIE_BUCKET_NAME" ]; then
    ENV_VARS="$ENV_VARS, \"COOKIE_S3_BUCKET\": \"$COOKIE_BUCKET_NAME\""
fi

# Update the service (this is a simplified version - in practice you'd need to preserve existing config)
echo "📝 Note: You may need to manually update your App Runner service configuration to include:"
echo "   COOKIE_LOCAL_DIR=/app/cookies"
if [ -n "$COOKIE_BUCKET_NAME" ]; then
    echo "   COOKIE_S3_BUCKET=$COOKIE_BUCKET_NAME"
fi

echo ""
echo "✅ Cookie feature deployment preparation complete!"
echo ""
echo "📋 Next steps:"
echo "1. Update your App Runner service environment variables via AWS Console or CLI"
echo "2. Deploy the updated application code"
echo "3. Test cookie upload functionality at /account/cookies"
echo ""
echo "🆘 Emergency disable: Set DISABLE_COOKIES=true environment variable"
echo ""
echo "📖 See deployment/cookie-deployment-guide.md for detailed instructions"