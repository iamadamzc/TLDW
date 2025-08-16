#!/bin/bash

# Simple IAM policy fix for Windows/Git Bash compatibility
# Uses the existing cookie-iam-policy.json file

set -e

echo "=== Fixing IAM Policy for Cookie S3 Access ==="

# Configuration
SERVICE_NAME="${SERVICE_NAME:-tldw-service}"
AWS_REGION="${AWS_REGION:-us-west-2}"

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

# Get current environment variables to find the cookie bucket
echo "🔍 Checking current configuration..."
CURRENT_CONFIG=$(aws apprunner describe-service --service-arn "$SERVICE_ARN")
COOKIE_BUCKET=$(echo "$CURRENT_CONFIG" | jq -r '.Service.SourceConfiguration.ImageRepository.ImageConfiguration.RuntimeEnvironmentVariables.COOKIE_S3_BUCKET // empty')

if [ -z "$COOKIE_BUCKET" ] || [ "$COOKIE_BUCKET" = "null" ]; then
    echo "⚠️  No COOKIE_S3_BUCKET found in current configuration"
    echo "📋 Please set COOKIE_S3_BUCKET environment variable in App Runner first"
    exit 1
fi

echo "✅ Found cookie bucket: $COOKIE_BUCKET"

# Get instance role
INSTANCE_ROLE_ARN=$(echo "$CURRENT_CONFIG" | jq -r '.Service.InstanceConfiguration.InstanceRoleArn // empty')

if [ -z "$INSTANCE_ROLE_ARN" ] || [ "$INSTANCE_ROLE_ARN" = "null" ]; then
    echo "❌ No instance role found in App Runner service"
    exit 1
fi

ROLE_NAME=$(echo "$INSTANCE_ROLE_ARN" | cut -d'/' -f2)
echo "✅ Found instance role: $ROLE_NAME"

# Create policy file with actual bucket name
echo "🔧 Creating IAM policy for bucket: $COOKIE_BUCKET"
POLICY_FILE="deployment/cookie-iam-policy-${COOKIE_BUCKET}.json"

# Replace placeholder with actual bucket name
sed "s/\${COOKIE_S3_BUCKET}/$COOKIE_BUCKET/g" deployment/cookie-iam-policy.json > "$POLICY_FILE"

echo "📄 Policy file created: $POLICY_FILE"

# Apply the policy
echo "🔑 Applying IAM policy to role: $ROLE_NAME"
aws iam put-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-name "AppRunnerCookieAccess" \
    --policy-document "file://$POLICY_FILE"

echo "✅ IAM policy applied successfully!"

# Clean up temp policy file
rm "$POLICY_FILE"

echo ""
echo "🎉 IAM permissions fixed!"
echo ""
echo "📋 Policy includes:"
echo "   - s3:GetObject on s3://$COOKIE_BUCKET/cookies/*"
echo "   - s3:PutObject on s3://$COOKIE_BUCKET/cookies/*" 
echo "   - s3:DeleteObject on s3://$COOKIE_BUCKET/cookies/*"
echo "   - kms:Decrypt for SSE-KMS encrypted buckets"
echo ""
echo "🔍 Next steps:"
echo "1. Deploy updated application code"
echo "2. Upload a cookie file via /account/cookies"
echo "3. Test video summarization"
echo ""
echo "📊 Monitor logs for 'Using user cookiefile for yt-dlp' success messages"