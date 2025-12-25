#!/usr/bin/env python3
"""
Integration Test for Host Cookie Sanitation
===========================================

Tests the complete integration of host cookie sanitation in the cookie conversion process.
"""

import unittest
import tempfile
import os
import json
from pathlib import Path
import sys

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from cookie_generator import convert_netscape_to_storage_state


class TestHostCookieIntegration(unittest.TestCase):
    """Test host cookie sanitation in the complete conversion process."""
    
    def setUp(self):
        """Set up test fixtures with temporary directories."""
        self.temp_dir = tempfile.mkdtemp()
        self.netscape_file = os.path.join(self.temp_dir, "cookies.txt")
        
        # Set COOKIE_DIR to our temp directory
        os.environ["COOKIE_DIR"] = self.temp_dir
        
        # Import after setting environment variable to get correct path
        import cookie_generator
        # Reload the module to pick up new COOKIE_DIR
        import importlib
        importlib.reload(cookie_generator)
        
        # Now get the correct storage state file path
        self.storage_state_file = cookie_generator.SESSION_FILE_PATH
    
    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_host_cookie_conversion_integration(self):
        """Test that __Host- cookies are properly sanitized during Netscape conversion."""
        # Create a Netscape cookies file with __Host- cookies
        netscape_content = """# Netscape HTTP Cookie File
# This is a generated file!  Do not edit.

.youtube.com	TRUE	/	FALSE	1735689600	VISITOR_INFO1_LIVE	abc123
.youtube.com	TRUE	/	TRUE	1735689600	__Host-session	secure_session_token
youtube.com	FALSE	/accounts	TRUE	1735689600	__Host-GAPS	1:gaps_token_here
.youtube.com	TRUE	/api	FALSE	1735689600	__Host-csrf	csrf_protection_token
"""
        
        # Write the Netscape file
        with open(self.netscape_file, 'w') as f:
            f.write(netscape_content)
        
        # Convert using the cookie generator
        success = convert_netscape_to_storage_state(self.netscape_file)
        self.assertTrue(success, "Conversion should succeed")
        
        # Verify the storage state file was created
        self.assertTrue(os.path.exists(self.storage_state_file), "Storage state file should be created")
        
        # Load and verify the storage state
        with open(self.storage_state_file, 'r') as f:
            storage_state = json.load(f)
        
        cookies = storage_state.get("cookies", [])
        self.assertGreater(len(cookies), 0, "Should have cookies")
        
        # Find __Host- cookies and verify they are sanitized
        host_cookies = [c for c in cookies if c.get("name", "").startswith("__Host-")]
        self.assertGreater(len(host_cookies), 0, "Should have __Host- cookies")
        
        for cookie in host_cookies:
            cookie_name = cookie.get("name")
            
            # Requirement 12.1: Must have secure=True
            self.assertTrue(cookie.get("secure"), f"__Host- cookie {cookie_name} must have secure=True")
            
            # Requirement 12.2: Must have path="/"
            self.assertEqual(cookie.get("path"), "/", f"__Host- cookie {cookie_name} must have path='/'")
            
            # Requirement 12.3: Must not have domain field, should have url field
            self.assertNotIn("domain", cookie, f"__Host- cookie {cookie_name} must not have domain field")
            self.assertIn("url", cookie, f"__Host- cookie {cookie_name} must have url field")
            
            # Verify url field format
            url = cookie.get("url")
            self.assertTrue(url.startswith("https://"), f"__Host- cookie {cookie_name} url must use HTTPS")
            self.assertTrue(url.endswith("/"), f"__Host- cookie {cookie_name} url must end with /")
    
    def test_mixed_cookies_conversion(self):
        """Test conversion with mix of regular and __Host- cookies."""
        # Create Netscape file with mixed cookie types
        netscape_content = """# Netscape HTTP Cookie File
# This is a generated file!  Do not edit.

.youtube.com	TRUE	/	FALSE	1735689600	VISITOR_INFO1_LIVE	visitor_token
.youtube.com	TRUE	/	TRUE	1735689600	__Host-session	host_session
youtube.com	FALSE	/	FALSE	1735689600	YSC	regular_cookie
.youtube.com	TRUE	/admin	TRUE	1735689600	__Host-admin	admin_token
"""
        
        # Write the Netscape file
        with open(self.netscape_file, 'w') as f:
            f.write(netscape_content)
        
        # Convert
        success = convert_netscape_to_storage_state(self.netscape_file)
        self.assertTrue(success, "Conversion should succeed")
        
        # Load storage state
        with open(self.storage_state_file, 'r') as f:
            storage_state = json.load(f)
        
        cookies = storage_state.get("cookies", [])
        
        # Separate regular and __Host- cookies
        regular_cookies = [c for c in cookies if not c.get("name", "").startswith("__Host-")]
        host_cookies = [c for c in cookies if c.get("name", "").startswith("__Host-")]
        
        # Verify regular cookies are not affected
        for cookie in regular_cookies:
            # Regular cookies should preserve their original domain/path if not __Host-
            if cookie.get("name") == "VISITOR_INFO1_LIVE":
                # This should have domain field (not __Host-)
                self.assertIn("domain", cookie, "Regular cookies should keep domain field")
        
        # Verify __Host- cookies are sanitized
        for cookie in host_cookies:
            self.assertTrue(cookie.get("secure"), "__Host- cookies must be secure")
            self.assertEqual(cookie.get("path"), "/", "__Host- cookies must have path='/'")
            self.assertNotIn("domain", cookie, "__Host- cookies must not have domain field")
            self.assertIn("url", cookie, "__Host- cookies must have url field")
    
    def test_host_cookie_with_leading_dot_domain(self):
        """Test __Host- cookie with leading dot in domain is handled correctly."""
        # Create Netscape file with leading dot domain
        netscape_content = """# Netscape HTTP Cookie File
# This is a generated file!  Do not edit.

.example.com	TRUE	/custom	TRUE	1735689600	__Host-test	test_value
"""
        
        # Write the Netscape file
        with open(self.netscape_file, 'w') as f:
            f.write(netscape_content)
        
        # Convert
        success = convert_netscape_to_storage_state(self.netscape_file)
        self.assertTrue(success, "Conversion should succeed")
        
        # Load storage state
        with open(self.storage_state_file, 'r') as f:
            storage_state = json.load(f)
        
        cookies = storage_state.get("cookies", [])
        host_cookie = next((c for c in cookies if c.get("name") == "__Host-test"), None)
        
        self.assertIsNotNone(host_cookie, "Should find __Host-test cookie")
        
        # Verify leading dot is removed from url
        self.assertEqual(host_cookie.get("url"), "https://example.com/", "Should remove leading dot from domain")
        self.assertEqual(host_cookie.get("path"), "/", "Should normalize path to /")
        self.assertTrue(host_cookie.get("secure"), "Should set secure=True")


def run_integration_tests():
    """Run all host cookie integration tests."""
    print("🧪 Running Host Cookie Integration Tests...")
    print("=" * 60)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestHostCookieIntegration)
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print("✅ All Host Cookie Integration tests passed!")
        print(f"📊 Ran {result.testsRun} tests successfully")
        return True
    else:
        print("❌ Some Host Cookie Integration tests failed!")
        print(f"📊 Ran {result.testsRun} tests, {len(result.failures)} failures, {len(result.errors)} errors")
        return False


if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)