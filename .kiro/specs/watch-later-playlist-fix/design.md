# Design Document

## Overview

The current implementation incorrectly assumes that the YouTube API has "limited access" to the Watch Later playlist and hardcodes the video count to 0. However, the YouTube Data API v3 does support accessing Watch Later playlist items through the `playlistItems().list()` endpoint with playlist ID 'WL', provided the application has the correct OAuth scopes (which it already has).

The bug is in the `get_user_playlists()` method where the Watch Later playlist is manually added with a hardcoded video count of 0, instead of actually querying the API to get the real count. The existing `get_playlist_videos()` method already demonstrates that Watch Later playlist access works correctly.

## Architecture

The fix involves modifying the `YouTubeService.get_user_playlists()` method to:

1. **Remove the hardcoded Watch Later entry** that assumes API limitations
2. **Add dynamic Watch Later playlist handling** that actually queries the API
3. **Implement proper pagination** to handle large Watch Later playlists
4. **Add robust error handling** specific to Watch Later playlist quirks
5. **Maintain backward compatibility** with the existing playlist structure

## Components and Interfaces

### Modified YouTubeService Class

The `YouTubeService` class will be enhanced with:

**New Private Method: `_get_watch_later_count()`**
- Purpose: Efficiently count videos in Watch Later playlist using pagination
- Returns: Integer count of videos or 0 if error occurs
- Handles: API errors, pagination, private/deleted video filtering

**Modified Method: `get_user_playlists()`**
- Remove hardcoded Watch Later playlist entry
- Call `_get_watch_later_count()` to get actual video count
- Add Watch Later playlist dynamically with real data
- Maintain existing error handling for regular playlists

### API Integration Strategy

**Watch Later Playlist Handling:**
- Use `playlistItems().list()` with `playlistId='WL'`
- Request only essential parts (`id` for counting, `snippet` for validation)
- Implement pagination with `nextPageToken`
- Filter out private/deleted videos during counting

**Error Handling Approach:**
- Graceful degradation: If Watch Later access fails, show it with 0 count and error indicator
- Detailed logging for debugging API issues
- Preserve existing functionality for other playlists

## Data Models

### Playlist Object Structure (Unchanged)
```python
{
    'id': str,           # 'WL' for Watch Later, playlist ID for others
    'title': str,        # 'Watch Later' or user-defined title
    'description': str,  # Playlist description
    'thumbnail': str,    # Thumbnail URL
    'video_count': int,  # ACTUAL count (not hardcoded 0)
    'is_special': bool   # True for Watch Later, False for user playlists
}
```

### Internal Count Response Structure
```python
{
    'count': int,        # Number of accessible videos
    'has_error': bool,   # Whether API errors occurred
    'error_message': str # Error details for logging
}
```

## Error Handling

### Watch Later Specific Error Scenarios

1. **API Access Denied (403)**
   - Log detailed error information
   - Return Watch Later playlist with 0 count and error indicator in title
   - Continue processing other playlists normally

2. **Rate Limiting (429)**
   - Implement exponential backoff for Watch Later counting
   - If retries fail, return 0 count with rate limit indicator

3. **Network/Timeout Errors**
   - Set reasonable timeout for Watch Later API calls
   - Return 0 count with network error indicator

4. **Malformed API Response**
   - Validate API response structure
   - Handle missing fields gracefully
   - Log unexpected response formats

### Error Recovery Strategy

- **Fail Gracefully**: Never let Watch Later errors break the entire playlist loading
- **User Feedback**: Indicate in the UI when Watch Later count is unavailable due to errors
- **Retry Logic**: Implement simple retry for transient errors
- **Fallback Behavior**: Always return a Watch Later entry, even if counting fails

## Testing Strategy

### Unit Tests

1. **Test `_get_watch_later_count()` method:**
   - Mock API responses for different scenarios (empty, single page, multiple pages)
   - Test error handling (403, 429, network errors)
   - Verify private/deleted video filtering
   - Test pagination logic

2. **Test modified `get_user_playlists()` method:**
   - Verify Watch Later playlist appears with correct count
   - Test integration with regular playlist fetching
   - Verify sorting (Watch Later first, then alphabetical)
   - Test error scenarios don't break other playlists

### Integration Tests

1. **API Integration Tests:**
   - Test with real YouTube API using test account
   - Verify Watch Later playlist with known video count
   - Test with empty Watch Later playlist
   - Test with large Watch Later playlist (pagination)

2. **Error Simulation Tests:**
   - Mock API errors and verify graceful handling
   - Test rate limiting scenarios
   - Verify logging output for different error types

### Manual Testing Scenarios

1. **User Acceptance Testing:**
   - Test with user accounts having various Watch Later playlist sizes
   - Verify UI displays correct counts
   - Test error states are user-friendly
   - Confirm other playlists remain unaffected

## Implementation Approach

### Phase 1: Core Fix Implementation
- Add `_get_watch_later_count()` private method
- Modify `get_user_playlists()` to use dynamic counting
- Remove hardcoded Watch Later entry
- Add basic error handling

### Phase 2: Robustness Enhancements
- Implement pagination for large playlists
- Add comprehensive error handling and logging
- Implement retry logic for transient failures
- Add performance optimizations

### Phase 3: Testing and Validation
- Add unit tests for new functionality
- Perform integration testing with real API
- Validate with multiple user accounts
- Performance testing with large playlists

## Performance Considerations

### API Efficiency
- Use minimal API parts (`id` only for counting)
- Implement reasonable `maxResults` (50 items per request)
- Cache results where appropriate
- Avoid unnecessary API calls

### Pagination Optimization
- Break pagination loop early if reasonable limits are reached
- Log performance metrics for large playlists
- Consider async processing for very large playlists (future enhancement)

### Error Handling Performance
- Quick failure for known error conditions
- Avoid blocking other playlist processing
- Efficient retry mechanisms with exponential backoff

## Security Considerations

### OAuth Scope Validation
- Verify existing scopes are sufficient (youtube.readonly confirmed)
- Handle scope-related errors gracefully
- Log security-related API errors appropriately

### Data Privacy
- Only request necessary data from API
- Handle private/deleted videos appropriately
- Ensure error logs don't expose sensitive information

### Rate Limiting Compliance
- Respect YouTube API rate limits
- Implement proper backoff strategies
- Monitor API usage patterns