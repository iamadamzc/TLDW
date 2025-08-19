#!/bin/bash

# Google OAuth Environment Variable Migration Script
# This script provides a one-time migration map for deployment rollout

set -e

echo "🔄 Google OAuth Environment Variable Migration"
echo "=============================================="
echo ""

# Migration mapping for backwards compatibility during rollout
export_google_oauth_vars() {
    echo "🔄 Setting up Google OAuth environment variable migration..."
    
    # Map old variable names to new ones during transition
    if [ -n "${GOOGLE_OAUTH_CLIENT_ID:-}" ] && [ -z "${GOOGLE_CLIENT_ID:-}" ]; then
        export GOOGLE_CLIENT_ID="$GOOGLE_OAUTH_CLIENT_ID"
        echo "   ✅ Mapped GOOGLE_OAUTH_CLIENT_ID → GOOGLE_CLIENT_ID"
    fi
    
    if [ -n "${GOOGLE_OAUTH_CLIENT_SECRET:-}" ] && [ -z "${GOOGLE_CLIENT_SECRET:-}" ]; then
        export GOOGLE_CLIENT_SECRET="$GOOGLE_OAUTH_CLIENT_SECRET"
        echo "   ✅ Mapped GOOGLE_OAUTH_CLIENT_SECRET → GOOGLE_CLIENT_SECRET"
    fi
    
    echo ""
    
    # Verify both sets are available during transition
    echo "🔍 Verifying environment variables..."
    if [ -n "${GOOGLE_CLIENT_ID:-}" ]; then
        echo "   ✅ GOOGLE_CLIENT_ID is set"
    else
        echo "   ❌ GOOGLE_CLIENT_ID is not set"
    fi
    
    if [ -n "${GOOGLE_CLIENT_SECRET:-}" ]; then
        echo "   ✅ GOOGLE_CLIENT_SECRET is set"
    else
        echo "   ❌ GOOGLE_CLIENT_SECRET is not set"
    fi
    
    echo ""
    
    # Show legacy variables status for debugging
    echo "📋 Legacy variable status (for debugging):"
    if [ -n "${GOOGLE_OAUTH_CLIENT_ID:-}" ]; then
        echo "   📝 GOOGLE_OAUTH_CLIENT_ID is set (legacy)"
    else
        echo "   📝 GOOGLE_OAUTH_CLIENT_ID is not set"
    fi
    
    if [ -n "${GOOGLE_OAUTH_CLIENT_SECRET:-}" ]; then
        echo "   📝 GOOGLE_OAUTH_CLIENT_SECRET is set (legacy)"
    else
        echo "   📝 GOOGLE_OAUTH_CLIENT_SECRET is not set"
    fi
    
    echo ""
}

# Call the migration function
export_google_oauth_vars

echo "✅ Environment variable migration complete"
echo ""
echo "💡 Usage:"
echo "   source deployment/migrate-env-vars.sh"
echo ""
echo "🔄 This ensures backwards compatibility during rollout by mapping:"
echo "   GOOGLE_OAUTH_CLIENT_ID → GOOGLE_CLIENT_ID"
echo "   GOOGLE_OAUTH_CLIENT_SECRET → GOOGLE_CLIENT_SECRET"