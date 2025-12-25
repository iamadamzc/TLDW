# Production Readiness Hardening

## Overview

This spec addresses critical production readiness gaps across the YouTube transcript pipeline, focusing on proxy enforcement, performance optimization, error recovery, and monitoring improvements. The current implementation has several areas that need hardening to achieve full production readiness with reliable proxy integration, optimized performance, and comprehensive observability.

## Problem Statement

**Current Issues:**

**Proxy Integration Gaps:**
1. **Inconsistent proxy enforcement** - Some HTTP calls bypass proxy_manager entirely
2. **Missing ASR proxy support** - Deepgram SDK calls don't use proxies
3. **Incomplete ENFORCE_PROXY_ALL implementation** - Some services ignore the enforcement flag
4. **No centralized proxy routing** - Each service implements proxy logic differently
5. **FFmpeg proxy gaps** - Some ffmpeg calls lack proper proxy configuration

**Performance Bottlenecks:**
6. **Sequential transcript attempts** - No parallel fallback racing between methods
7. **Heavy browser context creation** - New Playwright context for each video
8. **No connection pooling** - HTTP clients recreated for each request
9. **Missing transcript caching** - Repeated requests for same video

**Error Recovery Limitations:**
10. **Basic retry strategies** - No intelligent retry based on error types
11. **Limited circuit breaker patterns** - Only covers Playwright operations
12. **Inconsistent error classification** - Different error handling across services

**Monitoring and Observability Gaps:**
13. **No real-time alerting** - Only basic health checks available
14. **Limited performance metrics** - Missing latency percentiles and trends
15. **Incomplete proxy health monitoring** - No comprehensive proxy status tracking

**Impact:**
- IP address leaks that can trigger YouTube anti-bot detection
- Suboptimal performance due to sequential processing and resource recreation
- Inconsistent error recovery leading to unnecessary failures
- Limited operational visibility into system health and performance

## User Stories

### Story 1: Consistent Proxy Enforcement
**As a** system operator  
**I want** all external HTTP calls to consistently use the configured proxy  
**So that** IP address leaks are prevented and anti-bot protection is effective

**Acceptance Criteria:**
1. WHEN ENFORCE_PROXY_ALL=1 is set AND no proxy is available THEN all external calls must fail immediately
2. WHEN a proxy is configured THEN all HTTP clients (requests, httpx, Playwright, ffmpeg) must use job-scoped proxy sessions
3. WHEN proxy enforcement is enabled THEN no external call should bypass the proxy_manager
4. WHEN a service attempts to make an external call without proxy THEN it must raise ProxyEnforcementError immediately

### Story 2: ASR Proxy Integration
**As a** system operator  
**I want** ASR/Deepgram API calls to use the same proxy configuration as other services  
**So that** all external calls maintain consistent IP address and session correlation

**Acceptance Criteria:**
1. WHEN ASR fallback is triggered THEN Deepgram SDK calls must use job-scoped proxy configuration
2. WHEN ENFORCE_PROXY_ALL=1 is set THEN ASR calls must fail if no proxy is available
3. WHEN proxy authentication fails THEN ASR service must handle ProxyAuthError appropriately
4. WHEN ASR service is initialized THEN it must validate proxy configuration if enforcement is enabled

### Story 3: Centralized Proxy Middleware
**As a** developer  
**I want** a single proxy routing mechanism for all HTTP clients  
**So that** proxy configuration is consistent and maintainable across services

**Acceptance Criteria:**
1. WHEN any service needs an HTTP client THEN it must use the centralized proxy middleware
2. WHEN proxy middleware is used THEN it must provide job-scoped proxy sessions
3. WHEN proxy configuration changes THEN all active clients must use the updated configuration
4. WHEN proxy middleware detects enforcement violations THEN it must raise errors immediately

### Story 4: FFmpeg Proxy Hardening
**As a** system operator  
**I want** all ffmpeg operations to use consistent proxy and header configuration  
**So that** HLS/DASH downloads don't leak IP addresses or inconsistent session data

**Acceptance Criteria:**
1. WHEN ffmpeg is invoked THEN it must use a single header builder function for User-Agent and Cookie headers
2. WHEN proxy is available THEN ffmpeg must use both -http_proxy flag and proxy environment variables
3. WHEN ENFORCE_PROXY_ALL=1 is set THEN ffmpeg operations must fail if no proxy is configured
4. WHEN ffmpeg proxy authentication fails THEN the service must handle the error gracefully

### Story 5: Performance Optimization
**As a** system operator  
**I want** optimized transcript processing with parallel attempts and resource reuse  
**So that** processing latency is minimized and system resources are used efficiently

**Acceptance Criteria:**
1. WHEN multiple transcript methods are available THEN they must be attempted in parallel with timeout racing
2. WHEN browser contexts are needed THEN they must be reused efficiently within job scope
3. WHEN HTTP clients are created THEN they must use connection pooling and be cached per job
4. WHEN the same video is requested multiple times THEN cached transcripts must be used when available

### Story 6: Intelligent Error Recovery
**As a** system operator  
**I want** intelligent retry strategies based on error types  
**So that** transient failures are recovered efficiently without wasting resources on permanent failures

**Acceptance Criteria:**
1. WHEN network timeouts occur THEN exponential backoff with jitter must be used
2. WHEN rate limiting is detected THEN longer delays must be applied before retry
3. WHEN authentication errors occur THEN immediate failure must occur without retry
4. WHEN video unavailability is detected THEN no retries must be attempted

### Story 7: Enhanced Monitoring and Alerting
**As a** system operator  
**I want** real-time monitoring with alerting for critical failures  
**So that** production issues are detected and resolved quickly

**Acceptance Criteria:**
1. WHEN transcript success rates drop below threshold THEN alerts must be triggered
2. WHEN proxy health degrades THEN monitoring must detect and alert
3. WHEN processing latency increases significantly THEN performance alerts must fire
4. WHEN circuit breakers trip frequently THEN operational alerts must be sent

### Story 8: Comprehensive Testing
**As a** developer  
**I want** comprehensive integration tests covering all production scenarios  
**So that** production readiness issues are caught before deployment

**Acceptance Criteria:**
1. WHEN proxy enforcement tests run THEN they must validate all external call paths
2. WHEN performance tests run THEN they must validate parallel processing and caching
3. WHEN error recovery tests run THEN they must validate intelligent retry strategies
4. WHEN monitoring tests run THEN they must validate alerting and metrics collection

## Technical Requirements

### Requirement 1: Proxy Enforcement Validation
- **REQ-1.1**: All external HTTP calls must validate proxy availability before execution
- **REQ-1.2**: ENFORCE_PROXY_ALL=1 must be respected by all services without exception
- **REQ-1.3**: ProxyEnforcementError must be raised immediately when enforcement is violated
- **REQ-1.4**: Proxy enforcement validation must occur at HTTP client creation time

### Requirement 2: Centralized Proxy Middleware
- **REQ-2.1**: Create ProxyMiddleware class that all services must use for HTTP clients
- **REQ-2.2**: ProxyMiddleware must provide job-scoped proxy sessions for all client types
- **REQ-2.3**: ProxyMiddleware must handle proxy authentication errors consistently
- **REQ-2.4**: ProxyMiddleware must support requests, httpx, and Playwright client types

### Requirement 3: ASR Service Proxy Integration
- **REQ-3.1**: Deepgram SDK calls must use job-scoped proxy configuration
- **REQ-3.2**: ASR service must respect ENFORCE_PROXY_ALL flag
- **REQ-3.3**: ASR service must handle proxy authentication failures gracefully
- **REQ-3.4**: ASR service must validate proxy configuration during initialization

### Requirement 4: FFmpeg Proxy Standardization
- **REQ-4.1**: Create single ffmpeg header builder function used by all callers
- **REQ-4.2**: FFmpeg operations must use both -http_proxy flag and environment variables
- **REQ-4.3**: FFmpeg proxy configuration must respect ENFORCE_PROXY_ALL flag
- **REQ-4.4**: FFmpeg proxy errors must be handled consistently across all services

### Requirement 5: Comprehensive Testing
- **REQ-5.1**: Add proxy enforcement tests for all external call paths
- **REQ-5.2**: Add ENFORCE_PROXY_ALL validation tests for all services
- **REQ-5.3**: Add proxy authentication failure tests for all services
- **REQ-5.4**: Add job-scoped session correlation tests

## Non-Functional Requirements

### Performance
- **NFR-1**: Proxy middleware must not add more than 5ms overhead per HTTP client creation
- **NFR-2**: Proxy validation must complete within 100ms
- **NFR-3**: Proxy enforcement checks must not impact existing request latency

### Reliability
- **NFR-4**: Proxy enforcement must have 100% coverage across all external calls
- **NFR-5**: Proxy authentication failures must be handled gracefully without service crashes
- **NFR-6**: Proxy configuration changes must not disrupt active sessions

### Security
- **NFR-7**: Proxy credentials must never be logged or exposed in error messages
- **NFR-8**: IP address leaks must be prevented when ENFORCE_PROXY_ALL=1 is enabled
- **NFR-9**: Proxy session correlation must be maintained across all transcript methods

## Success Criteria

### Functional Success
1. **Zero IP address leaks** when ENFORCE_PROXY_ALL=1 is enabled
2. **100% proxy enforcement coverage** across all external HTTP calls
3. **Consistent proxy session correlation** across all transcript methods
4. **Graceful proxy error handling** without service crashes

### Technical Success
1. **All services use centralized proxy middleware** for HTTP client creation
2. **ASR service fully integrated** with proxy configuration
3. **FFmpeg operations standardized** with consistent proxy and header usage
4. **Comprehensive test coverage** for all proxy integration scenarios

### Operational Success
1. **No proxy-related errors** in production logs after deployment
2. **Improved anti-bot protection effectiveness** through consistent proxy usage
3. **Simplified proxy configuration management** through centralized middleware
4. **Faster debugging** of proxy-related issues through consistent error handling

## Out of Scope

- **Performance optimization** of existing proxy logic (separate spec)
- **Proxy provider changes** or additional proxy providers
- **Proxy health monitoring enhancements** (separate spec)
- **Circuit breaker pattern changes** (separate spec)
- **Logging format changes** (separate spec)

## Dependencies

- **proxy_manager.py** - Core proxy management functionality
- **reliability_config.py** - ENFORCE_PROXY_ALL configuration
- **ffmpeg_service.py** - FFmpeg operations requiring proxy integration
- **transcript_service.py** - Main transcript pipeline
- **youtubei_service.py** - Playwright-based transcript capture

## Risks and Mitigations

### Risk 1: Breaking Changes to Existing Services
**Mitigation**: Preserve all public interfaces and add proxy middleware as a wrapper layer

### Risk 2: Performance Impact from Additional Validation
**Mitigation**: Implement lazy validation and cache proxy configuration per job

### Risk 3: Complex Testing Requirements
**Mitigation**: Use mock proxy servers and dependency injection for comprehensive testing

### Risk 4: ASR Service Integration Complexity
**Mitigation**: Use HTTP client monkey-patching for Deepgram SDK proxy support

## Definition of Done

- [ ] All external HTTP calls use centralized proxy middleware
- [ ] ENFORCE_PROXY_ALL=1 is respected by all services
- [ ] ASR service fully integrated with proxy configuration
- [ ] FFmpeg operations use standardized proxy and header configuration
- [ ] Comprehensive proxy integration tests pass
- [ ] No IP address leaks detected in testing
- [ ] All proxy authentication errors handled gracefully
- [ ] Documentation updated with new proxy integration patterns
- [ ] Production deployment successful with zero proxy-related errors