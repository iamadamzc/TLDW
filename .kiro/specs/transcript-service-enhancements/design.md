# Design Document

## Overview

This design document outlines comprehensive enhancements to the TL;DW transcript service pipeline, building upon the existing Playwright integration, cookie management, and proxy infrastructure. The enhancements focus on improving reliability through deterministic network interception, multi-client profile support, enhanced cookie integration, and better circuit breaker patterns while maintaining the existing four-stage fallback architecture (yt-api → timedtext → YouTubei → ASR).

The design preserves backward compatibility while adding new capabilities for storage state management, Netscape cookie conversion, proxy-enforced subprocess operations, and comprehensive metrics collection.

## Architecture

### Current Architecture Overview

The transcript service currently implements a four-stage fallback pipeline:

1. **YouTube Transcript API** - Primary method using youtube-transcript-api library
2. **Timed-text extraction** - Direct HTTP requests to YouTube's timedtext endpoints
3. **YouTubei interception** - Playwright-based network interception of internal API calls
4. **ASR fallback** - Audio extraction and speech-to-text processing

**Constraint**: Stage order remains unchanged (yt-api → timedtext → YouTubei → ASR) to maintain backward compatibility and existing fallback logic.

### Enhanced Architecture Components

#### 1. Enhanced Playwright Context Management

**Current State**: Basic Playwright browser context creation with proxy support
**Enhancement**: Automatic storage state loading with fallback to Netscape conversion

```python
class EnhancedPlaywrightManager:
    def __init__(self, cookie_dir: str, proxy_manager: ProxyManager):
        self.cookie_dir = Path(cookie_dir)
        self.proxy_manager = proxy_manager
        self.storage_state_path = self.cookie_dir / "youtube_session.json"
        
    def create_browser_context(self, browser, profile: str = "desktop"):
        """Create browser context with storage state and profile-specific settings"""
        # Check for storage state, convert Netscape if needed
        # Apply profile-specific UA and viewport
        # Load proxy configuration
```

#### 2. Deterministic Network Interception

**Current State**: Response listener-based interception with timing dependencies
**Enhancement**: Route-based interception with Future resolution and timeout handling

```python
class DeterministicTranscriptCapture:
    def __init__(self):
        self.transcript_future = None
        self.timeout_seconds = 25
        
    async def setup_route_interception(self, page):
        """Setup deterministic route interception for /youtubei/v1/get_transcript"""
        await page.route("**/youtubei/v1/get_transcript*", self.handle_transcript_route)
        
    async def handle_transcript_route(self, route):
        """Handle transcript route with Future resolution"""
        # Continue request and capture response
        # Resolve Future with transcript data
        # Handle timeout and fallback scenarios
```

#### 3. Multi-Client Profile System

**Enhancement**: Support for desktop and mobile client profiles with different User-Agent strings and viewports

```python
@dataclass
class ClientProfile:
    name: str
    user_agent: str
    viewport: Dict[str, int]
    
PROFILES = {
    "desktop": ClientProfile(
        name="desktop",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080}
    ),
    "mobile": ClientProfile(
        name="mobile", 
        user_agent="Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        viewport={"width": 390, "height": 844}
    )
}
```

#### 4. Enhanced Cookie Integration Pipeline

**Enhancement**: User-specific cookie preference with S3 integration for timed-text methods

```python
class EnhancedCookieManager:
    def __init__(self, s3_bucket: str = "tldw-cookies-bucket"):
        self.s3_bucket = s3_bucket
        
    def get_cookies_for_request(self, user_id: Optional[str] = None) -> Dict[str, str]:
        """Get cookies with preference order: user S3 > env > file"""
        if user_id:
            s3_cookies = self.load_user_cookies_from_s3(user_id)
            if s3_cookies:
                return s3_cookies
        return self.load_fallback_cookies()
```

#### 5. Circuit Breaker Integration with Retry Logic

**Enhancement**: Tenacity-based retry wrapper with circuit breaker integration

```python
class EnhancedCircuitBreaker(PlaywrightCircuitBreaker):
    def __init__(self):
        super().__init__()
        
    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential_jitter(initial=1, max=10),
        retry=tenacity.retry_if_exception_type((TimeoutError, NavigationError))
    )
    def execute_with_retry(self, operation_func):
        """Execute operation with retry and circuit breaker integration"""
        try:
            result = operation_func()
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise
```

## Components and Interfaces

### 1. Enhanced TranscriptService Class

```python
class TranscriptService:
    def __init__(self, proxy_manager: ProxyManager, cookie_dir: str = "/app/cookies"):
        self.proxy_manager = proxy_manager
        self.cookie_manager = EnhancedCookieManager()
        self.playwright_manager = EnhancedPlaywrightManager(cookie_dir, proxy_manager)
        self.circuit_breaker = EnhancedCircuitBreaker()
        self.current_user_id: Optional[str] = None
        
    def set_current_user_id(self, user_id: str) -> None:
        """Set current user ID for cookie loading"""
        
    def get_transcript(self, video_id: str, user_id: Optional[str] = None) -> str:
        """Main transcript extraction with enhanced fallback pipeline"""
        
    def _get_transcript_via_youtubei_enhanced(self, video_id: str) -> Optional[str]:
        """Enhanced YouTubei extraction with deterministic capture and multi-profile support"""
```

### 2. Enhanced Cookie Generator

```python
class EnhancedCookieGenerator:
    def __init__(self, cookie_dir: str):
        self.cookie_dir = Path(cookie_dir)
        
    def convert_netscape_to_storage_state(self, netscape_path: str) -> str:
        """Convert Netscape cookies.txt to Playwright storage_state.json"""
        
    def sanitize_host_cookies(self, cookies: List[Dict]) -> List[Dict]:
        """Sanitize __Host- cookies for Playwright compatibility"""
        
    def inject_consent_cookies(self, storage_state: Dict) -> Dict:
        """Inject SOCS/CONSENT cookies if missing - run after conversion/warm-up only"""
```

### 3. Enhanced Proxy Manager Extensions

```python
class ProxyManager:
    # Existing methods...
    
    def proxy_env_for_subprocess(self) -> Dict[str, str]:
        """Return environment variables for subprocess proxy configuration"""
        
    def proxy_dict_for(self, client_type: str) -> Optional[Dict[str, str]]:
        """Unified proxy configuration for different client types"""
```

### 4. Enhanced Timed-Text Methods

```python
def _fetch_timedtext_json3_enhanced(
    video_id: str, 
    cookies: Optional[Union[str, Dict[str, str]]] = None,
    proxy_dict: Optional[Dict[str, str]] = None
) -> Optional[str]:
    """Enhanced timed-text JSON3 extraction with user cookie preference"""
    
def _fetch_timedtext_xml_enhanced(
    video_id: str,
    cookies: Optional[Union[str, Dict[str, str]]] = None, 
    proxy_dict: Optional[Dict[str, str]] = None
) -> Optional[str]:
    """Enhanced timed-text XML extraction with user cookie preference"""
```

### 5. Enhanced ASR Audio Extractor

```python
class ASRAudioExtractor:
    def __init__(self, proxy_manager: ProxyManager):
        self.proxy_manager = proxy_manager
        
    def _extract_audio_to_wav_enhanced(self, video_id: str, audio_url: str) -> Optional[str]:
        """Enhanced audio extraction with proxy environment variables"""
        # Set proxy environment for ffmpeg subprocess
        # Ensure proper header formatting and placement
        # Mask sensitive data in logs
```

## Data Models

### 1. Enhanced Storage State Structure

```python
@dataclass
class EnhancedStorageState:
    cookies: List[Dict[str, Any]]
    origins: List[Dict[str, Any]]
    localStorage: List[Dict[str, Any]]
    
    @classmethod
    def from_netscape_cookies(cls, netscape_path: str) -> 'EnhancedStorageState':
        """Create storage state from Netscape cookies file"""
```

### 2. Transcript Extraction Metrics

```python
@dataclass
class TranscriptMetrics:
    video_id: str
    stage: str  # "yt-api", "timedtext", "youtubei", "asr"
    profile: Optional[str]  # "desktop", "mobile"
    proxy_used: bool
    duration_ms: int
    success: bool
    error_type: Optional[str]
    cookie_source: Optional[str]  # "user", "env", "file"
```

### 3. Circuit Breaker State

```python
@dataclass
class CircuitBreakerState:
    failure_count: int
    last_failure_time: Optional[float]
    is_open: bool
    recovery_time_remaining: Optional[int]
```

## Error Handling

### 1. Enhanced Error Classification

The existing error classification system will be extended to handle new error scenarios:

- **Storage State Errors**: Missing or corrupted storage state files
- **Profile Switching Errors**: Failures during client profile transitions
- **Cookie Conversion Errors**: Issues during Netscape to storage state conversion
- **Proxy Environment Errors**: Subprocess proxy configuration failures
- **DOM Fallback Errors**: Issues during DOM-based transcript extraction

### 2. Graceful Degradation Patterns

```python
def handle_storage_state_error(error: Exception, cookie_dir: str) -> None:
    """Handle storage state loading errors with fallback to Netscape conversion"""
    
def handle_profile_switch_error(error: Exception, current_profile: str) -> str:
    """Handle profile switching errors with fallback to next profile"""
    
def handle_dom_fallback_timeout(page: Page, selectors: List[str]) -> Optional[str]:
    """Handle DOM fallback when network interception times out"""
```

### 3. Circuit Breaker Error Handling

Enhanced circuit breaker integration with proper error categorization and recovery mechanisms:

```python
def handle_circuit_breaker_activation(stage: str, remaining_time: int) -> None:
    """Handle circuit breaker activation with appropriate logging and metrics"""
    
def handle_retry_exhaustion(error: Exception, attempt_count: int) -> None:
    """Handle retry exhaustion with circuit breaker failure recording"""
```

## Testing Strategy

### 1. Unit Testing Enhancements

- **Storage State Management**: Test storage state loading, Netscape conversion, and cookie sanitization
- **Deterministic Interception**: Test route-based interception with mock Future resolution
- **Multi-Profile Support**: Test profile switching and UA/viewport configuration
- **Cookie Integration**: Test user cookie preference and S3 loading
- **Circuit Breaker**: Test retry logic and circuit breaker state transitions

### 2. Integration Testing

- **End-to-End Pipeline**: Test complete transcript extraction with all enhancements
- **Proxy Integration**: Test proxy configuration across all components (requests, Playwright, ffmpeg)
- **Cookie Authentication**: Test user-specific cookie loading and authentication
- **Error Recovery**: Test graceful degradation and fallback scenarios

### 3. Performance Testing

- **Stage Duration Metrics**: Measure and validate stage timing improvements
- **Circuit Breaker Behavior**: Test circuit breaker activation and recovery
- **Memory Usage**: Validate browser context reuse and cleanup
- **Concurrent Operations**: Test multiple transcript extractions with shared resources

### 4. Regression Testing

- **Backward Compatibility**: Ensure existing functionality continues working
- **API Interface Stability**: Validate no breaking changes to public interfaces
- **Configuration Compatibility**: Test with existing environment variable configurations
- **Deployment Compatibility**: Validate Docker container and AWS deployment compatibility

### 5. Circuit Breaker Monitoring

- **State Transition Logging**: Validate structured logs are emitted when circuit breaker state changes (open/closed/half-open)
- **Metrics Collection**: Test circuit breaker metrics collection and dashboard integration
- **Recovery Behavior**: Validate circuit breaker recovery after timeout period

## Implementation Phases

### Phase 1: Core Infrastructure Enhancements
1. Enhanced storage state management with Netscape conversion
2. Deterministic network interception with Future-based resolution
3. Multi-client profile system implementation
4. Enhanced cookie integration for timed-text methods

### Phase 2: Reliability and Resilience
1. Circuit breaker integration with retry logic
2. DOM fallback implementation for network timeout scenarios
3. Proxy environment configuration for subprocess operations
4. Enhanced error handling and classification

### Phase 3: Monitoring and Observability
1. Comprehensive metrics collection and structured logging
2. Circuit breaker state monitoring and alerting
3. Performance metrics and dashboard integration
4. Proxy health monitoring with masked credentials

### Phase 4: Testing and Validation
1. Comprehensive test suite implementation
2. Performance benchmarking and optimization
3. Regression testing and backward compatibility validation
4. Production deployment and monitoring setup

## Security Considerations

### 1. Credential Protection
- Maintain existing credential masking in logs
- Secure storage of user cookies in S3 with proper access controls
- Proxy credential protection in subprocess environments

### 2. Cookie Security
- Proper sanitization of __Host- cookies for security compliance
- Secure transmission of cookies between components
- User cookie isolation and access control

### 3. Network Security
- Consistent proxy usage across all network operations
- Secure handling of proxy credentials in environment variables
- Protection against credential leakage in error messages and logs

## Performance Considerations

### 1. Resource Optimization
- Browser context reuse across profile switches
- Efficient storage state loading and caching
- Memory management for concurrent operations

### 2. Network Efficiency
- Deterministic interception to reduce unnecessary waiting
- Optimized retry patterns with exponential backoff and jitter
- Circuit breaker to prevent resource waste on failing operations

### 3. Monitoring and Alerting
- Real-time metrics collection for performance tracking
- Circuit breaker state monitoring for operational awareness with structured logging of state transitions
- Stage duration tracking for performance optimization
- Structured event emission for circuit breaker state changes (open/closed/half-open)