#!/usr/bin/env python3
"""
Test Host Cookie Sanitation Implementation
==========================================

Tests for Requirement 12: Host Cookie Sanitation
- Implement __Host- cookie normalization with secure=True
- Set path="/" for all __Host- cookies  
- Remove domain field and use url field for __Host- cookies
- Prevent Playwright __Host- cookie validation errors
"""

import unittest
import sys
import os
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from cookie_generator import sanitize_host_cookie
from transcript_service import EnhancedPlaywrightManager


class TestHostCookieSanitation(unittest.TestCase):
    """Test host cookie sanitation functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.playwright_manager = EnhancedPlaywrightManager()
    
    def test_host_cookie_secure_normalization(self):
        """Test Requirement 12.1: __Host- cookies normalized with secure=True."""
        # Test cookie without secure flag
        cookie = {
            "name": "__Host-session",
            "value": "abc123",
            "domain": "example.com",
            "path": "/login",
            "secure": False
        }
        
        # Test cookie_generator function
        sanitized = sanitize_host_cookie(cookie.copy())
        self.assertTrue(sanitized["secure"], "Cookie generator should set secure=True for __Host- cookies")
        
        # Test EnhancedPlaywrightManager method
        sanitized_ts = self.playwright_manager._sanitize_host_cookie(cookie.copy())
        self.assertTrue(sanitized_ts["secure"], "EnhancedPlaywrightManager should set secure=True for __Host- cookies")
    
    def test_host_cookie_path_normalization(self):
        """Test Requirement 12.2: __Host- cookies normalized with path='/'."""
        # Test cookie with different path
        cookie = {
            "name": "__Host-auth",
            "value": "token123",
            "domain": "youtube.com",
            "path": "/api/auth",
            "secure": True
        }
        
        # Test cookie_generator function
        sanitized = sanitize_host_cookie(cookie.copy())
        self.assertEqual(sanitized["path"], "/", "Cookie generator should set path='/' for __Host- cookies")
        
        # Test EnhancedPlaywrightManager method
        sanitized_ts = self.playwright_manager._sanitize_host_cookie(cookie.copy())
        self.assertEqual(sanitized_ts["path"], "/", "EnhancedPlaywrightManager should set path='/' for __Host- cookies")
    
    def test_host_cookie_domain_removal(self):
        """Test Requirement 12.3: __Host- cookies have no domain field (use url field instead)."""
        # Test cookie with domain field
        cookie = {
            "name": "__Host-csrf",
            "value": "csrf_token",
            "domain": "youtube.com",
            "path": "/",
            "secure": True
        }
        
        # Test cookie_generator function
        sanitized = sanitize_host_cookie(cookie.copy())
        self.assertNotIn("domain", sanitized, "Cookie generator should remove domain field for __Host- cookies")
        self.assertIn("url", sanitized, "Cookie generator should add url field for __Host- cookies")
        self.assertEqual(sanitized["url"], "https://youtube.com/", "Cookie generator should set correct url")
        
        # Test EnhancedPlaywrightManager method
        sanitized_ts = self.playwright_manager._sanitize_host_cookie(cookie.copy())
        self.assertNotIn("domain", sanitized_ts, "EnhancedPlaywrightManager should remove domain field for __Host- cookies")
        self.assertIn("url", sanitized_ts, "EnhancedPlaywrightManager should add url field for __Host- cookies")
        self.assertEqual(sanitized_ts["url"], "https://youtube.com/", "EnhancedPlaywrightManager should set correct url")
    
    def test_host_cookie_domain_dot_handling(self):
        """Test that leading dots in domains are handled correctly."""
        # Test cookie with leading dot in domain (common in cookie files)
        cookie = {
            "name": "__Host-session",
            "value": "session123",
            "domain": ".youtube.com",
            "path": "/api",
            "secure": False
        }
        
        # Test cookie_generator function
        sanitized = sanitize_host_cookie(cookie.copy())
        self.assertEqual(sanitized["url"], "https://youtube.com/", "Cookie generator should remove leading dot from domain")
        
        # Test EnhancedPlaywrightManager method
        sanitized_ts = self.playwright_manager._sanitize_host_cookie(cookie.copy())
        self.assertEqual(sanitized_ts["url"], "https://youtube.com/", "EnhancedPlaywrightManager should remove leading dot from domain")
    
    def test_host_cookie_complete_sanitization(self):
        """Test complete sanitization of __Host- cookie meets all requirements."""
        # Test cookie that needs all sanitization
        cookie = {
            "name": "__Host-user-pref",
            "value": "preferences_data",
            "domain": ".example.com",
            "path": "/user/settings",
            "secure": False,
            "httpOnly": True
        }
        
        # Test cookie_generator function
        sanitized = sanitize_host_cookie(cookie.copy())
        
        # Verify all requirements
        self.assertTrue(sanitized["secure"], "Should set secure=True")
        self.assertEqual(sanitized["path"], "/", "Should set path='/'")
        self.assertNotIn("domain", sanitized, "Should remove domain field")
        self.assertEqual(sanitized["url"], "https://example.com/", "Should set correct url field")
        self.assertEqual(sanitized["name"], "__Host-user-pref", "Should preserve cookie name")
        self.assertEqual(sanitized["value"], "preferences_data", "Should preserve cookie value")
        self.assertTrue(sanitized.get("httpOnly", False), "Should preserve other cookie attributes")
        
        # Test EnhancedPlaywrightManager method
        sanitized_ts = self.playwright_manager._sanitize_host_cookie(cookie.copy())
        
        # Verify all requirements
        self.assertTrue(sanitized_ts["secure"], "Should set secure=True")
        self.assertEqual(sanitized_ts["path"], "/", "Should set path='/'")
        self.assertNotIn("domain", sanitized_ts, "Should remove domain field")
        self.assertEqual(sanitized_ts["url"], "https://example.com/", "Should set correct url field")
        self.assertEqual(sanitized_ts["name"], "__Host-user-pref", "Should preserve cookie name")
        self.assertEqual(sanitized_ts["value"], "preferences_data", "Should preserve cookie value")
    
    def test_host_cookie_without_domain(self):
        """Test __Host- cookie that doesn't have domain field."""
        # Test cookie without domain field
        cookie = {
            "name": "__Host-token",
            "value": "auth_token",
            "path": "/admin",
            "secure": False
        }
        
        # Test cookie_generator function
        sanitized = sanitize_host_cookie(cookie.copy())
        self.assertTrue(sanitized["secure"], "Should set secure=True")
        self.assertEqual(sanitized["path"], "/", "Should set path='/'")
        self.assertNotIn("domain", sanitized, "Should not have domain field")
        self.assertNotIn("url", sanitized, "Should not add url field if no domain was present")
        
        # Test EnhancedPlaywrightManager method
        sanitized_ts = self.playwright_manager._sanitize_host_cookie(cookie.copy())
        self.assertTrue(sanitized_ts["secure"], "Should set secure=True")
        self.assertEqual(sanitized_ts["path"], "/", "Should set path='/'")
        self.assertNotIn("domain", sanitized_ts, "Should not have domain field")
        self.assertNotIn("url", sanitized_ts, "Should not add url field if no domain was present")
    
    def test_playwright_compatibility_format(self):
        """Test that sanitized cookies match expected Playwright format."""
        # Test typical YouTube __Host- cookie
        cookie = {
            "name": "__Host-GAPS",
            "value": "1:abc123def456",
            "domain": ".youtube.com",
            "path": "/accounts",
            "secure": False,
            "httpOnly": True,
            "sameSite": "None"
        }
        
        sanitized = sanitize_host_cookie(cookie.copy())
        
        # Verify Playwright-compatible format
        expected_keys = {"name", "value", "url", "path", "secure", "httpOnly", "sameSite"}
        actual_keys = set(sanitized.keys())
        
        # Should have all expected keys except domain
        self.assertNotIn("domain", actual_keys, "Should not have domain field")
        self.assertIn("url", actual_keys, "Should have url field")
        self.assertIn("secure", actual_keys, "Should have secure field")
        self.assertIn("path", actual_keys, "Should have path field")
        
        # Verify values meet __Host- requirements
        self.assertTrue(sanitized["secure"], "Must be secure")
        self.assertEqual(sanitized["path"], "/", "Must have path='/'")
        self.assertEqual(sanitized["url"], "https://youtube.com/", "Must have correct url")


def run_tests():
    """Run all host cookie sanitation tests."""
    print("🧪 Running Host Cookie Sanitation Tests...")
    print("=" * 60)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestHostCookieSanitation)
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print("✅ All Host Cookie Sanitation tests passed!")
        print(f"📊 Ran {result.testsRun} tests successfully")
        return True
    else:
        print("❌ Some Host Cookie Sanitation tests failed!")
        print(f"📊 Ran {result.testsRun} tests, {len(result.failures)} failures, {len(result.errors)} errors")
        
        if result.failures:
            print("\n🔍 Failures:")
            for test, traceback in result.failures:
                print(f"  - {test}: {traceback}")
        
        if result.errors:
            print("\n🔍 Errors:")
            for test, traceback in result.errors:
                print(f"  - {test}: {traceback}")
        
        return False


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)