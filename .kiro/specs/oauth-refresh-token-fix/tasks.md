# Implementation Plan

- [x] 1. Create TokenManager class for centralized token management




  - Create new file `token_manager.py` with TokenManager class
  - Implement `refresh_access_token()` method to handle token refresh using Google OAuth2 API
  - Implement `get_valid_credentials()` method to return valid OAuth2 credentials
  - Implement `is_token_expired()` method to check token expiry status
  - Add proper error handling for refresh token scenarios
  - Include comprehensive logging for debugging token refresh issues
  - _Requirements: 2.1, 2.2, 3.1, 3.2_

- [x] 2. Enhance YouTubeService to use TokenManager


  - Modify YouTubeService constructor to accept user object instead of access_token
  - Integrate TokenManager into YouTubeService for automatic token management
  - Implement `_build_service()` method to create YouTube service with valid credentials
  - Add `_handle_auth_error()` wrapper method for API calls with retry logic
  - Update all YouTube API methods to use the auth error handler
  - Add unit tests for YouTubeService token refresh functionality
  - _Requirements: 2.1, 2.2, 2.4_

- [x] 3. Update routes to pass user objects to services


  - Modify dashboard route to pass current_user to YouTubeService instead of access_token
  - Update select_playlist route to use new YouTubeService constructor
  - Update summarize_videos route to use new YouTubeService constructor
  - Update test_watch_later route to use new YouTubeService constructor
  - Add proper error handling for authentication failures in all routes
  - _Requirements: 2.3, 4.1, 4.2_

- [x] 4. Enhance authentication error handling in routes


  - Implement user-friendly error messages for authentication failures
  - Add logic to preserve user's intended action during re-authentication
  - Implement redirect to login with appropriate error messages
  - Add session management for post-authentication redirects
  - Create helper functions for consistent error handling across routes
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 5. Improve OAuth callback error handling and logging


  - Add detailed logging for token acquisition in google_auth.py callback
  - Implement validation to ensure refresh tokens are properly received
  - Add error handling for cases where refresh token is not provided
  - Improve error messages when OAuth flow fails
  - Add logging for debugging OAuth token issues
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 6. Create comprehensive tests for token refresh functionality


  - Write unit tests for TokenManager class methods
  - Create tests for successful token refresh scenarios
  - Create tests for expired/invalid refresh token handling
  - Write integration tests for YouTubeService with token refresh
  - Create tests for authentication error handling in routes
  - Add mock tests for Google OAuth API interactions
  - _Requirements: 2.1, 2.2, 3.1, 3.2_

- [ ] 7. Add monitoring and logging improvements



  - Enhance logging throughout the authentication flow
  - Add structured logging for token refresh events
  - Implement logging for authentication error patterns
  - Add debug logging for OAuth flow troubleshooting
  - Create log messages that help identify token-related issues
  - _Requirements: 3.1, 3.2, 3.3, 3.4_