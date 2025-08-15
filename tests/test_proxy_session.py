"""
Unit tests for ProxySession sticky session functionality
Tests session ID generation, sticky username building, and URL encoding
"""

import unittest
from unittest.mock import patch, MagicMock
from proxy_manager import ProxySession


class TestProxySession(unittest.TestCase):
    """Test ProxySession sticky session functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.base_config = {
            'username': 'tldw__BwTQx',
            'password': 'b6AXONDdSBHA3U_',
            'geo_enabled': True,  # Now enabled by default for MVP reliability
            'country': 'us'
        }
    
    def test_session_id_generation_sanitization(self):
        """Test session ID generation from video_id sanitization"""
        test_cases = [
            ('dQw4w9WgXcQ', 'dQw4w9WgXcQ'),  # Normal video ID
            ('abc-123_def', 'abc123def'),     # With special chars
            ('test@#$%video', 'testvideo'),   # With symbols
            ('a' * 20, 'a' * 16),             # Test 16 char truncation
            ('MiX3d-Ch4r5_T3st!', 'MiX3dCh4r5T3st'),  # Mixed case with truncation
        ]
        
        for video_id, expected_session_id in test_cases:
            with self.subTest(video_id=video_id):
                session = ProxySession(video_id, self.base_config)
                self.assertEqual(session.session_id, expected_session_id)
                # Ensure session ID is alphanumeric only
                self.assertTrue(session.session_id.isalnum())
                # Ensure session ID is capped at 16 chars
                self.assertLessEqual(len(session.session_id), 16)
    
    def test_sticky_username_without_geo(self):
        """Test sticky username builder without geo-enabled (no -cc-<country>)"""
        config = self.base_config.copy()
        config['geo_enabled'] = False
        
        session = ProxySession('testVideo123', config)
        expected_username = f"customer-tldw__BwTQx-sessid-{session.session_id}"
        
        self.assertEqual(session.sticky_username, expected_username)
        # Ensure no -cc- segment is present
        self.assertNotIn('-cc-', session.sticky_username)
    
    def test_sticky_username_with_geo_enabled(self):
        """Test sticky username builder with geo-enabled (includes -cc-<country>)"""
        # base_config now has geo_enabled=True by default
        session = ProxySession('testVideo123', self.base_config)
        expected_username = f"customer-tldw__BwTQx-cc-us-sessid-{session.session_id}"
        
        self.assertEqual(session.sticky_username, expected_username)
        # Ensure -cc-us segment is present
        self.assertIn('-cc-us-', session.sticky_username)
    
    def test_sticky_username_geo_enabled_no_country(self):
        """Test sticky username builder with geo_enabled=True but no country specified"""
        config = self.base_config.copy()
        config['geo_enabled'] = True
        config['country'] = ''  # Empty country
        
        session = ProxySession('testVideo123', config)
        # Should still include -cc- segment with empty country
        expected_username = f"customer-tldw__BwTQx-cc--sessid-{session.session_id}"
        
        self.assertEqual(session.sticky_username, expected_username)
    
    def test_url_encoding_in_proxy_url(self):
        """Test URL encoding of credentials in proxy URL construction"""
        config = self.base_config.copy()
        config['username'] = 'user@test'  # Username with special char
        config['password'] = 'pass word!'  # Password with space and special char
        config['geo_enabled'] = False
        
        session = ProxySession('testVideo', config)
        proxy_url = session.proxy_url
        
        # Should contain URL-encoded credentials
        self.assertIn('user%40test', proxy_url)  # @ encoded as %40
        self.assertIn('pass%20word%21', proxy_url)  # space as %20, ! as %21
        # Should use hardcoded residential entrypoint
        self.assertIn('pr.oxylabs.io:7777', proxy_url)
    
    def test_proxy_url_hardcoded_endpoint(self):
        """Test that proxy URL uses hardcoded residential entrypoint"""
        session = ProxySession('testVideo', self.base_config)
        proxy_url = session.proxy_url
        
        # Should always use pr.oxylabs.io:7777 regardless of config
        self.assertIn('pr.oxylabs.io:7777', proxy_url)
        self.assertTrue(proxy_url.startswith('http://'))
    
    @patch('proxy_manager.logging')
    def test_credential_redaction_in_logging(self, mock_logging):
        """Test that credentials are never logged in debug messages"""
        config = self.base_config.copy()
        config['password'] = 'secret_password'
        
        session = ProxySession('testVideo', config)
        
        # Check that password is never logged
        for call in mock_logging.debug.call_args_list:
            call_str = str(call)
            self.assertNotIn('secret_password', call_str)
            self.assertNotIn(session.proxy_url, call_str)  # Full URL should not be logged
        
        # But sticky username should be logged
        logged_messages = [str(call) for call in mock_logging.debug.call_args_list]
        username_logged = any(session.sticky_username in msg for msg in logged_messages)
        self.assertTrue(username_logged, "Sticky username should be logged for debugging")
    
    def test_session_id_deterministic(self):
        """Test that session ID generation is deterministic for same video_id"""
        video_id = 'testVideo123'
        
        session1 = ProxySession(video_id, self.base_config)
        session2 = ProxySession(video_id, self.base_config)
        
        # Should generate identical session IDs for same video_id
        self.assertEqual(session1.session_id, session2.session_id)
    
    def test_empty_config_handling(self):
        """Test handling of empty or missing proxy configuration"""
        session = ProxySession('testVideo', {})
        
        self.assertEqual(session.proxy_url, "")
        self.assertEqual(session.sticky_username, "")


if __name__ == '__main__':
    unittest.main()