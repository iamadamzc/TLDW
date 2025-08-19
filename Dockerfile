FROM python:3.11-slim

# Set up working dir early
WORKDIR /app

# Install system deps for ffmpeg and cleanup (curl for health checks)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Enhanced yt-dlp version management with pinned default
ARG YTDLP_VERSION=2025.8.11
ARG CACHE_BUSTER

# Install yt-dlp with flexible version control
RUN if [ "$YTDLP_VERSION" = "latest" ]; then \
        echo "Cache Buster: $CACHE_BUSTER" && \
        echo "Installing latest yt-dlp version..." && \
        pip install --no-cache-dir -U yt-dlp; \
    else \
        echo "Installing pinned yt-dlp version: $YTDLP_VERSION" && \
        pip install --no-cache-dir yt-dlp=="$YTDLP_VERSION"; \
    fi

# Log installed yt-dlp version for debugging and health checks
RUN python -c "import yt_dlp; print('yt-dlp version:', yt_dlp.version.__version__)"

# Verify FFmpeg is available during build
RUN ffmpeg -version || echo "FFmpeg not found - downloads may fail"

# Copy application code
COPY . .

# Create non-root user for App Runner
RUN useradd -m app && chown -R app:app /app
USER app

# Environment variables
ENV PORT=8080 \
    FFMPEG_LOCATION=/usr/bin \
    ALLOW_MISSING_DEPS=false \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Health check script
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:${PORT}/healthz || exit 1

# Expose port and start Gunicorn
EXPOSE 8080
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 2 --threads 4 --timeout 120 wsgi:app"]
