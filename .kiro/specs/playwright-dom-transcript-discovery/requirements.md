# Requirements Document

## Introduction

This feature enhances the existing Playwright transcript pipeline to handle cases where the "Show transcript" button is hidden behind a collapsed description section on YouTube videos. The system will implement DOM interaction helpers to expand descriptions and discover transcript buttons that are not immediately visible, while maintaining the existing network interception approach and proxy/cookie behavior.

## Requirements

### Requirement 1

**User Story:** As a transcript extraction system, I want to discover transcript buttons hidden behind collapsed descriptions so that I can access transcripts for videos where the button is not immediately visible.

#### Acceptance Criteria

1. WHEN navigating to a YouTube video page THEN it SHALL set up route interception for /youtubei/v1/get_transcript BEFORE any DOM interactions
2. WHEN the page loads THEN it SHALL attempt to handle consent dialogs if present
3. WHEN looking for transcript buttons THEN it SHALL first try to expand collapsed descriptions using resilient selectors
4. WHEN description expansion succeeds THEN it SHALL attempt to click the "Show transcript" button
5. WHEN transcript button is not found after expansion THEN it SHALL scroll to page end and retry once before failing

### Requirement 2

**User Story:** As a consent handling system, I want to automatically dismiss common consent dialogs so that transcript discovery can proceed without manual intervention.

#### Acceptance Criteria

1. WHEN a consent dialog is present THEN it SHALL attempt to click common consent acceptance buttons
2. WHEN consent buttons are found THEN it SHALL click them and wait for dialog dismissal
3. WHEN consent handling fails THEN it SHALL log the failure and continue with transcript discovery
4. WHEN no consent dialog is present THEN it SHALL proceed directly to transcript discovery
5. WHEN consent handling times out THEN it SHALL continue without blocking transcript extraction

### Requirement 3

**User Story:** As a description expansion system, I want to use resilient selectors to expand collapsed descriptions so that hidden transcript buttons become discoverable.

#### Acceptance Criteria

1. WHEN looking for description expanders THEN it SHALL try 'ytd-text-inline-expander tp-yt-paper-button.more-button' selector first
2. WHEN first selector fails THEN it SHALL try 'tp-yt-paper-button:has-text("more")' selector
3. WHEN second selector fails THEN it SHALL try 'button[aria-label*="more"]' selector as fallback
4. WHEN description expander is found THEN it SHALL click it and wait for expansion to complete
5. WHEN no description expander is found THEN it SHALL proceed to transcript button discovery without expansion

### Requirement 4

**User Story:** As a transcript button discovery system, I want to use robust selectors to find "Show transcript" buttons so that transcript access works across different YouTube layouts.

#### Acceptance Criteria

1. WHEN looking for transcript buttons THEN it SHALL try 'tp-yt-paper-button:has-text("Show transcript")' selector first
2. WHEN first selector fails THEN it SHALL try 'button:has-text("Show transcript")' selector
3. WHEN second selector fails THEN it SHALL try 'button[aria-label*="transcript" i]' selector (case-insensitive)
4. WHEN third selector fails THEN it SHALL try 'tp-yt-paper-button[aria-label*="transcript" i]' selector
5. WHEN all primary selectors fail THEN it SHALL try fallback selector 'ytd-transcript-search-panel-renderer tp-yt-paper-button'

### Requirement 5

**User Story:** As a network interception system, I want to capture transcript data from route interception so that I can extract transcript content without relying on DOM parsing.

#### Acceptance Criteria

1. WHEN route interception is set up THEN it SHALL resolve a Future with (url, body) when /youtubei/v1/get_transcript is captured
2. WHEN transcript button is clicked THEN it SHALL wait for the Future to resolve within 25 seconds
3. WHEN Future resolves THEN it SHALL unroute the interceptor to clean up resources
4. WHEN waiting for response THEN it SHALL wait for the matching HTTP response within 6 seconds
5. WHEN response status is not 200 THEN it SHALL log youtubei_direct_fetch_failed and return None

### Requirement 6

**User Story:** As a retry mechanism, I want to implement scroll-and-retry logic so that transcript buttons that appear after scrolling can be discovered.

#### Acceptance Criteria

1. WHEN transcript button is not found initially THEN it SHALL scroll to the end of the page
2. WHEN scrolling completes THEN it SHALL retry transcript button discovery once
3. WHEN retry succeeds THEN it SHALL proceed with transcript extraction
4. WHEN retry fails THEN it SHALL return None and fall back to next transcript method
5. WHEN scrolling fails THEN it SHALL log the error and return None without retrying

### Requirement 7

**User Story:** As a logging system, I want compact structured logs for DOM interactions so that transcript discovery can be debugged without verbose output.

#### Acceptance Criteria

1. WHEN description is expanded THEN it SHALL log "youtubei_dom: expanded description via [selector]"
2. WHEN transcript button is clicked THEN it SHALL log "youtubei_dom: clicked transcript launcher ([selector])"
3. WHEN route is captured THEN it SHALL log "youtubei_route_captured url=[url]"
4. WHEN DOM interactions fail THEN it SHALL log specific failure reasons without verbose dumps
5. WHEN operations succeed THEN it SHALL log success with minimal context information

### Requirement 8

**User Story:** As a proxy and cookie system, I want DOM interactions to maintain existing proxy and cookie behavior so that network routing and authentication remain unchanged.

#### Acceptance Criteria

1. WHEN DOM interactions are performed THEN they SHALL use the same browser context with existing proxy configuration
2. WHEN DOM interactions are performed THEN they SHALL use the same storage state and cookies as network interception
3. WHEN DOM interactions are performed THEN they SHALL not alter browser launch flags or configuration
4. WHEN DOM interactions are performed THEN they SHALL maintain headless operation mode
5. WHEN DOM interactions are performed THEN they SHALL respect existing timeout configurations

### Requirement 9

**User Story:** As a graceful degradation system, I want DOM interactions to skip gracefully when elements are not found so that existing functionality continues to work.

#### Acceptance Criteria

1. WHEN description expander is not found THEN it SHALL proceed to transcript button discovery without failing
2. WHEN transcript button is already visible THEN it SHALL skip description expansion and click the button directly
3. WHEN DOM interactions timeout THEN it SHALL return None and allow fallback to next transcript method
4. WHEN DOM elements are not found THEN it SHALL not throw exceptions that break the transcript pipeline
5. WHEN DOM interactions succeed partially THEN it SHALL continue with available functionality

### Requirement 10

**User Story:** As a testing system, I want unit tests that mock DOM interactions so that transcript discovery logic can be validated without browser automation.

#### Acceptance Criteria

1. WHEN testing description expansion THEN it SHALL mock cases where expander exists and transcript appears
2. WHEN testing transcript discovery THEN it SHALL mock cases where expander is missing but transcript is present
3. WHEN testing failure paths THEN it SHALL mock cases where no button is found and timeout occurs
4. WHEN testing route interception THEN it SHALL mock successful capture of /youtubei/v1/get_transcript responses
5. WHEN testing retry logic THEN it SHALL mock scroll behavior and retry attempts

### Requirement 11

**User Story:** As a validation system, I want to test with specific video IDs so that DOM interaction enhancements can be verified against real YouTube content.

#### Acceptance Criteria

1. WHEN testing locally THEN it SHALL work with video ID rNxC16mlO60 as a test case
2. WHEN description expansion works THEN it SHALL log "youtubei_dom: expanded description via ..." message
3. WHEN transcript button is clicked THEN it SHALL log "youtubei_dom: clicked transcript launcher (...)" message
4. WHEN route capture succeeds THEN it SHALL log "youtubei_route_captured url=..." message
5. WHEN transcript extraction completes THEN it SHALL return JSON with transcript segments

### Requirement 12

**User Story:** As a timeout management system, I want appropriate timeouts for DOM interactions so that operations complete within reasonable time bounds.

#### Acceptance Criteria

1. WHEN waiting for route interception THEN it SHALL timeout after 25 seconds maximum
2. WHEN waiting for HTTP response THEN it SHALL timeout after 6 seconds maximum
3. WHEN clicking DOM elements THEN it SHALL use reasonable click timeouts to avoid hanging
4. WHEN scrolling pages THEN it SHALL wait for scroll completion before retrying
5. WHEN DOM operations timeout THEN it SHALL log timeout errors and continue to fallback methods

### Requirement 13

**User Story:** As an error handling system, I want specific error logging for DOM interaction failures so that issues can be diagnosed and resolved.

#### Acceptance Criteria

1. WHEN consent handling fails THEN it SHALL log consent_handling_failed with error details
2. WHEN description expansion fails THEN it SHALL log description_expansion_failed with selector information
3. WHEN transcript button is not found THEN it SHALL log transcript_button_not_found with attempted selectors
4. WHEN route interception times out THEN it SHALL log route_interception_timeout with elapsed time
5. WHEN HTTP response is invalid THEN it SHALL log youtubei_direct_fetch_failed with status code

### Requirement 14

**User Story:** As a backward compatibility system, I want DOM enhancements to integrate seamlessly with existing Playwright pipeline so that current functionality is not disrupted.

#### Acceptance Criteria

1. WHEN DOM interactions are added THEN they SHALL not change the existing _get_transcript_via_playwright method signature
2. WHEN DOM interactions are added THEN they SHALL not alter existing error handling or circuit breaker behavior
3. WHEN DOM interactions are added THEN they SHALL not change existing fallback order or ASR processing
4. WHEN DOM interactions fail THEN they SHALL return None and allow existing fallback methods to run
5. WHEN DOM interactions succeed THEN they SHALL return transcript data in the same format as existing methods

### Requirement 15

**User Story:** As a performance system, I want DOM interactions to be efficient so that transcript extraction remains fast and responsive.

#### Acceptance Criteria

1. WHEN DOM interactions are performed THEN they SHALL complete within the existing Playwright timeout bounds
2. WHEN DOM interactions are performed THEN they SHALL not significantly increase total transcript extraction time
3. WHEN DOM interactions are performed THEN they SHALL use efficient selectors that minimize DOM traversal
4. WHEN DOM interactions are performed THEN they SHALL avoid unnecessary waits or polling
5. WHEN DOM interactions are performed THEN they SHALL clean up resources (unroute) after completion
</content>