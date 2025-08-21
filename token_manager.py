import os
import logging
import requests
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError

# Avoid circular imports: fetch db only when needed
def _db():
    from app import db  # local import to avoid app<->youtube_service loop
    return db

class TokenManager:
    """Centralized token management for OAuth2 credentials"""
    
    def __init__(self, user):
        """
        Initialize TokenManager with user object
        
        Args:
            user: User model instance with access_token and refresh_token
        """
        self.user = user
        self.client_id = os.environ.get("GOOGLE_CLIENT_ID") or os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
        self.client_secret = os.environ.get("GOOGLE_CLIENT_SECRET") or os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
        self.token_uri = "https://oauth2.googleapis.com/token"
        
        if not self.client_id or not self.client_secret:
            raise ValueError("Google OAuth client credentials not configured")
    
    def refresh_access_token(self) -> bool:
        """
        Refresh the user's access token using refresh token
        
        Returns:
            bool: True if refresh successful, False otherwise
        """
        if not self.user.refresh_token:
            logging.error(f"No refresh token available for user {self.user.id}")
            return False
        
        try:
            logging.info(f"Attempting to refresh access token for user {self.user.id}")
            
            # Prepare refresh token request
            refresh_data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'refresh_token': self.user.refresh_token,
                'grant_type': 'refresh_token'
            }
            
            # Make refresh request to Google
            response = requests.post(self.token_uri, data=refresh_data)
            
            if response.status_code == 200:
                token_data = response.json()
                
                # Update user's access token
                self.user.access_token = token_data.get('access_token')
                
                # Update refresh token if provided (Google sometimes issues new ones)
                if token_data.get('refresh_token'):
                    self.user.refresh_token = token_data.get('refresh_token')
                    logging.info(f"Updated refresh token for user {self.user.id}")
                
                # Commit changes to database
                _db().session.commit()
                
                logging.info(f"Successfully refreshed access token for user {self.user.id}")
                return True
            else:
                error_data = response.json() if response.content else {}
                error_description = error_data.get('error_description', 'Unknown error')
                logging.error(f"Token refresh failed for user {self.user.id}: {response.status_code} - {error_description}")
                
                # Handle specific error cases
                if response.status_code == 400 and 'invalid_grant' in error_data.get('error', ''):
                    logging.warning(f"Refresh token expired for user {self.user.id}, clearing tokens")
                    self._clear_user_tokens()
                
                return False
                
        except requests.RequestException as e:
            logging.error(f"Network error during token refresh for user {self.user.id}: {str(e)}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error during token refresh for user {self.user.id}: {str(e)}")
            return False
    
    def get_valid_credentials(self) -> Credentials:
        """
        Get valid OAuth2 credentials, refreshing if necessary
        
        Returns:
            Credentials: Valid OAuth2 credentials object
            
        Raises:
            ValueError: If no valid credentials can be obtained
        """
        if not self.user.access_token:
            raise ValueError("No access token available for user")
        
        # Create credentials object
        credentials = Credentials(
            token=self.user.access_token,
            refresh_token=self.user.refresh_token,
            token_uri=self.token_uri,
            client_id=self.client_id,
            client_secret=self.client_secret
        )
        
        # Check if token is expired or about to expire
        if self.is_token_expired(credentials):
            logging.info(f"Access token expired for user {self.user.id}, attempting refresh")
            
            if not self.refresh_access_token():
                raise ValueError("Failed to refresh expired access token")
            
            # Create new credentials with refreshed token
            credentials = Credentials(
                token=self.user.access_token,
                refresh_token=self.user.refresh_token,
                token_uri=self.token_uri,
                client_id=self.client_id,
                client_secret=self.client_secret
            )
        
        return credentials
    
    def is_token_expired(self, credentials) -> bool:
        """
        Check if access token is expired or about to expire
        
        Args:
            credentials: OAuth2 credentials object
            
        Returns:
            bool: True if token is expired or expires within 5 minutes
        """
        if not credentials.expiry:
            # If no expiry info, assume token might be expired and try to refresh
            logging.debug(f"No expiry information for user {self.user.id} token, assuming expired")
            return True
        
        # Check if token expires within 5 minutes (buffer for safety)
        buffer_time = timedelta(minutes=5)
        return datetime.utcnow() + buffer_time >= credentials.expiry
    
    def _clear_user_tokens(self):
        """Clear user's stored tokens when they become invalid"""
        try:
            self.user.access_token = None
            self.user.refresh_token = None
            _db().session.commit()
            logging.info(f"Cleared invalid tokens for user {self.user.id}")
        except Exception as e:
            logging.error(f"Error clearing tokens for user {self.user.id}: {str(e)}")
    
    def force_refresh(self) -> bool:
        """
        Force refresh of access token regardless of expiry status
        
        Returns:
            bool: True if refresh successful, False otherwise
        """
        logging.info(f"Force refreshing access token for user {self.user.id}")
        return self.refresh_access_token()
    
    def has_valid_refresh_token(self) -> bool:
        """
        Check if user has a valid refresh token
        
        Returns:
            bool: True if refresh token exists, False otherwise
        """
        return bool(self.user.refresh_token)
    
    def get_token_info(self) -> dict:
        """
        Get information about current token status for debugging
        
        Returns:
            dict: Token status information
        """
        return {
            'user_id': self.user.id,
            'has_access_token': bool(self.user.access_token),
            'has_refresh_token': bool(self.user.refresh_token),
            'access_token_length': len(self.user.access_token) if self.user.access_token else 0,
            'refresh_token_length': len(self.user.refresh_token) if self.user.refresh_token else 0
        }
