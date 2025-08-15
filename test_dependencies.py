#!/usr/bin/env python3
"""
Test script to verify ffmpeg, ffprobe, and yt-dlp dependencies are available
Run this in the container to verify the build is correct
"""

import subprocess
import sys
import shutil


def test_ffmpeg():
    """Test ffmpeg availability and version"""
    print("Testing ffmpeg...")
    try:
        ffmpeg_path = shutil.which('ffmpeg')
        if not ffmpeg_path:
            print("❌ ffmpeg not found in PATH")
            return False
        
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"✅ ffmpeg: {version_line}")
            print(f"   Path: {ffmpeg_path}")
            return True
        else:
            print(f"❌ ffmpeg version check failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ ffmpeg test failed: {e}")
        return False


def test_ffprobe():
    """Test ffprobe availability and version"""
    print("\nTesting ffprobe...")
    try:
        ffprobe_path = shutil.which('ffprobe')
        if not ffprobe_path:
            print("❌ ffprobe not found in PATH")
            return False
        
        result = subprocess.run(['ffprobe', '-version'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"✅ ffprobe: {version_line}")
            print(f"   Path: {ffprobe_path}")
            return True
        else:
            print(f"❌ ffprobe version check failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ ffprobe test failed: {e}")
        return False


def test_yt_dlp():
    """Test yt-dlp availability and version"""
    print("\nTesting yt-dlp...")
    try:
        import yt_dlp
        version = yt_dlp.version.__version__
        print(f"✅ yt-dlp: {version}")
        
        # Test basic functionality
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            # Just test that we can create the object
            print("   yt-dlp object creation: OK")
        
        return True
    except Exception as e:
        print(f"❌ yt-dlp test failed: {e}")
        return False


def main():
    """Run all dependency tests"""
    print("🔍 Testing TL;DW Dependencies")
    print("=" * 40)
    
    tests = [
        ("ffmpeg", test_ffmpeg),
        ("ffprobe", test_ffprobe),
        ("yt-dlp", test_yt_dlp)
    ]
    
    results = {}
    for name, test_func in tests:
        results[name] = test_func()
    
    print("\n" + "=" * 40)
    print("📊 Test Results:")
    
    all_passed = True
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {name}: {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n🎉 All dependencies available - ASR functionality ready!")
        sys.exit(0)
    else:
        print("\n🚨 Some dependencies missing - ASR functionality will fail!")
        print("🔧 Check container build process and install missing dependencies")
        sys.exit(1)


if __name__ == "__main__":
    main()