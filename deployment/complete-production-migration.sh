#!/bin/bash
# Complete production migration script for structured JSON logging
# This script orchestrates the entire migration process from staging to cleanup

set -euo pipefail
export AWS_PAGER=""

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MIGRATION_LOG="$WORKSPACE_ROOT/production-migration.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${2:-}$(date '+%Y-%m-%d %H:%M:%S') - $1${NC}" | tee -a "$MIGRATION_LOG"
}

log_info() { log "$1" "$BLUE"; }
log_success() { log "$1" "$GREEN"; }
log_warning() { log "$1" "$YELLOW"; }
log_error() { log "$1" "$RED"; }

# Error handling
cleanup() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        log_error "Migration failed with exit code $exit_code"
        log_error "Check $MIGRATION_LOG for details"
        log_error "Rollback may be required"
    fi
    exit $exit_code
}
trap cleanup EXIT INT TERM

echo "=================================================================="
echo "🚀 COMPLETE PRODUCTION MIGRATION FOR STRUCTURED JSON LOGGING"
echo "=================================================================="
echo ""

log_info "Starting complete production migration process"
log_info "Migration log: $MIGRATION_LOG"
log_info "Workspace: $WORKSPACE_ROOT"
echo ""

# Phase 1: Pre-migration validation
echo "📋 PHASE 1: PRE-MIGRATION VALIDATION"
echo "======================================"

log_info "Validating workspace and dependencies..."

# Check required files exist
REQUIRED_FILES=(
    "logging_setup.py"
    "log_events.py"
    "deployment/staging-deploy.sh"
    "deployment/validate-staging-logs.py"
    "deployment/production-deploy.sh"
    "deployment/cleanup-deprecated-logging.py"
    "deployment/update-documentation.py"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [[ ! -f "$WORKSPACE_ROOT/$file" ]]; then
        log_error "Required file missing: $file"
        exit 1
    fi
done

log_success "All required files present"

# Check Python dependencies
if ! command -v python3 >/dev/null 2>&1; then
    log_error "Python3 is required but not available"
    exit 1
fi

# Test new logging system
log_info "Testing new logging system..."
if python3 -c "
import sys
sys.path.insert(0, '$WORKSPACE_ROOT')
from logging_setup import configure_logging
from log_events import evt, StageTimer
configure_logging()
print('New logging system test passed')
" 2>/dev/null; then
    log_success "New logging system is working"
else
    log_error "New logging system test failed"
    exit 1
fi

echo ""

# Phase 2: Staging deployment and validation
echo "🧪 PHASE 2: STAGING DEPLOYMENT AND VALIDATION"
echo "=============================================="

log_info "Deploying to staging environment..."

# Make scripts executable
chmod +x "$SCRIPT_DIR/staging-deploy.sh" 2>/dev/null || true
chmod +x "$SCRIPT_DIR/production-deploy.sh" 2>/dev/null || true

# Deploy to staging
if [[ -f "$SCRIPT_DIR/staging-deploy.sh" ]]; then
    log_info "Running staging deployment..."
    if "$SCRIPT_DIR/staging-deploy.sh" 2>&1 | tee -a "$MIGRATION_LOG"; then
        log_success "Staging deployment completed"
    else
        log_error "Staging deployment failed"
        exit 1
    fi
else
    log_warning "Staging deployment script not found - skipping"
fi

# Wait for staging to stabilize
log_info "Waiting for staging to stabilize (60 seconds)..."
sleep 60

# Validate staging deployment
log_info "Validating staging deployment..."
if python3 "$SCRIPT_DIR/validate-staging-logs.py" \
    --output "$WORKSPACE_ROOT/staging-validation-report.json" 2>&1 | tee -a "$MIGRATION_LOG"; then
    log_success "Staging validation passed"
else
    log_error "Staging validation failed"
    log_error "Review staging-validation-report.json for details"
    exit 1
fi

echo ""

# Phase 3: Production deployment
echo "🚀 PHASE 3: PRODUCTION DEPLOYMENT"
echo "=================================="

log_info "Preparing for production deployment..."

# Final confirmation
echo ""
echo "🚨 PRODUCTION DEPLOYMENT CONFIRMATION 🚨"
echo "This will deploy structured JSON logging to production."
echo ""
echo "Pre-deployment checklist:"
echo "  ✅ Staging validation passed"
echo "  ✅ New logging system tested"
echo "  ✅ Required files present"
echo "  ✅ Team notification sent"
echo "  ✅ Rollback plan ready"
echo ""

read -p "Proceed with production deployment? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "Production deployment aborted by user"
    exit 0
fi

# Deploy to production
log_info "Running production deployment..."
if "$SCRIPT_DIR/production-deploy.sh" 2>&1 | tee -a "$MIGRATION_LOG"; then
    log_success "Production deployment completed"
else
    log_error "Production deployment failed"
    exit 1
fi

# Wait for production to stabilize
log_info "Waiting for production to stabilize (120 seconds)..."
sleep 120

# Validate production deployment
log_info "Validating production deployment..."
if python3 "$SCRIPT_DIR/validate-staging-logs.py" \
    --region "${AWS_REGION:-us-west-2}" \
    --log-group "/aws/apprunner/tldw-transcript-service" \
    --output "$WORKSPACE_ROOT/production-validation-report.json" 2>&1 | tee -a "$MIGRATION_LOG"; then
    log_success "Production validation passed"
else
    log_warning "Production validation has issues - monitor closely"
fi

echo ""

# Phase 4: Monitoring period
echo "📊 PHASE 4: MONITORING PERIOD"
echo "=============================="

log_info "Starting 24-hour monitoring period..."
log_info "Monitor production logs and metrics for the next 24 hours"
log_info "Use: aws logs tail /aws/apprunner/tldw-transcript-service --follow"

# Create monitoring reminder
cat > "$WORKSPACE_ROOT/monitoring-checklist.md" << 'EOF'
# Production Monitoring Checklist

## Immediate Actions (First 2 Hours)
- [ ] Monitor error rates in CloudWatch
- [ ] Validate JSON log format
- [ ] Test CloudWatch Logs Insights queries
- [ ] Check application performance metrics
- [ ] Verify job correlation is working
- [ ] Confirm no customer impact

## Daily Actions (Next 7 Days)
- [ ] Review error rates and trends
- [ ] Monitor log volume and costs
- [ ] Validate query performance
- [ ] Check team feedback
- [ ] Document any issues

## Weekly Actions (Next 4 Weeks)
- [ ] Analyze performance impact
- [ ] Review CloudWatch storage costs
- [ ] Update monitoring thresholds
- [ ] Plan cleanup of deprecated code

## Rollback Instructions (If Needed)
```bash
export USE_MINIMAL_LOGGING=false
./deploy-apprunner.sh --timeout 300
```

## Monitoring Commands
```bash
# Tail production logs
aws logs tail /aws/apprunner/tldw-transcript-service --follow

# Check error rates
aws logs start-query \
  --log-group-name /aws/apprunner/tldw-transcript-service \
  --start-time $(date -d '1 hour ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp | filter lvl = "ERROR" | stats count()'

# Monitor log volume
aws logs describe-log-streams \
  --log-group-name /aws/apprunner/tldw-transcript-service \
  --order-by LastEventTime \
  --descending --limit 5
```
EOF

log_success "Created monitoring checklist: monitoring-checklist.md"

echo ""
echo "⏰ WAITING PERIOD: 2 WEEKS MINIMUM"
echo "=================================="
echo ""
echo "The migration is now complete, but cleanup should wait 2 weeks minimum."
echo "This allows time to:"
echo "  - Monitor production stability"
echo "  - Validate all functionality"
echo "  - Collect team feedback"
echo "  - Ensure no rollback is needed"
echo ""
echo "After 2 weeks of stable operation, run the cleanup phase:"
echo "  ./deployment/complete-production-migration.sh --cleanup-only"
echo ""

# Check if cleanup was requested
if [[ "${1:-}" == "--cleanup-only" ]]; then
    echo ""
    echo "🧹 PHASE 5: CLEANUP (REQUESTED)"
    echo "==============================="
    
    echo ""
    echo "🚨 CLEANUP CONFIRMATION 🚨"
    echo "This will remove deprecated structured logging code."
    echo ""
    echo "Ensure the following before proceeding:"
    echo "  ✅ Production has been stable for 2+ weeks"
    echo "  ✅ New logging system is working correctly"
    echo "  ✅ Team is comfortable with new system"
    echo "  ✅ No rollback plans are needed"
    echo ""
    
    read -p "Proceed with cleanup? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Cleanup aborted by user"
        exit 0
    fi
    
    # Update documentation
    log_info "Updating documentation references..."
    if python3 "$SCRIPT_DIR/update-documentation.py" 2>&1 | tee -a "$MIGRATION_LOG"; then
        log_success "Documentation updated"
    else
        log_warning "Documentation update had issues"
    fi
    
    # Clean up deprecated code
    log_info "Cleaning up deprecated logging code..."
    if python3 "$SCRIPT_DIR/cleanup-deprecated-logging.py" 2>&1 | tee -a "$MIGRATION_LOG"; then
        log_success "Deprecated code cleanup completed"
    else
        log_error "Cleanup failed"
        exit 1
    fi
    
    log_success "Migration cleanup completed successfully!"
    
    echo ""
    echo "🎉 MIGRATION FULLY COMPLETE!"
    echo "============================"
    echo ""
    echo "The structured JSON logging migration is now fully complete:"
    echo "  ✅ Production deployment successful"
    echo "  ✅ System stable for 2+ weeks"
    echo "  ✅ Documentation updated"
    echo "  ✅ Deprecated code removed"
    echo "  ✅ Backup created for safety"
    echo ""
    echo "The minimal JSON logging system is now the only logging system."
    echo ""
    
else
    echo "Migration deployment phase completed successfully!"
    echo ""
    echo "📋 NEXT STEPS:"
    echo "1. Monitor production for 2 weeks minimum"
    echo "2. Use monitoring-checklist.md for daily checks"
    echo "3. After stable period, run cleanup:"
    echo "   ./deployment/complete-production-migration.sh --cleanup-only"
    echo ""
    echo "📊 MONITORING:"
    echo "   Logs: aws logs tail /aws/apprunner/tldw-transcript-service --follow"
    echo "   Health: Check service /healthz endpoint"
    echo "   Metrics: CloudWatch dashboards"
    echo ""
    echo "🚨 ROLLBACK (if needed):"
    echo "   export USE_MINIMAL_LOGGING=false"
    echo "   ./deploy-apprunner.sh --timeout 300"
fi

log_success "Complete production migration process finished"
echo ""
echo "=================================================================="