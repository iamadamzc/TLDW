"""
WSGI entrypoint for TL;DW application
"""

import logging
import shutil
import subprocess
import sys

# Configure logging for container startup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def verify_startup_dependencies():
    """Verify critical dependencies on startup and fail fast if missing"""
    logging.info("=== TL;DW Container Startup Verification ===")
    
    # Check critical binaries
    dependencies = {
        'yt-dlp': shutil.which('yt-dlp'),
        'ffmpeg': shutil.which('ffmpeg'),
        'ffprobe': shutil.which('ffprobe')
    }
    
    missing = []
    for name, path in dependencies.items():
        if path:
            try:
                if name in ['ffmpeg', 'ffprobe']:
                    result = subprocess.run([name, '-version'], 
                                          capture_output=True, text=True, timeout=5)
                    version = result.stdout.split('\n')[0] if result.stdout else 'unknown'
                    logging.info(f"✅ {name}: {version} (at {path})")
                else:
                    logging.info(f"✅ {name}: available at {path}")
            except Exception as e:
                logging.error(f"❌ {name}: execution failed - {e}")
                missing.append(name)
        else:
            logging.error(f"❌ {name}: not found in PATH")
            missing.append(name)
    
    # Check yt-dlp import
    try:
        import yt_dlp
        logging.info(f"✅ yt-dlp module: {yt_dlp.version.__version__}")
    except Exception as e:
        logging.error(f"❌ yt-dlp import failed: {e}")
        missing.append('yt-dlp-module')
    
    if missing:
        logging.error(f"🚨 CRITICAL: Missing dependencies {missing}")
        logging.error("Container cannot start - fix dependencies and rebuild")
        sys.exit(1)
    
    logging.info("✅ All critical dependencies verified - starting application")
    logging.info("=== End Startup Verification ===")

# Verify dependencies before importing app
verify_startup_dependencies()

# Import app after dependency verification
from app import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)