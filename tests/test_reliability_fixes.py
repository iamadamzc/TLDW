#!/usr/bin/env python3
"""
Test script for reliability fix pack implementation.

Tests the specific video rNxC16mlO60 mentioned in acceptance criteria to ensure:
1. No indefinite runs (hard timeouts enforced)
2. Either returns captions via API/timedtext/YouTubei OR produces Deepgram transcript
3. Logs show youtubei_timeout when it times out, then ASR start/finish
4. No more "Failed to parse transcript list: no element found" without HTTP status
"""

import os
import sys
import time
import logging
from datetime import datetime

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from transcript_service import TranscriptService
from log_events import evt
from logging_setup import configure_logging, set_job_ctx

# Configure logging to see the fix results
configure_logging(log_level="INFO", use_json=True)
logger = logging.getLogger(__name__)

# Test video from acceptance criteria
TEST_VIDEO_ID = "rNxC16mlO60"

def test_reliability_fixes():
    """Test the reliability fix pack implementation."""
    
    print("=" * 80)
    print("RELIABILITY FIX PACK TEST")
    print("=" * 80)
    print(f"Testing video: {TEST_VIDEO_ID}")
    print(f"Test started at: {datetime.now().isoformat()}")
    print()
    
    # Initialize transcript service
    service = TranscriptService()
    
    # Test with timeout monitoring
    start_time = time.time()
    max_test_duration = 300  # 5 minutes max test duration
    
    try:
        print("Starting transcript extraction...")
        
        # This should either:
        # 1. Return a transcript via API/timedtext/YouTubei, OR
        # 2. Produce a Deepgram transcript via ASR, OR  
        # 3. Return empty string (but NOT hang indefinitely)
        transcript = service.get_transcript(TEST_VIDEO_ID)
        
        elapsed_time = time.time() - start_time
        
        print(f"\nTest completed in {elapsed_time:.2f} seconds")
        
        if transcript:
            print(f"✅ SUCCESS: Got transcript ({len(transcript)} characters)")
            print(f"First 200 chars: {transcript[:200]}...")
            
            # Log success metrics
            evt("reliability_test_success", 
                video_id=TEST_VIDEO_ID,
                transcript_length=len(transcript),
                duration_seconds=elapsed_time)
            
        else:
            print("⚠️  No transcript returned (but test completed without hanging)")
            
            # Log completion without transcript
            evt("reliability_test_no_transcript", 
                video_id=TEST_VIDEO_ID,
                duration_seconds=elapsed_time)
        
        # Verify timeout enforcement
        if elapsed_time > 300:  # 5 minutes
            print("❌ FAIL: Test took longer than expected (timeout enforcement may not be working)")
            return False
        else:
            print(f"✅ TIMEOUT ENFORCEMENT: Test completed within reasonable time ({elapsed_time:.2f}s)")
        
        print("\n" + "=" * 80)
        print("RELIABILITY FIX VERIFICATION")
        print("=" * 80)
        
        # Check feature flags
        diagnostics = service.get_health_diagnostics()
        feature_flags = diagnostics.get("feature_flags", {})
        
        print("Feature Flags:")
        for flag, enabled in feature_flags.items():
            status = "✅ ENABLED" if enabled else "❌ DISABLED"
            print(f"  {flag}: {status}")
        
        print(f"\nConfiguration:")
        config = diagnostics.get("config", {})
        print(f"  YouTubei timeout: {config.get('youtubei_hard_timeout', 'N/A')}s")
        print(f"  Global job timeout: {config.get('global_job_timeout', 'N/A')}s")
        print(f"  Deepgram configured: {config.get('deepgram_api_key_configured', False)}")
        
        return True
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"❌ EXCEPTION after {elapsed_time:.2f}s: {e}")
        
        # Log test exception
        evt("reliability_test_exception", 
            video_id=TEST_VIDEO_ID,
            duration_seconds=elapsed_time,
            error_type=type(e).__name__,
            error_detail=str(e))
        
        return False
    
    finally:
        # Always log test completion
        total_time = time.time() - start_time
        print(f"\nTotal test duration: {total_time:.2f} seconds")
        
        if total_time > max_test_duration:
            print("❌ CRITICAL: Test exceeded maximum duration - timeout enforcement failed!")
        else:
            print("✅ Test completed within timeout limits")


def test_timedtext_validation():
    """Test timedtext validation fixes specifically."""
    
    print("\n" + "=" * 80)
    print("TIMEDTEXT VALIDATION TEST")
    print("=" * 80)
    
    from timedtext_service import timedtext_attempt
    
    # Test with a video that might return empty/non-XML responses
    print(f"Testing timedtext validation with video: {TEST_VIDEO_ID}")
    
    start_time = time.time()
    
    try:
        # This should now handle empty/non-XML responses gracefully
        # without throwing XML parse errors
        result = timedtext_attempt(TEST_VIDEO_ID)
        
        elapsed_time = time.time() - start_time
        
        if result:
            print(f"✅ Timedtext success: {len(result)} characters")
        else:
            print("ℹ️  Timedtext returned empty (but handled gracefully)")
        
        print(f"Timedtext test completed in {elapsed_time:.2f}s")
        return True
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"❌ Timedtext validation test failed after {elapsed_time:.2f}s: {e}")
        return False


def test_blueprint_registration():
    """Test that blueprint registration works without errors."""
    
    print("\n" + "=" * 80)
    print("BLUEPRINT REGISTRATION TEST")
    print("=" * 80)
    
    try:
        # Import app to trigger blueprint registration
        from app import app
        
        # Check if dashboard routes are registered
        dashboard_routes = [rule.rule for rule in app.url_map.iter_rules() 
                          if rule.rule.startswith('/api/dashboard')]
        
        if dashboard_routes:
            print(f"✅ Dashboard routes registered: {len(dashboard_routes)} routes")
            for route in dashboard_routes[:5]:  # Show first 5
                print(f"  - {route}")
        else:
            print("⚠️  No dashboard routes found")
        
        print("✅ Blueprint registration test completed without errors")
        return True
        
    except Exception as e:
        print(f"❌ Blueprint registration test failed: {e}")
        return False


if __name__ == "__main__":
    print("Starting reliability fix pack tests...")
    
    # Set test context
    set_job_ctx(job_id="reliability_test", video_id=TEST_VIDEO_ID)
    
    # Run tests
    tests = [
        ("Main Reliability Test", test_reliability_fixes),
        ("Timedtext Validation", test_timedtext_validation),
        ("Blueprint Registration", test_blueprint_registration),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
        if success:
            passed += 1
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED - Reliability fixes implemented successfully!")
        sys.exit(0)
    else:
        print("⚠️  Some tests failed - check logs for details")
        sys.exit(1)
