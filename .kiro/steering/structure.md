# Project Structure

## Root Files
- `app.py` - Main Flask application with database initialization
- `main.py` - Application entry point
- `wsgi.py` - WSGI entry point for production
- `requirements.txt` - Python dependencies
- `Dockerfile` - Container configuration
- `Makefile` - Build and deployment commands
- `deploy-apprunner.sh` - AWS deployment script

## Core Services
- `routes.py` - Main application routes, async job management, and JobManager
- `google_auth.py` - Google OAuth authentication with YouTube Data API
- `cookies_routes.py` - Cookie management endpoints (Netscape format)
- `youtube_service.py` - YouTube Data API integration for playlists/videos
- `transcript_service.py` - Multi-layered transcript pipeline (youtube-transcript-api → timedtext → youtubei → ASR)
- `summarizer.py` - OpenAI GPT summarization with custom prompts
- `email_service.py` - Resend email delivery for clean digests
- `models.py` - SQLAlchemy database models and user session management

## Infrastructure & Utilities
- `proxy_manager.py` - Oxylabs proxy session management
- `user_agent_manager.py` - User-Agent rotation for bot detection
- `security_manager.py` - Credential protection and secure logging
- `error_handler.py` - Structured error handling and logging
- `config_validator.py` - Configuration validation
- `monitoring.py` - Application monitoring and metrics

## Directories

### `/templates/`
- HTML Jinja2 templates for web interface

### `/static/`
- `style.css` - Application styling
- `script.js` - Frontend JavaScript

### `/tests/`
- Comprehensive test suite with unit, integration, and smoke tests
- `run_all_tests.py` - Test runner
- `fixtures/` - Test data and mocks
- `legacy/` - Legacy tests with import issues

### `/deployment/`
- Deployment scripts and configuration files
- IAM policies and AWS configuration
- Environment variable migration scripts

### `/docs/`
- Technical documentation and guides
- API documentation and deployment guides

### `/instance/`
- SQLite database files (local development)

### `/transcript_cache/`
- Cached transcript files and database

## Coding Conventions

### File Naming
- Snake_case for Python files
- Descriptive service names (e.g., `transcript_service.py`)
- Test files prefixed with `test_`

### Architecture Patterns
- **Service-oriented design** with clear separation of concerns
- **Blueprint-based route organization** for modular Flask apps
- **Asynchronous job processing** with ThreadPoolExecutor and JobManager
- **Hierarchical fallback systems** for transcript extraction resilience
- **Structured logging** with credential redaction and pipeline breadcrumbs
- **Error isolation** - per-video failures don't stop entire jobs
- **Graceful degradation** with user-friendly error messages

### Pipeline Design
- **Multi-source transcript extraction**: youtube-transcript-api → timedtext → youtubei → ASR
- **Network resilience**: Direct connection → proxy rotation → cookie enhancement
- **XHR interception**: Playwright captures YouTubei API calls without DOM scraping
- **Audio processing**: HLS/DASH stream extraction via ffmpeg for ASR fallback

### Security Practices
- Credential protection in logs and errors
- Secure cookie management with encryption
- Environment variable validation
- Health check endpoints without sensitive data exposure