55# Implementation Plan

- [x] 1. Enhanced Storage State Management Implementation





  - Implement automatic storage state loading in Playwright context creation
  - Add fallback to Netscape conversion when storage_state.json is missing
  - Create warning logging with remediation instructions for missing files
  - _Requirements: 1.1, 1.2, 1.5, 1.6_

- [x] 2. Deterministic YouTubei Network Interception





  - Replace response listener-based interception with page.route() method
  - Implement asyncio.Future resolution pattern for transcript capture
  - Add 20-25 second timeout with fallback to next method
  - Remove all fixed wait_for_timeout calls from transcript capture
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 3. Multi-Client Profile System Implementation





  - Create ClientProfile dataclass with UA and viewport specifications
  - Implement desktop profile (Chrome Windows 10, 1920×1080 viewport)
  - Implement mobile profile (Android Chrome, 390×844 viewport)
  - Add profile switching logic with browser context reuse
  - Implement attempt sequence: desktop(no-proxy → proxy) then mobile(no-proxy → proxy)
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

- [x] 4. Enhanced Timed-Text Cookie Integration





  - Modify _fetch_timedtext_json3 to accept cookies parameter
  - Modify _fetch_timedtext_xml to accept cookies parameter  
  - Implement user cookie preference over environment/file cookies
  - Add debug logging for cookie source (user vs env)
  - Thread user cookies through timed-text extraction pipeline
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [x] 5. Complete HTTP Adapter Configuration





  - Add HTTP adapter mounting in make_http_session function
  - Mount retry adapter for both http:// and https:// URLs
  - Ensure no warnings about unmounted adapters
  - Verify retry logic applies equally to HTTP and HTTPS requests
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 6. Circuit Breaker Integration Hooks





  - Integrate record_failure/record_success calls with circuit breaker after retry completion
  - Implement circuit breaker skip logic with "open → skip" logging
  - Ensure breaker observes post-retry outcomes (success resets, failure increments)
  - Add circuit breaker state monitoring and structured logging
  - _Requirements: 6.3, 6.4, 6.5, 6.6_

- [x] 7. DOM Fallback Implementation





  - Add DOM polling after network route Future timeout
  - Implement transcript line selector polling for 3-5 seconds
  - Extract text from DOM nodes when network is blocked
  - Add logging for successful DOM fallback scenarios
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 8. Proxy-Enforced FFmpeg Audio Extraction





  - Implement proxy environment variable computation in ASRAudioExtractor
  - Set http_proxy and https_proxy environment variables for ffmpeg subprocess
  - Add immediate failure detection for broken proxy configurations
  - Verify external IP changes when proxy environment is set
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 9. FFmpeg Header Hygiene and Placement





  - Ensure CRLF-joined header string formatting
  - Place -headers parameter before -i parameter in ffmpeg command
  - Implement cookie value masking in all log output
  - Add validation to prevent "No trailing CRLF" errors
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 10. Comprehensive Metrics and Structured Logging





  - Implement structured event emission for circuit breaker state changes
  - Emit structured logs whenever breaker transitions (closed → open, open → half-open, half-open → closed)
  - Add stage duration logging with success/failure tracking
  - Log which transcript extraction attempt succeeded (timedtext/YouTubei/ASR)
  - Add stage_duration_ms metrics with labels {stage, proxy_used, profile}
  - Implement p50/p95 computation for dashboard integration
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

- [x] 11. Netscape to Storage State Conversion










  - Implement CLI flag --from-netscape in cookie_generator.py
  - Create conversion function from cookies.txt to storage_state.json
  - Generate minimal origins structure for Playwright compatibility
  - Ensure converted storage_state loads without Playwright errors
  - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

- [x] 12. Host Cookie Sanitation





  - Implement __Host- cookie normalization with secure=True
  - Set path="/" for all __Host- cookies
  - Remove domain field and use url field for __Host- cookies
  - Prevent Playwright __Host- cookie validation errors
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

- [x] 13. Explicit SOCS/CONSENT Cookie Injection





  - Add SOCS/CONSENT cookie presence check after generation/conversion
  - Implement synthesis of safe "accepted" values when missing
  - Scope synthesized cookies to .youtube.com with long expiry
  - Ensure storage_state always includes consent cookies
  - Implement synthesis in cookie_generator.py after conversion/warm-up only (not at runtime)
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6_

- [x] 14. Proxy Environment Builder for Subprocesses





  - Implement proxy_env_for_subprocess() method in ProxyManager
  - Return dict with http_proxy and https_proxy environment variables
  - Use existing secret/session builder for proxy URL computation
  - Return empty dict when no proxy is configured
  - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_

- [x] 15. Unified Proxy Dictionary Interface





  - Implement proxy_dict_for("requests") returning {"http":..., "https":...}
  - Implement proxy_dict_for("playwright") returning {"server":..., "username":..., "password":...}
  - Use current ProxySecret and session token generator
  - Add error logging and appropriate fallback for wrong formats
  - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_

- [x] 16. Proxy Health Metrics and Preflight Monitoring




  - Add preflight check counters for hits/misses logging
  - Implement masked username tail logging for identification
  - Provide healthy boolean accessor for proxy status
  - Emit structured logs showing proxy health without credential leakage
  - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5_

- [x] 17. Tenacity Retry Wrapper Implementation





  - Apply tenacity retry wrapper to complete YouTubei attempt function (nav + route + parse)
  - Implement exponential backoff with jitter for navigation timeouts
  - Add 2-3 retry attempts for interception failures
  - Ensure circuit breaker activates only after retry exhaustion
  - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.6_

- [x] 18. Integration Testing and Validation





  - Create comprehensive test suite for all enhanced functionality
  - Test storage state loading and Netscape conversion
  - Validate deterministic interception and multi-profile support
  - Test cookie integration and circuit breaker behavior
  - Verify proxy configuration across all components
  - _Requirements: All requirements validation_

- [x] 19. Performance Optimization and Monitoring Setup





  - Implement performance metrics collection and dashboard integration
  - Add circuit breaker state monitoring and alerting
  - Optimize browser context reuse and memory management
  - Set up structured logging for production monitoring
  - _Requirements: Performance and monitoring aspects of all requirements_

- [x] 20. Documentation and Deployment Preparation





  - Update technical documentation with enhancement details
  - Create deployment guide for new functionality
  - Prepare environment variable migration guide
  - Document troubleshooting procedures for new features
  - _Requirements: Documentation and deployment aspects_

## Non-Functional Constraints

These constraints must be verified during implementation but are not implemented as separate tasks:

### Constraint 1: Preserved Stage Order and Early Exit
- Transcript extraction must maintain order: yt-api → timedtext → YouTubei → ASR
- Processing must stop when any stage succeeds
- Enhancements must only improve reliability within each stage
- Existing fallback logic must continue working

### Constraint 2: Backward Compatibility Maintenance  
- Existing API interfaces must remain unchanged
- New parameters must be optional with sensible defaults
- New functionality must not break existing transcript extraction
- System must fall back to previous behavior when configuration is missing

### Constraint 3: Development and Production Environment Support
- Enhancements must work in both development and production environments
- Local development must support custom COOKIE_DIR configuration
- Production must default to /app/cookies
- Clear installation instructions must be provided for missing dependencies