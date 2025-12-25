#!/usr/bin/env python3
"""
Smoke test for transcript extraction methods.
Tests all fallback methods (API → timedtext → YouTubei → ASR) using a known video with transcript.
"""

import os
import sys
import logging
import time
from typing import Dict, Any

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from transcript_service import (
    TranscriptService,
    get_captions_via_timedtext,
    get_transcript_via_youtubei,
    youtube_reachable
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('smoke_test_transcripts.log')
    ]
)

# Test video: Rick Astley - Never Gonna Give You Up (guaranteed to have transcript)
TEST_VIDEO_ID = "dQw4w9WgXcQ"

def test_method(method_name: str, method_func, *args, **kwargs) -> Dict[str, Any]:
    """Test a single transcript extraction method and return results."""
    print(f"\n{'='*60}")
    print(f"Testing {method_name}")
    print(f"{'='*60}")
    
    start_time = time.time()
    result = {
        "method": method_name,
        "success": False,
        "transcript_length": 0,
        "duration_ms": 0,
        "error": None,
        "transcript_preview": ""
    }
    
    try:
        logging.info(f"Starting {method_name} test for video {TEST_VIDEO_ID}")
        transcript = method_func(*args, **kwargs)
        
        duration_ms = int((time.time() - start_time) * 1000)
        result["duration_ms"] = duration_ms
        
        if transcript and transcript.strip():
            result["success"] = True
            result["transcript_length"] = len(transcript)
            # Get first 200 characters as preview
            result["transcript_preview"] = transcript[:200] + "..." if len(transcript) > 200 else transcript
            
            print(f"✅ SUCCESS: {method_name}")
            print(f"   Duration: {duration_ms}ms")
            print(f"   Length: {len(transcript)} characters")
            print(f"   Preview: {result['transcript_preview']}")
            logging.info(f"{method_name} SUCCESS: {len(transcript)} chars in {duration_ms}ms")
        else:
            print(f"❌ FAILED: {method_name} - Empty result")
            logging.warning(f"{method_name} returned empty result in {duration_ms}ms")
            
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        result["duration_ms"] = duration_ms
        result["error"] = str(e)
        
        print(f"❌ ERROR: {method_name} - {e}")
        logging.error(f"{method_name} failed in {duration_ms}ms: {e}")
    
    return result

def main():
    """Run smoke tests for all transcript extraction methods."""
    print(f"🚀 Starting transcript extraction smoke tests")
    print(f"Test video: {TEST_VIDEO_ID} (Rick Astley - Never Gonna Give You Up)")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check YouTube connectivity first
    print(f"\n{'='*60}")
    print("Checking YouTube connectivity")
    print(f"{'='*60}")
    
    if youtube_reachable():
        print("✅ YouTube is reachable")
        logging.info("YouTube connectivity check passed")
    else:
        print("⚠️  YouTube connectivity check failed - tests may fail")
        logging.warning("YouTube connectivity check failed")
    
    # Initialize transcript service
    try:
        service = TranscriptService()
        logging.info("TranscriptService initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize TranscriptService: {e}")
        logging.error(f"TranscriptService initialization failed: {e}")
        return 1
    
    # Test results storage
    results = []
    
    # Test 1: YouTube Transcript API
    result = test_method(
        "YouTube Transcript API",
        service.get_captions_via_api,
        TEST_VIDEO_ID,
        ("en", "en-US", "es")
    )
    results.append(result)
    
    # Test 2: Timedtext
    result = test_method(
        "Timedtext",
        get_captions_via_timedtext,
        TEST_VIDEO_ID,
        service.proxy_manager,
        None  # cookies
    )
    results.append(result)
    
    # Test 3: YouTubei
    result = test_method(
        "YouTubei",
        get_transcript_via_youtubei,
        TEST_VIDEO_ID,
        service.proxy_manager,
        None,  # cookies
        45000  # timeout_ms
    )
    results.append(result)
    
    # Test 4: ASR (only if Deepgram key is available)
    if service.deepgram_api_key:
        result = test_method(
            "ASR (Deepgram)",
            service.asr_from_intercepted_audio,
            TEST_VIDEO_ID,
            service.proxy_manager,
            None  # cookies
        )
        results.append(result)
    else:
        print(f"\n{'='*60}")
        print("Skipping ASR test - DEEPGRAM_API_KEY not configured")
        print(f"{'='*60}")
        logging.info("ASR test skipped - no Deepgram API key")
        results.append({
            "method": "ASR (Deepgram)",
            "success": False,
            "transcript_length": 0,
            "duration_ms": 0,
            "error": "DEEPGRAM_API_KEY not configured",
            "transcript_preview": ""
        })
    
    # Test 5: Full service fallback chain
    result = test_method(
        "Full Service (Fallback Chain)",
        service.get_transcript,
        TEST_VIDEO_ID,
        "en",
        None,  # user_cookies
        None   # playwright_cookies
    )
    results.append(result)
    
    # Print summary
    print(f"\n{'='*60}")
    print("SMOKE TEST SUMMARY")
    print(f"{'='*60}")
    
    successful_methods = [r for r in results if r["success"]]
    failed_methods = [r for r in results if not r["success"]]
    
    print(f"✅ Successful methods: {len(successful_methods)}/{len(results)}")
    for result in successful_methods:
        print(f"   • {result['method']}: {result['transcript_length']} chars in {result['duration_ms']}ms")
    
    if failed_methods:
        print(f"\n❌ Failed methods: {len(failed_methods)}")
        for result in failed_methods:
            error_msg = result['error'] if result['error'] else "Empty result"
            print(f"   • {result['method']}: {error_msg}")
    
    # Overall assessment
    print(f"\n{'='*60}")
    if len(successful_methods) >= 1:
        print("🎉 SMOKE TEST PASSED - At least one method working")
        logging.info(f"Smoke test PASSED: {len(successful_methods)}/{len(results)} methods successful")
        return 0
    else:
        print("💥 SMOKE TEST FAILED - No methods working")
        logging.error("Smoke test FAILED: No methods returned transcripts")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
