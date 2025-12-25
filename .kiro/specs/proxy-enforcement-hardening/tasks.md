# Proxy Enforcement Hardening - Implementation Tasks

## Task Overview

This implementation plan converts the proxy enforcement hardening design into discrete, manageable coding steps that build incrementally. Each task focuses on a specific aspect of proxy integration while maintaining backward compatibility and following the golden rules for surgical PRs.

## Implementation Tasks

### Phase 1: Core Infrastructure

- [ ] 1. Create ProxyMiddleware core class
  - Implement ProxyMiddleware class with all client factory methods
  - Add ProxyEnforcementError exception class with service and job_id context
  - Implement proxy configuration validation and enforcement checking
  - Add job-scoped client caching with proper lifecycle management
  - _Requirements: REQ-2.1, REQ-2.2, REQ-1.3, REQ-1.4_

- [ ] 1.1 Implement requests session factory
  - Create get_requests_session method with job-scoped proxy configuration
  - Add proxy authentication error handling and retry logic
  - Implement session caching and reuse within job scope
  - Add comprehensive error logging with credential sanitization
  - _Requirements: REQ-2.2, REQ-2.3, REQ-1.1_

- [ ] 1.2 Implement httpx client factory
  - Create get_httpx_client method with async proxy support
  - Add timeout configuration and connection pooling
  - Implement proper client lifecycle management and cleanup
  - Add proxy authentication failure handling for async clients
  - _Requirements: REQ-2.2, REQ-2.4, REQ-1.2_

- [ ] 1.3 Implement Playwright proxy configuration
  - Create get_playwright_proxy_config method for browser contexts
  - Add proxy configuration validation for Playwright format
  - Implement job-scoped proxy session correlation for browser contexts
  - Add error handling for Playwright-specific proxy issues
  - _Requirements: REQ-2.2, REQ-2.4, REQ-1.1_

- [ ] 1.4 Implement ffmpeg proxy configuration
  - Create get_ffmpeg_proxy_config method returning environment and -http_proxy flag
  - Add proxy URL validation and formatting for ffmpeg compatibility
  - Implement environment variable preparation for subprocess calls
  - Add proxy enforcement validation for ffmpeg operations
  - _Requirements: REQ-4.2, REQ-4.3, REQ-1.1_

### Phase 2: Service Integration

- [ ] 2. Update transcript_service.py proxy integration
  - Replace all direct HTTP calls with ProxyMiddleware usage
  - Add ProxyMiddleware injection to TranscriptService constructor
  - Update timedtext methods to use proxy-configured sessions
  - Preserve existing public interfaces and error handling patterns
  - _Requirements: REQ-2.1, REQ-1.1, REQ-1.2_

- [ ] 2.1 Fix YouTube Transcript API proxy usage
  - Update youtube_transcript_api_compat.py to use ProxyMiddleware
  - Add proxy enforcement validation before API calls
  - Implement proper error handling for proxy authentication failures
  - Maintain compatibility with existing transcript API error types
  - _Requirements: REQ-1.1, REQ-1.3, REQ-2.3_

- [ ] 2.2 Fix timedtext endpoint proxy usage
  - Update _fetch_timedtext_json3_enhanced to use ProxyMiddleware
  - Update _fetch_timedtext_xml_enhanced to use ProxyMiddleware
  - Add proxy enforcement validation for all timedtext calls
  - Implement consistent error handling across timedtext methods
  - _Requirements: REQ-1.1, REQ-1.2, REQ-2.1_

- [ ] 3. Update youtubei_service.py proxy integration
  - Update DeterministicYouTubeiCapture to use ProxyMiddleware
  - Fix _fetch_transcript_xml_via_requests to use proxy-configured httpx client
  - Add ProxyMiddleware injection to constructor with job_id correlation
  - Implement proxy enforcement validation for all HTTP calls
  - _Requirements: REQ-2.1, REQ-1.1, REQ-1.2_

- [ ] 3.1 Fix YouTubei caption track fetching
  - Update _extract_captions_from_player_response HTTP calls to use ProxyMiddleware
  - Add proxy enforcement validation before caption track requests
  - Implement proper error handling for proxy failures in caption fetching
  - Maintain existing error types and fallback behavior
  - _Requirements: REQ-1.1, REQ-1.3, REQ-2.3_

### Phase 3: FFmpeg Standardization

- [ ] 4. Create standardized ffmpeg proxy configuration
  - Create build_ffmpeg_headers function for consistent User-Agent and Cookie headers
  - Create build_ffmpeg_command_with_proxy function using ProxyMiddleware
  - Update all ffmpeg callers to use standardized configuration builder
  - Add proxy enforcement validation for all ffmpeg operations
  - _Requirements: REQ-4.1, REQ-4.2, REQ-4.3_

- [ ] 4.1 Update ffmpeg_service.py proxy integration
  - Replace existing ffmpeg command building with standardized function
  - Update _ffmpeg_extract_attempt to use ProxyMiddleware configuration
  - Add proxy enforcement validation in FFmpegService constructor
  - Implement consistent error handling for ffmpeg proxy failures
  - _Requirements: REQ-4.1, REQ-4.2, REQ-4.4_

- [ ] 4.2 Update requests streaming fallback proxy usage
  - Update _requests_streaming_fallback to use ProxyMiddleware
  - Add proxy enforcement validation before streaming requests
  - Implement proper error handling for proxy failures in streaming
  - Maintain existing fallback behavior and error types
  - _Requirements: REQ-1.1, REQ-1.2, REQ-2.1_

### Phase 4: ASR Service Integration

- [ ] 5. Create ASR service with proxy integration
  - Create new ASRService class with ProxyMiddleware integration
  - Implement Deepgram SDK proxy monkey-patching approach
  - Add patch_deepgram_http_client context manager for HTTP interception
  - Implement proxy enforcement validation for all ASR operations
  - _Requirements: REQ-3.1, REQ-3.2, REQ-3.4_

- [ ] 5.1 Implement Deepgram SDK proxy monkey-patching
  - Create HTTP client interception for Deepgram SDK internal calls
  - Route all Deepgram HTTP requests through proxy-configured httpx client
  - Maintain existing Deepgram SDK API compatibility
  - Add comprehensive error handling for proxy failures in ASR calls
  - _Requirements: REQ-3.1, REQ-3.3, REQ-2.4_

- [ ] 5.2 Integrate ASR service into transcript pipeline
  - Update transcript_service.py to use new ASRService with proxy support
  - Add ASR service initialization with ProxyMiddleware injection
  - Implement proper error handling and fallback behavior
  - Maintain existing ASR timeout and retry logic
  - _Requirements: REQ-3.1, REQ-3.2, REQ-1.1_

### Phase 5: Testing and Validation

- [ ] 6. Create comprehensive proxy integration tests
  - Create MockProxyServer for testing proxy scenarios
  - Add unit tests for ProxyMiddleware all client factory methods
  - Add proxy enforcement validation tests for ENFORCE_PROXY_ALL scenarios
  - Add error handling tests for all proxy failure conditions
  - _Requirements: REQ-5.1, REQ-5.2, REQ-5.3_

- [ ] 6.1 Add service-specific proxy integration tests
  - Add transcript_service.py proxy integration tests
  - Add youtubei_service.py proxy integration tests  
  - Add ffmpeg_service.py proxy integration tests
  - Add ASR service proxy integration tests
  - _Requirements: REQ-5.1, REQ-5.4_

- [ ] 6.2 Add end-to-end proxy enforcement tests
  - Create full transcript pipeline tests with proxy enforcement enabled
  - Add job-scoped proxy session correlation validation tests
  - Add proxy authentication failure recovery tests
  - Add IP leak prevention validation tests
  - _Requirements: REQ-5.1, REQ-5.4, REQ-1.1_

- [ ] 6.3 Add proxy performance and reliability tests
  - Add proxy middleware performance benchmarks
  - Add proxy client caching and lifecycle tests
  - Add concurrent job proxy isolation tests
  - Add proxy configuration change handling tests
  - _Requirements: REQ-5.1, REQ-5.4_

### Phase 6: Integration and Deployment

- [ ] 7. Update service initialization with ProxyMiddleware
  - Update routes.py to inject ProxyMiddleware into all services
  - Add ProxyMiddleware initialization in app.py startup
  - Update shared_managers.py to provide ProxyMiddleware instance
  - Implement proper dependency injection pattern for all services
  - _Requirements: REQ-2.1, REQ-1.4_

- [ ] 7.1 Add proxy enforcement configuration validation
  - Update config_validator.py to validate proxy enforcement settings
  - Add startup validation for ProxyMiddleware configuration
  - Implement health check integration for proxy enforcement status
  - Add configuration documentation and troubleshooting guides
  - _Requirements: REQ-1.4, REQ-5.2_

- [ ] 7.2 Update monitoring and observability
  - Add structured logging events for all proxy operations
  - Add proxy enforcement metrics collection
  - Update health check endpoints with proxy enforcement status
  - Add proxy-related error classification and user-friendly messages
  - _Requirements: REQ-1.3, REQ-2.3_

- [ ] 8. Documentation and deployment preparation
  - Update API documentation with new proxy integration patterns
  - Create migration guide for proxy enforcement hardening
  - Update troubleshooting guides with new error patterns and solutions
  - Create deployment checklist for proxy enforcement validation
  - _Requirements: All requirements_

## Task Dependencies

```
1 → 1.1, 1.2, 1.3, 1.4
1.1, 1.2, 1.3, 1.4 → 2, 3, 4, 5
2 → 2.1, 2.2
3 → 3.1
4 → 4.1, 4.2
5 → 5.1, 5.2
2, 3, 4, 5 → 6
6 → 6.1, 6.2, 6.3
6.1, 6.2, 6.3 → 7
7 → 7.1, 7.2, 8
```

## Success Metrics

### Functional Metrics
- **Zero IP address leaks** detected in testing with ENFORCE_PROXY_ALL=1
- **100% proxy enforcement coverage** across all external HTTP calls
- **All services successfully integrated** with ProxyMiddleware
- **All tests passing** including new proxy integration test suite

### Performance Metrics
- **ProxyMiddleware overhead < 5ms** per HTTP client creation
- **No regression** in existing request latency
- **Proper resource cleanup** with no memory leaks in long-running jobs
- **Efficient client caching** with job-scoped reuse

### Quality Metrics
- **100% test coverage** for ProxyMiddleware public methods
- **All proxy error scenarios tested** with appropriate mocking
- **Comprehensive integration tests** for all service proxy integration
- **Documentation complete** with migration guides and troubleshooting

## Risk Mitigation

### Breaking Changes Prevention
- **Preserve all public interfaces** during service integration
- **Maintain existing error types** where possible
- **Use dependency injection** to avoid constructor changes
- **Feature flags** for gradual rollout if needed

### Performance Risk Mitigation
- **Benchmark ProxyMiddleware** before and after implementation
- **Profile memory usage** during long-running jobs
- **Monitor connection pooling** efficiency
- **Load test** with proxy enforcement enabled

### Integration Risk Mitigation
- **Mock all external dependencies** in tests
- **Test proxy authentication failures** thoroughly
- **Validate job-scoped isolation** in concurrent scenarios
- **Test configuration edge cases** and error conditions

## Definition of Done

- [ ] All tasks completed and tested
- [ ] ProxyMiddleware integrated into all services
- [ ] ENFORCE_PROXY_ALL=1 respected by all external calls
- [ ] ASR service fully integrated with proxy support
- [ ] FFmpeg operations use standardized proxy configuration
- [ ] Comprehensive test suite passing with 100% coverage
- [ ] No IP address leaks detected in testing
- [ ] All proxy authentication errors handled gracefully
- [ ] Documentation updated and deployment ready
- [ ] Performance benchmarks meet requirements