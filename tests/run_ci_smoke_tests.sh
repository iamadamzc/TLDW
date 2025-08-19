#!/bin/bash

# CI Smoke Test Runner
# This script runs the comprehensive smoke test suite for CI/CD pipelines

set -e  # Exit on any error to fail CI build

echo "🚀 Starting CI Smoke Test Suite"
echo "================================"
echo ""

# Set test environment
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
export CI_MODE=true
export DISABLE_COOKIES=false  # Enable cookie testing

# Create test fixtures directory if it doesn't exist
mkdir -p tests/fixtures

# Run the comprehensive smoke test suite
echo "📋 Running comprehensive smoke tests..."
python tests/ci_smoke_test_suite.py

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ All CI smoke tests passed!"
    echo "🎉 Build is ready for deployment"
    exit 0
else
    echo ""
    echo "❌ CI smoke tests failed!"
    echo "🚨 Build failed - do not deploy"
    exit 1
fi