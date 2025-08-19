#!/bin/bash

# Google OAuth Environment Variable Migration Script
# This script provides a one-time migration map for deployment rollout

# Migration mapping for backwards compatibility during rollout
export_google_oauth_vars() {
    echo "🔄 Setting up Google OAuth environment variable migration..."
    
    # Map old variable names to new ones during transition
    if [ -n "$GOOGLE_CLIENT_ID" ] && [ -z "$GOOGLE_CLIENT_ID" ]; then
        export GOOGLE_CLIENT_ID="$GOOGLE_CLIENT_ID"
        echo "   Mapped GOOGLE_CLIENT_ID → GOOGLE_CLIENT_ID"
    fi
    
    if [ -n "$GOOGLE_CLIENT_SECRET" ] && [ -z "$GOOGLE_CLIENT_SECRET" ]; then
        export GOOGLE_CLIENT_SECRET="$GOOGLE_CLIENT_SECRET"
        echo "   Mapped GOOGLE_CLIENT_SECRET → GOOGLE_CLIENT_SECRET"
    fi
    
    # Verify both sets are available during transition
    if [ -n "$GOOGLE_CLIENT_ID" ]; then
        echo "   ✅ GOOGLE_CLIENT_ID is set"
    else
        echo "   ❌ GOOGLE_CLIENT_ID is not set"
    fi
    
    if [ -n "$GOOGLE_CLIENT_SECRET" ]; then
        echo "   ✅ GOOGLE_CLIENT_SECRET is set"
    else
        echo "   ❌ GOOGLE_CLIENT_SECRET is not set"
    fi
}

# Call the migration function
export_google_oauth_vars
