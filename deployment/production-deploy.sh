#!/bin/bash
# Production deployment script for structured JSON logging migration
# This script deploys to production with minimal logging enabled and monitoring

set -euo pipefail
export AWS_PAGER=""

# Production configuration
AWS_REGION="${AWS_REGION:-us-west-2}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-528131355234}"
ECR_REPOSITORY="${ECR_REPOSITORY:-tldw}"
SERVICE_NAME="${SERVICE_NAME:-tldw-container-app}"

echo "=== Production Deployment for Structured JSON Logging ==="
echo "Service: ${SERVICE_NAME}"
echo "Region: ${AWS_REGION}"
echo ""

# Validate production environment variables
echo "🔍 Validating production environment configuration..."

# Required production environment variables for minimal logging
PRODUCTION_ENV_VARS=(
    "USE_MINIMAL_LOGGING=true"
    "LOG_LEVEL=INFO"
    "CLOUDWATCH_LOG_GROUP=/aws/apprunner/tldw-transcript-service"
    "RATE_LIMIT_PER_KEY=5"
    "RATE_LIMIT_WINDOW_SEC=60"
    "FFMPEG_STDERR_TAIL_LINES=40"
    "PERF_METRICS_ENABLED=true"
    "PERF_METRICS_INTERVAL=30"
)

echo "Production environment variables:"
for env_var in "${PRODUCTION_ENV_VARS[@]}"; do
    echo "  - $env_var"
done
echo ""

# Validate staging deployment first
echo "🔍 Validating staging deployment before production..."
if command -v python3 >/dev/null 2>&1; then
    if python3 deployment/validate-staging-logs.py --region "$AWS_REGION"; then
        echo "✅ Staging validation passed"
    else
        echo "❌ Staging validation failed - aborting production deployment"
        exit 1
    fi
else
    echo "⚠️  Python3 not available - skipping staging validation"
    echo "   Ensure staging validation was completed manually"
    read -p "Continue with production deployment? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Production deployment aborted"
        exit 1
    fi
fi

# Create production CloudWatch log group if it doesn't exist
echo "📊 Setting up production CloudWatch log group..."
PRODUCTION_LOG_GROUP="/aws/apprunner/tldw-transcript-service"

if ! aws logs describe-log-groups \
    --log-group-name-prefix "$PRODUCTION_LOG_GROUP" \
    --region "$AWS_REGION" \
    --query "logGroups[?logGroupName=='$PRODUCTION_LOG_GROUP']" \
    --output text | grep -q "$PRODUCTION_LOG_GROUP"; then
    
    echo "Creating production log group: $PRODUCTION_LOG_GROUP"
    aws logs create-log-group \
        --log-group-name "$PRODUCTION_LOG_GROUP" \
        --region "$AWS_REGION"
    
    # Set 30-day retention for production
    aws logs put-retention-policy \
        --log-group-name "$PRODUCTION_LOG_GROUP" \
        --retention-in-days 30 \
        --region "$AWS_REGION"
    
    echo "✅ Production log group created with 30-day retention"
else
    echo "✅ Production log group already exists"
fi

# Deploy monitoring dashboards and alerts
echo "📊 Deploying monitoring configuration..."
if [[ -f "cloudwatch_dashboard_config.py" ]]; then
    echo "Deploying CloudWatch dashboards..."
    python3 cloudwatch_dashboard_config.py --deploy --environment production
    echo "✅ Dashboards deployed"
else
    echo "⚠️  Dashboard configuration not found - skipping"
fi

if [[ -f "cloudwatch_alerts_config.py" ]]; then
    echo "Deploying CloudWatch alerts..."
    python3 cloudwatch_alerts_config.py --deploy --environment production
    echo "✅ Alerts deployed"
else
    echo "⚠️  Alert configuration not found - skipping"
fi

# Confirmation prompt for production deployment
echo ""
echo "🚨 PRODUCTION DEPLOYMENT CONFIRMATION 🚨"
echo "This will deploy structured JSON logging to production."
echo "Ensure the following have been completed:"
echo "  ✓ Staging validation passed"
echo "  ✓ Team has been notified"
echo "  ✓ Rollback plan is ready"
echo "  ✓ Monitoring is configured"
echo ""
read -p "Proceed with production deployment? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Production deployment aborted"
    exit 1
fi

# Deploy to production using main deployment script
echo "🚀 Deploying to production environment..."
export SERVICE_NAME="$SERVICE_NAME"

# Call main deployment script with production configuration
./deploy-apprunner.sh --timeout 600

# Post-deployment monitoring setup
echo ""
echo "📊 Setting up post-deployment monitoring..."

# Wait for deployment to stabilize
echo "⏳ Waiting for deployment to stabilize (60 seconds)..."
sleep 60

# Validate production deployment
echo "🔍 Validating production deployment..."
if command -v python3 >/dev/null 2>&1; then
    if python3 deployment/validate-staging-logs.py \
        --region "$AWS_REGION" \
        --log-group "$PRODUCTION_LOG_GROUP" \
        --output "production-validation-report.json"; then
        echo "✅ Production validation passed"
    else
        echo "⚠️  Production validation has issues - monitor closely"
    fi
else
    echo "⚠️  Python3 not available - manual validation required"
fi

# Set up continuous monitoring
echo "📊 Setting up continuous monitoring..."

# Create monitoring script for the first 24 hours
cat > monitor-production-logs.sh << 'EOF'
#!/bin/bash
# Continuous monitoring script for production logging migration
# Run this script to monitor the first 24 hours after deployment

LOG_GROUP="/aws/apprunner/tldw-transcript-service"
REGION="us-west-2"

echo "=== Production Logging Monitoring ==="
echo "Log Group: $LOG_GROUP"
echo "Region: $REGION"
echo "Started: $(date)"
echo ""

# Monitor for 24 hours with 15-minute intervals
for i in {1..96}; do
    echo "--- Check $i/96 at $(date) ---"
    
    # Get error count in last 15 minutes
    ERROR_COUNT=$(aws logs start-query \
        --log-group-name "$LOG_GROUP" \
        --start-time $(date -d '15 minutes ago' +%s) \
        --end-time $(date +%s) \
        --query-string 'fields @timestamp | filter lvl = "ERROR" | stats count()' \
        --region "$REGION" \
        --query 'queryId' --output text 2>/dev/null || echo "")
    
    if [[ -n "$ERROR_COUNT" ]]; then
        sleep 5
        RESULT=$(aws logs get-query-results --query-id "$ERROR_COUNT" --region "$REGION" 2>/dev/null || echo "")
        if echo "$RESULT" | grep -q "Complete"; then
            ERRORS=$(echo "$RESULT" | jq -r '.results[0][0].value // "0"' 2>/dev/null || echo "0")
            echo "  Errors in last 15 min: $ERRORS"
            
            if [[ "$ERRORS" -gt 10 ]]; then
                echo "  ⚠️  HIGH ERROR RATE DETECTED!"
            fi
        fi
    fi
    
    # Check log volume
    VOLUME=$(aws logs describe-log-streams \
        --log-group-name "$LOG_GROUP" \
        --order-by LastEventTime \
        --descending \
        --limit 1 \
        --region "$REGION" \
        --query 'logStreams[0].storedBytes' --output text 2>/dev/null || echo "0")
    
    echo "  Log volume: $VOLUME bytes"
    
    # Sleep for 15 minutes
    if [[ $i -lt 96 ]]; then
        sleep 900
    fi
done

echo ""
echo "=== 24-hour monitoring completed at $(date) ==="
EOF

chmod +x monitor-production-logs.sh

echo ""
echo "🎉 Production deployment completed!"
echo ""
echo "📊 Monitoring Information:"
echo "   Log Group: $PRODUCTION_LOG_GROUP"
echo "   Region: $AWS_REGION"
echo "   Monitor logs: aws logs tail $PRODUCTION_LOG_GROUP --follow --region $AWS_REGION"
echo ""
echo "🔍 Immediate Actions Required:"
echo "1. Monitor error rates for the next 2 hours"
echo "2. Validate JSON log format in CloudWatch"
echo "3. Test CloudWatch Logs Insights queries"
echo "4. Check application performance metrics"
echo "5. Verify job correlation is working"
echo ""
echo "📊 Continuous Monitoring:"
echo "   Run: ./monitor-production-logs.sh (monitors for 24 hours)"
echo ""
echo "🚨 Rollback Instructions (if needed):"
echo "   Set USE_MINIMAL_LOGGING=false and redeploy:"
echo "   export USE_MINIMAL_LOGGING=false"
echo "   ./deploy-apprunner.sh --timeout 300"
echo ""
echo "✅ Production deployment with structured JSON logging is now active!"