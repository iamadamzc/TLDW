# Use Playwright’s Python image that includes OS deps
FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

# Set up working dir early
WORKDIR /app

# Install system deps for ffmpeg, fonts, and cleanup (curl for health checks)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg curl \
        fonts-unifont fonts-liberation fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Verify FFmpeg is available during build
RUN ffmpeg -version || echo "FFmpeg not found - downloads may fail"

# Copy application code
COPY . .

# Create non-root user for App Runner and ensure browser access
RUN useradd -m app && \
    chown -R app:app /app && \
    (chown -R app:app /ms-playwright 2>/dev/null || true)
USER app

# Environment variables
ENV PORT=8080 \
    FFMPEG_LOCATION=/usr/bin \
    ALLOW_MISSING_DEPS=true \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

# Health check script
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:${PORT}/healthz || exit 1

# Expose port and start Gunicorn
EXPOSE 8080
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 2 --threads 4 --timeout 120 --graceful-timeout 30 wsgi:app"]
