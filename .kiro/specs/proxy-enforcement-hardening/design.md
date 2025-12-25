# Proxy Enforcement Hardening - Design Document

## Overview

This design implements comprehensive proxy enforcement across all external HTTP calls in the YouTube transcript pipeline. The solution provides a centralized proxy middleware that ensures consistent proxy usage, prevents IP leaks, and properly enforces the ENFORCE_PROXY_ALL flag.

## Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    ProxyMiddleware                          │
│  ┌─────────────────┬─────────────────┬─────────────────┐   │
│  │   HTTP Client   │   Proxy Config  │   Enforcement   │   │
│  │    Factory      │    Validator    │    Guardian     │   │
│  └─────────────────┴─────────────────┴─────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 Service Integration Layer                   │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐ │
│  │ Transcript  │   YouTubei  │   FFmpeg    │     ASR     │ │
│  │  Service    │   Service   │   Service   │   Service   │ │
│  └─────────────┴─────────────┴─────────────┴─────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   HTTP Client Layer                        │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐ │
│  │  requests   │    httpx    │ Playwright  │   ffmpeg    │ │
│  │   Session   │   Client    │   Context   │   Process   │ │
│  └─────────────┴─────────────┴─────────────┴─────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Single Responsibility**: ProxyMiddleware handles all proxy routing logic
2. **Fail Fast**: Proxy enforcement violations raise errors immediately
3. **Consistent Interface**: All services use the same proxy middleware API
4. **Job Correlation**: Maintain job-scoped proxy sessions across all calls
5. **Backward Compatibility**: Preserve existing public interfaces

## Component Design

### 1. ProxyMiddleware Class

```python
class ProxyMiddleware:
    """Centralized proxy routing for all HTTP clients."""
    
    def __init__(self, proxy_manager: ProxyManager, reliability_config: ReliabilityConfig):
        self.proxy_manager = proxy_manager
        self.enforce_all = reliability_config.enforce_proxy_all
        self._client_cache = {}  # Job-scoped client caching
    
    def get_requests_session(self, job_id: str) -> requests.Session:
        """Get requests session with job-scoped proxy configuration."""
        
    def get_httpx_client(self, job_id: str) -> httpx.AsyncClient:
        """Get httpx client with job-scoped proxy configuration."""
        
    def get_playwright_proxy_config(self, job_id: str) -> Dict[str, str]:
        """Get Playwright proxy configuration for job."""
        
    def get_ffmpeg_proxy_config(self, job_id: str) -> Tuple[Dict[str, str], Optional[str]]:
        """Get ffmpeg proxy environment and -http_proxy flag."""
        
    def validate_enforcement(self, job_id: str) -> None:
        """Validate proxy enforcement requirements."""
```

### 2. ProxyEnforcementError

```python
class ProxyEnforcementError(Exception):
    """Raised when ENFORCE_PROXY_ALL=1 but no proxy is available."""
    
    def __init__(self, service: str, job_id: str, message: str = None):
        self.service = service
        self.job_id = job_id
        default_msg = f"ENFORCE_PROXY_ALL=1 but no proxy available for {service} (job: {job_id})"
        super().__init__(message or default_msg)
```

### 3. Service Integration Pattern

Each service will follow this integration pattern:

```python
class ServiceWithProxyIntegration:
    def __init__(self, proxy_middleware: ProxyMiddleware):
        self.proxy_middleware = proxy_middleware
    
    def make_external_call(self, job_id: str, url: str):
        # Validate enforcement BEFORE creating client
        self.proxy_middleware.validate_enforcement(job_id)
        
        # Get proxy-configured client
        session = self.proxy_middleware.get_requests_session(job_id)
        
        # Make the call
        return session.get(url)
```

## Implementation Details

### 1. Transcript Service Integration

**Current Issue**: Some HTTP calls bypass proxy_manager
```python
# BEFORE (problematic)
response = requests.get(url, headers=headers, timeout=timeout)
```

**Solution**: Use proxy middleware for all calls
```python
# AFTER (fixed)
session = self.proxy_middleware.get_requests_session(job_id)
response = session.get(url, headers=headers, timeout=timeout)
```

**Files to Modify**:
- `transcript_service.py`: Update all HTTP calls to use proxy middleware
- Add proxy middleware injection to TranscriptService constructor

### 2. ASR Service Proxy Integration

**Current Issue**: Deepgram SDK doesn't support proxies directly

**Solution**: HTTP client monkey-patching approach
```python
class ASRService:
    def __init__(self, proxy_middleware: ProxyMiddleware):
        self.proxy_middleware = proxy_middleware
    
    def transcribe_audio(self, job_id: str, audio_path: str) -> str:
        # Validate enforcement
        self.proxy_middleware.validate_enforcement(job_id)
        
        # Get proxy-configured httpx client
        proxy_client = self.proxy_middleware.get_httpx_client(job_id)
        
        # Monkey-patch Deepgram SDK to use our proxy client
        with patch_deepgram_http_client(proxy_client):
            # Use Deepgram SDK normally - it will use our proxy client
            client = deepgram.Deepgram(api_key)
            return client.transcription.sync_prerecorded(audio_path)
```

**Implementation Strategy**:
1. Create `patch_deepgram_http_client` context manager
2. Intercept HTTP calls within Deepgram SDK
3. Route through proxy-configured httpx client
4. Maintain existing Deepgram SDK API

### 3. FFmpeg Proxy Standardization

**Current Issue**: Inconsistent ffmpeg proxy and header configuration

**Solution**: Centralized ffmpeg configuration builder
```python
def build_ffmpeg_command_with_proxy(
    proxy_middleware: ProxyMiddleware,
    job_id: str,
    input_url: str,
    output_path: str,
    cookies: Optional[str] = None
) -> Tuple[List[str], Dict[str, str]]:
    """Build ffmpeg command with standardized proxy and header configuration."""
    
    # Validate enforcement
    proxy_middleware.validate_enforcement(job_id)
    
    # Get proxy configuration
    proxy_env, proxy_url = proxy_middleware.get_ffmpeg_proxy_config(job_id)
    
    # Build standardized headers
    headers = build_ffmpeg_headers(cookies)
    
    # Build command with proxy support
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-headers", headers,
    ]
    
    # Add proxy flag if available
    if proxy_url:
        cmd.extend(["-http_proxy", proxy_url])
    
    cmd.extend(["-i", input_url, output_path])
    
    return cmd, proxy_env
```

**Files to Modify**:
- `ffmpeg_service.py`: Replace existing ffmpeg command building with centralized function
- Extract header building logic into shared function
- Update all ffmpeg callers to use new standardized approach

### 4. YouTubei Service Integration

**Current Issue**: Some HTTP calls in caption track fetching bypass proxy

**Solution**: Ensure all httpx calls use proxy middleware
```python
class DeterministicYouTubeiCapture:
    def __init__(self, job_id: str, video_id: str, proxy_middleware: ProxyMiddleware):
        self.job_id = job_id
        self.video_id = video_id
        self.proxy_middleware = proxy_middleware
    
    async def _fetch_transcript_xml_via_requests(self, base_url: str, cookies: Optional[str] = None) -> Optional[str]:
        # Validate enforcement
        self.proxy_middleware.validate_enforcement(self.job_id)
        
        # Get proxy-configured client
        async with self.proxy_middleware.get_httpx_client(self.job_id) as client:
            response = await client.get(base_url, headers=headers)
            return response.text
```

**Files to Modify**:
- `youtubei_service.py`: Update HTTP calls to use proxy middleware
- Add proxy middleware injection to DeterministicYouTubeiCapture constructor

## Error Handling Strategy

### 1. Enforcement Violations
```python
# Immediate failure when enforcement is violated
try:
    proxy_middleware.validate_enforcement(job_id)
except ProxyEnforcementError as e:
    evt("proxy_enforcement_violation", 
        service=e.service, 
        job_id=e.job_id, 
        outcome="error")
    return ""  # Fail fast, don't attempt the call
```

### 2. Proxy Authentication Failures
```python
# Consistent handling across all services
try:
    response = session.get(url)
except requests.exceptions.ProxyError as e:
    if "407" in str(e):
        evt("proxy_auth_failed", job_id=job_id, outcome="error")
        raise ProxyAuthError(f"Proxy authentication failed: {e}")
    raise
```

### 3. Proxy Unavailability
```python
# Graceful degradation when proxy is unavailable but not enforced
if not proxy_manager.in_use and not enforce_all:
    evt("proxy_unavailable_continuing", job_id=job_id, outcome="warning")
    # Continue without proxy
    session = requests.Session()
else:
    # Use proxy or fail if enforced
    session = proxy_middleware.get_requests_session(job_id)
```

## Testing Strategy

### 1. Unit Tests
- **ProxyMiddleware**: Test all client factory methods
- **Enforcement validation**: Test ENFORCE_PROXY_ALL scenarios
- **Error handling**: Test all proxy error conditions
- **Configuration**: Test proxy configuration parsing and validation

### 2. Integration Tests
- **End-to-end proxy flow**: Test complete transcript pipeline with proxy
- **Service integration**: Test each service's proxy integration
- **Error scenarios**: Test proxy failures and enforcement violations
- **Job correlation**: Test job-scoped proxy session maintenance

### 3. Mock Testing Strategy
```python
class MockProxyServer:
    """Mock proxy server for testing proxy integration."""
    
    def __init__(self, auth_required=True, should_fail=False):
        self.auth_required = auth_required
        self.should_fail = should_fail
        self.requests_received = []
    
    def start(self) -> str:
        """Start mock proxy server and return proxy URL."""
        
    def stop(self):
        """Stop mock proxy server."""
        
    def get_request_log(self) -> List[Dict]:
        """Get log of all requests received by proxy."""
```

### 4. Test Coverage Requirements
- **100% coverage** of proxy enforcement validation paths
- **100% coverage** of ProxyMiddleware public methods
- **All service integration points** tested with proxy scenarios
- **All error conditions** tested with appropriate mocking

## Migration Strategy

### Phase 1: Core Infrastructure (Week 1)
1. Create ProxyMiddleware class with all client factory methods
2. Create ProxyEnforcementError exception class
3. Add comprehensive unit tests for ProxyMiddleware
4. Update reliability_config.py to support new enforcement patterns

### Phase 2: Service Integration (Week 2)
1. Update transcript_service.py to use ProxyMiddleware
2. Update ffmpeg_service.py with standardized proxy configuration
3. Update youtubei_service.py HTTP calls to use ProxyMiddleware
4. Add integration tests for each service

### Phase 3: ASR Integration (Week 3)
1. Implement Deepgram SDK proxy monkey-patching
2. Create ASR service proxy integration
3. Add comprehensive ASR proxy tests
4. Validate end-to-end ASR proxy functionality

### Phase 4: Validation and Deployment (Week 4)
1. Run comprehensive proxy integration test suite
2. Validate ENFORCE_PROXY_ALL functionality across all services
3. Performance testing to ensure no regression
4. Production deployment with monitoring

## Monitoring and Observability

### 1. Structured Logging Events
```python
# Proxy enforcement validation
evt("proxy_enforcement_check", job_id=job_id, service=service, outcome="success")

# Proxy client creation
evt("proxy_client_created", job_id=job_id, client_type="requests", outcome="success")

# Proxy authentication
evt("proxy_auth_attempt", job_id=job_id, outcome="success", duration_ms=duration)

# Enforcement violations
evt("proxy_enforcement_violation", job_id=job_id, service=service, outcome="error")
```

### 2. Metrics Collection
- **Proxy enforcement violations per service**
- **Proxy authentication success/failure rates**
- **Proxy client creation latency**
- **Job-scoped proxy session correlation**

### 3. Health Checks
- **Proxy middleware initialization status**
- **ENFORCE_PROXY_ALL configuration validation**
- **Proxy manager availability**
- **Service proxy integration status**

## Performance Considerations

### 1. Client Caching
- **Job-scoped caching**: Reuse HTTP clients within the same job
- **Connection pooling**: Maintain persistent connections through proxy
- **Resource cleanup**: Properly close clients when jobs complete

### 2. Lazy Validation
- **Deferred enforcement checks**: Only validate when making actual calls
- **Configuration caching**: Cache proxy configuration per job
- **Minimal overhead**: Keep proxy middleware overhead under 5ms

### 3. Memory Management
- **Client lifecycle**: Properly manage HTTP client lifecycles
- **Resource limits**: Limit number of concurrent proxy connections
- **Garbage collection**: Clean up unused proxy sessions

## Security Considerations

### 1. Credential Protection
- **No logging**: Never log proxy credentials or URLs
- **Error sanitization**: Sanitize proxy-related errors before logging
- **Memory safety**: Clear proxy credentials from memory when possible

### 2. IP Leak Prevention
- **Enforcement validation**: Strict validation of ENFORCE_PROXY_ALL flag
- **Fallback blocking**: Block direct connections when enforcement is enabled
- **DNS leak prevention**: Ensure DNS queries also go through proxy

### 3. Session Isolation
- **Job-scoped sessions**: Isolate proxy sessions per job
- **Session rotation**: Support proxy session rotation for long-running jobs
- **Authentication isolation**: Prevent credential sharing between jobs

## Backward Compatibility

### 1. Interface Preservation
- **Public APIs**: All existing public interfaces remain unchanged
- **Configuration**: Existing proxy configuration continues to work
- **Error types**: Existing error types preserved where possible

### 2. Migration Path
- **Gradual rollout**: Services can be migrated one at a time
- **Feature flags**: Use feature flags to control proxy middleware adoption
- **Rollback capability**: Maintain ability to rollback to previous implementation

### 3. Documentation Updates
- **API documentation**: Update all proxy-related API documentation
- **Migration guide**: Provide clear migration guide for developers
- **Troubleshooting**: Update troubleshooting guides with new error patterns