# OAuth Token Refresh Logging Guide

## Overview

This document outlines the comprehensive logging improvements implemented for OAuth token refresh functionality. The logging system provides detailed information for monitoring, debugging, and troubleshooting authentication issues.

## Logging Categories

### 1. Token Manager Logging

**Location**: `token_manager.py`

**Key Log Messages**:
- `Attempting to refresh access token for user {user_id}` - INFO level
- `Successfully refreshed access token for user {user_id}` - INFO level  
- `Token refresh failed for user {user_id}: {status_code} - {error_description}` - ERROR level
- `Refresh token expired for user {user_id}, clearing tokens` - WARNING level
- `Network error during token refresh for user {user_id}: {error}` - ERROR level
- `No refresh token available for user {user_id}` - ERROR level
- `Cleared invalid tokens for user {user_id}` - INFO level

**Monitoring Points**:
- Token refresh success/failure rates
- Network errors during refresh attempts
- Missing refresh token incidents
- Token expiry patterns

### 2. YouTube Service Logging

**Location**: `youtube_service.py`

**Key Log Messages**:
- `Failed to build YouTube service for user {user_id}: {error}` - ERROR level
- `Authentication error (401) for user {user_id}, attempting token refresh` - WARNING level
- `Successfully refreshed token and rebuilt service for user {user_id}` - INFO level
- `Retry failed after token refresh for user {user_id}: {error}` - ERROR level
- `Token refresh failed for user {user_id}` - ERROR level
- `Unexpected error in YouTube API call for user {user_id}: {error}` - ERROR level

**Monitoring Points**:
- 401 authentication errors
- Successful token refresh and retry operations
- Service initialization failures
- API call retry patterns

### 3. OAuth Callback Logging

**Location**: `google_auth.py`

**Key Log Messages**:
- `OAuth error in callback: {error} - {error_description}` - ERROR level
- `No authorization code received in OAuth callback` - ERROR level
- `Processing OAuth callback with authorization code` - INFO level
- `Failed to get Google provider configuration: {error}` - ERROR level
- `Token request failed: {error}` - ERROR level
- `Token acquisition successful - Access token: ✓, Refresh token: {status}` - INFO level
- `No refresh token received - user may need to re-authenticate more frequently` - WARNING level
- `Processing authentication for user: {email} (Google ID: {google_id})` - INFO level
- `Creating new user: {name} ({email})` - INFO level
- `Updating tokens for existing user: {email}` - INFO level
- `Updated refresh token for existing user` - INFO level
- `No new refresh token received, keeping existing one` - INFO level
- `No access token available for user after OAuth flow` - ERROR level
- `No refresh token available for user {email} - may need frequent re-authentication` - WARNING level
- `Successfully authenticated user: {email}` - INFO level
- `Database error during user authentication: {error}` - ERROR level
- `Unexpected error in OAuth callback: {error}` - ERROR level

**Monitoring Points**:
- OAuth callback success/failure rates
- Missing refresh token incidents during login
- User creation vs. existing user login patterns
- Database errors during authentication

### 4. Route Error Handling Logging

**Location**: `routes.py`

**Key Log Messages**:
- `Authentication error loading dashboard for user {email}: {error}` - ERROR level
- `Authentication error selecting playlist for user {email}: {error}` - ERROR level
- `Authentication error testing Watch Later for user {email}: {error}` - ERROR level
- `Authentication error initializing services for user {email}: {error}` - ERROR level

**Monitoring Points**:
- Authentication failures in different application areas
- User experience impact of authentication errors
- Service initialization failures

## Log Analysis Patterns

### Success Patterns

1. **Successful Token Refresh**:
   ```
   INFO: Attempting to refresh access token for user 123
   INFO: Successfully refreshed access token for user 123
   ```

2. **Successful OAuth Login**:
   ```
   INFO: Processing OAuth callback with authorization code
   INFO: Token acquisition successful - Access token: ✓, Refresh token: ✓
   INFO: Processing authentication for user: user@example.com (Google ID: 12345)
   INFO: Successfully authenticated user: user@example.com
   ```

3. **Successful API Call with Token Refresh**:
   ```
   WARNING: Authentication error (401) for user 123, attempting token refresh
   INFO: Successfully refreshed token and rebuilt service for user 123
   ```

### Error Patterns

1. **Missing Refresh Token**:
   ```
   ERROR: No refresh token available for user 123
   WARNING: No refresh token received - user may need to re-authenticate more frequently
   ```

2. **Expired Refresh Token**:
   ```
   ERROR: Token refresh failed for user 123: 400 - Token has been expired or revoked
   WARNING: Refresh token expired for user 123, clearing tokens
   ```

3. **OAuth Callback Failure**:
   ```
   ERROR: OAuth error in callback: access_denied - User denied access
   ERROR: No authorization code received in OAuth callback
   ```

## Monitoring Recommendations

### Key Metrics to Track

1. **Token Refresh Success Rate**
   - Target: >95% success rate
   - Alert threshold: <90% success rate over 1 hour

2. **Missing Refresh Token Rate**
   - Target: <5% of new logins
   - Alert threshold: >10% of new logins over 1 hour

3. **Authentication Error Rate**
   - Target: <1% of API calls
   - Alert threshold: >5% of API calls over 15 minutes

4. **OAuth Callback Success Rate**
   - Target: >98% success rate
   - Alert threshold: <95% success rate over 1 hour

### Log Aggregation Queries

**Token Refresh Failures**:
```
level:ERROR AND message:"Token refresh failed"
```

**Missing Refresh Tokens**:
```
level:WARNING AND message:"No refresh token"
```

**Authentication Errors**:
```
level:ERROR AND message:"Authentication error"
```

**OAuth Callback Issues**:
```
level:ERROR AND message:"OAuth" AND source:"google_auth.py"
```

## Troubleshooting Guide

### Common Issues and Log Patterns

1. **User Needs to Re-authenticate**
   - Look for: `Token refresh failed` + `invalid_grant`
   - Action: User should log out and log back in

2. **OAuth Configuration Issues**
   - Look for: `Failed to get Google provider configuration`
   - Action: Check network connectivity and Google OAuth endpoints

3. **Missing OAuth Scopes**
   - Look for: `No refresh token received` during new user login
   - Action: Verify OAuth request includes `access_type=offline` and `prompt=consent`

4. **Database Issues**
   - Look for: `Database error during user authentication`
   - Action: Check database connectivity and schema

### Debug Mode

For enhanced debugging, increase log level to DEBUG to see additional information:
- Token expiry checks
- Credential validation steps
- API request/response details (without sensitive data)

## Security Considerations

**What is NOT logged**:
- Actual token values (access tokens, refresh tokens)
- User passwords or sensitive personal information
- Full API request/response bodies that might contain sensitive data

**What IS logged**:
- Token presence/absence (boolean indicators)
- Token length for validation
- Error messages and status codes
- User identifiers (email, user ID)
- Timing information for performance monitoring