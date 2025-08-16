# Implementation Plan

- [x] 1. Create cookie status helper function in routes


  - Add `get_user_cookie_status()` function to `routes.py` that checks file existence and validity
  - Function should return status dictionary with has_cookies, upload_date, file_size_kb, and status_text
  - Reuse existing `_local_cookie_path()` function from `cookies_routes.py` for consistent file path handling
  - _Requirements: 1.3, 1.4, 3.1_



- [ ] 2. Integrate cookie status into dashboard route
  - Modify the `dashboard()` function in `routes.py` to include cookie status in template context
  - Call `get_user_cookie_status()` and pass result to template as `cookie_status` variable


  - Ensure error handling doesn't break dashboard loading if cookie status check fails
  - _Requirements: 1.1, 3.1_

- [x] 3. Add cookie management section to dashboard template

  - Insert cookie status card in `templates/index.html` between dashboard header and playlist selection
  - Create responsive card layout with status indicator, description, and action buttons
  - Use existing Bootstrap classes and Feather icons for consistency with current UI
  - _Requirements: 1.1, 2.1, 2.2, 2.3_

- [x] 4. Implement dynamic cookie status display

  - Add conditional template logic to show different content based on cookie status
  - Display "Active" status with green badge when cookies are present
  - Display "Not Configured" status with yellow badge when cookies are missing
  - Include upload date and file size when cookies are present
  - _Requirements: 1.3, 1.4, 3.1, 3.2_


- [ ] 5. Add cookie management action buttons
  - Create "Upload Cookies" button that links to `/account/cookies` when no cookies present
  - Create "Manage Cookies" button that links to `/account/cookies` when cookies are present
  - Style buttons consistently with existing dashboard button styles


  - _Requirements: 1.1, 1.2, 3.2, 3.3_

- [ ] 6. Add informational content for cookie benefits
  - Include brief explanation of what cookies do (improve YouTube access reliability)



  - Add security note that cookies are stored encrypted
  - Show content conditionally - more detailed when no cookies, brief when cookies present
  - _Requirements: 2.1, 2.2, 2.3_

- [ ] 7. Write unit tests for cookie status functionality
  - Test `get_user_cookie_status()` with various file states (missing, empty, valid)
  - Test dashboard route includes cookie status in template context
  - Mock file system operations to test error handling scenarios
  - _Requirements: All requirements validation_

- [ ] 8. Write integration tests for cookie management flow
  - Test complete flow from dashboard cookie section to cookie upload page
  - Verify status updates correctly after cookie upload/deletion operations
  - Test responsive behavior and accessibility features
  - _Requirements: 1.1, 1.2, 3.2, 3.3_