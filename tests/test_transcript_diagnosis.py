#!/usr/bin/env python3
"""
Diagnostic script to identify transcript extraction issues
"""
import os
import sys
import logging
import traceback

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_youtube_transcript_api():
    """Test YouTube Transcript API import and functionality"""
    print("=== Testing YouTube Transcript API ===")
    
    try:
        # Test import
        from youtube_transcript_api import YouTubeTranscriptApi
        print("✓ YouTubeTranscriptApi imported successfully")
        
        # Check if get_transcript method exists
        if hasattr(YouTubeTranscriptApi, 'get_transcript'):
            print("✓ get_transcript method exists")
        else:
            print("✗ get_transcript method NOT found")
            print("Available methods:", [m for m in dir(YouTubeTranscriptApi) if not m.startswith('_')])
        
        # Check version
        try:
            import youtube_transcript_api as yta_mod
            version = getattr(yta_mod, '__version__', 'unknown')
            print(f"✓ Version: {version}")
        except Exception as e:
            print(f"✗ Could not get version: {e}")
        
        # Test with a known video
        test_video_id = "BPjmmZlDhNc"  # From the logs
        try:
            transcript = YouTubeTranscriptApi.get_transcript(test_video_id, languages=['en'])
            print(f"✓ Successfully got transcript for {test_video_id}: {len(transcript)} segments")
            return True
        except Exception as e:
            print(f"✗ Failed to get transcript for {test_video_id}: {e}")
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"✗ Import failed: {e}")
        traceback.print_exc()
        return False

def test_feature_flags():
    """Test feature flag configuration"""
    print("\n=== Testing Feature Flags ===")
    
    # Import the flags from transcript_service
    try:
        from transcript_service import (
            ENABLE_YT_API, ENABLE_TIMEDTEXT, ENABLE_YOUTUBEI, 
            ASR_DISABLED, ENABLE_ASR_FALLBACK
        )
        
        print(f"ENABLE_YT_API: {ENABLE_YT_API}")
        print(f"ENABLE_TIMEDTEXT: {ENABLE_TIMEDTEXT}")
        print(f"ENABLE_YOUTUBEI: {ENABLE_YOUTUBEI}")
        print(f"ASR_DISABLED: {ASR_DISABLED}")
        print(f"ENABLE_ASR_FALLBACK: {ENABLE_ASR_FALLBACK}")
        
        # Check environment variables
        print("\nEnvironment variables:")
        for var in ['ENABLE_YT_API', 'ENABLE_TIMEDTEXT', 'ENABLE_YOUTUBEI', 'ASR_DISABLED']:
            value = os.getenv(var, 'not set')
            print(f"  {var}: {value}")
            
    except Exception as e:
        print(f"✗ Failed to import feature flags: {e}")
        traceback.print_exc()

def test_dependencies():
    """Test critical dependencies"""
    print("\n=== Testing Dependencies ===")
    
    dependencies = [
        'playwright',
        'requests',
        'deepgram',
        'youtube_transcript_api'
    ]
    
    for dep in dependencies:
        try:
            __import__(dep)
            print(f"✓ {dep} imported successfully")
        except ImportError as e:
            print(f"✗ {dep} import failed: {e}")

def test_transcript_service():
    """Test TranscriptService initialization and basic functionality"""
    print("\n=== Testing TranscriptService ===")
    
    try:
        from transcript_service import TranscriptService
        
        # Initialize service
        service = TranscriptService()
        print("✓ TranscriptService initialized")
        
        # Test health diagnostics
        diagnostics = service.get_health_diagnostics()
        print("✓ Health diagnostics:")
        for key, value in diagnostics.items():
            print(f"  {key}: {value}")
        
        # Test with the problematic video
        test_video_id = "BPjmmZlDhNc"
        print(f"\nTesting transcript extraction for {test_video_id}...")
        
        transcript = service.get_transcript(test_video_id)
        if transcript:
            print(f"✓ Got transcript: {len(transcript)} characters")
            print(f"Preview: {transcript[:200]}...")
        else:
            print("✗ No transcript returned")
            
    except Exception as e:
        print(f"✗ TranscriptService test failed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    print("TLDW Transcript Diagnosis Tool")
    print("=" * 50)
    
    test_youtube_transcript_api()
    test_feature_flags()
    test_dependencies()
    test_transcript_service()
    
    print("\n" + "=" * 50)
    print("Diagnosis complete!")
