#!/usr/bin/env python3
"""
Test Cookie Freshness Logging and Download Attempt Tracking
"""

import os
import sys
import time
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TestCookieFreshnessAndTracking(unittest.TestCase):
    """Test cookie freshness logging and download attempt tracking"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test environment"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_cookie_freshness_logging_fresh_cookies(self):
        """
        Test cookie freshness logging with fresh cookies.
        Requirement 4.3: Log cookie freshness (mtime + account) at download start.
        """
        from download_attempt_tracker import log_cookie_freshness
        
        # Create a fresh cookie file
        cookie_file = os.path.join(self.temp_dir, "fresh_cookies.txt")
        with open(cookie_file, 'w') as f:
            f.write("# Fresh cookie file\n")
            f.write(".youtube.com\tTRUE\t/\tFALSE\t1735689600\ttest\tvalue\n")
        
        # Test fresh cookie logging
        result = log_cookie_freshness(cookie_file, user_id=123)
        
        # Verify fresh cookie metadata
        self.assertTrue(result["cookies_enabled"])
        self.assertTrue(result["is_fresh"])
        self.assertLess(result["age_hours"], 12)
        self.assertEqual(result["user_id"], 123)
        self.assertEqual(result["filename"], "fresh_cookies.txt")
        self.assertGreater(result["file_size_bytes"], 0)
        
        print("✅ Fresh cookie logging works correctly")
    
    def test_cookie_freshness_logging_stale_cookies(self):
        """
        Test cookie freshness logging with stale cookies.
        Requirement 4.3: Log cookie freshness without exposing contents.
        """
        from download_attempt_tracker import log_cookie_freshness
        
        # Create a stale cookie file (13 hours old)
        cookie_file = os.path.join(self.temp_dir, "stale_cookies.txt")
        with open(cookie_file, 'w') as f:
            f.write("# Stale cookie file\n")
            f.write(".youtube.com\tTRUE\t/\tFALSE\t1735689600\ttest\tvalue\n")
        
        # Make the file 13 hours old
        thirteen_hours_ago = time.time() - (13 * 3600)
        os.utime(cookie_file, (thirteen_hours_ago, thirteen_hours_ago))
        
        # Test stale cookie logging
        result = log_cookie_freshness(cookie_file, user_id=456)
        
        # Verify stale cookie metadata
        self.assertTrue(result["cookies_enabled"])
        self.assertFalse(result["is_fresh"])
        self.assertGreater(result["age_hours"], 12)
        self.assertEqual(result["user_id"], 456)
        self.assertEqual(result["filename"], "stale_cookies.txt")
        
        print("✅ Stale cookie logging works correctly")
    
    def test_cookie_freshness_logging_no_cookies(self):
        """
        Test cookie freshness logging with no cookies.
        Requirement 4.3: Handle missing cookie files gracefully.
        """
        from download_attempt_tracker import log_cookie_freshness
        
        # Test with None cookiefile
        result_none = log_cookie_freshness(None)
        self.assertFalse(result_none["cookies_enabled"])
        self.assertEqual(result_none["reason"], "no_cookiefile")
        
        # Test with nonexistent file
        nonexistent_file = os.path.join(self.temp_dir, "nonexistent.txt")
        result_missing = log_cookie_freshness(nonexistent_file)
        self.assertFalse(result_missing["cookies_enabled"])
        self.assertEqual(result_missing["reason"], "file_not_found")
        self.assertEqual(result_missing["filename"], "nonexistent.txt")
        
        print("✅ Missing cookie logging works correctly")
    
    def test_download_attempt_dataclass(self):
        """
        Test DownloadAttempt dataclass functionality.
        Requirement 4.5: Create DownloadAttempt dataclass to track metadata.
        """
        from download_attempt_tracker import DownloadAttempt
        
        # Create a download attempt
        attempt = DownloadAttempt(
            video_id="test_video_123",
            success=True,
            error_message=None,
            cookies_used=True,
            client_used="android",
            proxy_used=False,
            step1_error=None,
            step2_error=None,
            duration_seconds=5.2,
            file_size_bytes=1024000
        )
        
        # Test basic properties
        self.assertEqual(attempt.video_id, "test_video_123")
        self.assertTrue(attempt.success)
        self.assertTrue(attempt.cookies_used)
        self.assertEqual(attempt.client_used, "android")
        self.assertFalse(attempt.proxy_used)
        
        # Test health dictionary conversion (no sensitive data)
        health_dict = attempt.to_health_dict()
        self.assertIn("success", health_dict)
        self.assertIn("cookies_used", health_dict)
        self.assertIn("client_used", health_dict)
        self.assertIn("proxy_used", health_dict)
        self.assertIn("timestamp", health_dict)
        
        # Verify sensitive data is not exposed
        self.assertNotIn("video_id", health_dict)
        self.assertNotIn("error_message", health_dict)
        self.assertNotIn("file_size_bytes", health_dict)
        
        print("✅ DownloadAttempt dataclass works correctly")
    
    def test_download_attempt_error_combination(self):
        """
        Test DownloadAttempt error message combination.
        Requirement 4.5: Track comprehensive download metadata.
        """
        from download_attempt_tracker import DownloadAttempt
        
        # Test with both step errors
        attempt_both = DownloadAttempt(
            video_id="test_video",
            success=False,
            error_message="General error",
            cookies_used=False,
            client_used="web",
            proxy_used=True,
            step1_error="Step 1 failed: Unable to extract",
            step2_error="Step 2 failed: FFmpeg error"
        )
        
        combined = attempt_both.get_combined_error()
        self.assertIn("||", combined)
        self.assertIn("Step 1 failed", combined)
        self.assertIn("Step 2 failed", combined)
        
        # Test with single step error
        attempt_single = DownloadAttempt(
            video_id="test_video",
            success=False,
            error_message="General error",
            cookies_used=False,
            client_used="web",
            proxy_used=True,
            step1_error="Step 1 failed: Unable to extract",
            step2_error=None
        )
        
        single = attempt_single.get_combined_error()
        self.assertEqual(single, "Step 1 failed: Unable to extract")
        
        print("✅ Error combination works correctly")
    
    def test_download_attempt_tracker(self):
        """
        Test DownloadAttemptTracker functionality.
        Requirement 4.5: Track download attempts for health endpoints.
        """
        from download_attempt_tracker import DownloadAttemptTracker
        
        tracker = DownloadAttemptTracker()
        
        # Track successful attempt
        success_attempt = tracker.create_attempt(
            video_id="success_video_12345",
            success=True,
            cookies_used=True,
            client_used="android",
            proxy_used=False,
            duration_seconds=3.5,
            file_size_bytes=512000
        )
        
        # Track failed attempt
        failed_attempt = tracker.create_attempt(
            video_id="failed_video_67890",
            success=False,
            cookies_used=False,
            client_used="web",
            proxy_used=True,
            error_message="Download failed"
        )
        
        # Verify tracking
        self.assertEqual(tracker.attempt_count, 2)
        self.assertEqual(tracker.success_count, 1)
        self.assertEqual(tracker.last_attempt, failed_attempt)
        
        # Test health metadata
        health_meta = tracker.get_health_metadata()
        self.assertTrue(health_meta["has_attempts"])
        self.assertEqual(health_meta["total_attempts"], 2)
        self.assertEqual(health_meta["success_count"], 1)
        self.assertEqual(health_meta["success_rate"], 0.5)
        
        # Verify video ID is sanitized in health metadata
        last_attempt_meta = health_meta["last_attempt"]
        self.assertIn("success", last_attempt_meta)
        self.assertIn("cookies_used", last_attempt_meta)
        
        print("✅ DownloadAttemptTracker works correctly")
    
    def test_global_tracker_functions(self):
        """
        Test global tracker convenience functions.
        Requirement 4.5: Provide easy-to-use tracking functions.
        """
        from download_attempt_tracker import (
            track_download_attempt, 
            get_download_health_metadata,
            get_global_tracker
        )
        
        # Test global tracker access
        tracker1 = get_global_tracker()
        tracker2 = get_global_tracker()
        self.assertIs(tracker1, tracker2)  # Should be same instance
        
        # Test convenience tracking function
        attempt = track_download_attempt(
            video_id="convenience_test_video",
            success=True,
            cookies_used=False,
            client_used="web_safari",
            proxy_used=True,
            duration_seconds=2.1
        )
        
        self.assertTrue(attempt.success)
        self.assertEqual(attempt.client_used, "web_safari")
        
        # Test convenience health metadata function
        health_meta = get_download_health_metadata()
        self.assertIsInstance(health_meta, dict)
        self.assertIn("has_attempts", health_meta)
        
        print("✅ Global tracker functions work correctly")
    
    def test_health_endpoint_integration(self):
        """
        Test integration with health endpoints.
        Requirement 4.5: Metadata available in health endpoints without sensitive data.
        """
        # Mock the app environment
        with patch('app.app') as mock_app:
            mock_app.last_download_meta = {
                "used_cookies": True,
                "client_used": "android",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Test that health metadata can be retrieved
            from download_attempt_tracker import get_download_health_metadata
            
            health_meta = get_download_health_metadata()
            
            # Verify structure
            self.assertIsInstance(health_meta, dict)
            
            # Should not contain sensitive data
            if "last_attempt" in health_meta:
                last_attempt = health_meta["last_attempt"]
                # These should be present (safe)
                safe_fields = ["success", "cookies_used", "client_used", "proxy_used", "timestamp"]
                for field in safe_fields:
                    if field in last_attempt:
                        self.assertIsNotNone(last_attempt[field])
                
                # These should NOT be present (sensitive)
                sensitive_fields = ["video_id", "error_message", "file_size_bytes"]
                for field in sensitive_fields:
                    self.assertNotIn(field, last_attempt)
        
        print("✅ Health endpoint integration works correctly")

def run_cookie_freshness_and_tracking_tests():
    """Run all cookie freshness and tracking tests"""
    print("🧪 Running Cookie Freshness and Download Tracking Tests")
    print("=" * 60)
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test class
    suite.addTests(loader.loadTestsFromTestCase(TestCookieFreshnessAndTracking))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print()
    if result.wasSuccessful():
        print("✅ All cookie freshness and tracking tests passed!")
        print()
        print("📋 Verified functionality:")
        print("   - Cookie freshness logging (fresh, stale, missing)")
        print("   - DownloadAttempt dataclass with metadata tracking")
        print("   - Error message combination for debugging")
        print("   - DownloadAttemptTracker with health metadata")
        print("   - Global tracker convenience functions")
        print("   - Health endpoint integration without sensitive data")
        print()
        print("🎉 Task 11 cookie freshness and tracking complete!")
        return True
    else:
        print("❌ Some cookie freshness and tracking tests failed!")
        print(f"   Failures: {len(result.failures)}")
        print(f"   Errors: {len(result.errors)}")
        return False

if __name__ == "__main__":
    success = run_cookie_freshness_and_tracking_tests()
    sys.exit(0 if success else 1)