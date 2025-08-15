#!/usr/bin/env python3
"""
Test script to verify all dependencies are working correctly
Run this to test the container setup before deployment
"""

import sys
import subprocess
import shutil
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def test_ffmpeg():
    """Test ffmpeg installation and functionality"""
    logging.info("Testing ffmpeg...")
    
    ffmpeg_path = shutil.which('ffmpeg')
    if not ffmpeg_path:
        logging.error("❌ ffmpeg not found in PATH")
        return False
    
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            logging.info(f"✅ ffmpeg available: {version_line}")
            return True
        else:
            logging.error(f"❌ ffmpeg execution failed: {result.stderr}")
            return False
    except Exception as e:
        logging.error(f"❌ ffmpeg test failed: {e}")
        return False

def test_ffprobe():
    """Test ffprobe installation and functionality"""
    logging.info("Testing ffprobe...")
    
    ffprobe_path = shutil.which('ffprobe')
    if not ffprobe_path:
        logging.error("❌ ffprobe not found in PATH")
        return False
    
    try:
        result = subprocess.run(['ffprobe', '-version'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            logging.info(f"✅ ffprobe available: {version_line}")
            return True
        else:
            logging.error(f"❌ ffprobe execution failed: {result.stderr}")
            return False
    except Exception as e:
        logging.error(f"❌ ffprobe test failed: {e}")
        return False

def test_yt_dlp():
    """Test yt-dlp installation"""
    logging.info("Testing yt-dlp...")
    
    try:
        import yt_dlp
        logging.info(f"✅ yt-dlp available: {yt_dlp.version.__version__}")
        return True
    except ImportError as e:
        logging.error(f"❌ yt-dlp import failed: {e}")
        return False

def test_flask_app():
    """Test Flask app can be imported"""
    logging.info("Testing Flask app import...")
    
    try:
        from app import app
        logging.info("✅ Flask app imported successfully")
        return True
    except Exception as e:
        logging.error(f"❌ Flask app import failed: {e}")
        return False

def main():
    """Run all dependency tests"""
    logging.info("=== TL;DW Dependency Test Suite ===")
    
    tests = [
        ("ffmpeg", test_ffmpeg),
        ("ffprobe", test_ffprobe),
        ("yt-dlp", test_yt_dlp),
        ("Flask app", test_flask_app)
    ]
    
    results = {}
    for test_name, test_func in tests:
        results[test_name] = test_func()
    
    logging.info("=== Test Results ===")
    passed = 0
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logging.info(f"{test_name}: {status}")
        if result:
            passed += 1
    
    logging.info(f"=== Summary: {passed}/{len(tests)} tests passed ===")
    
    if passed == len(tests):
        logging.info("🎉 All tests passed! Container is ready for deployment.")
        return 0
    else:
        logging.error("💥 Some tests failed! Fix issues before deployment.")
        return 1

if __name__ == "__main__":
    sys.exit(main())