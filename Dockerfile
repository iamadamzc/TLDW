FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including ffmpeg for yt-dlp audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Verify critical dependencies are available and fail fast if missing
RUN python3 -c "
import shutil, subprocess, sys
print('=== Container Dependency Verification ===')
deps = {'ffmpeg': shutil.which('ffmpeg'), 'ffprobe': shutil.which('ffprobe')}
for name, path in deps.items():
    if path:
        try:
            result = subprocess.run([name, '-version'], capture_output=True, timeout=10)
            print(f'✅ {name}: {path}')
        except Exception as e:
            print(f'❌ {name}: execution failed - {e}')
            sys.exit(1)
    else:
        print(f'❌ {name}: not found in PATH')
        sys.exit(1)
print('✅ All dependencies verified')
"

# Test yt-dlp import
RUN python3 -c "import yt_dlp; print(f'✅ yt-dlp: {yt_dlp.version.__version__}')"

# Set environment variables
ENV PORT=8080

# Expose port 8080 for App Runner
EXPOSE 8080

# Start the Flask application with gunicorn using wsgi:app
CMD ["gunicorn", "-b", "0.0.0.0:8080", "wsgi:app", "--workers", "2", "--threads", "4", "--timeout", "120", "-k", "gthread"]