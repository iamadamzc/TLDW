# TL;DW - YouTube Video Summarizer

A Flask application that provides AI-powered summaries of YouTube videos using transcript extraction and ASR fallback.

## Quick Start

### Deployment
```bash
# Main deployment script (builds and pushes Docker image)
./deploy.sh
```

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
python app.py
```

### Testing
```bash
# Run all tests
python tests/run_all_tests.py
```

## Project Structure

- `app.py` - Main Flask application
- `deploy.sh` - **Main deployment script** (builds Docker image and pushes to ECR)
- `Dockerfile` - Container configuration
- `requirements.txt` - Python dependencies

### Core Services
- `transcript_service.py` - Main transcript fetching logic with ASR fallback
- `yt_download_helper.py` - YouTube audio download with yt-dlp
- `proxy_manager.py` - Proxy session management
- `user_agent_manager.py` - User-Agent rotation for bot detection avoidance

### Directories
- `deployment/` - Deployment scripts and configuration
- `tests/` - Test suites
- `templates/` - HTML templates
- `static/` - CSS/JS assets
- `docs/` - Documentation

## Features

- YouTube transcript extraction with language support
- Robust proxy authentication with fail-fast validation
- Session rotation to prevent recurring 407 errors
- Health monitoring endpoints for deployment validation

## Proxy Configuration

### RAW Secret Format (Required)

Store proxy credentials in AWS Secrets Manager using **RAW format** (not URL-encoded):

```json
{
  "provider": "oxylabs",
  "host": "pr.oxylabs.io",
  "port": 7777,
  "username": "customer-<your-account>",
  "password": "<RAW-PASSWORD-NOT-ENCODED>",
  "geo_enabled": false,
  "country": "us",
  "version": 1
}
```

### Environment Variables

```bash
# Required
OXYLABS_PROXY_CONFIG=<JSON-secret-from-secrets-manager>

# Optional (with defaults)
OXY_PREFLIGHT_TTL_SECONDS=300
OXY_PREFLIGHT_MAX_PER_MINUTE=10
OXY_DISABLE_GEO=true
OXY_PREFLIGHT_DISABLED=false
```

### Deployment Validation

Before deploying, validate your proxy configuration:

```bash
# Validate secret format and proxy connectivity
python validate_deployment.py
```

### Common Issues

❌ **Password is URL-encoded** (contains `%` characters)
- Store RAW password in secrets, not URL-encoded

❌ **Host contains scheme** (`http://` or `https://`)
- Use hostname only: `pr.oxylabs.io`

❌ **Missing required fields**
- Ensure all required fields are present in secret JSON

✅ **Correct format**: RAW credentials, hostname only, all fields present
- ASR fallback using Deepgram when transcripts unavailable
- Proxy rotation and sticky sessions for bot detection avoidance
- Per-user cookie support for enhanced YouTube access
- Comprehensive caching system
- User authentication and management

## Environment Variables

See `.env.example` for required configuration.

## Documentation

- `deployment/cookie-deployment-guide.md` - Cookie feature deployment
- `docs/` - Additional documentation