#!/usr/bin/env python3
"""
Quick installation check for youtube-transcript-api
"""
import sys
import subprocess

def check_installation():
    """Check if youtube-transcript-api is properly installed"""
    print("=== YouTube Transcript API Installation Check ===\n")
    
    # Check Python version
    print(f"Python version: {sys.version}")
    print(f"Python executable: {sys.executable}\n")
    
    # Try to import the library
    try:
        import youtube_transcript_api
        print("✅ youtube-transcript-api is importable")
        print(f"   Version: {getattr(youtube_transcript_api, '__version__', 'unknown')}")
        print(f"   Location: {youtube_transcript_api.__file__}")
    except ImportError as e:
        print(f"❌ youtube-transcript-api import failed: {e}")
        print("\n🔧 To fix this, run:")
        print("   pip install youtube-transcript-api")
        return False
    
    # Check the main class
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        print("✅ YouTubeTranscriptApi class is importable")
        
        # List available methods
        methods = [method for method in dir(YouTubeTranscriptApi) if not method.startswith('_')]
        print(f"   Available methods: {methods}")
        
        # Check for expected methods
        expected_methods = ['get_transcript', 'list_transcripts']
        for method in expected_methods:
            if hasattr(YouTubeTranscriptApi, method):
                print(f"   ✅ {method} method found")
            else:
                print(f"   ❌ {method} method NOT found")
        
    except ImportError as e:
        print(f"❌ YouTubeTranscriptApi import failed: {e}")
        return False
    
    # Check pip list for the package
    try:
        result = subprocess.run([sys.executable, '-m', 'pip', 'list'], 
                              capture_output=True, text=True)
        if 'youtube-transcript-api' in result.stdout:
            for line in result.stdout.split('\n'):
                if 'youtube-transcript-api' in line:
                    print(f"✅ Package installed: {line.strip()}")
        else:
            print("❌ youtube-transcript-api not found in pip list")
    except Exception as e:
        print(f"⚠️  Could not check pip list: {e}")
    
    print("\n=== Installation Check Complete ===")
    return True

if __name__ == "__main__":
    success = check_installation()
    if not success:
        print("\n🔧 Recommended fix:")
        print("   pip install --upgrade youtube-transcript-api")
        sys.exit(1)
    else:
        print("\n✅ Installation looks good! You can now run test_api.py")