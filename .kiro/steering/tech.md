# Technology Stack

## Core Framework
- **Flask 3.0.3**: Web framework with SQLAlchemy integration
- **Python 3.11+**: Primary language with async support
- **SQLAlchemy 2.0**: ORM with PostgreSQL/SQLite support
- **Flask-Login**: User session management

## Key Dependencies
- **youtube-transcript-api**: Primary transcript extraction
- **Google APIs**: OAuth2 and YouTube Data API integration
- **OpenAI**: GPT-based video summarization with custom prompts
- **Deepgram SDK**: ASR fallback for audio-to-text conversion
- **Playwright**: Browser automation for YouTubei XHR interception
- **ffmpeg**: Audio extraction from HLS/DASH streams
- **Resend**: Clean digest email delivery
- **boto3**: AWS Secrets Manager integration
- **httpx**: HTTP client for API calls
- **requests**: HTTP requests with proxy support

## Infrastructure
- **Docker**: Containerization with multi-stage builds
- **AWS App Runner**: Container deployment platform
- **AWS ECR**: Container registry
- **AWS Secrets Manager**: Secure credential storage
- **Gunicorn**: WSGI server with worker processes

## Build System

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run application
python app.py

# Run tests
python tests/run_all_tests.py
```

### Docker Build
```bash
# Build image
make build

# Test container
make test

# Deploy to AWS
make deploy
```

### Deployment
```bash
# Main deployment script
./deploy-apprunner.sh

# With options
./deploy-apprunner.sh --dry-run --timeout 600
```

## Environment Configuration
- Uses `.env` files for local development
- AWS Secrets Manager for production secrets (proxy config, API keys)
- Cookie management via `COOKIE_DIR=/app/cookies` (Netscape format)
- Environment variable migration support for backwards compatibility
- Health check endpoints for deployment validation

## API Design
- **Asynchronous Processing**: `/api/summarize` returns 202 with job_id
- **Job Status**: `/api/jobs/<job_id>` for progress tracking
- **Health Endpoints**: `/health`, `/healthz`, `/health/live`, `/health/ready`
- **Authentication**: Google OAuth with YouTube Data API scopes

## Pipeline Architecture
1. **Direct Connection**: First attempt without proxy
2. **Proxy Fallback**: Oxylabs residential proxy rotation
3. **Cookie Enhancement**: Optional user cookies for restricted content
4. **Multi-Source Transcripts**: Hierarchical fallback through multiple APIs
5. **ASR Processing**: Audio extraction → Deepgram when transcripts unavailable