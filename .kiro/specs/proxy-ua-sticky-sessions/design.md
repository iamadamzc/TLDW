# Design Document: Proxy and User Agent Sticky Sessions

## Overview

This design implements reliable proxy and user agent handling for transcript fetching and yt-dlp operations using sticky sessions. The system will enhance the existing ProxyManager and integrate with UserAgentManager to provide consistent, session-based access to YouTube content while avoiding bot detection and rate limiting.

The design builds upon the existing architecture with ProxyManager, UserAgentManager, TranscriptService, and YouTubeService, adding sticky session functionality with proper credential management, retry logic, and comprehensive logging.

## Architecture

### High-Level Flow

```mermaid
graph TD
    A[Video Processing Request] --> B[Get/Create Sticky Session]
    B --> C[Check Discovery Gate]
    C --> D{Has Captions?}
    D -->|No| E[Skip to ASR Path]
    D -->|Yes/Unknown| F[Attempt Transcript Fetch]
    F --> G{Success?}
    G -->|Yes| H[Cache & Return]
    G -->|No - Bot Check| I[Rotate Session & Retry]
    I --> J{Retry Success?}
    J -->|Yes| H
    J -->|No| E
    E --> K[yt-dlp Audio Download]
    K --> L[Deepgram Transcription]
    L --> M[Cache & Return]
```

### Component Integration

```mermaid
graph LR
    A[TranscriptService] --> B[ProxyManager]
    A --> C[UserAgentManager]
    A --> D[YouTubeService]
    B --> E[ProxySession]
    C --> F[User-Agent Headers]
    D --> G[Caption Discovery]
    E --> H[Oxylabs Proxy]
    F --> I[HTTP Requests]
    F --> J[yt-dlp Process]
```

## Components and Interfaces

### Enhanced ProxySession Class

The existing ProxySession will be enhanced to support the new sticky session format:

```python
class ProxySession:
    def __init__(self, video_id: str, proxy_config: Dict[str, Any]):
        self.video_id = video_id
        self.session_id = self._generate_session_id()
        self.proxy_url = self._build_sticky_proxy_url()
        self.created_at = datetime.now()
        self.last_used = datetime.now()
        self.request_count = 0
        self.failed_count = 0
        self.is_blocked = False
        self.retry_count = 0  # Track retries for this session
    
    def _generate_session_id(self) -> str:
        """Generate deterministic session ID from sanitized video_id"""
        # Sanitize to alphanumeric only, cap at 16 chars for proxy compatibility
        sanitized = re.sub(r'[^a-zA-Z0-9]', '', self.video_id)
        return sanitized[:16]
    
    def _build_sticky_proxy_url(self) -> str:
        """
        Build Oxylabs sticky session URL with proper encoding
        Format: customer-<SUBUSER>-cc-<country>-sessid-<SESSION_ID>
        Note: -cc-<country> is omitted if geo_enabled is False or PROXY_COUNTRY unset
        Hardcoded to residential entrypoint pr.oxylabs.io:7777
        """
        subuser = self.proxy_config.get('username')  # From AWS Secrets Manager
        password = self.proxy_config.get('password')
        geo_enabled = self.proxy_config.get('geo_enabled', False)
        country = self.proxy_config.get('country', 'us')
        
        # Build sticky username - omit -cc-<country> if not geo-enabled
        if geo_enabled and country:
            sticky_username = f"customer-{subuser}-cc-{country}-sessid-{self.session_id}"
        else:
            sticky_username = f"customer-{subuser}-sessid-{self.session_id}"
        
        # URL encode credentials (NEVER log password or full URL)
        encoded_username = quote(sticky_username, safe="")
        encoded_password = quote(password, safe="")
        
        # Build proxy URL with hardcoded residential entrypoint
        proxy_url = f"http://{encoded_username}:{encoded_password}@pr.oxylabs.io:7777"
        
        # Log only the sticky username (no password/full URL)
        logging.debug(f"Built sticky proxy for video {self.video_id}: {sticky_username}@pr.oxylabs.io:7777")
        return proxy_url
```

### Enhanced ProxyManager Class

The ProxyManager will be updated to support the new sticky session requirements:

```python
class ProxyManager:
    def __init__(self):
        self.sessions: Dict[str, ProxySession] = {}
        self.proxy_config = None
        self.subuser = None  # From AWS Secrets Manager
        self.geo_enabled = False  # Account capability flag
        self.enabled = os.getenv('USE_PROXIES', 'true').lower() == 'true'
    
    def get_session_for_video(self, video_id: str) -> Optional[ProxySession]:
        """Get or create sticky session with proper credential format"""
    
    def rotate_session(self, video_id: str) -> Optional[ProxySession]:
        """Create new session with different session ID for retry"""
    
    def _validate_proxy_connectivity(self, session: ProxySession) -> bool:
        """Test proxy with ipinfo.io smoke test"""
```

### UserAgentManager Integration

The UserAgentManager will be enhanced to provide consistent headers:

```python
class UserAgentManager:
    def get_transcript_headers(self) -> Dict[str, str]:
        """Get headers for transcript requests with Accept-Language"""
        user_agent = self.get_user_agent()  # Same UA string for both paths
        return {
            'User-Agent': user_agent,
            'Accept-Language': 'en-US,en;q=0.9'  # Only for transcript HTTP
        }
    
    def get_yt_dlp_user_agent(self) -> str:
        """Get identical User-Agent string for yt-dlp --user-agent parameter"""
        return self.get_user_agent()  # Ensures UA parity between transcript and yt-dlp
```

### Enhanced TranscriptService

The TranscriptService will be updated to use sticky sessions and proper retry logic:

```python
class TranscriptService:
    def get_transcript(self, video_id: str, has_captions: Optional[bool] = None, language: str = "en") -> Optional[str]:
        """
        Main transcript fetching with discovery gate and sticky sessions
        CONTRACT: ASR path uses same session for yt-dlp audio download
        """
        
        # Discovery gate implementation - skip transcript scraping if no captions
        if has_captions is False:
            return self._transcribe_audio_with_proxy(video_id)
        
        # Attempt transcript fetch with sticky session
        session = self.proxy_manager.get_session_for_video(video_id)
        
        try:
            return self._fetch_transcript_with_session(video_id, session, language)
        except YouTubeBlockingError:
            # Single retry with rotated session
            rotated_session = self.proxy_manager.rotate_session(video_id)
            try:
                return self._fetch_transcript_with_session(video_id, rotated_session, language)
            except YouTubeBlockingError:
                # Fall back to ASR with SAME rotated session (critical for consistency)
                return self._transcribe_audio_with_proxy(video_id, rotated_session)
    
    def _transcribe_audio_with_proxy(self, video_id: str, session: Optional[ProxySession] = None) -> Optional[str]:
        """
        ASR fallback using yt-dlp with sticky proxy and 15s timeout
        Uses same session as transcript attempt for IP consistency
        """
        if not session:
            session = self.proxy_manager.get_session_for_video(video_id)
        
        # Configure yt-dlp with sticky proxy and matching User-Agent
        ydl_opts = {
            'proxy': session.proxy_url if session else None,
            'user_agent': self.user_agent_manager.get_yt_dlp_user_agent(),
            'socket_timeout': 15  # Hard timeout to prevent hung jobs
        }
```

## Data Models

### ProxySession Data Structure

```python
@dataclass
class ProxySession:
    video_id: str
    session_id: str  # Sanitized from video_id
    proxy_url: str   # Full encoded URL
    created_at: datetime
    last_used: datetime
    request_count: int
    failed_count: int
    retry_count: int
    is_blocked: bool
    
    # Computed properties
    @property
    def sticky_username(self) -> str:
        """Returns the sticky username without password"""
    
    @property
    def is_expired(self) -> bool:
        """Check if session has exceeded TTL"""
```

### Proxy Configuration Schema

```python
{
    "host": "pr.oxylabs.io",  # Hardcoded residential entrypoint
    "port": 7777,             # Hardcoded residential port
    "username": "tldw__BwTQx",  # Base SUBUSER from Secrets Manager
    "password": "b6AXONDdSBHA3U_",  # URL-encoded or URL-safe password
    "geo_enabled": false,     # If false or PROXY_COUNTRY unset, omit -cc-<country>
    "country": "us",          # Optional, only used if geo_enabled=true
    "session_ttl_minutes": 30,
    "timeout_seconds": 15,    # Hard default for all outbound calls
    "max_retries": 1          # Single rotate+retry, then fall back
}
```

### Structured Log Format

```python
{
    "timestamp": "2024-01-15T10:30:45.123Z",
    "level": "INFO",
    "message": "STRUCTURED_LOG",
    "step": "transcript|ytdlp",
    "video_id": "dQw4w9WgXcQ",
    "session": "dQw4w9WgXcQ123",  # Sanitized session ID
    "ua_applied": true,
    "latency_ms": 1250,
    "status": "ok|blocked_403|blocked_429|bot_check|proxy_407|timeout",
    "attempt": 1,
    "proxy_host": "pr.oxylabs.io"  # No credentials logged
}
```

## Error Handling

### Error Classification

1. **Proxy Authentication Errors (407)**
   - Treat as configuration/encoding error
   - Log as `proxy_407` for instant misconfiguration detection
   - **No retry** - rotation won't help, fail fast

2. **Bot Detection Errors**
   - Response contains "Sign in to confirm you're not a bot"
   - HTTP 403 with specific patterns
   - Log as `bot_check`
   - Single retry with new session

3. **Rate Limiting Errors (429)**
   - HTTP 429 status
   - Log as `blocked_429`
   - Single retry with new session

4. **Network Timeouts**
   - Connection timeouts after 15 seconds (hard default)
   - Log as `timeout`
   - Single retry with same session

### Retry Logic Flow

```mermaid
graph TD
    A[Request Attempt] --> B{Error Type?}
    B -->|407/403/429/Bot| C[Rotate Session]
    B -->|Timeout/Network| D[Keep Session]
    B -->|Success| E[Mark Success]
    C --> F[Single Retry]
    D --> F
    F --> G{Retry Success?}
    G -->|Yes| E
    G -->|No| H[Fall Back to ASR]
    H --> I[Use Same Session for yt-dlp]
```

### Environment Variable Collision Handling

```python
def _handle_env_proxy_collision():
    """Check and warn about HTTP_PROXY/HTTPS_PROXY conflicts"""
    env_proxies = []
    if os.getenv('HTTP_PROXY'):
        env_proxies.append('HTTP_PROXY')
    if os.getenv('HTTPS_PROXY'):
        env_proxies.append('HTTPS_PROXY')
    
    if env_proxies:
        logging.warning(f"Ignoring environment proxy variables {env_proxies} - using sticky proxy configuration")

def _configure_requests_session(session: requests.Session, sticky_proxy_url: str):
    """Explicitly ignore env proxies in requests when sticky URL provided"""
    # Override any environment proxy settings
    session.proxies = {
        'http': sticky_proxy_url,
        'https': sticky_proxy_url
    }
    # Prevent requests from reading HTTP_PROXY/HTTPS_PROXY env vars
    session.trust_env = False
```

## Testing Strategy

### Unit Tests

1. **ProxySession Creation**
   - Test session ID generation from video IDs
   - Test sticky username formatting
   - Test URL encoding of credentials
   - Test geo-enabled vs non-geo accounts

2. **UserAgent Integration**
   - Test header generation for transcript requests
   - Test yt-dlp user agent parameter
   - Test Accept-Language header inclusion

3. **Error Handling**
   - Test retry logic for different error types
   - Test session rotation mechanics
   - Test fallback to ASR path

### Integration Tests (MVP Priority)

1. **Core MVP Tests**
   - Sticky username builder unit test (deterministic session ID generation)
   - One E2E happy path (transcript → yt-dlp with same session)
   - One bot-check retry path (first fails, second succeeds)
   - One 407 fail-fast path (no retry, immediate failure with proxy_407 log)

2. **Session Consistency**
   - Test transcript fetch → yt-dlp using identical session
   - Test discovery gate bypassing transcript attempts
   - Test structured logging shows same session ID

3. **Deferred to Post-MVP**
   - Proxy health scoring/cooldowns
   - IP smoke test endpoint validation
   - Full test suite breadth

### Acceptance Tests (Definition of Done)

1. **Zero 407 Errors**
   - 0 occurrences of proxy_407 across 3 test videos
   - Validates proper credential formatting and encoding

2. **Bot Detection Recovery**
   - If first attempt hits bot-check, second (rotated session) succeeds
   - Otherwise ASR path succeeds with audio downloaded via same sticky session

3. **Session and Logging Consistency**
   - Logs show identical session=<sid> for transcript + yt-dlp per video
   - All logs show ua_applied=true and latency_ms present
   - No passwords or full proxy URLs in logs (only sticky username)

## Implementation Phases

### Phase 1: Core Sticky Session Implementation
- Enhance ProxySession with sticky username generation
- Update ProxyManager credential handling
- Implement AWS Secrets Manager integration
- Add URL encoding and geo-capability detection

### Phase 2: User Agent Integration
- Enhance UserAgentManager for transcript headers
- Add Accept-Language header support
- Integrate yt-dlp user agent parameter
- Add environment variable collision detection

### Phase 3: Retry Logic and Error Handling
- Implement single retry with session rotation
- Add bot detection pattern matching
- Enhance structured logging with latency tracking
- Add credential redaction in logs

### Phase 4: Discovery Gate and Testing
- Implement caption availability checking
- Add ipinfo.io smoke test validation
- Create comprehensive test suite
- Add acceptance test automation

## Security Considerations

### Credential Protection
- Never log full proxy URLs or passwords
- Redact credentials in error messages
- Use URL-safe encoding for special characters
- Store credentials securely in AWS Secrets Manager

### Session Management
- Limit session lifetime to prevent abuse
- Clean up expired sessions from memory
- Use video-specific session IDs to prevent cross-contamination
- Implement reasonable retry limits to prevent loops

### Logging Security
- Log only sanitized usernames (customer-<subuser>-cc-<country>-sessid-<sid>)
- Include latency_ms for performance monitoring
- Avoid logging sensitive request/response content
- Use structured format for automated analysis

## Performance Considerations

### Session Reuse
- Cache sessions per video ID for consistency
- Implement TTL-based cleanup to prevent memory leaks
- Reuse sessions across transcript and yt-dlp operations
- Monitor session success rates for optimization

### Network Optimization
- Use 15-second timeouts to prevent hanging
- Implement single retry to balance reliability and speed
- Apply rate limiting to avoid overwhelming proxies
- Use connection pooling for HTTP requests

### Resource Management
- Clean up temporary audio files after transcription
- Close HTTP sessions properly to prevent leaks
- Monitor proxy session statistics for capacity planning
- Implement graceful degradation when proxies unavailable