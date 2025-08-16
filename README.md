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