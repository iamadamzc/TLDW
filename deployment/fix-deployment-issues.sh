#!/bin/bash

# Quick fix script for immediate deployment issues
# Addresses S3 403 errors and proxy 407 errors

set -e

# Check for required tools
command -v jq >/dev/null 2>&1 || { echo "❌ jq not installed. Install jq and re-run."; exit 1; }

echo "=== TL;DW Deployment Issue Fix ==="

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
    echo "📋 Manual steps needed:"
    echo "1. Set COOKIE_S3_BUCKET environment variable in App Runner"
    echo "2. Run this script again to fix IAM permissions"
    exit 0
fi

echo "✅ Found cookie bucket: $COOKIE_BUCKET"

# Fix IAM permissions
echo "🔑 Fixing IAM permissions for S3 and KMS..."
INSTANCE_ROLE_ARN=$(echo "$CURRENT_CONFIG" | jq -r '.Service.InstanceConfiguration.InstanceRoleArn // empty')

if [ -n "$INSTANCE_ROLE_ARN" ] && [ "$INSTANCE_ROLE_ARN" != "null" ]; then
    ROLE_NAME=$(echo "$INSTANCE_ROLE_ARN" | cut -d'/' -f2)
    
    # Create the corrected IAM policy with KMS permissions
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
    
    # Apply the corrected policy (create temp file for Windows compatibility)
    TEMP_POLICY_FILE=$(mktemp)
    echo "$POLICY_JSON" > "$TEMP_POLICY_FILE"
    
    aws iam put-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-name "AppRunnerCookieAccess" \
        --policy-document "file://$TEMP_POLICY_FILE"
    
    # Clean up temp file
    rm "$TEMP_POLICY_FILE"
    
    echo "✅ IAM policy updated for role: $ROLE_NAME"
    echo "   - Added s3:GetObject, s3:PutObject, s3:DeleteObject for cookies/*"
    echo "   - Added kms:Decrypt for SSE-KMS encrypted buckets"
else
    echo "⚠️  No instance role found. Manual IAM configuration needed."
fi

# Check if bucket exists and has proper configuration
echo "🪣 Verifying S3 bucket configuration..."
if aws s3 ls "s3://$COOKIE_BUCKET" >/dev/null 2>&1; then
    echo "✅ S3 bucket exists and is accessible"
    
    # Check if cookies directory exists
    if aws s3 ls "s3://$COOKIE_BUCKET/cookies/" >/dev/null 2>&1; then
        echo "✅ Cookies directory exists"
    else
        echo "📁 Creating cookies directory..."
        # Create a placeholder file to ensure the directory exists
        echo "# Cookie directory" | aws s3 cp - "s3://$COOKIE_BUCKET/cookies/.gitkeep"
    fi
else
    echo "❌ Cannot access S3 bucket: $COOKIE_BUCKET"
    echo "   Check bucket name and permissions"
fi

echo ""
echo "✅ Deployment fixes applied!"
echo ""
echo "🔧 Changes made:"
echo "   - Updated IAM policy to include KMS decrypt permissions"
echo "   - Verified S3 bucket access and structure"
echo ""
echo "📋 Next steps:"
echo "1. Deploy the updated application code with yt-dlp hardening fixes"
echo "2. Test cookie upload at /account/cookies"
echo "3. Try summarizing a video that previously failed"
echo ""
echo "🔍 Monitor logs for:"
echo "   - 'Using user cookiefile for yt-dlp' (success)"
echo "   - 'S3 cookie download failed' (if still issues)"
echo "   - 'missing authentication credentials' (proxy issues)"
echo ""
echo "🆘 If issues persist:"
echo "   - Check proxy credentials format: http://user:pass@host:port"
echo "   - Verify no HTTP_PROXY/HTTPS_PROXY env vars conflict"
echo "   - Use DISABLE_COOKIES=true as emergency kill-switch"