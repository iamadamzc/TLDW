# Implementation Plan

- [x] 1. Create helper method for Watch Later playlist counting


  - Implement `_get_watch_later_count()` private method in YouTubeService class
  - Add pagination logic to handle playlists with more than 50 videos
  - Include filtering for private/deleted videos during counting
  - Add comprehensive error handling with detailed logging
  - _Requirements: 1.1, 1.3, 3.1, 3.3, 4.1, 4.2_

- [x] 2. Modify get_user_playlists method to use dynamic Watch Later counting


  - Remove the hardcoded Watch Later playlist entry with video_count: 0
  - Replace with dynamic call to `_get_watch_later_count()` method
  - Maintain the same playlist object structure for backward compatibility
  - Preserve existing error handling for regular playlists
  - _Requirements: 1.1, 2.1, 2.3, 3.2_

- [x] 3. Implement robust error handling for Watch Later API calls


  - Add specific error handling for common API errors (403, 429, network timeouts)
  - Implement graceful degradation when Watch Later access fails
  - Add error indicators in playlist title when counting fails
  - Ensure Watch Later errors don't break other playlist processing
  - _Requirements: 2.2, 4.2, 4.3_

- [x] 4. Add comprehensive logging for Watch Later operations

  - Log successful Watch Later playlist processing with video counts
  - Log detailed error information for failed API calls
  - Add debug logging for pagination and API request details
  - Include performance timing logs for large playlist processing
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 5. Create unit tests for Watch Later counting functionality


  - Write tests for `_get_watch_later_count()` method with mocked API responses
  - Test pagination logic with multiple pages of results
  - Test error handling scenarios (API errors, network failures)
  - Test filtering of private/deleted videos during counting
  - _Requirements: 1.1, 1.2, 1.3, 3.3_

- [x] 6. Create integration tests for modified playlist functionality


  - Test complete `get_user_playlists()` method with Watch Later integration
  - Verify Watch Later playlist appears with correct video count
  - Test that regular playlists continue to work correctly
  - Test playlist sorting with Watch Later appearing first
  - _Requirements: 1.1, 2.1, 2.3_

- [x] 7. Add error scenario testing


  - Create tests that simulate API errors for Watch Later playlist
  - Verify graceful error handling doesn't break other playlist loading
  - Test error message formatting and logging output
  - Verify error indicators appear correctly in playlist titles
  - _Requirements: 2.2, 4.2, 4.3_

- [ ] 8. Performance optimization and validation



  - Add performance timing measurements for Watch Later API calls
  - Optimize API requests to use minimal required data parts
  - Test with large Watch Later playlists to verify pagination performance
  - Add reasonable timeout limits for API calls
  - _Requirements: 1.3, 3.1, 3.3_