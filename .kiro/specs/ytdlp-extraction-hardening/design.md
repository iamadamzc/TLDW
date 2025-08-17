# Design Document

## Overview

The yt-dlp extraction hardening feature enhances the existing YouTube download pipeline by implementing mandatory A/B testing, removing GEO variability, expanding failure detection patterns, and providing comprehensive diagnostic logging. The design builds upon the existing `download_audio_with_retry` function in `yt_download_helper.py` and the `TranscriptService` class to provide more resilient video extraction.

## Architecture

### Current Architecture
The system currently follows this flow:
1. `TranscriptService._transcribe_audio_with_proxy()` calls `_attempt_ytdlp_download()`
2. `_attempt_ytdlp_download()` calls `download_audio_with_retry()` from `yt_download_helper.py`
3. `download_audio_with_retry()` calls `download_audio_with_fallback()` with retry logic
4. `download_audio_with_fallback()` performs 2-step download (m4a → mp3 fallback)

### Enhanced Architecture
The hardening maintains the same flow but adds:
- **Environment-based GEO control** at startup
- **Mandatory A/B testing** regardless of cookie freshness
- **Enhanced failure detection** with expanded patterns
- **Circuit breaker protection** for repeated failures
- **Comprehensive logging** with standardized keys
- **Runtime toggles** for operational control

## Components and Interfaces

### 1. Environment Configuration Manager
**Location**: `app.py` startup sequence
**Purpose**: Configure GEO and runtime toggles

```python
def _configure_extraction_hardening():
    """Configure extraction hardening environment variables"""
    # Force GEO disable
    os.environ['OXY_DISABLE_GEO'] = 'true'
    
    # Unset PROXY_COUNTRY if present
    if 'PROXY_COUNTRY' in os.environ:
        del os.environ['PROXY_COUNTRY']
        logging.info("PROXY_COUNTRY unset for extraction hardening")
    
    # Log configuration state
    disable_cookies = os.getenv('DISABLE_COOKIES', 'false').lower() == 'true'
    logging.info(f'{{"extraction_hardening": true, "geo_disabled": true, "cookies_disabled": {disable_cookies}}}')
```

### 2. Enhanced Failure Detection
**Location**: `yt_download_helper.py`
**Purpose**: Expand extraction failure pattern matching

```python
def _detect_extraction_failure(error_text: str) -> bool:
    """Enhanced extraction failure detection with modern YouTube error patterns"""
    if not error_text:
        return False
    
    error_lower = error_text.lower()
    extraction_patterns = [
        # Existing patterns
        'unable to extract player response',
        'unable to extract video data', 
        'unable to extract initial player response',
        'video unavailable',
        'this video is not available',
        'extraction failed',
        # New patterns for modern YouTube errors
        'unable to extract yt initial data',
        'failed to parse json',
        'unable to extract player version',
        'failed to extract any player response'
    ]
    
    return any(pattern in error_lower for pattern in extraction_patterns)
```

### 3. Mandatory A/B Testing Logic
**Location**: `yt_download_helper.py` - `download_audio_with_retry()`
**Purpose**: Always attempt without cookies on extraction failure

```python
def download_audio_with_retry(...) -> str:
    """Enhanced retry with mandatory A/B testing"""
    
    # Check environment disable flag
    cookies_disabled = os.getenv('DISABLE_COOKIES', 'false').lower() == 'true'
    
    # Determine attempt 1 cookie usage
    cookies_fresh = _check_cookie_freshness(cookiefile)
    use_cookies_attempt1 = bool(cookiefile and cookies_fresh and not cookies_disabled)
    
    # Log attempt 1 configuration
    if cookiefile and not cookies_fresh:
        logging.info(f"yt_dlp_attempt=1 use_cookies=false reason=stale_cookiefile")
    elif cookies_disabled:
        logging.info(f"yt_dlp_attempt=1 use_cookies=false reason=environment_disabled")
    else:
        logging.info(f"yt_dlp_attempt=1 use_cookies={use_cookies_attempt1}")
    
    # Attempt 1
    attempt_cookiefile = cookiefile if use_cookies_attempt1 else None
    try:
        return download_audio_with_fallback(...)
    except RuntimeError as e:
        error_text = str(e)
        
        # Detect failure types
        cookie_invalid = _detect_cookie_invalidation(error_text)
        extraction_failure = _detect_extraction_failure(error_text)
        
        # Mandatory A/B testing: always retry without cookies on extraction failure
        if extraction_failure or (use_cookies_attempt1 and cookie_invalid):
            # Sleep to reduce throttling
            time.sleep(random.uniform(1.0, 2.0))
            
            # Determine retry reason
            if cookie_invalid:
                retry_reason = "cookie_invalid"
            elif extraction_failure:
                retry_reason = "extraction_failure"
            
            logging.info(f"yt_dlp_attempt=2 use_cookies=false retry_reason={retry_reason}")
            
            try:
                return download_audio_with_fallback(..., cookiefile=None)
            except RuntimeError as e2:
                # Both attempts failed
                combined_error = f"Attempt 1: {error_text} | Attempt 2: {str(e2)}"
                raise RuntimeError(f"{combined_error} - consider updating yt-dlp")
        
        # Single attempt failure
        raise RuntimeError(f"{error_text} - consider updating yt-dlp")
```

### 4. Enhanced Logging System (MVP Focus)
**Location**: `transcript_service.py` - `_log_structured()`
**Purpose**: Lightweight structured logging without persistence complexity

```python
def _log_structured(self, component: str, video_id: str, status: str, 
                   attempt: int, latency_ms: int, method: str, 
                   ua_applied: bool, session_id: str, cookies_used: bool = False):
    """Lightweight structured logging with standardized keys (MVP)"""
    
    log_data = {
        "component": component,
        "video_id": video_id,
        "status": status,
        "yt_dlp_attempt": attempt,
        "latency_ms": latency_ms,
        "method": method,
        "ua_applied": ua_applied,
        "session_id": session_id,
        "use_cookies": cookies_used
    }
    
    # Add reason/retry_reason based on attempt (simple, no state tracking)
    if attempt == 1 and not cookies_used and status == "attempt":
        if os.getenv('DISABLE_COOKIES', 'false').lower() == 'true':
            log_data["reason"] = "environment_disabled"
        else:
            log_data["reason"] = "stale_cookiefile"
    elif attempt == 2:
        # Simple retry reason determination
        log_data["retry_reason"] = "extraction_failure"  # Primary case for MVP
    
    logging.info(json.dumps(log_data))
```

### 5. Proxy Username Masking
**Location**: `yt_download_helper.py`
**Purpose**: Enhanced credential masking for security

```python
def _extract_proxy_username(proxy_url: str) -> str:
    """Enhanced proxy username extraction with better masking"""
    if not proxy_url:
        return "none"
    
    try:
        parsed = urlparse(proxy_url)
        if parsed.username:
            # Mask all but first 3 characters for security
            username = parsed.username
            if len(username) > 6:
                return f"{username[:3]}***{username[-2:]}"
            else:
                return f"{username[:2]}***"
    except Exception:
        pass
    
    return "unknown"
```

## Data Models

### Circuit Breaker State
```python
CircuitBreakerState = {
    "key": "(video_id, user_id)",
    "failures": List[float],  # timestamps
    "is_open": bool,
    "failure_count": int
}
```

### Enhanced Log Entry
```python
LogEntry = {
    "component": str,           # "ytdlp" | "transcript"
    "video_id": str,
    "status": str,              # "attempt" | "ok" | "bot_check" | "extraction_failure"
    "yt_dlp_attempt": int,      # 1 | 2
    "use_cookies": bool,
    "reason": Optional[str],    # For attempt 1: "stale_cookiefile" | "environment_disabled"
    "retry_reason": Optional[str], # For attempt 2: "cookie_invalid" | "extraction_failure"
    "latency_ms": int,
    "method": str,              # "asr" | "transcript_api"
    "ua_applied": bool,
    "session_id": str,
    "proxy_username": str       # Masked username
}
```

### Metrics Counters
```python
MetricsCounters = {
    "attempts_with_cookies": int,
    "attempts_without_cookies": int,
    "extraction_failures": int,
    "cookie_invalid": int,
    "successes": int,
    "circuit_breaker_opens": int
}
```

## Error Handling

### 1. GEO Configuration Validation
- Validate `OXY_DISABLE_GEO=true` is set at startup
- Warn if `PROXY_COUNTRY` is still present
- Log proxy username format to verify no `-cc-` segments

### 2. Cookie-GEO Mismatch Detection
- When cookies are present and GEO is disabled, log WARNING about potential region mismatch
- Include guidance that this may explain edge case failures
- Do not block operation, just provide diagnostic information

### 3. Circuit Breaker Error Handling
- When circuit is open, return clean error message
- Include video_id and user_id in circuit breaker logs
- Provide clear indication that repeated failures triggered protection

### 4. Enhanced Error Messages
- All final errors must include "consider updating yt-dlp" string
- Combine attempt 1 and attempt 2 error messages with " | " separator
- Preserve original yt-dlp error details for debugging

## Testing Strategy

### 1. Unit Tests
**File**: `tests/test_extraction_hardening.py`

```python
def test_detect_extraction_failure_new_patterns():
    """Test new extraction failure patterns"""
    assert _detect_extraction_failure("unable to extract yt initial data")
    assert _detect_extraction_failure("Failed to parse JSON response")
    assert _detect_extraction_failure("Unable to extract player version")
    assert _detect_extraction_failure("Failed to extract any player response")

def test_stale_cookie_logging():
    """Test stale cookie reason logging"""
    # Mock 13-hour old cookie file
    # Verify reason=stale_cookiefile is logged

def test_mandatory_ab_testing():
    """Test extraction failure triggers attempt 2"""
    # Mock attempt 1 failure with "failed to parse json"
    # Verify attempt 2 runs with use_cookies=false
    # Verify retry_reason=extraction_failure is logged
```

### 2. Integration Tests
**File**: `tests/test_extraction_integration.py`

```python
def test_end_to_end_ab_flow():
    """Test complete A/B testing flow"""
    # Test with fresh cookies that cause extraction failure
    # Verify both attempts are logged correctly
    # Verify final error includes "consider updating yt-dlp"

def test_circuit_breaker_protection():
    """Test circuit breaker prevents repeated failures"""
    # Simulate 3 consecutive failures for same video/user
    # Verify circuit opens and blocks further attempts
```

### 3. Canary Tests
**File**: `tests/test_canary_validation.py`

```python
def test_canary_no_cookies_no_geo():
    """Test canary configuration works end-to-end"""
    # Set DISABLE_COOKIES=true and OXY_DISABLE_GEO=true
    # Download one known public video
    # Verify success without cookies or geo targeting
```

### 4. Environment Tests
**File**: `tests/test_environment_config.py`

```python
def test_geo_disable_configuration():
    """Test GEO disable configuration"""
    # Verify OXY_DISABLE_GEO=true is set
    # Verify PROXY_COUNTRY is unset
    # Verify proxy usernames don't contain -cc- segments
```

## MVP Implementation Plan

### Phase 1: Core Hardening (Files: `yt_download_helper.py`)
1. Expand `_detect_extraction_failure()` with new patterns
2. Implement mandatory A/B testing in `download_audio_with_retry()`
3. Add randomized backoff sleep between attempts (1-2s)
4. Enhance error message formatting with "consider updating yt-dlp"

### Phase 2: Environment Configuration (Files: `app.py`)
1. Add `_configure_extraction_hardening()` function to startup
2. Set `OXY_DISABLE_GEO=true` and unset `PROXY_COUNTRY`
3. Add structured JSON logging for yt-dlp version at startup
4. Log cookie/geo state for operational visibility

### Phase 3: Enhanced Logging (Files: `transcript_service.py`)
1. Update `_log_structured()` with standardized keys
2. Add cookie-GEO mismatch warnings (simple, no state)
3. Integrate enhanced logging into `_attempt_ytdlp_download()`
4. Enhance proxy username masking for security

### Phase 4: Testing & Validation
1. Create unit tests for extraction failure pattern detection
2. Test mandatory A/B flow (attempt 1 fails → attempt 2 without cookies)
3. Test logging reasons (stale_cookiefile, environment_disabled)
4. Basic integration test for end-to-end A/B testing

This MVP design maintains backward compatibility while providing enhanced resilience and diagnostic capabilities without introducing new infrastructure dependencies or persistent state management.