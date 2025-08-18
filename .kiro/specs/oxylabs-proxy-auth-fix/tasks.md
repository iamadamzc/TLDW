# Implementation Plan

## MVP Tasks (Required for 407 Error Elimination)

- [x] 1. **[MVP - CRITICAL]** Create core proxy management with strict secret validation


  - Implement ProxySecret dataclass with RAW format validation (reject pre-encoded passwords, host schemes)
  - Add ProxyError exception hierarchy and looks_preencoded helper using quote/unquote roundtrip
  - **MUST validate and reject malformed secrets before any proxy operations**
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_



- [ ] 2. **[MVP]** Implement preflight cache with basic TTL
  - Create PreflightCache with 300s TTL and ±10% jitter


  - Add cache expiration and get/set methods
  - _Requirements: 2.1, 2.3, 5.6, 5.7_

- [x] 3. **[MVP]** Build ProxyManager with preflight and session rotation

  - Add preflight validation with single-flight guard and rate limiting
  - Implement unique session tokens per video with blacklisting on auth failures
  - Create BoundedBlacklist with TTL cleanup
  - _Requirements: 2.1, 2.2, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_



- [ ] 4. **[MVP]** Implement safe structured logging
  - Create SafeStructuredLogger with deny-list for sensitive fields

  - Wrap data under 'evt' key, ensure never crashes pipeline
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.6, 4.7_

- [x] 5. **[MVP]** Create health endpoints


  - Add /health/live (always 200) and /health/ready (cached proxy status)
  - Return proper HTTP status codes and Retry-After headers
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.8_



- [ ] 6. **[MVP]** Implement standardized error responses
  - Create error_response helper with HTTP_MAP (502/503 codes)
  - Add correlation IDs and structured error format




  - _Requirements: 2.6, 2.7_

- [ ] 7. **[MVP]** Integrate proxy validation into transcript service
  - Add preflight fail-fast behavior (502 on auth failure)
  - Implement session rotation on 401/403/407/429 errors
  - _Requirements: 6.1, 6.2, 6.4, 6.8_

- [ ] 8. **[MVP - HIGH PRIORITY]** Integrate proxy validation into YouTube/yt-dlp service
  - Add cookie fast-fail validation (file exists, >1KB, contains SID/SAPISID) to reduce fallback noise
  - Implement session rotation on auth errors (401/403/407/429)
  - Configure yt-dlp with proxy and conditional cookiefile (avoid None values)
  - _Requirements: 6.3, 6.5, 6.6, 6.7_

- [ ] 9. **[MVP]** Basic testing and deployment with secret hygiene validation
  - Unit tests for secret validation (host scheme rejection, pre-encoded password detection)
  - Integration tests for preflight and health endpoints
  - **Deploy with validated RAW secret format in AWS Secrets Manager**
  - **Smoke test: Verify secret validation rejects malformed secrets before proxy operations**
  - Confirm 407 errors eliminated and session rotation working correctly
  - _Requirements: All verification requirements_

## Fast-Follow Tasks (Post-MVP Enhancements)

- [ ] 10. **[Fast-Follow]** Secret refresh and precedence management
  - Implement SecretRefreshManager with periodic refresh and last-known-good fallback
  - Add secret precedence handling (RuntimeEnvironmentSecrets → AWS → env vars)
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [ ] 11. **[Fast-Follow]** Comprehensive metrics and SLO tracking
  - Add full metrics collection (proxy.preflight.ok, ytdlp.407, etc.)
  - Implement SLO tracking: proxy.preflight.ok_rate ≥ 99% over 15m
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ] 12. **[Fast-Follow]** Extended configuration management
  - Add all environment variables (OXY_PREFLIGHT_MAX_PER_MINUTE, etc.)
  - Create configuration validation utilities
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

- [ ] 13. **[Fast-Follow]** Load testing and extended observability
  - Performance tests for preflight cache and session rotation under load
  - Memory usage monitoring and cleanup optimization
  - Extended logging and debugging capabilities

- [ ] 14. **[Fast-Follow]** Documentation and runbooks
  - Comprehensive troubleshooting guides and proxy debugging runbooks
  - Extended deployment documentation and secret hygiene guides
  - App Runner health check configuration documentation