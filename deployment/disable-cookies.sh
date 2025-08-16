#!/bin/bash

# Disable cookie functionality for TL;DW App Runner service
# Usage: ./disable-cookies.sh [--remove-s3-data]

set -e

# Configuration
SERVICE_NAME="${SERVICE_NAME:-tldw-service}"
AWS_REGION="${AWS_REGION:-us-west-2}"
REMOVE_S3_DATA=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --remove-s3-data)
            REMOVE_S3_DATA=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--remove-s3-data]"
            exit 1
            ;;
    esac
done

echo "=== TL;DW Cookie Feature Rollback ==="

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

# Get current service configuration to find S3 bucket
echo "🔍 Checking current configuration..."
CURRENT_CONFIG=$(aws apprunner describe-service --service-arn "$SERVICE_ARN")
COOKIE_BUCKET=$(echo "$CURRENT_CONFIG" | jq -r '.Service.SourceConfiguration.ImageRepository.ImageConfiguration.RuntimeEnvironmentVariables.COOKIE_S3_BUCKET // empty')

# Emergency disable via environment variable
echo "🚨 Activating emergency kill-switch..."
echo "📝 Note: You need to manually update your App Runner service to set:"
echo "   DISABLE_COOKIES=true"
echo ""
echo "This will immediately disable cookie functionality without code changes."

# Remove IAM policy if we can identify it
if [ -n "$COOKIE_BUCKET" ]; then
    echo "🔑 Removing IAM permissions for bucket: $COOKIE_BUCKET"
    
    INSTANCE_ROLE_ARN=$(echo "$CURRENT_CONFIG" | jq -r '.Service.InstanceConfiguration.InstanceRoleArn // empty')
    
    if [ -n "$INSTANCE_ROLE_ARN" ] && [ "$INSTANCE_ROLE_ARN" != "null" ]; then
        ROLE_NAME=$(echo "$INSTANCE_ROLE_ARN" | cut -d'/' -f2)
        
        # Remove the cookie access policy
        aws iam delete-role-policy \
            --role-name "$ROLE_NAME" \
            --policy-name "AppRunnerCookieAccess" 2>/dev/null || echo "⚠️  Policy may not exist or already removed"
        
        echo "✅ IAM policy removed from role: $ROLE_NAME"
    fi
fi

# Optionally remove S3 data
if [ "$REMOVE_S3_DATA" = true ] && [ -n "$COOKIE_BUCKET" ]; then
    echo "🗑️  Removing S3 cookie data..."
    
    read -p "⚠️  This will permanently delete all user cookies in s3://$COOKIE_BUCKET/cookies/. Continue? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        aws s3 rm "s3://$COOKIE_BUCKET/cookies/" --recursive
        echo "✅ S3 cookie data removed"
    else
        echo "❌ S3 data removal cancelled"
    fi
fi

echo ""
echo "✅ Cookie feature rollback preparation complete!"
echo ""
echo "📋 Manual steps required:"
echo "1. Set DISABLE_COOKIES=true in App Runner environment variables (immediate effect)"
echo "2. Remove COOKIE_S3_BUCKET environment variable"
echo "3. Remove COOKIE_LOCAL_DIR environment variable (optional)"
echo "4. Deploy previous version of code if needed"
echo ""
echo "🔄 To re-enable: Remove DISABLE_COOKIES or set to 'false'"
echo ""
echo "📖 See deployment/cookie-deployment-guide.md for detailed instructions"