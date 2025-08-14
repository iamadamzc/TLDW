# Design Document

## Overview

This design implements a rotating proxy system to solve YouTube IP blocking issues in the TL;DW application. The solution involves creating a proxy manager that handles multiple proxy servers, implements intelligent rotation logic, and provides transparent integration with the existing transcript fetching service. The system will use AWS Secrets Manager for secure proxy credential storage and implement robust error handling and fallback mechanisms.

## Architecture

### Current Problem Analysis

The application is failing because:
1. App Runner service has a fixed IP address that gets blocked by YouTube
2. High volume of transcript requests from the same IP triggers YouTube's anti-bot protection
3. No retry mechanism or alternative request paths when IP blocking occurs
4. Direct HTTP requests to YouTube's transcript API without any proxy infrastructure

### Solution Architecture

**Proxy Management Layer**
- Centralized proxy manager that handles multiple proxy providers
- Intelligent rotation algorithm that distributes requests across available proxies
- Health monitoring and automatic failover for blocked or failed proxies
- Configurable retry logic with exponential backoff

**Integration Layer**
- Transparent proxy integration with existing transcript_service.py
- Minimal code changes to maintain existing functionality
- Environment-based configuration for development vs production

**Configuration Management**
- Secure proxy credentials storage in AWS Secrets Manager
- Dynamic configuration updates without application restart
- Support for multiple proxy types and providers

## Components and Interfaces

### Proxy Manager Component

#### ProxyManager Class
```python
class ProxyManager:
    def __init__(self):
        self.proxies = []
        self.current_index = 0
        self.failed_proxies = {}
        self.config = self._load_proxy_config()
    
    def get_next_proxy(self) -> dict
    def mark_proxy_failed(self, proxy: dict) -> None
    def is_proxy_available(self, proxy: dict) -> bool
    def health_check_proxy(self, proxy: dict) -> bool
```

#### Proxy Configuration Structure
```python
{
    "proxy_type": "http|https|socks5",
    "host": "proxy.example.com",
    "port": 8080,
    "username": "user",
    "password": "pass",
    "timeout": 30,
    "max_retries": 3
}
```

### AWS Secrets Manager Integration

#### Proxy Secrets Structure
```json
{
    "proxies": [
        {
            "name": "proxy1",
            "type": "http",
            "host": "proxy1.provider.com",
            "port": 8080,
            "username": "username1",
            "password": "password1"
        },
        {
            "name": "proxy2", 
            "type": "socks5",
            "host": "proxy2.provider.com",
            "port": 1080,
            "username": "username2",
            "password": "password2"
        }
    ],
    "settings": {
        "rotation_strategy": "round_robin",
        "health_check_interval": 300,
        "failure_cooldown": 600,
        "max_retries_per_proxy": 3
    }
}
```

### Integration with Transcript Service

#### Modified TranscriptService Class
```python
class TranscriptService:
    def __init__(self):
        self.proxy_manager = ProxyManager() if os.getenv('USE_PROXIES', 'true').lower() == 'true' else None
    
    def get_transcript(self, video_id: str) -> str:
        if self.proxy_manager:
            return self._get_transcript_with_proxy(video_id)
        else:
            return self._get_transcript_direct(video_id)
    
    def _get_transcript_with_proxy(self, video_id: str) -> str:
        max_attempts = 3
        for attempt in range(max_attempts):
            proxy = self.proxy_manager.get_next_proxy()
            try:
                # Use proxy for transcript request
                return self._fetch_with_proxy(video_id, proxy)
            except ProxyError:
                self.proxy_manager.mark_proxy_failed(proxy)
                continue
            except Exception as e:
                # Non-proxy related error
                raise e
        raise Exception("All proxy attempts failed")
```

### Proxy Rotation Strategies

#### Round Robin Strategy
- Cycles through proxies in order
- Simple and predictable distribution
- Good for evenly distributed load

#### Weighted Random Strategy  
- Selects proxies based on success rates
- Better performing proxies get more requests
- Adapts to proxy performance over time

#### Least Recently Used Strategy
- Uses proxy that hasn't been used for longest time
- Helps avoid overusing any single proxy
- Good for avoiding rate limits

## Data Models

### Proxy Configuration Model
```python
@dataclass
class ProxyConfig:
    name: str
    proxy_type: str  # http, https, socks5
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3
    is_active: bool = True
```

### Proxy Health Model
```python
@dataclass
class ProxyHealth:
    proxy_name: str
    is_available: bool
    last_success: datetime
    last_failure: datetime
    failure_count: int
    success_rate: float
    average_response_time: float
```

### Request Statistics Model
```python
@dataclass
class ProxyStats:
    proxy_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    blocked_requests: int
    average_response_time: float
    last_used: datetime
```

## Error Handling

### Proxy-Specific Error Types

```python
class ProxyError(Exception):
    """Base exception for proxy-related errors"""
    pass

class ProxyConnectionError(ProxyError):
    """Proxy connection failed"""
    pass

class ProxyAuthenticationError(ProxyError):
    """Proxy authentication failed"""
    pass

class ProxyTimeoutError(ProxyError):
    """Proxy request timed out"""
    pass

class AllProxiesFailedError(ProxyError):
    """All available proxies have failed"""
    pass
```

### Error Handling Strategy

1. **Proxy Connection Failures**
   - Mark proxy as temporarily unavailable
   - Implement exponential backoff for retry attempts
   - Switch to next available proxy immediately

2. **Authentication Failures**
   - Mark proxy as permanently failed until configuration update
   - Log security alert for potential credential issues
   - Continue with other available proxies

3. **Timeout Errors**
   - Increase timeout for slow proxies
   - Mark proxy as slow but still usable
   - Prefer faster proxies in rotation

4. **YouTube Blocking Detection**
   - Detect HTTP 429, 403, or specific error patterns
   - Mark proxy as blocked with longer cooldown period
   - Implement intelligent retry with different proxy

### Fallback Mechanisms

1. **Direct Connection Fallback**
   - If all proxies fail, attempt direct connection
   - Implement rate limiting for direct connections
   - Log fallback usage for monitoring

2. **Graceful Degradation**
   - Return cached transcripts if available
   - Provide user-friendly error messages
   - Queue failed requests for retry later

## Testing Strategy

### Proxy Manager Testing

1. **Unit Tests**
   - Test proxy rotation algorithms
   - Test failure detection and recovery
   - Test configuration loading and validation

2. **Integration Tests**
   - Test with real proxy providers
   - Test YouTube transcript fetching through proxies
   - Test error handling and fallback scenarios

3. **Load Testing**
   - Test proxy performance under high load
   - Test rotation efficiency with multiple concurrent requests
   - Measure proxy success rates and response times

### Health Monitoring

1. **Proxy Health Checks**
   - Periodic connectivity tests to each proxy
   - Response time monitoring
   - Success rate tracking

2. **Application Monitoring**
   - Track transcript fetch success rates
   - Monitor proxy usage distribution
   - Alert on high failure rates

## Implementation Approach

### Phase 1: Core Proxy Manager
- Implement basic ProxyManager class with round-robin rotation
- Add proxy configuration loading from AWS Secrets Manager
- Implement basic error handling and retry logic

### Phase 2: Integration with Transcript Service
- Modify TranscriptService to use ProxyManager
- Add proxy-aware HTTP request handling
- Implement transparent fallback to direct connections

### Phase 3: Advanced Features
- Add multiple rotation strategies
- Implement proxy health monitoring
- Add comprehensive logging and monitoring

### Phase 4: Production Optimization
- Fine-tune retry logic and timeouts
- Implement advanced error detection
- Add performance monitoring and alerting

## Proxy Provider Recommendations

### Residential Proxy Providers
- **Bright Data (Luminati)**: High-quality residential IPs, good for YouTube
- **Smartproxy**: Cost-effective residential proxies
- **Oxylabs**: Enterprise-grade proxy infrastructure

### Datacenter Proxy Providers
- **ProxyMesh**: Rotating datacenter proxies
- **Storm Proxies**: High-speed datacenter proxies
- **MyPrivateProxy**: Dedicated datacenter proxies

### Configuration Considerations
- Start with 5-10 proxies for initial testing
- Mix of residential and datacenter proxies
- Geographic distribution to avoid regional blocking
- Monitor costs and adjust proxy count based on usage

This design ensures robust proxy rotation while maintaining the existing application architecture and providing clear paths for testing, monitoring, and scaling the proxy infrastructure.
#
# Oxylabs Proxy Configuration

We will use Oxylabs as our proxy provider with the following configuration:

### Connection Details
- **Proxy Host**: `pr.oxylabs.io`
- **Proxy Port**: `7777`
- **Username**: `customer-tldw__BwTQx-cc-US`
- **Password**: `b6AXONDdSBHA3U_`
- **Proxy Type**: HTTP/HTTPS

### Oxylabs Features
- **Rotating Residential Proxies**: Automatic IP rotation on each request
- **Geographic Targeting**: US-based IPs (cc-US in username)
- **High Success Rate**: Enterprise-grade infrastructure optimized for web scraping
- **Session Management**: Sticky sessions available if needed

### Example Configuration
```python
OXYLABS_CONFIG = {
    "name": "oxylabs_residential",
    "type": "http", 
    "host": "pr.oxylabs.io",
    "port": 7777,
    "username": "customer-tldw__BwTQx-cc-US",
    "password": "b6AXONDdSBHA3U_",
    "timeout": 30,
    "max_retries": 3
}
```

### Test Command
```bash
curl 'https://ip.oxylabs.io/location' -U 'customer-tldw__BwTQx-cc-US:b6AXONDdSBHA3U_' -x 'pr.oxylabs.io:7777'
```

This configuration provides automatic IP rotation through Oxylabs' residential proxy network, which should effectively solve the YouTube IP blocking issue.