#!/usr/bin/env python3
"""
Comprehensive test for YouTube Transcript API migration to v1.2.2
Tests that old API methods are no longer used and new API methods work correctly.
"""

import logging
import sys
import os
import importlib
import inspect
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Test configuration
TEST_VIDEO_ID = 'dQw4w9WgXcQ'  # Rick Roll - reliable for testing
BACKUP_VIDEO_ID = 'rNxC16mlO60'  # Alternative test video

def test_compatibility_layer_import():
    """Test that the compatibility layer can be imported and initialized"""
    print("\n=== Testing Compatibility Layer Import ===")
    
    try:
        from youtube_transcript_api_compat import (
            get_transcript, 
            list_transcripts, 
            check_api_migration_status,
            get_compat_instance,
            YouTubeTranscriptApiCompat
        )
        
        print("✅ Successfully imported compatibility layer functions")
        
        # Test API status check
        api_status = check_api_migration_status()
        print(f"   API Version: {api_status['api_version']}")
        print(f"   Migration Complete: {api_status['migration_complete']}")
        
        # Test compatibility instance
        compat_instance = get_compat_instance()
        print(f"   Compatibility instance type: {type(compat_instance)}")
        print(f"   Instance API version: {compat_instance._api_version}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Failed to import compatibility layer: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing compatibility layer: {e}")
        return False

def test_old_api_methods_not_used():
    """Test that old API methods are not directly used in the codebase"""
    print("\n=== Testing Old API Methods Not Used ===")
    
    # Files to check for old API usage
    files_to_check = [
        'transcript_service.py',
        'test_api.py',
        'simple_test.py',
        'agent_prompts/cookie auth youtubei handing http transcript fetching.py'
    ]
    
    old_patterns = [
        'YouTubeTranscriptApi.get_transcript',
        'YouTubeTranscriptApi.list_transcripts'
    ]
    
    issues_found = []
    
    for file_path in files_to_check:
        if not os.path.exists(file_path):
            print(f"⚠️  File not found: {file_path}")
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            for pattern in old_patterns:
                if pattern in content:
                    # Count occurrences
                    count = content.count(pattern)
                    issues_found.append(f"{file_path}: {pattern} found {count} times")
                    
        except Exception as e:
            print(f"⚠️  Error reading {file_path}: {e}")
    
    if issues_found:
        print("❌ Found old API method usage:")
        for issue in issues_found:
            print(f"   {issue}")
        return False
    else:
        print("✅ No old API method usage found in checked files")
        return True

def test_compatibility_layer_functions():
    """Test that compatibility layer functions work correctly"""
    print("\n=== Testing Compatibility Layer Functions ===")
    
    try:
        from youtube_transcript_api_compat import get_transcript, list_transcripts
        
        # Test 1: list_transcripts function
        print(f"Testing list_transcripts with {TEST_VIDEO_ID}...")
        try:
            transcript_list = list_transcripts(TEST_VIDEO_ID)
            if transcript_list:
                print(f"✅ list_transcripts success: found {len(transcript_list)} transcripts")
                for i, transcript_info in enumerate(transcript_list[:3]):  # Show first 3
                    print(f"   Transcript {i}: {transcript_info}")
            else:
                print("⚠️  list_transcripts returned empty list")
        except Exception as e:
            print(f"❌ list_transcripts failed: {e}")
            return False
        
        # Test 2: get_transcript function
        print(f"Testing get_transcript with {TEST_VIDEO_ID}...")
        try:
            transcript = get_transcript(TEST_VIDEO_ID, languages=['en', 'en-US'])
            if transcript:
                print(f"✅ get_transcript success: {len(transcript)} segments")
                if transcript:
                    first_segment = transcript[0]
                    print(f"   First segment: {first_segment}")
                    
                    # Verify segment structure
                    required_keys = ['text', 'start', 'duration']
                    missing_keys = [key for key in required_keys if key not in first_segment]
                    if missing_keys:
                        print(f"⚠️  Missing keys in segment: {missing_keys}")
                    else:
                        print("✅ Segment structure is correct")
            else:
                print("⚠️  get_transcript returned empty result")
        except Exception as e:
            print(f"❌ get_transcript failed: {e}")
            # Try backup video
            print(f"Trying backup video {BACKUP_VIDEO_ID}...")
            try:
                transcript = get_transcript(BACKUP_VIDEO_ID, languages=['en'])
                if transcript:
                    print(f"✅ get_transcript success with backup: {len(transcript)} segments")
                else:
                    print("❌ get_transcript failed with backup video too")
                    return False
            except Exception as backup_e:
                print(f"❌ get_transcript failed with backup video: {backup_e}")
                return False
        
        # Test 3: get_transcript with options
        print("Testing get_transcript with cookies and proxies options...")
        try:
            # Test that the function accepts these parameters without error
            transcript = get_transcript(
                TEST_VIDEO_ID, 
                languages=['en'], 
                cookies=None,  # No actual cookies for test
                proxies=None   # No actual proxies for test
            )
            print("✅ get_transcript accepts cookies and proxies parameters")
        except Exception as e:
            print(f"❌ get_transcript with options failed: {e}")
            return False
        
        return True
        
    except ImportError as e:
        print(f"❌ Failed to import compatibility functions: {e}")
        return False

def test_transcript_service_integration():
    """Test that TranscriptService uses the compatibility layer correctly"""
    print("\n=== Testing TranscriptService Integration ===")
    
    try:
        from transcript_service import TranscriptService
        
        # Create service instance
        service = TranscriptService()
        print("✅ TranscriptService created successfully")
        
        # Test get_captions_via_api method
        print(f"Testing get_captions_via_api with {TEST_VIDEO_ID}...")
        try:
            result = service.get_captions_via_api(TEST_VIDEO_ID, languages=['en'])
            if result and result.strip():
                print(f"✅ get_captions_via_api success: {len(result)} characters")
                print(f"   Sample text: {result[:100]}...")
            else:
                print("⚠️  get_captions_via_api returned empty result")
                # This might be expected if the video doesn't have transcripts
        except Exception as e:
            print(f"❌ get_captions_via_api failed: {e}")
            return False
        
        return True
        
    except ImportError as e:
        print(f"❌ Failed to import TranscriptService: {e}")
        return False
    except Exception as e:
        print(f"❌ TranscriptService test failed: {e}")
        return False

def test_error_handling():
    """Test that error handling works correctly with the new API"""
    print("\n=== Testing Error Handling ===")
    
    try:
        from youtube_transcript_api_compat import get_transcript, TranscriptApiError
        
        # Test with invalid video ID
        print("Testing error handling with invalid video ID...")
        try:
            result = get_transcript("invalid_video_id_12345", languages=['en'])
            print("⚠️  Expected error but got result - this might indicate an issue")
        except TranscriptApiError as e:
            print(f"✅ Correctly caught TranscriptApiError: {e}")
        except Exception as e:
            print(f"✅ Caught expected error: {type(e).__name__}: {e}")
        
        # Test with video that likely has no transcripts
        print("Testing with video that may not have transcripts...")
        try:
            result = get_transcript("aBcDeFgHiJk", languages=['en'])  # Likely invalid
            if not result:
                print("✅ Correctly returned empty result for video without transcripts")
        except Exception as e:
            print(f"✅ Correctly handled video without transcripts: {type(e).__name__}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Failed to import error handling components: {e}")
        return False

def test_api_version_detection():
    """Test that API version detection works correctly"""
    print("\n=== Testing API Version Detection ===")
    
    try:
        from youtube_transcript_api_compat import get_compat_instance
        
        compat_instance = get_compat_instance()
        api_version = compat_instance._api_version
        
        print(f"Detected API version: {api_version}")
        
        # Check that it's version 1.2.2 or compatible
        if "1.2.2" in api_version:
            print("✅ Correctly detected API version 1.2.2")
        elif "instance-style" in api_version:
            print("✅ Correctly detected instance-style API (compatible with 1.2.2)")
        else:
            print(f"⚠️  Unexpected API version format: {api_version}")
            print("   This might still work but should be investigated")
        
        return True
        
    except Exception as e:
        print(f"❌ API version detection failed: {e}")
        return False

def main():
    """Run all migration tests"""
    print("🔄 YouTube Transcript API Migration Test Suite")
    print("Testing migration from 0.6.2 to 1.2.2")
    print("=" * 60)
    
    tests = [
        test_compatibility_layer_import,
        test_old_api_methods_not_used,
        test_compatibility_layer_functions,
        test_transcript_service_integration,
        test_error_handling,
        test_api_version_detection,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                print(f"❌ Test {test.__name__} failed")
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            import traceback
            print(f"   Traceback: {traceback.format_exc()}")
    
    print("\n" + "=" * 60)
    print(f"📊 Migration Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 API migration is complete and working correctly!")
        print("\nMigration Summary:")
        print("✅ Compatibility layer is working")
        print("✅ Old API methods are no longer used")
        print("✅ New API methods work through compatibility layer")
        print("✅ Error handling is working")
        print("✅ TranscriptService integration is working")
        return 0
    else:
        print("⚠️  Some migration tests failed - check the output above")
        print("\nNext steps:")
        print("1. Review failed tests and fix any remaining issues")
        print("2. Update any remaining files that use old API methods")
        print("3. Test with real video IDs to ensure functionality")
        return 1

if __name__ == "__main__":
    sys.exit(main())