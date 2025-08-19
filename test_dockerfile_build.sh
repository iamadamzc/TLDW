#!/bin/bash
# Test script to validate Dockerfile build arguments

echo "Testing Dockerfile build arguments..."

# Test 1: Default pinned version
echo "Test 1: Building with default pinned version (2025.8.11)"
echo "Command: docker build --build-arg YTDLP_VERSION=2025.8.11 -t test-ytdlp-pinned ."

# Test 2: Latest version
echo "Test 2: Building with latest version"
echo "Command: docker build --build-arg YTDLP_VERSION=latest -t test-ytdlp-latest ."

# Test 3: Custom pinned version
echo "Test 3: Building with custom pinned version"
echo "Command: docker build --build-arg YTDLP_VERSION=2024.8.6 -t test-ytdlp-custom ."

echo "All build commands are ready for testing when Docker is available"
echo "The Dockerfile now supports:"
echo "- ARG YTDLP_VERSION=2025.8.11 (pinned default)"
echo "- Conditional pip install for latest vs pinned versions"
echo "- Build-time version logging"
echo "- FFmpeg availability verification"