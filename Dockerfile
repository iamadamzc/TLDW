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

# Optional: Auto-update yt-dlp at build time for latest extractors
# Set YT_DLP_AUTO_UPDATE=true during build to enable
ARG YT_DLP_AUTO_UPDATE=false
RUN if [ "$YT_DLP_AUTO_UPDATE" = "true" ]; then \
        echo "Auto-updating yt-dlp to latest version..." && \
        pip install --no-cache-dir -U yt-dlp; \
    else \
        echo "Using yt-dlp version from requirements.txt"; \
    fi

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
