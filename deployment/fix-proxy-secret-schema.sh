#!/bin/bash

# Fix AWS Secrets Manager Proxy Secret Schema
# This script helps fix the "proxy_secret_missing_provider" error by updating
# existing proxy secrets to include all required fields.

set -e

# Configuration
AWS_REGION="${AWS_REGION:-us-west-2}"
SECRET_NAME="${PROXY_SECRET_NAME:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if AWS CLI is available and configured
check_aws_cli() {
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed"
        echo "Install it from: https://aws.amazon.com/cli/"
        exit 1
    fi
    
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS CLI is not configured or credentials are invalid"
        echo "Run: aws configure"
        exit 1
    fi
    
    log_success "AWS CLI is configured"
}

# Check if jq is available
check_jq() {
    if ! command -v jq &> /dev/null; then
        log_error "jq is required but not installed"
        echo "Install with:"
        echo "  macOS: brew install jq"
        echo "  Ubuntu/Debian: apt-get install jq"
        echo "  Windows: choco install jq"
        exit 1
    fi
    
    log_success "jq is available"
}

# List potential proxy secrets
list_proxy_secrets() {
    log_info "Searching for proxy secrets in region: $AWS_REGION"
    
    # Get all secrets and filter for proxy-related ones
    aws secretsmanager list-secrets \
        --region "$AWS_REGION" \
        --query 'SecretList[?contains(Name, `proxy`) || contains(Name, `oxylabs`) || contains(Name, `brightdata`) || contains(Description, `proxy`) || contains(Description, `oxylabs`) || contains(Description, `brightdata`)]' \
        --output table \
        --no-cli-pager
    
    echo ""
    log_info "To validate a specific secret, run:"
    echo "  $0 validate <secret-name>"
}

# Validate secret schema
validate_secret() {
    local secret_name="$1"
    
    log_info "Validating secret: $secret_name"
    
    # Get the secret
    local secret_json
    if ! secret_json=$(aws secretsmanager get-secret-value \
        --secret-id "$secret_name" \
        --region "$AWS_REGION" \
        --query 'SecretString' \
        --output text 2>/dev/null); then
        log_error "Failed to retrieve secret '$secret_name'"
        echo "Possible reasons:"
        echo "  - Secret doesn't exist"
        echo "  - No permission to access secret"
        echo "  - Wrong region (current: $AWS_REGION)"
        return 1
    fi
    
    # Parse JSON
    if ! echo "$secret_json" | jq . > /dev/null 2>&1; then
        log_error "Secret contains invalid JSON"
        return 1
    fi
    
    log_success "Secret retrieved and parsed successfully"
    
    # Check required fields
    local required_fields=("provider" "host" "port" "username" "password" "protocol")
    local missing_fields=()
    
    for field in "${required_fields[@]}"; do
        if ! echo "$secret_json" | jq -e ".$field" > /dev/null 2>&1; then
            missing_fields+=("$field")
        elif [ "$(echo "$secret_json" | jq -r ".$field // empty")" = "" ]; then
            missing_fields+=("$field (empty)")
        fi
    done
    
    if [ ${#missing_fields[@]} -eq 0 ]; then
        log_success "Secret schema is valid!"
        
        # Show current fields (with sensitive data masked)
        echo ""
        log_info "Current secret contains:"
        for field in "${required_fields[@]}"; do
            local value
            value=$(echo "$secret_json" | jq -r ".$field")
            
            # Mask sensitive fields
            if [[ "$field" == "password" || "$field" == "username" ]]; then
                if [ ${#value} -gt 4 ]; then
                    local masked="${value:0:2}***${value: -2}"
                else
                    local masked="***"
                fi
                echo "  ✅ $field: $masked"
            else
                echo "  ✅ $field: $value"
            fi
        done
        
        return 0
    else
        log_error "Secret schema is invalid!"
        echo ""
        log_warning "Missing required fields: ${missing_fields[*]}"
        echo ""
        echo "This will cause 'proxy_secret_missing_provider' errors in production."
        echo ""
        log_info "To fix this issue:"
        echo "  1. Update the secret manually in AWS Console, or"
        echo "  2. Use the Python validation script: python validate_proxy_secret.py validate $secret_name --fix"
        
        return 1
    fi
}

# Create example secret file
create_example() {
    local output_file="${1:-proxy-secret-example.json}"
    
    log_info "Creating example secret file: $output_file"
    
    cat > "$output_file" << 'EOF'
{
  "provider": "oxylabs",
  "host": "pr.oxylabs.io",
  "port": 60000,
  "username": "your-username",
  "password": "your-password",
  "protocol": "http",
  "geo_enabled": false,
  "country": null,
  "version": 1
}
EOF
    
    log_success "Example secret created: $output_file"
    echo ""
    log_info "Required fields:"
    echo "  • provider: Proxy provider name (e.g., 'oxylabs')"
    echo "  • host: Proxy hostname without protocol"
    echo "  • port: Proxy port number"
    echo "  • username: Proxy username"
    echo "  • password: Proxy password (RAW, not URL-encoded)"
    echo "  • protocol: Usually 'http'"
    echo ""
    log_info "Optional fields:"
    echo "  • geo_enabled: Enable geo-targeting (boolean)"
    echo "  • country: Country code for geo-targeting"
    echo "  • version: Schema version number"
    echo ""
    log_info "To create this secret in AWS:"
    echo "  aws secretsmanager create-secret \\"
    echo "    --name 'my-proxy-secret' \\"
    echo "    --description 'Proxy configuration for TL;DW' \\"
    echo "    --secret-string file://$output_file \\"
    echo "    --region $AWS_REGION"
}

# Update secret with provider field
quick_fix_provider() {
    local secret_name="$1"
    local provider="${2:-oxylabs}"
    
    log_info "Quick fix: Adding provider field to secret '$secret_name'"
    
    # Get current secret
    local current_secret
    if ! current_secret=$(aws secretsmanager get-secret-value \
        --secret-id "$secret_name" \
        --region "$AWS_REGION" \
        --query 'SecretString' \
        --output text 2>/dev/null); then
        log_error "Failed to retrieve secret '$secret_name'"
        return 1
    fi
    
    # Add provider field
    local updated_secret
    updated_secret=$(echo "$current_secret" | jq --arg provider "$provider" '. + {provider: $provider}')
    
    # Update the secret
    if aws secretsmanager update-secret \
        --secret-id "$secret_name" \
        --secret-string "$updated_secret" \
        --region "$AWS_REGION" > /dev/null; then
        log_success "Provider field added successfully!"
        log_info "Secret '$secret_name' now includes: provider = '$provider'"
        return 0
    else
        log_error "Failed to update secret"
        return 1
    fi
}

# Show usage
show_usage() {
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  list                     List potential proxy secrets"
    echo "  validate <secret-name>   Validate a proxy secret schema"
    echo "  example [filename]       Create example secret file"
    echo "  quick-fix <secret-name> [provider]  Add missing provider field"
    echo ""
    echo "Environment Variables:"
    echo "  AWS_REGION              AWS region (default: us-west-2)"
    echo "  PROXY_SECRET_NAME       Default secret name to validate"
    echo ""
    echo "Examples:"
    echo "  $0 list"
    echo "  $0 validate oxylabs-proxy-secret"
    echo "  $0 example my-proxy-config.json"
    echo "  $0 quick-fix oxylabs-proxy-secret oxylabs"
}

# Main execution
main() {
    local command="$1"
    
    case "$command" in
        "list")
            check_aws_cli
            check_jq
            list_proxy_secrets
            ;;
        "validate")
            if [ -z "$2" ]; then
                log_error "Secret name is required"
                echo "Usage: $0 validate <secret-name>"
                exit 1
            fi
            check_aws_cli
            check_jq
            validate_secret "$2"
            ;;
        "example")
            create_example "$2"
            ;;
        "quick-fix")
            if [ -z "$2" ]; then
                log_error "Secret name is required"
                echo "Usage: $0 quick-fix <secret-name> [provider]"
                exit 1
            fi
            check_aws_cli
            check_jq
            quick_fix_provider "$2" "$3"
            ;;
        "help"|"--help"|"-h"|"")
            show_usage
            ;;
        *)
            log_error "Unknown command: $command"
            show_usage
            exit 1
            ;;
    esac
}

echo "🔧 AWS Secrets Manager Proxy Secret Schema Fixer"
echo "================================================"
echo ""

main "$@"