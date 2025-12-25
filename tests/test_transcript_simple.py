#!/usr/bin/env python3
"""
Simple test for transcript service configuration and feature flags
"""
import os
import sys
import logging

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all required modules can be imported"""
    try:
        from transcript_service import TranscriptService, ENABLE_YT_API, ENABLE_TIMEDTEXT
        from youtube_transcript_api import YouTubeTranscriptApi
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def test_feature_flags():
    """Test that feature flags are properly configured"""
    from transcript_service import ENABLE_YT_API, ENABLE_TIMEDTEXT, ENABLE_YOUTUBEI, ENABLE_ASR_FALLBACK
    
    print("\n=== Feature Flag Status ===")
    print(f"ENABLE_YT_API: {ENABLE_YT_API}")
    print(f"ENABLE_TIMEDTEXT: {ENABLE_TIMEDTEXT}")
    print(f"ENABLE_YOUTUBEI: {ENABLE_YOUTUBEI}")
    print(f"ENABLE_ASR_FALLBACK: {ENABLE_ASR_FALLBACK}")
    
    # Verify Phase 1 flags are enabled
    if ENABLE_YT_API and ENABLE_TIMEDTEXT:
        print("✅ Phase 1 flags properly configured")
        return True
    else:
        print("❌ Phase 1 flags not properly configured")
        return False

def test_service_initialization():
    """Test that TranscriptService can be initialized"""
    try:
        from transcript_service import TranscriptService
        service = TranscriptService()
        
        # Test health diagnostics
        diagnostics = service.get_health_diagnostics()
        print(f"\n=== Health Diagnostics ===")
        print(f"Feature flags: {diagnostics['feature_flags']}")
        print(f"Config: {diagnostics['config']}")
        
        print("✅ Service initialization successful")
        return True
    except Exception as e:
        print(f"❌ Service initialization failed: {e}")
        return False

def test_hierarchical_methods():
    """Test that all hierarchical methods exist and are callable"""
    try:
        from transcript_service import TranscriptService
        service = TranscriptService()
        
        # Test that methods exist
        methods = [
            'get_transcript',
            'get_captions_via_api',
            '_get_transcript_with_fallback'
        ]
        
        for method_name in methods:
            if hasattr(service, method_name):
                print(f"✅ Method {method_name} exists")
            else:
                print(f"❌ Method {method_name} missing")
                return False
        
        return True
    except Exception as e:
        print(f"❌ Method check failed: {e}")
        return False

if __name__ == "__main__":
    print("=== Transcript Service Foundation Test ===")
    
    import_success = test_imports()
    flags_success = test_feature_flags()
    init_success = test_service_initialization()
    methods_success = test_hierarchical_methods()
    
    if import_success and flags_success and init_success and methods_success:
        print("\n✅ All foundation tests passed!")
        print("Task 1 & 2: Enhanced transcript service foundation with feature flags - COMPLETE")
        sys.exit(0)
    else:
        print("\n❌ Some foundation tests failed!")
        sys.exit(1)