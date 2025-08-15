"""
Unit tests for UserAgentManager enhancements
Tests transcript headers and yt-dlp User-Agent consistency
"""

import unittest
from unittest.mock import patch
from user_agent_manager import UserAgentManager


class TestUserAgentManager(unittest.TestCase):
    """Test UserAgentManager enhanced functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.ua_manager = UserAgentManager()
    
    def test_transcript_headers_include_accept_language(self):
        """Test that transcript headers include Accept-Language"""
        headers = self.ua_manager.get_transcript_headers()
        
        self.assertIn('User-Agent', headers)
        self.assertIn('Accept-Language', headers)
        self.assertEqual(headers['Accept-Language'], 'en-US,en;q=0.9')
        
        # Verify User-Agent is valid
        self.assertTrue(self.ua_manager.validate_user_agent(headers['User-Agent']))
    
    def test_user_agent_consistency_transcript_ytdlp(self):
        """Test that transcript and yt-dlp use identical User-Agent strings"""
        transcript_headers = self.ua_manager.get_transcript_headers()
        ytdlp_user_agent = self.ua_manager.get_yt_dlp_user_agent()
        
        # Should be identical User-Agent strings
        self.assertEqual(transcript_headers['User-Agent'], ytdlp_user_agent)
    
    def test_transcript_headers_different_request_types(self):
        """Test transcript headers with different request types"""
        for request_type in ['default', 'fallback', 'firefox', 'edge']:
            with self.subTest(request_type=request_type):
                headers = self.ua_manager.get_transcript_headers(request_type)
                ytdlp_ua = self.ua_manager.get_yt_dlp_user_agent(request_type)
                
                # Should have consistent User-Agent
                self.assertEqual(headers['User-Agent'], ytdlp_ua)
                # Should always have Accept-Language
                self.assertEqual(headers['Accept-Language'], 'en-US,en;q=0.9')
    
    @patch('user_agent_manager.logging')
    def test_error_handling_transcript_headers(self, mock_logging):
        """Test error handling in transcript header generation"""
        # Temporarily break the USER_AGENT_CONFIG
        original_config = self.ua_manager.USER_AGENT_CONFIG
        self.ua_manager.USER_AGENT_CONFIG = None
        
        try:
            headers = self.ua_manager.get_transcript_headers()
            
            # Should still return headers with default User-Agent
            self.assertIn('User-Agent', headers)
            self.assertIn('Accept-Language', headers)
            self.assertEqual(headers['Accept-Language'], 'en-US,en;q=0.9')
            
            # Should have logged an error
            mock_logging.error.assert_called()
            
        finally:
            # Restore original config
            self.ua_manager.USER_AGENT_CONFIG = original_config
    
    def test_user_agent_validation_in_get_user_agent(self):
        """Test that get_user_agent validates User-Agent strings"""
        # This should work normally
        ua = self.ua_manager.get_user_agent('default')
        self.assertTrue(self.ua_manager.validate_user_agent(ua))
        
        # Test with invalid request type
        ua = self.ua_manager.get_user_agent('invalid_type')
        self.assertTrue(self.ua_manager.validate_user_agent(ua))  # Should fall back to default
    
    def test_backward_compatibility(self):
        """Test that existing methods still work as expected"""
        # Test existing get_headers method
        headers = self.ua_manager.get_headers()
        self.assertIn('User-Agent', headers)
        
        # Test existing get_yt_dlp_user_agent method
        ua = self.ua_manager.get_yt_dlp_user_agent()
        self.assertTrue(self.ua_manager.validate_user_agent(ua))
        
        # Test existing rotate_user_agent method
        rotated_ua = self.ua_manager.rotate_user_agent()
        self.assertTrue(self.ua_manager.validate_user_agent(rotated_ua))


if __name__ == '__main__':
    unittest.main()