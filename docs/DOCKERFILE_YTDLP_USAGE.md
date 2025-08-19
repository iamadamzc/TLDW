# Dockerfile yt-dlp Version Management

## Overview

The Dockerfile now supports flexible yt-dlp version management with build-time logging and validation.

## Build Arguments

### YTDLP_VERSION
- **Default**: `2025.8.11` (pinned for stability)
- **Options**: 
  - `latest` - Install the latest available version
  - `X.Y.Z` - Install a specific pinned version (e.g., `2024.8.6`)

## Usage Examples

### Default Build (Pinned Version)
```bash
docker build -t my-app .
# Uses YTDLP_VERSION=2025.8.11 by default
```

### Latest Version Build
```bash
docker build --build-arg YTDLP_VERSION=latest -t my-app .
# Installs the latest yt-dlp version
```

### Custom Pinned Version
```bash
docker build --build-arg YTDLP_VERSION=2024.8.6 -t my-app .
# Installs specific version 2024.8.6
```

### CI/CD Usage
```bash
# For production: use pinned version
docker build --build-arg YTDLP_VERSION=2025.8.11 -t my-app:prod .

# For testing: use latest
docker build --build-arg YTDLP_VERSION=latest -t my-app:test .
```

## Build-time Validation

The Dockerfile includes:
1. **Version Logging**: Displays installed yt-dlp version during build
2. **FFmpeg Verification**: Checks FFmpeg availability and warns if missing
3. **Conditional Installation**: Uses appropriate pip command based on version argument

## Health Check Integration

The installed yt-dlp version is logged during build and can be exposed via health endpoints for monitoring and debugging.