"""
WSGI entrypoint for TL;DW application
"""

import os
import shutil
import subprocess
import logging
import sys

# Configure logging for container startup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Align with gunicorn handlers if present
_guni = logging.getLogger('gunicorn.error')
if _guni.handlers:
    logging.root.handlers = _guni.handlers
    logging.root.setLevel(_guni.level)

ALLOW_MISSING = os.getenv("ALLOW_MISSING_DEPS", "false").lower() == "true"

def _check_binary(name: str):
    """Check if binary is available and return path or None with appropriate logging"""
    path = shutil.which(name)
    if not path:
        msg = f"{name} missing from PATH"
        if ALLOW_MISSING:
            logging.warning("STARTUP: %s (ALLOW_MISSING_DEPS=true, continuing)", msg)
            return None
        logging.error("STARTUP: %s", msg)
        raise RuntimeError(msg)
    
    # Print version to logs with timeout to prevent hangs
    try:
        subprocess.run([name, "-version"], check=True, 
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
    except Exception as e:
        if ALLOW_MISSING:
            logging.warning("STARTUP: %s present but version check failed: %s (continuing)", name, e)
            return path
        logging.error("STARTUP: %s present but version check failed: %s", name, e)
        raise
    
    logging.info("STARTUP: %s at %s", name, path)
    return path

def log_startup_dependencies():
    """Enhanced dependency verification with dev override support"""
    logging.info("TL;DW Startup Dependency Check")
    
    ffmpeg = _check_binary("ffmpeg")
    ffprobe = _check_binary("ffprobe")
    
    # Export explicit ffmpeg location for the app to use
    if ffmpeg:
        os.environ.setdefault("FFMPEG_LOCATION", "/usr/bin")
        logging.info("STARTUP: FFMPEG_LOCATION=%s", os.environ["FFMPEG_LOCATION"])
    else:
        if ALLOW_MISSING:
            logging.warning("STARTUP: FFMPEG_LOCATION not set (ffmpeg missing, ALLOW_MISSING_DEPS=true)")
    
    # Log environment configuration for debugging
    logging.info("STARTUP: ALLOW_MISSING_DEPS=%s", ALLOW_MISSING)
    logging.info("STARTUP: Environment ready for application startup")

# Verify dependencies before importing app
log_startup_dependencies()

# Robust app import with fallback
try:
    from app import app
except ImportError:
    from main import app  # fallback if the app lives in main.py

# Health endpoints already exist in app.py - no need to duplicate

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
