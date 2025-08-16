#!/bin/bash

# Fix S3 permissions by adding missing HeadObject permission
# This is needed because s3.download_file() calls HeadObject first

set -e

echo "=== Fixing S3 HeadObject Permission ==="

# Configuration
SERVICE_NAME="${SERVICE_NAME:-tldw-container-app}"
AWS_REGION="${AWS_REGION:-us-west-2}"

# Get App Runner service ARN
echo "🔍 Finding App Runner service..."
SERVICE_ARN=$(aws apprunner list-services --region "$AWS_REGION" --query "ServiceSummaryList[?ServiceName=='$SERVICE_NAME'].ServiceArn" --output text)

if [ -z "$SERVICE_ARN" ]; then
    echo "❌ App Runner service '$SERVICE_NAME' not found"
    exit 1
fi

# Get current config to find bucket and role
CURRENT_CONFIG=$(aws apprunner describe-service --service-arn "$SERVICE_ARN")
COOKIE_BUCKET=$(echo "$CURRENT_CONFIG" | jq -r '.Service.SourceConfiguration.ImageRepository.ImageConfiguration.RuntimeEnvironmentVariables.COOKIE_S3_BUCKET // empty')
INSTANCE_ROLE_ARN=$(echo "$CURRENT_CONFIG" | jq -r '.Service.InstanceConfiguration.InstanceRoleArn // empty')

if [ -z "$COOKIE_BUCKET" ] || [ "$COOKIE_BUCKET" = "null" ]; then
    echo "❌ No COOKIE_S3_BUCKET found"
    exit 1
fi

if [ -z "$INSTANCE_ROLE_ARN" ] || [ "$INSTANCE_ROLE_ARN" = "null" ]; then
    echo "❌ No instance role found"
    exit 1
fi

ROLE_NAME=$(echo "$INSTANCE_ROLE_ARN" | cut -d'/' -f2)

echo "✅ Found bucket: $COOKIE_BUCKET"
echo "✅ Found role: $ROLE_NAME"

# Create the corrected IAM policy with HeadObject permission
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

# Apply the corrected policy
echo "🔧 Adding s3:HeadObject permission..."
TEMP_POLICY_FILE=$(mktemp)
echo "$POLICY_JSON" > "$TEMP_POLICY_FILE"

aws iam put-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-name "AppRunnerCookieAccess" \
    --policy-document "file://$TEMP_POLICY_FILE"

rm "$TEMP_POLICY_FILE"

echo "✅ S3 permissions updated!"
echo ""
echo "📋 Policy now includes:"
echo "   - s3:GetObject"
echo "   - s3:HeadObject (ADDED - this was missing!)"
echo "   - s3:PutObject"
echo "   - s3:DeleteObject"
echo "   - kms:Decrypt for SSE-KMS"
echo ""
echo "🧪 Test by uploading a cookie file and trying video summarization"