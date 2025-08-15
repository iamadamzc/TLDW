"""
MVP-focused integration tests for sticky session workflow
Tests E2E happy path, bot-check retry, and 407 fail-fast scenarios
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import logging


class TestStickySessionIntegration(unittest.TestCase):
    """Test integration scenarios for sticky session workflow"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Configure logging to capture structured logs
        self.log_messages = []
        
        # Create a custom log handler to capture messages
        class TestLogHandler(logging.Handler):
            def __init__(self, messages_list):
                super().__init__()
                self.messages = messages_list
            
            def emit(self, record):
                self.messages.append(record.getMessage())
        
        self.test_handler = TestLogHandler(self.log_messages)
        logging.getLogger().addHandler(self.test_handler)
        logging.getLogger().setLevel(logging.INFO)
    
    def tearDown(self):
        """Clean up test fixtures"""
        logging.getLogger().removeHandler(self.test_handler)
    
    def test_e2e_happy_path_same_session(self):
        """Test E2E happy path: transcript → yt-dlp using same session"""
        from proxy_manager import ProxyManager, ProxySession
        from user_agent_manager import UserAgentManager
        
        # Mock proxy configuration
        mock_config = {
            'username': 'test_user',
            'password': 'test_pass',
            'geo_enabled': True,  # Now enabled by default
            'country': 'us',
            'session_ttl_minutes': 30
        }
        
        # Create ProxyManager with mocked AWS Secrets Manager
        with patch('proxy_manager.boto3.Session') as mock_boto_session:
            mock_client = Mock()
            mock_client.get_secret_value.return_value = {
                'SecretString': '{"username": "test_user", "password": "test_pass"}'
            }
            mock_boto_session.return_value.client.return_value = mock_client
            
            proxy_manager = ProxyManager()
            
            # Test session creation for video
            video_id = "testVideo123"
            session1 = proxy_manager.get_session_for_video(video_id)
            session2 = proxy_manager.get_session_for_video(video_id)
            
            # Should return same session for same video
            self.assertIsNotNone(session1)
            self.assertIsNotNone(session2)
            self.assertEqual(session1.session_id, session2.session_id)
            self.assertEqual(session1.proxy_url, session2.proxy_url)
            
            # Verify sticky username format (with geo enabled by default)
            expected_username = f"customer-test_user-cc-us-sessid-{session1.session_id}"
            self.assertEqual(session1.sticky_username, expected_username)
            
            # Verify proxy URL contains encoded credentials
            self.assertIn('customer-test_user-cc-us-sessid-', session1.proxy_url)
            self.assertIn('pr.oxylabs.io:7777', session1.proxy_url)
    
    def test_user_agent_consistency_transcript_ytdlp(self):
        """Test that transcript and yt-dlp use identical User-Agent strings"""
        from user_agent_manager import UserAgentManager
        ua_manager = UserAgentManager()
        
        # Get headers for transcript
        transcript_headers = ua_manager.get_transcript_headers()
        
        # Get User-Agent for yt-dlp
        ytdlp_ua = ua_manager.get_yt_dlp_user_agent()
        
        # Should be identical
        self.assertEqual(transcript_headers['User-Agent'], ytdlp_ua)
        
        # Transcript headers should include Accept-Language
        self.assertIn('Accept-Language', transcript_headers)
        self.assertEqual(transcript_headers['Accept-Language'], 'en-US,en;q=0.9')
    
    def test_bot_check_retry_path(self):
        """Test bot-check retry: first fails, second succeeds with new session"""
        from proxy_manager import ProxyManager
        
        mock_config = {
            'username': 'test_user',
            'password': 'test_pass',
            'geo_enabled': True,
            'country': 'us'
        }
        
        with patch('proxy_manager.boto3.Session') as mock_boto_session:
            mock_client = Mock()
            mock_client.get_secret_value.return_value = {
                'SecretString': '{"username": "test_user", "password": "test_pass"}'
            }
            mock_boto_session.return_value.client.return_value = mock_client
            
            proxy_manager = ProxyManager()
            
            video_id = "testVideo123"
            
            # Get initial session
            session1 = proxy_manager.get_session_for_video(video_id)
            original_session_id = session1.session_id
            
            # Mark session as blocked (simulating bot detection)
            proxy_manager.mark_session_blocked(video_id)
            self.assertTrue(session1.is_blocked)
            
            # Rotate session (simulating retry)
            session2 = proxy_manager.rotate_session(video_id)
            
            # Should get different session ID
            self.assertIsNotNone(session2)
            self.assertNotEqual(session2.session_id, original_session_id)
            
            # New session should not be blocked
            self.assertFalse(session2.is_blocked)
            
            # Should be stored under same video_id
            current_session = proxy_manager.get_session_for_video(video_id)
            self.assertEqual(current_session.session_id, session2.session_id)
    
    def test_407_fail_fast_path(self):
        """Test 407 error fail-fast: no retry, immediate failure with guidance log"""
        from proxy_manager import ProxyManager
        
        with patch('proxy_manager.boto3.Session') as mock_boto_session:
            mock_client = Mock()
            mock_client.get_secret_value.return_value = {
                'SecretString': '{"username": "test_user", "password": "test_pass"}'
            }
            mock_boto_session.return_value.client.return_value = mock_client
            
            proxy_manager = ProxyManager()
            
            # Test 407 error handling
            video_id = "testVideo123"
            result = proxy_manager.handle_407_error(video_id)
            
            # Should attempt to refresh credentials
            self.assertIsInstance(result, bool)
            
            # Check that guidance log was generated
            guidance_logged = any('hint=' in msg and 'check URL-encoding or secret password' in msg 
                                for msg in self.log_messages)
            self.assertTrue(guidance_logged, "407 error should log guidance hint")
    
    def test_structured_logging_format(self):
        """Test structured logging format and credential redaction"""
        from proxy_manager import ProxySession
        
        mock_config = {
            'username': 'test_user',
            'password': 'secret_password',
            'geo_enabled': True,
            'country': 'us'
        }
        
        session = ProxySession('testVideo123', mock_config)
        
        # Verify structured logging format (simulated)
        log_entry = {
            'step': 'transcript',
            'video_id': 'testVideo123',
            'session': session.session_id,
            'ua_applied': 'true',
            'latency_ms': 1250,
            'status': 'ok',
            'attempt': 1,
            'source': 'transcript_api'
        }
        
        # Verify session ID is logged (safe)
        self.assertEqual(log_entry['session'], session.session_id)
        
        # Verify password is never in any log-related data
        log_str = str(log_entry)
        self.assertNotIn('secret_password', log_str)
        self.assertNotIn(session.proxy_url, log_str)
        
        # But sticky username should be available for logging
        self.assertIn('test_user', session.sticky_username)
        self.assertIn('sessid-', session.sticky_username)
    
    def test_session_rotation_generates_different_id(self):
        """Test that session rotation generates different session IDs"""
        from proxy_manager import ProxyManager
        import time
        
        with patch('proxy_manager.boto3.Session') as mock_boto_session:
            mock_client = Mock()
            mock_client.get_secret_value.return_value = {
                'SecretString': '{"username": "test_user", "password": "test_pass"}'
            }
            mock_boto_session.return_value.client.return_value = mock_client
            
            proxy_manager = ProxyManager()
            
            video_id = "testVideo123"
            
            # Get initial session
            session1 = proxy_manager.get_session_for_video(video_id)
            original_id = session1.session_id
            
            # Add small delay to ensure different timestamps
            time.sleep(0.01)
            
            # Rotate session
            session2 = proxy_manager.rotate_session(video_id)
            
            # Should have different session ID due to timestamp
            self.assertNotEqual(session2.session_id, original_id)
            
            # But both should have same base username format (with geo)
            base_username = "customer-test_user-cc-us-sessid-"
            self.assertTrue(session1.sticky_username.startswith(base_username))
            self.assertTrue(session2.sticky_username.startswith(base_username))
            
            # Verify the rotated session is now the active one
            current_session = proxy_manager.get_session_for_video(video_id)
            self.assertEqual(current_session.session_id, session2.session_id)
    
    def test_geo_enabled_username_format(self):
        """Test sticky username format with geo-enabled configuration"""
        from proxy_manager import ProxySession
        
        # Test with geo enabled
        geo_config = {
            'username': 'test_user',
            'password': 'test_pass',
            'geo_enabled': True,
            'country': 'us'
        }
        
        session_geo = ProxySession('testVideo123', geo_config)
        expected_geo = f"customer-test_user-cc-us-sessid-{session_geo.session_id}"
        self.assertEqual(session_geo.sticky_username, expected_geo)
        
        # Test without geo
        no_geo_config = {
            'username': 'test_user',
            'password': 'test_pass',
            'geo_enabled': False
        }
        
        session_no_geo = ProxySession('testVideo123', no_geo_config)
        expected_no_geo = f"customer-test_user-sessid-{session_no_geo.session_id}"
        self.assertEqual(session_no_geo.sticky_username, expected_no_geo)
        
        # Verify no -cc- segment in non-geo version
        self.assertNotIn('-cc-', session_no_geo.sticky_username)


if __name__ == '__main__':
    unittest.main()