import unittest
from unittest.mock import Mock, patch, MagicMock
import os
import requests
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials

# Mock the app and db imports to avoid Flask app context issues
with patch.dict('sys.modules', {'app': Mock(), 'app.db': Mock()}):
    from token_manager import TokenManager

class TestTokenManager(unittest.TestCase):
    """Test cases for TokenManager class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_user = Mock()
        self.mock_user.id = 123
        self.mock_user.access_token = "test_access_token"
        self.mock_user.refresh_token = "test_refresh_token"
        
        # Mock environment variables
        self.env_patcher = patch.dict(os.environ, {
            'GOOGLE_CLIENT_ID': 'test_client_id',
            'GOOGLE_CLIENT_SECRET': 'test_client_secret'
        })
        self.env_patcher.start()
        
        # Mock database session
        self.db_patcher = patch('token_manager.db')
        self.mock_db = self.db_patcher.start()
        
        self.token_manager = TokenManager(self.mock_user)
    
    def tearDown(self):
        """Clean up test fixtures"""
        self.env_patcher.stop()
        self.db_patcher.stop()
    
    def test_init_with_valid_credentials(self):
        """Test TokenManager initialization with valid credentials"""
        self.assertEqual(self.token_manager.user, self.mock_user)
        self.assertEqual(self.token_manager.client_id, 'test_client_id')
        self.assertEqual(self.token_manager.client_secret, 'test_client_secret')
    
    def test_init_without_credentials_raises_error(self):
        """Test TokenManager initialization without credentials raises ValueError"""
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError) as context:
                TokenManager(self.mock_user)
            self.assertIn("Google OAuth client credentials not configured", str(context.exception))
    
    @patch('token_manager.requests.post')
    def test_refresh_access_token_success(self, mock_post):
        """Test successful access token refresh"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'new_access_token',
            'refresh_token': 'new_refresh_token'
        }
        mock_post.return_value = mock_response
        
        result = self.token_manager.refresh_access_token()
        
        self.assertTrue(result)
        self.assertEqual(self.mock_user.access_token, 'new_access_token')
        self.assertEqual(self.mock_user.refresh_token, 'new_refresh_token')
        self.mock_db.session.commit.assert_called_once()
    
    @patch('token_manager.requests.post')
    def test_refresh_access_token_no_refresh_token(self, mock_post):
        """Test refresh attempt with no refresh token"""
        self.mock_user.refresh_token = None
        
        result = self.token_manager.refresh_access_token()
        
        self.assertFalse(result)
        mock_post.assert_not_called()
    
    @patch('token_manager.requests.post')
    def test_refresh_access_token_failure(self, mock_post):
        """Test failed access token refresh"""
        # Mock failed response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'error': 'invalid_grant',
            'error_description': 'Token has been expired or revoked'
        }
        mock_post.return_value = mock_response
        
        result = self.token_manager.refresh_access_token()
        
        self.assertFalse(result)
        # Should clear tokens on invalid_grant error
        self.assertIsNone(self.mock_user.access_token)
        self.assertIsNone(self.mock_user.refresh_token)
    
    def test_get_valid_credentials_with_valid_token(self):
        """Test getting valid credentials when token is not expired"""
        with patch.object(self.token_manager, 'is_token_expired', return_value=False):
            credentials = self.token_manager.get_valid_credentials()
            
            self.assertIsInstance(credentials, Credentials)
            self.assertEqual(credentials.token, 'test_access_token')
    
    def test_get_valid_credentials_with_expired_token(self):
        """Test getting valid credentials when token is expired"""
        with patch.object(self.token_manager, 'is_token_expired', return_value=True), \
             patch.object(self.token_manager, 'refresh_access_token', return_value=True):
            
            credentials = self.token_manager.get_valid_credentials()
            
            self.assertIsInstance(credentials, Credentials)
    
    def test_get_valid_credentials_no_access_token(self):
        """Test getting credentials when no access token exists"""
        self.mock_user.access_token = None
        
        with self.assertRaises(ValueError) as context:
            self.token_manager.get_valid_credentials()
        
        self.assertIn("No access token available", str(context.exception))
    
    def test_is_token_expired_no_expiry(self):
        """Test token expiry check when no expiry information is available"""
        mock_credentials = Mock()
        mock_credentials.expiry = None
        
        result = self.token_manager.is_token_expired(mock_credentials)
        
        self.assertTrue(result)  # Should assume expired if no expiry info
    
    def test_is_token_expired_within_buffer(self):
        """Test token expiry check when token expires within buffer time"""
        mock_credentials = Mock()
        # Token expires in 3 minutes (within 5-minute buffer)
        mock_credentials.expiry = datetime.utcnow() + timedelta(minutes=3)
        
        result = self.token_manager.is_token_expired(mock_credentials)
        
        self.assertTrue(result)
    
    def test_is_token_expired_outside_buffer(self):
        """Test token expiry check when token expires outside buffer time"""
        mock_credentials = Mock()
        # Token expires in 10 minutes (outside 5-minute buffer)
        mock_credentials.expiry = datetime.utcnow() + timedelta(minutes=10)
        
        result = self.token_manager.is_token_expired(mock_credentials)
        
        self.assertFalse(result)
    
    def test_has_valid_refresh_token_true(self):
        """Test has_valid_refresh_token returns True when refresh token exists"""
        result = self.token_manager.has_valid_refresh_token()
        self.assertTrue(result)
    
    def test_has_valid_refresh_token_false(self):
        """Test has_valid_refresh_token returns False when no refresh token"""
        self.mock_user.refresh_token = None
        result = self.token_manager.has_valid_refresh_token()
        self.assertFalse(result)
    
    def test_get_token_info(self):
        """Test getting token information for debugging"""
        info = self.token_manager.get_token_info()
        
        expected_info = {
            'user_id': 123,
            'has_access_token': True,
            'has_refresh_token': True,
            'access_token_length': len('test_access_token'),
            'refresh_token_length': len('test_refresh_token')
        }
        
        self.assertEqual(info, expected_info)

if __name__ == '__main__':
    unittest.main()