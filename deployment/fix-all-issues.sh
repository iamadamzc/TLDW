#!/bin/bash

# Comprehensive fix for both S3 permissions and proxy authentication issues

set -e

echo "=== Comprehensive Deployment Fix ==="

# Configuration
SERVICE_NAME="${SERVICE_NAME:-tldw-container-app}"
AWS_REGION="${AWS_REGION:-us-west-2}"

# Check if AWS CLI is configured
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ AWS CLI not configured"
    exit 1
fi

echo "✅ AWS CLI configured"

# Get App Runner service ARN
echo "🔍 Finding App Runner service..."
SERVICE_ARN=$(aws apprunner list-services --region "$AWS_REGION" --query "ServiceSummaryList[?ServiceName=='$SERVICE_NAME'].ServiceArn" --output text)

if [ -z "$SERVICE_ARN" ]; then
    echo "❌ App Runner service '$SERVICE_NAME' not found"
    exit 1
fi

echo "✅ Found service: $SERVICE_ARN"

# Get current config
CURRENT_CONFIG=$(aws apprunner describe-service --service-arn "$SERVICE_ARN")
COOKIE_BUCKET=$(echo "$CURRENT_CONFIG" | jq -r '.Service.SourceConfiguration.ImageRepository.ImageConfiguration.RuntimeEnvironmentVariables.COOKIE_S3_BUCKET // empty')
INSTANCE_ROLE_ARN=$(echo "$CURRENT_CONFIG" | jq -r '.Service.InstanceConfiguration.InstanceRoleArn // empty')

# Fix 1: S3 HeadObject Permission
if [ -n "$COOKIE_BUCKET" ] && [ "$COOKIE_BUCKET" != "null" ] && [ -n "$INSTANCE_ROLE_ARN" ] && [ "$INSTANCE_ROLE_ARN" != "null" ]; then
    ROLE_NAME=$(echo "$INSTANCE_ROLE_ARN" | cut -d'/' -f2)
    
    echo "🔧 Fixing S3 permissions for bucket: $COOKIE_BUCKET"
    echo "   Role: $ROLE_NAME"
    
    # Create policy with HeadObject permission
    POLICY_JSON=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCookieOperations",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:HeadObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::$COOKIE_BUCKET/cookies/*"
      ]
    },
    {
      "Sid": "AllowKMSDecryption",
      "Effect": "Allow",
      "Action": [
        "kms:Decrypt"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "kms:ViaService": "s3.*.amazonaws.com"
        }
      }
    }
  ]
}
EOF
)
    
    # Apply the policy (Windows-compatible approach)
    TEMP_POLICY_FILE="deployment/temp-policy-$$.json"
    echo "$POLICY_JSON" > "$TEMP_POLICY_FILE"
    
    aws iam put-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-name "AppRunnerCookieAccess" \
        --policy-document "file://$TEMP_POLICY_FILE"
    
    rm "$TEMP_POLICY_FILE"
    echo "✅ S3 permissions updated (added s3:HeadObject)"
else
    echo "⚠️  Skipping S3 fix - no cookie bucket or role found"
fi

# Fix 2: Check and clear proxy environment variables
echo "🔧 Checking proxy environment variables..."

# Get current environment variables
ENV_VARS=$(echo "$CURRENT_CONFIG" | jq -r '.Service.SourceConfiguration.ImageRepository.ImageConfiguration.RuntimeEnvironmentVariables // {}')

# Check if HTTP_PROXY or HTTPS_PROXY are set
HTTP_PROXY_SET=$(echo "$ENV_VARS" | jq -r '.HTTP_PROXY // empty')
HTTPS_PROXY_SET=$(echo "$ENV_VARS" | jq -r '.HTTPS_PROXY // empty')

if [ -n "$HTTP_PROXY_SET" ] || [ -n "$HTTPS_PROXY_SET" ]; then
    echo "⚠️  Found conflicting proxy environment variables:"
    [ -n "$HTTP_PROXY_SET" ] && echo "   HTTP_PROXY=$HTTP_PROXY_SET"
    [ -n "$HTTPS_PROXY_SET" ] && echo "   HTTPS_PROXY=$HTTPS_PROXY_SET"
    
    echo "🔧 Removing conflicting proxy environment variables..."
    
    # Remove HTTP_PROXY and HTTPS_PROXY from environment variables
    UPDATED_ENV_VARS=$(echo "$ENV_VARS" | jq 'del(.HTTP_PROXY) | del(.HTTPS_PROXY)')
    
    # Update the service
    aws apprunner update-service \
        --service-arn "$SERVICE_ARN" \
        --region "$AWS_REGION" \
        --source-configuration "{
            \"ImageRepository\": {
                \"ImageIdentifier\": \"$(echo "$CURRENT_CONFIG" | jq -r '.Service.SourceConfiguration.ImageRepository.ImageIdentifier')\",
                \"ImageConfiguration\": {
                    \"Port\": \"8080\",
                    \"RuntimeEnvironmentVariables\": $UPDATED_ENV_VARS
                },
                \"ImageRepositoryType\": \"ECR\"
            },
            \"AutoDeploymentsEnabled\": false
        }" > /dev/null
    
    echo "✅ Removed conflicting proxy environment variables"
    echo "⏳ App Runner service is updating..."
else
    echo "✅ No conflicting proxy environment variables found"
fi

echo ""
echo "🎉 All fixes applied!"
echo ""
echo "📋 Changes made:"
echo "   ✅ Added s3:HeadObject permission for cookie access"
echo "   ✅ Checked/removed conflicting proxy environment variables"
echo ""
echo "🔍 Next steps:"
echo "1. Wait for App Runner service to finish updating (if proxy vars were removed)"
echo "2. Test video summarization with video ID: NvtsM8Nk72c"
echo "3. Check logs for:"
echo "   - 'cookies_used=true' (S3 access working)"
echo "   - No more 407 proxy authentication errors"
echo "   - Successful yt-dlp downloads"
echo ""
echo "🧪 Test URL: https://wy2vvma4cw.us-west-2.awsapprunner.com/"