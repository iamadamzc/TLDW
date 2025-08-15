FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including ffmpeg for yt-dlp audio processing
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Verify ffmpeg and ffprobe are installed and accessible
RUN ffmpeg -version && ffprobe -version

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose port 8000 for App Runner
EXPOSE 8000

# Start the Flask application with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "app:app"]