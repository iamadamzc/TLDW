import os
import logging
from typing import Optional, Tuple, Dict, List, Any
import xml.etree.ElementTree as ET
import json
import requests
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import sys
import importlib.util
import inspect
import tempfile
from datetime import datetime
from http.cookies import SimpleCookie
from pathlib import Path
from dataclasses import dataclass
import tenacity

# Import new structured logging components
from log_events import evt, StageTimer
from logging_setup import set_job_ctx, get_job_ctx

# Import enhanced services
from timedtext_service import timedtext_with_job_proxy
from storage_state_manager import get_storage_state_manager
from ffmpeg_service import extract_audio_with_job_proxy
from youtubei_service import extract_transcript_with_job_proxy
from reliability_config import get_reliability_config

from playwright.sync_api import sync_playwright, Page
from playwright.async_api import async_playwright

# --- Version marker for deployed image provenance ---
APP_VERSION = "playwright-fix-2025-08-24T2"

# Startup sanity check to catch local module shadowing
assert (
    importlib.util.find_spec("youtube_transcript_api") is not None
), "youtube-transcript-api not installed"
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
    # New error types in API 1.2.2
    AgeRestricted,
    CookieError,
    CookieInvalid,
    CookiePathInvalid,
    CouldNotRetrieveTranscript,
    FailedToCreateConsentCookie,
    HTTPError,
    InvalidVideoId,
    IpBlocked,
    NotTranslatable,
    PoTokenRequired,
    RequestBlocked,
    TranslationLanguageNotAvailable,
    VideoUnplayable,
    YouTubeDataUnparsable,
    YouTubeRequestFailed,
    YouTubeTranscriptApiException,
)
# Import our compatibility layer
from youtube_transcript_api_compat import get_transcript, list_transcripts, TranscriptApiError

# Guard against local-file shadowing (e.g., youtube_transcript_api.py in repo)
try:
    source_file = inspect.getsourcefile(YouTubeTranscriptApi)
    assert source_file and (
        "youtube_transcript_api" in source_file
    ), f"Shadowed import detected: {source_file}"
    evt("yt_api_import", outcome="success", source_file=source_file)
except Exception as e:
    evt("yt_api_import", outcome="validation_failed", detail=str(e))

from proxy_manager import (
    ProxyManager,
    ProxyAuthError,
    ProxyConfigError,
    generate_correlation_id,
    error_response,
)
from transcript_cache import TranscriptCache
from shared_managers import shared_managers
from error_handler import (
    StructuredLogger,
    handle_transcript_error,
    log_performance_metrics,
    log_resource_cleanup,
)
from transcript_metrics import inc_success, inc_fail, record_stage_metrics, record_circuit_breaker_event, log_successful_transcript_method
from performance_monitor import get_optimized_browser_context, emit_performance_metric
from logging_setup import get_logger
from log_events import StageTimer
from logging_setup import set_job_ctx, get_job_ctx

logger = get_logger(__name__)

_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)


# --- XML Content Validation Helpers (Requirements 3.1, 3.3) ---

def _is_html_response(content: str) -> bool:
    """Detect if response content is HTML rather than XML."""
    content_lower = content.lower().strip()
    
    # Check for HTML doctype or opening tags
    html_indicators = [
        "<!doctype html",
        "<html",
        "<head>",
        "<body>",
        "<title>",
        "<meta ",
        "<script",
        "<style"
    ]
    
    return any(indicator in content_lower for indicator in html_indicators)


def _is_consent_or_captcha_response(content: str) -> bool:
    """Detect consent walls, captcha pages, or other blocking responses."""
    content_lower = content.lower()
    
    # Common consent/blocking patterns
    blocking_patterns = [
        "before you continue to youtube",
        "consent",
        "captcha",
        "verify you are human",
        "automated requests",
        "unusual traffic",
        "access denied",
        "blocked",
        "robot",
        "bot detection"
    ]
    
    return any(pattern in content_lower for pattern in blocking_patterns)


def _validate_xml_content(content: str) -> Tuple[bool, str]:
    """
    Validate XML content before parsing with early blocking detection.
    Returns (is_valid, error_reason).
    """
    if not content or not content.strip():
        return False, "empty_body"
    
    content_stripped = content.strip()
    
    # Early HTML detection
    if _is_html_response(content_stripped):
        if _is_consent_or_captcha_response(content_stripped):
            return False, "html_consent_or_captcha"
        return False, "html_response"
    
    # Check if content starts with XML declaration or root element
    if not content_stripped.startswith(("<", "<?xml")):
        return False, "not_xml_format"
    
    # Basic XML structure validation
    try:
        # Quick validation without full parsing - just check if it's well-formed
        ET.fromstring(content_stripped)
        return True, "valid"
    except ET.ParseError as e:
        return False, f"xml_parse_error: {str(e)[:100]}"
    except Exception as e:
        return False, f"validation_error: {str(e)[:100]}"


class ContentValidationError(Exception):
    """Exception raised when content validation fails, potentially requiring retry with cookies."""
    def __init__(self, message: str, error_reason: str, should_retry_with_cookies: bool = False):
        super().__init__(message)
        self.error_reason = error_reason
        self.should_retry_with_cookies = should_retry_with_cookies


def _validate_and_parse_xml(response, context: str = "unknown") -> ET.Element:
    """
    Validate response content before XML parsing with early blocking detection.
    
    Args:
        response: HTTP response object with .text attribute
        context: Context string for logging (e.g., "timedtext", "captionTracks")
    
    Returns:
        ET.Element: Parsed XML root element
        
    Raises:
        ContentValidationError: If content validation fails (may suggest retry with cookies)
        ET.ParseError: If XML parsing fails after validation
    
    Requirements: 3.1, 3.3
    """
    if not response or not hasattr(response, 'text'):
        evt("xml_validation_failed", context=context, reason="no_response_text")
        raise ContentValidationError("No response text available", "no_response_text")
    
    xml_text = response.text.strip() if response.text else ""
    
    # Validate content before parsing
    is_valid, error_reason = _validate_xml_content(xml_text)
    
    if not is_valid:
        # Determine if we should retry with cookies (Requirement 3.2)
        should_retry = "html_consent_or_captcha" in error_reason or "html_response" in error_reason
        
        # Log specific validation failure types (Requirement 3.3)
        if error_reason == "empty_body":
            evt("timedtext_empty_body", context=context)
        elif "html_consent_or_captcha" in error_reason:
            evt("timedtext_html_or_block", context=context, content_preview=xml_text[:200])
        elif "html_response" in error_reason:
            evt("timedtext_html_or_block", context=context, content_preview=xml_text[:200])
        elif "not_xml_format" in error_reason:
            evt("timedtext_not_xml", context=context, content_preview=xml_text[:120])
        else:
            evt("timedtext_not_xml", context=context, content_preview=xml_text[:120])
        
        raise ContentValidationError(
            f"Content validation failed: {error_reason}", 
            error_reason, 
            should_retry_with_cookies=should_retry
        )
    
    # Parse validated XML
    try:
        return ET.fromstring(xml_text)
    except ET.ParseError as e:
        evt("xml_parse_failed", context=context, error=str(e)[:100])
        raise


@dataclass
class ClientProfile:
    """Client profile configuration for multi-client support."""
    name: str
    user_agent: str
    viewport: Dict[str, int]


# Multi-client profile configurations
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

# Feature flags for operational safety
ENABLE_YT_API = os.getenv("ENABLE_YT_API", "1") == "1"
ENABLE_TIMEDTEXT = os.getenv("ENABLE_TIMEDTEXT", "1") == "1"
ENABLE_YOUTUBEI = (
    os.getenv("ENABLE_YOUTUBEI", "1") == "1"
)  # Enable by default for better fallback
ASR_DISABLED = os.getenv("ASR_DISABLED", "false").lower() in ("1", "true", "yes")
ENABLE_ASR_FALLBACK = (
    not ASR_DISABLED
)  # Enable ASR by default unless explicitly disabled

# Get reliability configuration
_config = get_reliability_config()

# Performance and safety controls from centralized config
PW_NAV_TIMEOUT_MS = _config.playwright_navigation_timeout * 1000  # Convert to milliseconds
USE_PROXY_FOR_TIMEDTEXT = _config.use_proxy_for_timedtext
ENFORCE_PROXY_ALL = _config.enforce_proxy_all
ASR_MAX_VIDEO_MINUTES = _config.asr_max_video_minutes

# Timeout configuration from centralized config
YOUTUBEI_HARD_TIMEOUT = _config.youtubei_hard_timeout
PLAYWRIGHT_NAVIGATION_TIMEOUT = _config.playwright_navigation_timeout
CIRCUIT_BREAKER_RECOVERY = _config.circuit_breaker_recovery
GLOBAL_JOB_TIMEOUT = 240  # 4 minutes maximum job duration (global watchdog)

# Log configuration for debugging deployment issues
def _log_transcript_service_config():
    """Log transcript service configuration for debugging."""
    logger.info("Transcript service configuration:")
    logger.info(f"  Feature flags: YT_API={ENABLE_YT_API}, TIMEDTEXT={ENABLE_TIMEDTEXT}, YOUTUBEI={ENABLE_YOUTUBEI}, ASR={ENABLE_ASR_FALLBACK}")
    logger.info(f"  Reliability config: proxy_enforcement={ENFORCE_PROXY_ALL}, proxy_timedtext={USE_PROXY_FOR_TIMEDTEXT}")
    logger.info(f"  Timeouts: youtubei={YOUTUBEI_HARD_TIMEOUT}s, playwright_nav={PLAYWRIGHT_NAVIGATION_TIMEOUT}s, global_job={GLOBAL_JOB_TIMEOUT}s")
    logger.info(f"  ASR: max_minutes={ASR_MAX_VIDEO_MINUTES}, circuit_breaker_recovery={CIRCUIT_BREAKER_RECOVERY}s")

# Log configuration on module load
_log_transcript_service_config()


class PlaywrightCircuitBreaker:
    """Enhanced circuit breaker pattern for Playwright operations with structured logging."""
    
    def __init__(self):
        self.failure_count = 0
        self.last_failure_time = None
        self.FAILURE_THRESHOLD = 3
        self.RECOVERY_TIME_SECONDS = CIRCUIT_BREAKER_RECOVERY
        self._last_state = "closed"  # Track state changes for logging
    
    def is_open(self) -> bool:
        """Check if circuit breaker is open (blocking operations)."""
        if self.failure_count < self.FAILURE_THRESHOLD:
            self._emit_state_change("closed")
            return False
        
        if self.last_failure_time is None:
            self._emit_state_change("closed")
            return False
        
        time_since_failure = time.time() - self.last_failure_time
        if time_since_failure > self.RECOVERY_TIME_SECONDS:
            # Reset circuit breaker after recovery time
            self.failure_count = 0
            self.last_failure_time = None
            self._emit_state_change("closed")
            evt("circuit_breaker_reset", 
                reason="recovery_timeout",
                recovery_time_seconds=self.RECOVERY_TIME_SECONDS)
            return False
        
        # Check if we're in half-open state (near recovery)
        if time_since_failure > (self.RECOVERY_TIME_SECONDS * 0.8):
            self._emit_state_change("half-open")
        else:
            self._emit_state_change("open")
        
        return True
    
    def get_state(self) -> str:
        """Get current circuit breaker state for monitoring."""
        if self.failure_count < self.FAILURE_THRESHOLD:
            return "closed"
        
        if self.last_failure_time is None:
            return "closed"
        
        time_since_failure = time.time() - self.last_failure_time
        if time_since_failure > self.RECOVERY_TIME_SECONDS:
            return "closed"
        elif time_since_failure > (self.RECOVERY_TIME_SECONDS * 0.8):
            return "half-open"
        else:
            return "open"
    
    def get_recovery_time_remaining(self) -> Optional[int]:
        """Get remaining recovery time in seconds, None if not in recovery."""
        if not self.is_open():
            return None
        
        time_since_failure = time.time() - self.last_failure_time
        remaining = self.RECOVERY_TIME_SECONDS - time_since_failure
        return max(0, int(remaining))
    
    def _emit_state_change(self, new_state: str) -> None:
        """Emit structured log when circuit breaker state changes."""
        if new_state != self._last_state:
            # Use enhanced metrics system for structured logging
            from transcript_metrics import record_circuit_breaker_event
            
            record_circuit_breaker_event(
                event_type="state_change",
                previous_state=self._last_state,
                new_state=new_state,
                failure_count=self.failure_count,
                threshold=self.FAILURE_THRESHOLD
            )
            self._last_state = new_state
    
    def record_success(self) -> None:
        """Reset failure count on successful operation with structured logging."""
        previous_count = self.failure_count
        previous_state = self.get_state()
        
        self.failure_count = 0
        self.last_failure_time = None
        
        if previous_count > 0:
            # Use enhanced metrics system for structured logging
            from transcript_metrics import record_circuit_breaker_event
            
            record_circuit_breaker_event(
                event_type="success_reset",
                previous_failure_count=previous_count,
                previous_state=previous_state
            )
        
        self._emit_state_change("closed")

    def record_failure(self) -> None:
        """Increment failure count and activate if threshold reached with structured logging."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        current_state = self.get_state()

        # Use enhanced metrics system for structured logging
        from transcript_metrics import record_circuit_breaker_event

        if self.failure_count >= self.FAILURE_THRESHOLD:
            record_circuit_breaker_event(
                event_type="activated",
                failure_count=self.failure_count,
                threshold=self.FAILURE_THRESHOLD,
                recovery_time_seconds=self.RECOVERY_TIME_SECONDS,
                state=current_state
            )
        else:
            record_circuit_breaker_event(
                event_type="failure_recorded",
                failure_count=self.failure_count,
                threshold=self.FAILURE_THRESHOLD,
                state=current_state
            )
        
        self._emit_state_change(current_state)


class ProxyAwareCircuitBreaker(PlaywrightCircuitBreaker):
    """Circuit breaker that's more tolerant with proxies"""
    
    def __init__(self):
        super().__init__()
        # More lenient thresholds for proxy environments
        self.FAILURE_THRESHOLD = 5  # Increased from 3
        self.RECOVERY_TIME_SECONDS = 300  # 5 minutes instead of full hour
    
    def get_state(self) -> str:
        """Get current circuit breaker state for monitoring with proxy-aware logic."""
        if self.failure_count < self.FAILURE_THRESHOLD:
            return "closed"
        
        if self.last_failure_time is None:
            return "closed"
        
        time_since_failure = time.time() - self.last_failure_time
        
        # Check time-based states
        if time_since_failure > self.RECOVERY_TIME_SECONDS:
            return "closed"
        elif time_since_failure >= (self.RECOVERY_TIME_SECONDS * 0.8):
            # Half-open state: we're in the 80%-100% recovery window
            return "half-open"
        else:
            return "open"
        
    def record_failure(self) -> None:
        """Record failure but be more tolerant of timeouts with proxies"""
        # Check if we're in half-open state BEFORE updating failure count and time
        current_state = self.get_state()
        is_half_open = (current_state == "half-open")
        
        # Update the failure time first
        self.last_failure_time = time.time()
        
        # Don't penalize as harshly for timeouts when using proxies in half-open state
        # Access ENFORCE_PROXY_ALL dynamically to support test mocking
        from reliability_config import get_reliability_config
        enforce_proxy_all = get_reliability_config().enforce_proxy_all
        
        if enforce_proxy_all and is_half_open:
            self.failure_count += 0.5  # Partial failure count
        else:
            self.failure_count += 1.0
        
        # Get the updated state after failure count and time change
        updated_state = self.get_state()

        # Use enhanced metrics system for structured logging
        from transcript_metrics import record_circuit_breaker_event

        if self.failure_count >= self.FAILURE_THRESHOLD:
            record_circuit_breaker_event(
                event_type="activated",
                failure_count=self.failure_count,
                threshold=self.FAILURE_THRESHOLD,
                recovery_time_seconds=self.RECOVERY_TIME_SECONDS,
                state=updated_state
            )
        else:
            record_circuit_breaker_event(
                event_type="failure_recorded",
                failure_count=self.failure_count,
                threshold=self.FAILURE_THRESHOLD,
                state=updated_state
            )
        
        self._emit_state_change(updated_state)


# Global circuit breaker instance - use proxy-aware version when proxies are enforced
_playwright_circuit_breaker = ProxyAwareCircuitBreaker() if ENFORCE_PROXY_ALL else PlaywrightCircuitBreaker()


def get_circuit_breaker_status() -> Dict[str, Any]:
    """Get current circuit breaker status for monitoring and health checks."""
    return {
        "state": _playwright_circuit_breaker.get_state(),
        "failure_count": _playwright_circuit_breaker.failure_count,
        "failure_threshold": _playwright_circuit_breaker.FAILURE_THRESHOLD,
        "recovery_time_remaining": _playwright_circuit_breaker.get_recovery_time_remaining(),
        "last_failure_time": _playwright_circuit_breaker.last_failure_time,
        "recovery_time_seconds": _playwright_circuit_breaker.RECOVERY_TIME_SECONDS
    }


def _should_retry_youtubei_error(exception):
    """
    Determine if a YouTubei error should trigger a retry.
    
    Implements requirement 17.1 and 17.2:
    - Retry on Playwright navigation timeouts
    - Retry on Playwright interception failures
    - Use exponential backoff with jitter for transient errors
    """
    error_str = str(exception).lower()
    error_type = type(exception).__name__
    
    # Retry on timeout and navigation errors (Requirement 17.1)
    timeout_conditions = [
        "timeout" in error_str,
        "timeouterror" in error_type.lower(),
        "asyncio.timeouterror" in error_type.lower(),
        "concurrent.futures.timeouterror" in error_type.lower(),
        "navigation timeout" in error_str,
        "page.goto" in error_str and "timeout" in error_str,
    ]
    
    # Retry on navigation errors (Requirement 17.1)
    navigation_conditions = [
        "navigation" in error_str,
        "navigationerror" in error_type.lower(),
        "page navigation" in error_str,
        "failed to navigate" in error_str,
        "navigation failed" in error_str,
    ]
    
    # Retry on interception failures (Requirement 17.2)
    interception_conditions = [
        "route" in error_str and ("failed" in error_str or "error" in error_str),
        "interception" in error_str,
        "route handler" in error_str,
        "route.fetch" in error_str,
        "route.fulfill" in error_str,
        "route.continue" in error_str,
    ]
    
    # Retry on network errors that are likely transient
    network_conditions = [
        "net::" in error_str,  # Chromium network errors
        "connection" in error_str,
        "connection refused" in error_str,
        "connection reset" in error_str,
        "connection aborted" in error_str,
        "dns" in error_str,
        "resolve" in error_str,
    ]
    
    # Retry on blocking that might be transient
    blocking_conditions = [
        "blocked" in error_str,
        "rate limit" in error_str,
        "too many requests" in error_str,
        "service unavailable" in error_str,
    ]
    
    # Combine all retry conditions
    all_conditions = (
        timeout_conditions + 
        navigation_conditions + 
        interception_conditions + 
        network_conditions + 
        blocking_conditions
    )
    
    should_retry = any(all_conditions)
    
    if should_retry:
        evt("youtubei_retry_decision", decision="retry", error_type=error_type, error_preview=error_str[:100])
    else:
        evt("youtubei_retry_decision", decision="no_retry", error_type=error_type, error_preview=error_str[:100])
    
    return should_retry


def _log_retry_attempt(retry_state, video_id: str):
    """Log retry attempt with detailed information for monitoring."""
    exception = retry_state.outcome.exception()
    next_sleep = retry_state.next_action.sleep if retry_state.next_action else 0
    
    evt("youtubei_retry_attempt", 
        attempt_number=retry_state.attempt_number,
        error_type=type(exception).__name__,
        error_message=str(exception)[:100],
        next_sleep=next_sleep,
        total_attempts=retry_state.attempt_number)
    
    # Use enhanced metrics system for structured logging
    from transcript_metrics import record_circuit_breaker_event
    
    record_circuit_breaker_event(
        event_type="retry_attempt",
        video_id=video_id,
        attempt_number=retry_state.attempt_number,
        error_type=type(exception).__name__,
        next_sleep_seconds=next_sleep
    )


def _log_retry_completion(retry_state, video_id: str):
    """Log retry completion statistics."""
    if retry_state.outcome.failed:
        evt("youtubei_retry_exhausted", 
            total_attempts=retry_state.attempt_number,
            final_error=str(retry_state.outcome.exception()))
    else:
        evt("youtubei_retry_succeeded", 
            attempts_needed=retry_state.attempt_number)


def _execute_youtubei_with_circuit_breaker(operation_func, video_id: str):
    """
    Execute YouTubei operation with circuit breaker integration and retry logic.
    
    Implements Requirements 17.1-17.6:
    - Exponential backoff with jitter for navigation timeouts
    - 2-3 retry attempts for interception failures  
    - Circuit breaker activation after retry exhaustion
    - Tenacity-based retry logic
    - Complete YouTubei attempt function as single retry unit
    """
    
    # Check circuit breaker before attempting operation
    if _playwright_circuit_breaker.is_open():
        recovery_time = _playwright_circuit_breaker.get_recovery_time_remaining()
        
        # Use enhanced metrics system for structured logging
        from transcript_metrics import record_circuit_breaker_event
        
        record_circuit_breaker_event(
            event_type="skip_operation",
            video_id=video_id,
            state="open",
            recovery_time_remaining=recovery_time,
            reason="circuit_breaker_open"
        )
        return ""
    
    # Define retry wrapper with tenacity (Requirements 17.1, 17.2, 17.3, 17.5)
    @tenacity.retry(
        # Requirement 17.2: 2-3 retry attempts for interception failures
        stop=tenacity.stop_after_attempt(3),
        # Requirement 17.1: Exponential backoff with jitter for navigation timeouts
        wait=tenacity.wait_exponential_jitter(
            initial=1,      # Start with 1 second
            max=10,         # Cap at 10 seconds
            jitter=2        # Add up to 2 seconds of jitter
        ),
        # Retry only on specific error types that are likely transient
        retry=tenacity.retry_if_exception(_should_retry_youtubei_error),
        # Enhanced logging for retry attempts
        before_sleep=lambda retry_state: _log_retry_attempt(retry_state, video_id),
        # Log retry statistics after completion
        after=lambda retry_state: _log_retry_completion(retry_state, video_id)
    )
    def _retry_wrapper():
        return operation_func()
    
    try:
        # Execute with retry logic
        result = _retry_wrapper()
        
        # Record success after retry completion
        if result:  # Only record success if we got a transcript
            _playwright_circuit_breaker.record_success()
            
            # Use enhanced metrics system for structured logging
            from transcript_metrics import record_circuit_breaker_event
            
            record_circuit_breaker_event(
                event_type="post_retry_success",
                video_id=video_id,
                state=_playwright_circuit_breaker.get_state()
            )
        
        return result
        
    except Exception as e:
        # Record failure after retry exhaustion
        _playwright_circuit_breaker.record_failure()
        
        # Use enhanced metrics system for structured logging
        from transcript_metrics import record_circuit_breaker_event
        
        record_circuit_breaker_event(
            event_type="post_retry_failure",
            video_id=video_id,
            error=str(e),
            state=_playwright_circuit_breaker.get_state(),
            failure_count=_playwright_circuit_breaker.failure_count
        )
        return ""


def detect_youtube_blocking(error_message: str, response_content: str = "") -> bool:
    """Detect various forms of YouTube anti-bot blocking."""
    blocking_indicators = [
        "no element found: line 1, column 0",
        "ParseError",
        "XML document structures must start and end within the same entity",
        "not well-formed (invalid token)",
        "syntax error: line 1, column 0"
    ]
    
    error_lower = error_message.lower()
    content_lower = response_content.lower()
    
    # Check error message indicators
    for indicator in blocking_indicators:
        if indicator.lower() in error_lower:
            return True
    
    # Check response content for blocking patterns
    if response_content:
        blocking_content_patterns = [
            "access denied",
            "blocked",
            "captcha",
            "robot",
            "automated"
        ]
        for pattern in blocking_content_patterns:
            if pattern in content_lower:
                return True
    
    return False


def handle_timeout_error(video_id: str, elapsed_time: float, method: str) -> None:
    """Handle timeout errors with circuit breaker integration."""
    evt("timeout_error", method=method, elapsed_time=elapsed_time)
    
    # Update circuit breaker for Playwright timeouts
    if method in ["youtubei", "playwright", "asr"]:
        _playwright_circuit_breaker.record_failure()
    
    # Log timeout details for monitoring
    evt("timeout_event", method=method, elapsed_time=elapsed_time)


def get_user_friendly_error_message(error_classification: str, video_id: str) -> str:
    """Get user-friendly error message for different error types."""
    error_messages = {
        "no_transcript": f"No transcript is available for video {video_id}. The video may not have captions enabled.",
        "video_unavailable": f"Video {video_id} is unavailable. It may be private, deleted, or have an invalid ID.",
        "age_restricted": f"Video {video_id} is age-restricted and requires authentication to access transcripts.",
        "cookie_error": f"Authentication failed for video {video_id}. Please check your cookies or login credentials.",
        "request_blocked": f"Request blocked for video {video_id}. YouTube may be limiting access.",
        "po_token_required": f"Video {video_id} requires additional authentication (PoToken) that is not currently supported.",
        "http_error": f"Network error occurred while accessing video {video_id}. Please try again later.",
        "api_migration_error": f"Internal API error for video {video_id}. Please report this issue.",
        "youtube_blocking": f"YouTube is blocking transcript requests for video {video_id}. Trying alternative methods.",
        "timeout": f"Request timed out for video {video_id}. Trying alternative methods.",
        "translation_error": f"Translation not available for video {video_id} in the requested language.",
        "parsing_error": f"Failed to parse transcript data for video {video_id}. The video format may not be supported.",
        "retrieval_error": f"Could not retrieve transcript for video {video_id}. The transcript may be corrupted or inaccessible.",
        "compat_error": f"Compatibility layer error for video {video_id}. Trying alternative methods.",
        "unknown": f"Unknown error occurred for video {video_id}. Trying alternative methods."
    }
    
    return error_messages.get(error_classification, f"Error processing video {video_id}.")


def classify_transcript_error(error: Exception, video_id: str, method: str) -> str:
    """Classify transcript errors for better debugging and monitoring with API 1.2.2 support."""
    error_type = type(error).__name__
    error_msg = str(error)
    
    # Handle new API 1.2.2 specific errors first
    if isinstance(error, (TranscriptsDisabled, NoTranscriptFound)):
        evt("error_classification", error_type="no_transcript", method=method, detail=error_msg)
        return "no_transcript"
    
    elif isinstance(error, (VideoUnavailable, VideoUnplayable, InvalidVideoId)):
        evt("error_classification", error_type="video_unavailable", method=method, detail=error_msg)
        return "video_unavailable"
    
    elif isinstance(error, AgeRestricted):
        evt("error_classification", error_type="age_restricted", method=method, detail=error_msg)
        return "age_restricted"
    
    elif isinstance(error, (CookieError, CookieInvalid, CookiePathInvalid, FailedToCreateConsentCookie)):
        evt("error_classification", error_type="cookie_error", method=method, detail=error_msg)
        return "cookie_error"
    
    elif isinstance(error, (IpBlocked, RequestBlocked)):
        evt("error_classification", error_type="request_blocked", method=method, detail=error_msg)
        return "request_blocked"
    
    elif isinstance(error, PoTokenRequired):
        evt("error_classification", error_type="po_token_required", method=method, detail=error_msg)
        return "po_token_required"
    
    elif isinstance(error, (HTTPError, YouTubeRequestFailed)):
        evt("error_classification", error_type="http_error", method=method, detail=error_msg)
        return "http_error"
    
    elif isinstance(error, (NotTranslatable, TranslationLanguageNotAvailable)):
        evt("error_classification", error_type="translation_error", method=method, detail=error_msg)
        return "translation_error"
    
    elif isinstance(error, YouTubeDataUnparsable):
        evt("error_classification", error_type="parsing_error", method=method, detail=error_msg)
        return "parsing_error"
    
    elif isinstance(error, CouldNotRetrieveTranscript):
        evt("error_classification", error_type="retrieval_error", method=method, detail=error_msg)
        return "retrieval_error"
    
    elif isinstance(error, YouTubeTranscriptApiException):
        evt("error_classification", error_type="api_error", method=method, detail=error_msg)
        return "api_error"
    
    # Handle compatibility layer errors
    from youtube_transcript_api_compat import TranscriptApiError
    if isinstance(error, TranscriptApiError):
        if "Old API method" in error_msg:
            evt("error_classification", error_type="api_migration_error", method=method, detail=error_msg)
            return "api_migration_error"
        else:
            evt("error_classification", error_type="compat_error", method=method, detail=error_msg)
            return "compat_error"
    
    # Timeout errors (legacy handling)
    if "TimeoutError" in error_type or "timeout" in error_msg.lower():
        handle_timeout_error(video_id, 0.0, method)  # elapsed_time would need to be passed in
        return "timeout"
    
    # YouTube blocking detection (legacy handling)
    if detect_youtube_blocking(error_msg):
        evt("error_classification", error_type="youtube_blocking", method=method, detail=error_msg)
        return "youtube_blocking"
    
    # Authentication issues (legacy handling)
    if any(auth_indicator in error_msg.lower() for auth_indicator in ["unauthorized", "forbidden", "401", "403"]):
        evt("error_classification", error_type="auth_failure", method=method, detail=error_msg)
        return "auth_failure"
    
    # Network issues (legacy handling)
    if any(net_indicator in error_msg.lower() for net_indicator in ["connection", "network", "dns", "resolve"]):
        evt("error_classification", error_type="network_error", method=method, detail=error_msg)
        return "network_error"
    
    # Content issues (legacy handling)
    if any(content_indicator in error_msg.lower() for content_indicator in ["not found", "unavailable", "private", "deleted"]):
        evt("error_classification", error_type="content_unavailable", method=method, detail=error_msg)
        return "content_unavailable"
    
    # Generic error
    evt("error_classification", error_type="unknown", method=method, detail=f"{error_type}: {error_msg}")
    return "unknown"


class ResourceCleanupManager:
    """Ensures proper cleanup of resources on timeout or failure."""
    
    @staticmethod
    def cleanup_playwright_resources(browser, context=None, page=None):
        """Clean up Playwright resources in proper order."""
        try:
            if page:
                page.close()
                evt("resource_cleanup", resource="playwright_page", outcome="success")
        except Exception as e:
            evt("resource_cleanup", resource="playwright_page", outcome="error", detail=str(e))
        
        try:
            if context:
                context.close()
                evt("resource_cleanup", resource="playwright_context", outcome="success")
        except Exception as e:
            evt("resource_cleanup", resource="playwright_context", outcome="error", detail=str(e))
        
        try:
            if browser:
                browser.close()
                evt("resource_cleanup", resource="playwright_browser", outcome="success")
        except Exception as e:
            evt("resource_cleanup", resource="playwright_browser", outcome="error", detail=str(e))
    
    @staticmethod
    def cleanup_temp_files(temp_dir_path: str):
        """Clean up temporary files from ASR processing."""
        try:
            import shutil
            if os.path.exists(temp_dir_path):
                shutil.rmtree(temp_dir_path)
                evt("resource_cleanup", resource="temp_directory", outcome="success", path=temp_dir_path)
        except Exception as e:
            evt("resource_cleanup", resource="temp_directory", outcome="error", path=temp_dir_path, detail=str(e))
    
    @staticmethod
    def cleanup_network_connections(session):
        """Close HTTP sessions and network connections."""
        try:
            if hasattr(session, 'close'):
                session.close()
                evt("resource_cleanup", resource="http_session", outcome="success")
        except Exception as e:
            evt("resource_cleanup", resource="http_session", outcome="error", detail=str(e))


def _resolve_cookie_file_path() -> Optional[str]:
    """Prefer COOKIE_DIR/cookies.txt, then latest .txt in COOKIE_DIR, then legacy COOKIE_LOCAL_DIR, finally COOKIES_FILE_PATH."""
    explicit = os.getenv("COOKIES_FILE_PATH")
    if explicit and os.path.exists(explicit):
        return explicit
    for envvar in ("COOKIE_DIR", "COOKIE_LOCAL_DIR"):
        d = os.getenv(envvar)
        if d and os.path.isdir(d):
            cand = os.path.join(d, "cookies.txt")
            if os.path.isfile(cand):
                return cand
            try:
                txts = [os.path.join(d, f) for f in os.listdir(d) if f.endswith(".txt")]
                if txts:
                    return sorted(
                        txts, key=lambda p: os.path.getmtime(p), reverse=True
                    )[0]
            except Exception:
                pass
    return None


def _cookie_header_from_env_or_file() -> Optional[str]:
    """
    Return a 'name=value; name2=value2' cookie string from COOKIES_HEADER (preferred) or cookies.txt.
    """
    hdr = os.getenv("COOKIES_HEADER")
    if hdr:
        val = hdr.strip()
        if val.lower().startswith("cookie:"):
            val = val.split(":", 1)[1].strip()
        return val or None
    path = _resolve_cookie_file_path()
    if not path or not os.path.exists(path):
        return None
    try:
        pairs = []
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith(("#", " ")):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    name, val = parts[5], parts[6]
                    if name and val:
                        pairs.append(f"{name}={val}")
        return "; ".join(pairs) if pairs else None
    except Exception:
        return None


# S3 Cookie Loading Infrastructure
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False
    evt("s3_availability", available=False, reason="boto3_not_available")

# Cookie configuration
COOKIE_S3_BUCKET = os.getenv("COOKIE_S3_BUCKET")
COOKIE_RETRY_DELAY = 30  # seconds between S3 cookie retry attempts


class CookieSecurityManager:
    """Secure cookie handling with validation and sanitization."""
    
    @staticmethod
    def sanitize_cookie_logs(cookie_dict: Dict[str, str]) -> List[str]:
        """Return only cookie names for logging (never values)."""
        return list(cookie_dict.keys())
    
    @staticmethod
    def validate_cookie_format(cookie_content: str) -> bool:
        """Validate Netscape format before parsing."""
        if not cookie_content.strip():
            return False
        
        lines = cookie_content.strip().split('\n')
        # Check for Netscape format indicators
        has_comment = any(line.startswith('#') for line in lines[:5])
        has_tabs = any('\t' in line for line in lines if not line.startswith('#'))
        
        return has_comment and has_tabs
    
    @staticmethod
    def check_cookie_expiration(cookie_dict: Dict[str, str]) -> Dict[str, bool]:
        """Check which cookies are expired (simplified check)."""
        # For now, assume all cookies are valid - full expiry checking would need timestamp parsing
        return {name: True for name in cookie_dict.keys()}


class EnhancedPlaywrightManager:
    """Enhanced Playwright context management with automatic storage state loading and Netscape conversion."""
    
    def __init__(self, cookie_dir: str = None):
        self.cookie_dir = Path(cookie_dir or os.getenv("COOKIE_DIR", "/app/cookies"))
        self.storage_state_path = self.cookie_dir / "youtube_session.json"
        self.netscape_cookies_path = self.cookie_dir / "cookies.txt"
    
    def ensure_storage_state_available(self) -> bool:
        """
        Ensure storage state is available, converting from Netscape if needed.
        Returns True if storage state is available, False otherwise.
        """
        # Check if storage state already exists
        if self.storage_state_path.exists():
            evt("storage_state_check", outcome="found", path=str(self.storage_state_path))
            return True
        
        # Check if Netscape cookies exist for conversion
        if self.netscape_cookies_path.exists():
            evt("storage_state_conversion", action="attempting", source=str(self.netscape_cookies_path))
            try:
                success = self._convert_netscape_to_storage_state(str(self.netscape_cookies_path))
                if success:
                    evt("storage_state_conversion", outcome="success", target=str(self.storage_state_path))
                    return True
                else:
                    evt("storage_state_conversion", outcome="failed")
                    return False
            except Exception as e:
                evt("storage_state_conversion", outcome="error", detail=str(e))
                return False
        
        # No storage state or Netscape cookies available
        self._log_missing_storage_state_warning()
        return False
    
    def _log_missing_storage_state_warning(self) -> None:
        """Log detailed warning with remediation instructions for missing storage state."""
        logging.warning("=" * 60)
        logging.warning("STORAGE STATE MISSING - REMEDIATION REQUIRED")
        logging.warning("=" * 60)
        logging.warning(f"Expected storage state file: {self.storage_state_path}")
        logging.warning(f"Expected Netscape cookies file: {self.netscape_cookies_path}")
        logging.warning("")
        logging.warning("REMEDIATION OPTIONS:")
        logging.warning("1. Generate storage state using cookie_generator.py:")
        logging.warning("   python cookie_generator.py")
        logging.warning("")
        logging.warning("2. Convert existing Netscape cookies:")
        logging.warning("   python cookie_generator.py --from-netscape /path/to/cookies.txt")
        logging.warning("")
        logging.warning("3. Place Netscape format cookies at:")
        logging.warning(f"   {self.netscape_cookies_path}")
        logging.warning("   (Will be auto-converted on next run)")
        logging.warning("")
        logging.warning("4. Set COOKIE_DIR environment variable if using custom location")
        logging.warning("")
        logging.warning("WITHOUT STORAGE STATE:")
        logging.warning("- Playwright will run without authentication")
        logging.warning("- May encounter GDPR consent walls")
        logging.warning("- Reduced success rate for restricted content")
        logging.warning("=" * 60)
    
    def _convert_netscape_to_storage_state(self, netscape_path: str) -> bool:
        """
        Convert Netscape cookies.txt to Playwright storage_state.json format.
        Returns True if conversion successful, False otherwise.
        """
        try:
            # Read and validate Netscape cookies
            with open(netscape_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            if not CookieSecurityManager.validate_cookie_format(content):
                logging.error(f"Invalid Netscape cookie format in {netscape_path}")
                return False
            
            # Parse Netscape cookies
            cookies = []
            for line in content.strip().split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split('\t')
                if len(parts) >= 7:
                    domain, flag, path, secure, expiry, name, value = parts[:7]
                    
                    # Skip empty names or values
                    if not name or not value:
                        continue
                    
                    # Convert to Playwright cookie format
                    cookie = {
                        "name": name,
                        "value": value,
                        "domain": domain if not domain.startswith('.') else domain[1:],
                        "path": path,
                        "secure": secure.lower() == 'true',
                        "httpOnly": False,  # Default for Netscape format
                    }
                    
                    # Handle expiry (convert to seconds since epoch)
                    try:
                        if expiry and expiry != '0':
                            cookie["expires"] = int(expiry)
                    except (ValueError, TypeError):
                        pass  # Skip invalid expiry dates
                    
                    # Sanitize __Host- cookies for Playwright compatibility
                    if name.startswith('__Host-'):
                        cookie = self._sanitize_host_cookie(cookie)
                    
                    cookies.append(cookie)
            
            if not cookies:
                logging.error("No valid cookies found in Netscape file")
                return False
            
            # Create storage state structure
            storage_state = {
                "cookies": cookies,
                "origins": self._create_minimal_origins_structure(cookies),
                "localStorage": []
            }
            
            # Inject SOCS/CONSENT cookies if missing
            storage_state = self._inject_consent_cookies_if_missing(storage_state)
            
            # Ensure cookie directory exists
            self.cookie_dir.mkdir(parents=True, exist_ok=True)
            
            # Write storage state file
            with open(self.storage_state_path, 'w', encoding='utf-8') as f:
                json.dump(storage_state, f, indent=2)
            
            logging.info(f"Converted {len(cookies)} cookies to storage state format")
            return True
            
        except Exception as e:
            logging.error(f"Failed to convert Netscape cookies: {e}")
            return False
    
    def _sanitize_host_cookie(self, cookie: Dict) -> Dict:
        """
        Sanitize __Host- cookies for Playwright compatibility.
        
        __Host- cookies have strict requirements:
        - Must have secure=True
        - Must have path="/"
        - Must NOT have domain field (use url field instead)
        
        This prevents Playwright __Host- cookie validation errors.
        """
        # Requirement 12.1: Normalize with secure=True
        cookie["secure"] = True
        
        # Requirement 12.2: Normalize with path="/"
        cookie["path"] = "/"
        
        # Requirement 12.3: Remove domain field and use url field instead
        if "domain" in cookie:
            domain = cookie["domain"]
            # Remove leading dot if present (common in cookie files)
            if domain.startswith('.'):
                domain = domain[1:]
            # Store original domain as url for Playwright
            cookie["url"] = f"https://{domain}/"
            del cookie["domain"]
        
        return cookie
    
    def _create_minimal_origins_structure(self, cookies: List[Dict]) -> List[Dict]:
        """Create minimal origins structure for Playwright compatibility."""
        origins = set()
        
        # Extract unique domains from cookies
        for cookie in cookies:
            domain = cookie.get("domain", "")
            if domain:
                # Add both www and non-www variants for YouTube
                if "youtube" in domain.lower():
                    origins.add("https://www.youtube.com")
                    origins.add("https://youtube.com")
                    origins.add("https://m.youtube.com")
                else:
                    origins.add(f"https://{domain}")
        
        # Ensure YouTube origins are always present
        origins.update([
            "https://www.youtube.com",
            "https://youtube.com",
            "https://m.youtube.com"
        ])
        
        return [{"origin": origin, "localStorage": []} for origin in sorted(origins)]
    
    def _inject_consent_cookies_if_missing(self, storage_state: Dict) -> Dict:
        """Inject SOCS/CONSENT cookies if missing to prevent consent dialogs."""
        cookies = storage_state.get("cookies", [])
        
        # Check if SOCS or CONSENT cookies already exist
        has_consent = any(
            cookie.get("name") in ["SOCS", "CONSENT"] 
            for cookie in cookies
        )
        
        if not has_consent:
            logging.info("Injecting CONSENT cookie to prevent consent dialogs")
            
            # Add CONSENT cookie with safe "accepted" value
            consent_cookie = {
                "name": "CONSENT",
                "value": "YES+cb.20210328-17-p0.en+FX+1",
                "domain": "youtube.com",
                "path": "/",
                "secure": True,
                "httpOnly": False,
                "expires": int(time.time()) + (365 * 24 * 60 * 60)  # 1 year from now
            }
            
            cookies.append(consent_cookie)
            storage_state["cookies"] = cookies
            
            logging.info("CONSENT cookie injected successfully")
        
        return storage_state
    
    def create_enhanced_context(self, browser, proxy_dict: Optional[Dict] = None, profile: str = "desktop") -> tuple:
        """
        Create enhanced browser context with automatic storage state loading and profile support.
        Returns (context, storage_state_loaded) tuple.
        """
        # Ensure storage state is available (convert if needed)
        storage_state_available = self.ensure_storage_state_available()
        
        # Get profile configuration
        client_profile = PROFILES.get(profile, PROFILES["desktop"])
        logging.info(f"Creating browser context with profile: {client_profile.name}")
        
        # Prepare context arguments with profile-specific settings
        context_kwargs = {
            "user_agent": client_profile.user_agent,
            "viewport": client_profile.viewport,
            "locale": "en-US",
            "ignore_https_errors": True,
        }
        
        # Add proxy if provided
        if proxy_dict:
            context_kwargs["proxy"] = proxy_dict
        
        # Add storage state if available
        if storage_state_available and self.storage_state_path.exists():
            context_kwargs["storage_state"] = str(self.storage_state_path)
            logging.info(f"Using Playwright storage_state from {self.storage_state_path}")
            
            # Verify storage state contains cookies
            try:
                with open(self.storage_state_path, 'r') as f:
                    state_data = json.load(f)
                    cookie_count = len(state_data.get("cookies", []))
                    logging.info(f"Storage state contains {cookie_count} cookies")
            except Exception as e:
                logging.warning(f"Could not verify storage state contents: {e}")
        
        # Create context
        context = browser.new_context(**context_kwargs)
        
        return context, storage_state_available


def load_user_cookies_from_s3(user_id: int) -> Optional[Dict[str, str]]:
    """
    Load user cookies from S3 bucket with error handling.
    Returns cookie dictionary or None on failure.
    """
    if not S3_AVAILABLE or not COOKIE_S3_BUCKET:
        logging.debug(f"S3 cookie loading not available for user {user_id}")
        return None
    
    try:
        s3_client = boto3.client('s3')
        cookie_key = f"cookies/{user_id}.txt"
        
        logging.info(f"Attempting to load cookies from S3 for user {user_id}")
        
        # Download cookie file from S3
        response = s3_client.get_object(Bucket=COOKIE_S3_BUCKET, Key=cookie_key)
        cookie_content = response['Body'].read().decode('utf-8')
        
        # Validate cookie format
        if not CookieSecurityManager.validate_cookie_format(cookie_content):
            logging.warning(f"Invalid cookie format for user {user_id}")
            return None
        
        # Parse Netscape format cookies
        cookies = {}
        for line in cookie_content.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            parts = line.split('\t')
            if len(parts) >= 7:
                domain, flag, path, secure, expiry, name, value = parts[:7]
                if name and value:
                    cookies[name] = value
        
        if cookies:
            cookie_names = CookieSecurityManager.sanitize_cookie_logs(cookies)
            logging.info(f"Loaded {len(cookies)} cookies from S3 for user {user_id}")
            logging.debug(f"Cookie names for user {user_id}: {cookie_names[:5]}")  # Log first 5 names only
            return cookies
        else:
            logging.warning(f"No valid cookies found in S3 file for user {user_id}")
            return None
            
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        if error_code == 'NoSuchKey':
            logging.info(f"No S3 cookies found for user {user_id}")
        else:
            logging.error(f"S3 error loading cookies for user {user_id}: {error_code}")
        return None
    except NoCredentialsError:
        logging.error(f"S3 credentials not available for user {user_id}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error loading S3 cookies for user {user_id}: {e}")
        return None


def get_user_cookies_with_fallback(user_id: Optional[int] = None) -> Optional[str]:
    """
    Get user cookies with S3-first, environment-fallback strategy.
    Returns cookie header string or None.
    """
    # Strategy 1: Try S3 cookies if user_id provided
    if user_id:
        s3_cookies = load_user_cookies_from_s3(user_id)
        if s3_cookies:
            # Convert dict to cookie header string
            cookie_pairs = [f"{name}={value}" for name, value in s3_cookies.items()]
            cookie_header = "; ".join(cookie_pairs)
            logging.info(f"Using S3 cookies for user {user_id}")
            return cookie_header
        else:
            logging.info(f"S3 cookies not available for user {user_id}, falling back to environment")
    
    # Strategy 2: Fallback to environment/file cookies
    env_cookies = _cookie_header_from_env_or_file()
    if env_cookies:
        logging.info("Using environment/file cookies")
        return env_cookies
    
    logging.info("No cookies available")
    return None


def make_http_session():
    """Create HTTP session with retry logic for timed-text requests"""
    session = requests.Session()
    retry = Retry(
        total=2,
        connect=1,
        read=2,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    # Mount retry adapter for both HTTP and HTTPS URLs
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers["User-Agent"] = _CHROME_UA
    return session


# Global HTTP session for timed-text requests
HTTP = make_http_session()


def _requests_proxies(pm) -> Optional[Dict[str, str]]:
    if not pm:
        return None
    try:
        return pm.proxy_dict_for("requests") or None
    except Exception:
        return None

def _playwright_proxy(pm) -> Optional[Dict[str, str]]:
    if not pm:
        return None
    try:
        return pm.proxy_dict_for("playwright") or None
    except Exception:
        return None

def _ffmpeg_proxy_url(pm) -> Optional[str]:
    """
    Build an http(s) proxy URL for ffmpeg. Prefer requests-style https proxy URL.
    """
    if not pm:
        return None
    try:
        req = pm.proxy_dict_for("requests") or {}
        for key in ("https", "http"):
            url = req.get(key)
            if url:
                return url
    except Exception:
        pass
    try:
        pw = pm.proxy_dict_for("playwright") or {}
        server = pw.get("server")
        if server:
            user = pw.get("username")
            pwd  = pw.get("password")
            if user and pwd and "://" in server:
                scheme, rest = server.split("://", 1)
                return f"{scheme}://{user}:{pwd}@{rest}"
            return server
    except Exception:
        pass
    return None


def validate_config():
    """Validate configuration for ASR only (email is validated in EmailService)."""
    if ENABLE_ASR_FALLBACK and not os.getenv("DEEPGRAM_API_KEY"):
        raise ValueError("DEEPGRAM_API_KEY required when ENABLE_ASR_FALLBACK=1")


# Validate configuration on module load (non-blocking)
try:
    validate_config()
    logging.info("Configuration validation passed")
except ValueError as e:
    logging.warning(f"Configuration validation failed: {e}")
    # Don't fail startup - let health checks handle it


def _fetch_timedtext_xml(
    video_id: str, lang: str, kind=None, cookies=None, proxies=None, timeout_s=15
) -> str:
    """Enhanced timed-text XML extraction with user cookie preference."""
    headers = {"Accept-Language": "en-US,en;q=0.8"}
    params = {"v": video_id, "lang": lang}
    if kind:
        params["kind"] = kind
    
    # Enhanced cookie integration with debug logging
    cookie_source = "none"
    if cookies:
        if isinstance(cookies, str):
            # Convert header string to dict for requests cookies parameter
            cookie_dict = {}
            for pair in cookies.split("; "):
                if "=" in pair:
                    name, value = pair.split("=", 1)
                    cookie_dict[name] = value
            cookies = cookie_dict
            cookie_source = "user"
        elif isinstance(cookies, dict):
            cookie_source = "user"
        logging.debug(f"Using user cookies for timedtext xml extraction: cookie_source={cookie_source}")
    else:
        # Fall back to environment/file cookies
        ck = _cookie_header_from_env_or_file()
        if ck:
            cookie_dict = {}
            for pair in ck.split("; "):
                if "=" in pair:
                    name, value = pair.split("=", 1)
                    cookie_dict[name] = value
            cookies = cookie_dict
            cookie_source = "env"
            logging.debug(f"Using environment/file cookies for timedtext xml extraction: cookie_source={cookie_source}")

    # 1) Try json3 on youtube.com
    r = HTTP.get(
        "https://www.youtube.com/api/timedtext",
        params={**params, "fmt": "json3"},
        headers=headers,
        cookies=cookies,
        proxies=proxies,
        timeout=(5, timeout_s),
        allow_redirects=True,
    )
    if r.status_code == 200 and r.text.strip():
        try:
            data = r.json()
            events = data.get("events", [])
            parts = []
            for ev in events:
                segs = ev.get("segs")
                if not segs:
                    continue
                parts.append("".join(s.get("utf8", "") for s in segs))
            txt = "\n".join(t.strip() for t in parts if t and t.strip())
            if txt:
                return txt
        except json.JSONDecodeError:
            pass  # fall through to XML

    # 2) Try XML on youtube.com
    if r.status_code == 200 and r.text.strip():
        try:
            root = _validate_and_parse_xml(r, "timedtext_xml")
            texts = [
                ("".join(node.itertext())).strip() for node in root.findall(".//text")
            ]
            if texts:
                return "\n".join(texts)
        except ContentValidationError as e:
            # Retry with cookies if blocking is detected (Requirement 3.2)
            if e.should_retry_with_cookies and not cookies:
                evt("timedtext_retry_with_cookies", context="timedtext_xml", reason=e.error_reason)
                # Get cookies from environment/file for retry
                ck = _cookie_header_from_env_or_file()
                if ck:
                    cookie_dict = {}
                    for pair in ck.split("; "):
                        if "=" in pair:
                            name, value = pair.split("=", 1)
                            cookie_dict[name] = value
                    
                    # Retry the same request with cookies
                    r_retry = HTTP.get(
                        "https://www.youtube.com/api/timedtext",
                        params={**params, "fmt": "xml"},
                        headers=headers,
                        cookies=cookie_dict,
                        proxies=proxies,
                        timeout=(5, timeout_s),
                        allow_redirects=True,
                    )
                    if r_retry.status_code == 200 and r_retry.text.strip():
                        try:
                            root_retry = _validate_and_parse_xml(r_retry, "timedtext_xml_retry")
                            texts_retry = [
                                ("".join(node.itertext())).strip() for node in root_retry.findall(".//text")
                            ]
                            if texts_retry:
                                evt("timedtext_retry_success", context="timedtext_xml")
                                return "\n".join(texts_retry)
                        except Exception:
                            pass
        except Exception:
            pass

    # 3) Try alternate host (older endpoint) with XML
    r2 = HTTP.get(
        "https://video.google.com/timedtext",
        params=params,
        headers=headers,
        cookies=cookies,
        proxies=proxies,
        timeout=(5, timeout_s),
        allow_redirects=True,
    )
    if r2.status_code == 200 and r2.text.strip():
        try:
            root = _validate_and_parse_xml(r2, "timedtext_xml_fallback")
            texts = [
                ("".join(node.itertext())).strip() for node in root.findall(".//text")
            ]
            if texts:
                return "\n".join(texts)
        except ContentValidationError as e:
            # Retry with cookies if blocking is detected (Requirement 3.2)
            if e.should_retry_with_cookies and not cookies:
                evt("timedtext_retry_with_cookies", context="timedtext_xml_fallback", reason=e.error_reason)
                # Get cookies from environment/file for retry
                ck = _cookie_header_from_env_or_file()
                if ck:
                    cookie_dict = {}
                    for pair in ck.split("; "):
                        if "=" in pair:
                            name, value = pair.split("=", 1)
                            cookie_dict[name] = value
                    
                    # Retry the same request with cookies
                    r2_retry = HTTP.get(
                        "https://video.google.com/timedtext",
                        params=params,
                        headers=headers,
                        cookies=cookie_dict,
                        proxies=proxies,
                        timeout=(5, timeout_s),
                        allow_redirects=True,
                    )
                    if r2_retry.status_code == 200 and r2_retry.text.strip():
                        try:
                            root_retry = _validate_and_parse_xml(r2_retry, "timedtext_xml_fallback_retry")
                            texts_retry = [
                                ("".join(node.itertext())).strip() for node in root_retry.findall(".//text")
                            ]
                            if texts_retry:
                                evt("timedtext_retry_success", context="timedtext_xml_fallback")
                                return "\n".join(texts_retry)
                        except Exception:
                            pass
        except Exception:
            pass

    return ""


def _fetch_timedtext_json3(video_id: str, proxy_manager=None, cookies=None) -> str:
    """Timedtext with Cookie header first, json3 parse; falls back by lang/kind."""
    headers = {"Accept-Language": "en-US,en;q=0.8"}
    
    # Enhanced cookie integration with user preference over environment/file cookies
    cookie_source = "none"
    if cookies:
        # User cookies provided - highest priority
        if isinstance(cookies, str):
            headers["Cookie"] = cookies
            cookie_source = "user"
        elif isinstance(cookies, dict):
            # Convert dict to header string
            cookie_pairs = [f"{name}={value}" for name, value in cookies.items()]
            headers["Cookie"] = "; ".join(cookie_pairs)
            cookie_source = "user"
        logging.debug(f"Using user cookies for timedtext json3 extraction: cookie_source={cookie_source}")
    else:
        # Fall back to environment/file cookies
        ck = _cookie_header_from_env_or_file()
        if ck:
            headers["Cookie"] = ck
            cookie_source = "env"
            logging.debug(f"Using environment/file cookies for timedtext json3 extraction: cookie_source={cookie_source}")

    languages = ["en", "en-US", "en-GB", "es", "es-ES", "es-419"]
    kinds = [None, "asr"]
    # Respect global enforcement to avoid any direct calls
    proxies = None
    if proxy_manager:
        try:
            if ENFORCE_PROXY_ALL or USE_PROXY_FOR_TIMEDTEXT:
                proxies = proxy_manager.proxy_dict_for("requests")
        except Exception:
            proxies = None

    for lang in languages:
        for kind in kinds:
            params = {"v": video_id, "lang": lang, "fmt": "json3"}
            if kind:
                params["kind"] = kind

            try:
                r = HTTP.get(
                    "https://www.youtube.com/api/timedtext",
                    params=params,
                    headers=headers,
                    proxies=proxies,
                    timeout=(5, 15),
                    allow_redirects=True,
                )
                if r.status_code == 200 and r.text.strip():
                    try:
                        data = r.json()
                        events = data.get("events", [])
                        parts = []
                        for ev in events:
                            segs = ev.get("segs")
                            if not segs:
                                continue
                            parts.append("".join(s.get("utf8", "") for s in segs))
                        txt = "\n".join(t.strip() for t in parts if t and t.strip())
                        if txt:
                            logging.info(
                                f"Timedtext hit: lang={lang}, kind={kind or 'caption'}"
                            )
                            return txt
                    except json.JSONDecodeError:
                        pass
            except Exception:
                continue

    return ""


def _fetch_timedtext(
    video_id: str, lang: str, kind=None, cookies=None, proxies=None, timeout_s=15
) -> str:
    """Backward compatibility wrapper for _fetch_timedtext_xml."""
    return _fetch_timedtext_xml(video_id, lang, kind, cookies, proxies, timeout_s)


def get_transcript_with_cookies_fixed(video_id: str, language_codes: list, user_id: int, proxies=None) -> str:
    """
    Fixed version with proper S3 cookie handling and error propagation.
    This replaces the broken get_transcript_with_cookies function.
    """
    # Load user cookies from S3
    cookie_header = get_user_cookies_with_fallback(user_id)
    if not cookie_header:
        logging.warning(f"No cookies available for user {user_id}")
        return ""
    
    headers = {
        'User-Agent': _CHROME_UA,
        'Accept-Language': 'en-US,en;q=0.8',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': f'https://www.youtube.com/watch?v={video_id}',
        'Cookie': cookie_header
    }
    
    session = requests.Session()
    session.headers.update(headers)
    if ENFORCE_PROXY_ALL:
        # Force proxy for all calls within this session
        from urllib.parse import urlparse
        # Prefer caller-supplied proxies; else derive from global ProxyManager via shared_managers
        if not proxies:
            try:
                proxies = shared_managers.get_proxy_manager().proxy_dict_for("requests")
            except Exception:
                proxies = None
    
    # Try each language code
    for lang in language_codes:
        try:
            # First try to get the transcript list to find available transcripts
            list_url = f'https://www.youtube.com/api/timedtext?type=list&v={video_id}'
            
            response = session.get(list_url, proxies=proxies, timeout=10)
            if response.status_code != 200:
                continue
                
            # Parse the transcript list XML
            try:
                root = _validate_and_parse_xml(response, "transcript_list")
                
                # Find transcripts for the requested language
                transcript_tracks = []
                for track in root.findall('.//track'):
                    track_lang = track.get('lang_code', '')
                    track_kind = track.get('kind', '')
                    if track_lang == lang:
                        transcript_tracks.append({
                            'lang': track_lang,
                            'kind': track_kind,
                            'name': track.get('name', ''),
                            'is_auto': track_kind == 'asr'
                        })
                
                # Prefer manual transcripts over auto-generated
                transcript_tracks.sort(key=lambda x: x['is_auto'])
                
                if not transcript_tracks:
                    continue
                    
                # Try to fetch the transcript
                for track in transcript_tracks:
                    transcript_url = f'https://www.youtube.com/api/timedtext?v={video_id}&lang={track["lang"]}'
                    if track['kind']:
                        transcript_url += f'&kind={track["kind"]}'
                    
                    try:
                        transcript_response = session.get(transcript_url, proxies=proxies, timeout=15)
                        if transcript_response.status_code == 200 and transcript_response.text.strip():
                            try:
                                # Parse the transcript XML
                                transcript_root = _validate_and_parse_xml(transcript_response, "transcript_content_1")
                                texts = []
                                for text_elem in transcript_root.findall('.//text'):
                                    text_content = ''.join(text_elem.itertext()).strip()
                                    if text_content and text_content not in ['[Music]', '[Applause]', '[Laughter]']:
                                        texts.append(text_content)
                                
                                if texts:
                                    transcript_text = '\n'.join(texts)
                                    logging.info(f"Direct HTTP transcript success for {video_id}, lang={lang}, kind={track['kind'] or 'manual'}")
                                    return transcript_text
                            except ContentValidationError as e:
                                # Log validation failure and continue to next track
                                evt("transcript_validation_failed", video_id=video_id, lang=lang, reason=e.error_reason)
                                continue
                                
                    except Exception as e:
                        logging.warning(f"Failed to fetch transcript for {video_id}, lang={lang}: {e}")
                        continue
                        
            except Exception as e:
                logging.warning(f"Failed to parse transcript list for {video_id}: {e}")
                continue
                
        except Exception as e:
            logging.warning(f"Direct HTTP transcript error for {video_id}, lang={lang}: {e}")
            continue
    
    return ""


def get_transcript_with_cookies(video_id: str, language_codes: list, cookies=None, proxies=None) -> str:
    """
    Direct HTTP transcript fetching with cookie support.
    This bypasses the youtube-transcript-api library's cookie limitation.
    """
    headers = {
        'User-Agent': _CHROME_UA,
        'Accept-Language': 'en-US,en;q=0.8',
        'Referer': f'https://www.youtube.com/watch?v={video_id}'
    }
    
    # Add cookies if provided
    if cookies:
        if isinstance(cookies, str):
            headers['Cookie'] = cookies
        elif isinstance(cookies, dict):
            cookie_str = '; '.join([f'{k}={v}' for k, v in cookies.items()])
            headers['Cookie'] = cookie_str
    
    session = requests.Session()
    session.headers.update(headers)
    if ENFORCE_PROXY_ALL:
        if not proxies:
            try:
                proxies = shared_managers.get_proxy_manager().proxy_dict_for("requests")
            except Exception:
                proxies = None
    
    # Try each language code
    for lang in language_codes:
        try:
            # First try to get the transcript list to find available transcripts
            list_url = f'https://www.youtube.com/api/timedtext?type=list&v={video_id}'
            
            response = session.get(list_url, proxies=(proxies or None), timeout=10)
            if response.status_code != 200:
                continue
                
            # Parse the transcript list XML
            try:
                import xml.etree.ElementTree as ET
                root = _validate_and_parse_xml(response, "transcript_list_2")
                
                # Find transcripts for the requested language
                transcript_tracks = []
                for track in root.findall('.//track'):
                    track_lang = track.get('lang_code', '')
                    track_kind = track.get('kind', '')
                    if track_lang == lang:
                        transcript_tracks.append({
                            'lang': track_lang,
                            'kind': track_kind,
                            'name': track.get('name', ''),
                            'is_auto': track_kind == 'asr'
                        })
                
                # Prefer manual transcripts over auto-generated
                transcript_tracks.sort(key=lambda x: x['is_auto'])
                
                if not transcript_tracks:
                    continue
                    
                # Try to fetch the transcript
                for track in transcript_tracks:
                    transcript_url = f'https://www.youtube.com/api/timedtext?v={video_id}&lang={track["lang"]}'
                    if track['kind']:
                        transcript_url += f'&kind={track["kind"]}'
                    
                    try:
                        transcript_response = session.get(transcript_url, proxies=(proxies or None), timeout=15)
                        if transcript_response.status_code == 200 and transcript_response.text.strip():
                            try:
                                # Parse the transcript XML
                                transcript_root = _validate_and_parse_xml(transcript_response, "transcript_content_2")
                                texts = []
                                for text_elem in transcript_root.findall('.//text'):
                                    text_content = ''.join(text_elem.itertext()).strip()
                                    if text_content and text_content not in ['[Music]', '[Applause]', '[Laughter]']:
                                        texts.append(text_content)
                                
                                if texts:
                                    transcript_text = '\n'.join(texts)
                                    logging.info(f"Direct HTTP transcript success for {video_id}, lang={lang}, kind={track['kind'] or 'manual'}")
                                    return transcript_text
                            except ContentValidationError as e:
                                # Log validation failure and continue to next track
                                evt("transcript_validation_failed", video_id=video_id, lang=lang, reason=e.error_reason)
                                continue
                                
                    except Exception as e:
                        logging.warning(f"Failed to fetch transcript for {video_id}, lang={lang}: {e}")
                        continue
                        
            except Exception as e:
                logging.warning(f"Failed to parse transcript list for {video_id}: {e}")
                continue
                
        except Exception as e:
            logging.warning(f"Direct HTTP transcript error for {video_id}, lang={lang}: {e}")
            continue
    
    return ""


def get_captions_via_timedtext(
    video_id: str, proxy_manager=None, cookie_jar=None, user_cookies=None
) -> str:
    """Enhanced timed-text with user cookie preference and robust fallback strategy."""
    languages = ["en", "en-US", "en-GB", "es", "es-ES", "es-419"]
    kinds = [None, "asr"]  # prefer official, then auto
    proxies = _requests_proxies(proxy_manager) if (proxy_manager and (USE_PROXY_FOR_TIMEDTEXT or ENFORCE_PROXY_ALL)) else None

    # Enhanced cookie resolution with user preference over environment/file cookies
    effective_cookies = None
    cookie_source = "none"
    
    if user_cookies:
        # User cookies have highest priority
        effective_cookies = user_cookies
        cookie_source = "user"
        evt("timedtext_cookie_source", cookie_source=cookie_source)
    elif cookie_jar:
        # Legacy cookie_jar parameter (second priority)
        effective_cookies = cookie_jar
        cookie_source = "legacy"
        evt("timedtext_cookie_source", cookie_source=cookie_source)
    
    # First: try JSON3 with enhanced cookie integration
    try:
        txt0 = _fetch_timedtext_json3(video_id, proxy_manager=proxy_manager, cookies=effective_cookies)
        if txt0:
            evt("timedtext_success", method="json3", cookie_source=cookie_source)
            return txt0
    except Exception:
        pass

    # Build effective cookie jar for requests 'cookies=' parameter
    # Priority: user_cookies > cookie_jar > env/file
    if not effective_cookies:
        if cookie_jar is None:
            ck = _cookie_header_from_env_or_file()
            if ck:
                cookie_jar = {
                    p.split("=", 1)[0]: p.split("=", 1)[1]
                    for p in ck.split("; ")
                    if "=" in p
                }
                cookie_source = "env"
                evt("timedtext_cookie_source", cookie_source=cookie_source)
        effective_cookies = cookie_jar

    # When NOT enforcing, try no-proxy first; otherwise skip direct attempts.
    if not ENFORCE_PROXY_ALL:
        for attempt in range(2):
            try:
                for lang in languages:
                    for kind in kinds:
                        txt = _fetch_timedtext_xml(
                            video_id, lang, kind, cookies=effective_cookies, proxies=None, timeout_s=15,
                        )
                        if txt:
                            evt("timedtext_success", method="xml", use_proxy=False, lang=lang, kind=kind or 'caption', cookie_source=cookie_source)
                            return txt
            except (requests.ReadTimeout, requests.ConnectTimeout, requests.RequestException) as e:
                evt("timedtext_attempt", method="xml", use_proxy=False, attempt=attempt + 1, outcome="timeout", detail=str(e))
            time.sleep(1 + attempt)

    # Then proxy if enabled and available
    if proxies:
        for attempt in range(2):
            try:
                for lang in languages:
                    for kind in kinds:
                        txt = _fetch_timedtext_xml(
                            video_id,
                            lang,
                            kind,
                            cookies=effective_cookies,
                            proxies=proxies,
                            timeout_s=15,
                        )
                        if txt:
                            evt("timedtext_success", method="xml", use_proxy=True, lang=lang, kind=kind or 'caption', cookie_source=cookie_source)
                            return txt
            except (
                requests.ReadTimeout,
                requests.ConnectTimeout,
                requests.RequestException,
            ) as e:
                evt("timedtext_attempt", method="xml", use_proxy=True, attempt=attempt + 1, outcome="timeout", detail=str(e))
            time.sleep(1 + attempt)

    evt("timedtext_result", outcome="no_captions")
    return ""


def _try_click_any(page, selectors, wait_after=0):
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            loc.wait_for(state="visible", timeout=3000)
            loc.click()
            if wait_after:
                page.wait_for_timeout(wait_after)
            return True
        except Exception:
            continue
    return False


async def _try_click_any_async(page, selectors, wait_after=0):
    """Async version of _try_click_any for use with async Playwright"""
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            await loc.wait_for(state="visible", timeout=3000)
            await loc.click()
            if wait_after:
                await page.wait_for_timeout(wait_after)
            return True
        except Exception:
            continue
    return False


def _launch_args_with_proxy(proxy_manager):
    args = {"headless": True}
    if proxy_manager:
        cfg = proxy_manager.proxy_dict_for("playwright")
        if cfg:
            args["proxy"] = cfg
            logging.info(f"Playwright proxy -> server={cfg['server']}")
        else:
            logging.info("Playwright proxy -> none")
    return args


def _scroll_until(page, is_ready, max_steps=40, dy=3000, pause_ms=200):
    """Scrolls until is_ready() returns True or steps exhausted."""
    for _ in range(max_steps):
        try:
            if is_ready():
                return True
        except Exception:
            pass
        page.mouse.wheel(0, dy)
        page.wait_for_timeout(pause_ms)
    return False


# Playwright circuit breaker and concurrency control (module globals)
_PW_FAILS = {"count": 0, "until": 0}

# Semaphore for browser concurrency control
import threading
import tempfile
import subprocess

WORKER_CONCURRENCY = int(os.getenv("WORKER_CONCURRENCY", "2"))
_BROWSER_SEM = threading.Semaphore(WORKER_CONCURRENCY)


class ASRAudioExtractor:
    """ASR fallback system with HLS audio extraction and Deepgram transcription"""

    def __init__(self, deepgram_api_key: str, proxy_manager=None):
        self.deepgram_api_key = deepgram_api_key
        self.proxy_manager = proxy_manager
        self.max_video_minutes = ASR_MAX_VIDEO_MINUTES

    def _trigger_asr_playback(self, page) -> None:
        """
        Start video playback to trigger HLS/MPD manifest requests.
        
        Implements Requirements 3.5, 3.6:
        - Use keyboard shortcuts (k key) and video element clicks
        - Add asr_playback_initiated logging before HLS capture
        - Add error handling for playback initiation failures
        
        Args:
            page: Playwright page object (sync)
        """
        try:
            evt("asr_playback_initiated")
            
            # Method 1: Use keyboard shortcut to start playback
            try:
                page.keyboard.press("k")  # YouTube play/pause toggle
                page.wait_for_timeout(1000)  # Give time for playback to start
                evt("asr_playback_keyboard_success")
            except Exception as e:
                evt("asr_playback_keyboard_failed", err=str(e)[:100])
            
            # Method 2: Click video element directly
            try:
                video_locator = page.locator("video").first
                video_locator.wait_for(state="visible", timeout=5000)
                video_locator.click(timeout=3000)
                page.wait_for_timeout(1000)
                evt("asr_playback_click_success")
            except Exception as e:
                evt("asr_playback_click_failed", err=str(e)[:100])
            
            # Method 3: JavaScript-based playback initiation (muted to satisfy autoplay policy)
            try:
                page.evaluate("""
                    () => {
                        const video = document.querySelector('video');
                        if (video) {
                            video.muted = true;
                            video.play().catch(err => console.log('Video play failed:', err));
                        }
                    }
                """)
                page.wait_for_timeout(1000)
                evt("asr_playback_js_success")
            except Exception as e:
                evt("asr_playback_js_failed", err=str(e)[:100])
            
            # Give additional time for HLS/MPD manifest requests to be triggered
            page.wait_for_timeout(2000)
            
        except Exception as e:
            evt("asr_playback_trigger_failed", err=str(e)[:100])
            # Continue anyway - some videos may already be playing or may start playing later

    def extract_and_transcribe(
        self, video_id: str, proxy_manager=None, cookies=None
    ) -> str:
        """
        Extract audio via HLS interception and transcribe with Deepgram.
        Includes cost controls and duration limits.
        """
        evt("asr_start")

        # Step 1: Extract HLS audio URL using Playwright
        audio_url = self._extract_hls_audio_url(video_id, proxy_manager, cookies)
        if not audio_url:
            evt("asr_step", step="hls_extraction", outcome="no_url")
            return ""

        # Step 2: Convert audio to WAV using ffmpeg
        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = os.path.join(temp_dir, "audio.wav")

            if not self._extract_audio_to_wav(audio_url, wav_path):
                evt("asr_step", step="audio_extraction", outcome="failed")
                return ""

            # Step 3: Check duration limits
            duration_minutes = self._get_audio_duration_minutes(wav_path)
            if duration_minutes > self.max_video_minutes:
                evt("asr_step", step="duration_check", outcome="exceeded_limit", 
                    duration_minutes=duration_minutes, limit_minutes=self.max_video_minutes)
                return ""

            # Step 4: Transcribe with Deepgram
            return self._transcribe_with_deepgram(wav_path, video_id)

    def _extract_hls_audio_url(
        self, video_id: str, proxy_manager=None, cookies=None
    ) -> str:
        """Use Playwright to capture HLS audio stream URL"""
        timeout_ms = PW_NAV_TIMEOUT_MS

        # Circuit breaker check
        now_ms = int(time.time() * 1000)
        if not _pw_allowed(now_ms):
            evt("asr_circuit_breaker", state="active")
            return ""

        # Non-fatal preflight check: log only
        try:
            if not youtube_reachable():
                evt("asr_preflight", outcome="failed", detail="YouTube not reachable")
        except Exception as e:
            evt("asr_preflight", outcome="error", detail=str(e))

        captured_url = {"url": None}

        def capture_m3u8_response(response):
            """Capture audio stream URLs: HLS (.m3u8), DASH (.mpd), or direct 'videoplayback?mime=audio'."""
            url = response.url.lower()
            if (url.endswith(".m3u8") or ".m3u8?" in url) and (
                "audio" in url or "mime=audio" in url
            ):
                captured_url["url"] = response.url
                evt("asr_capture", stream_type="hls", url_preview=response.url[:140])
            elif url.endswith(".mpd") or ".mpd?" in url:
                # DASH manifest; ffmpeg can handle most mpd manifests
                if "audio" in url or "mime=audio" in url:
                    captured_url["url"] = response.url
                    evt("asr_capture", stream_type="dash", url_preview=response.url[:140])
            elif "videoplayback" in url and (
                "mime=audio" in url or "mime=audio%2F" in url
            ):
                captured_url["url"] = response.url
                evt("asr_capture", stream_type="direct", url_preview=response.url[:140])

        proxy_strategies = []
        if ENFORCE_PROXY_ALL:
            pw_proxy_config = _playwright_proxy(proxy_manager)
            if pw_proxy_config:
                proxy_strategies = [pw_proxy_config]
            else:
                proxy_strategies = []  # no valid proxy -> skip attempts
        else:
            proxy_strategies = [None]
            pw_proxy_config = _playwright_proxy(proxy_manager)
            if pw_proxy_config:
                proxy_strategies.append(pw_proxy_config)

        with _BROWSER_SEM:
            with sync_playwright() as p:
                for strategy_index, pw_proxy in enumerate(proxy_strategies):
                    browser = None
                    try:
                        strategy_name = "direct" if pw_proxy is None else "proxy"
                        evt("asr_strategy", strategy=strategy_name)
                        
                        browser = p.chromium.launch(
                            headless=True,
                            proxy=pw_proxy,
                            args=[
                                "--no-sandbox",
                                "--autoplay-policy=no-user-gesture-required",
                            ],
                        )
                        ctx = browser.new_context(locale="en-US")
                        # Pre-bypass consent wall
                        try:
                            ctx.add_cookies(
                            [
                                {
                                    "name": "CONSENT",
                                    "value": "YES+1",
                                    "domain": ".youtube.com",
                                    "path": "/",
                                },
                                {
                                    "name": "CONSENT",
                                    "value": "YES+1",
                                    "domain": ".m.youtube.com",
                                    "path": "/",
                                },
                            ]
                        )
                        except Exception:
                            pass

                        if cookies:
                            pw_cookies = _convert_cookiejar_to_playwright_format(cookies)
                            if pw_cookies:
                                ctx.add_cookies(pw_cookies)

                        page = ctx.new_page()
                        page.set_default_navigation_timeout(timeout_ms)
                        # Set up HLS/MPD listeners BEFORE navigation and playback (Requirement 3.5, 3.6)
                        page.on("response", capture_m3u8_response)

                        # Try desktop first, then mobile, then embed with retry logic
                        urls = [
                            f"https://www.youtube.com/watch?v={video_id}&hl=en",
                            f"https://m.youtube.com/watch?v={video_id}&hl=en",
                            f"https://www.youtube.com/embed/{video_id}?autoplay=1&hl=en",
                        ]

                        for url_index, url in enumerate(urls):
                            max_retries = 2
                            for retry in range(max_retries):
                                try:
                                    # Exponential backoff for retries
                                    if retry > 0:
                                        backoff_time = (2 ** retry) * 1000  # 2s, 4s, etc.
                                        logging.info(f"ASR retry {retry + 1} for {url} after {backoff_time}ms backoff")
                                        page.wait_for_timeout(backoff_time)
                                    
                                    # YouTube rarely reaches "networkidle"; use domcontentloaded to avoid timeouts
                                    page.goto(url, wait_until="domcontentloaded", timeout=90000)  # Increased timeout

                                    # Handle consent dialog immediately after page load
                                    try:
                                        consent_selectors = [
                                            'button:has-text("Accept all")',
                                            'button:has-text("I agree")',
                                            'button:has-text("Acepto todo")',
                                            '[aria-label*="Accept"]'
                                        ]
                                        for selector in consent_selectors:
                                            try:
                                                loc = page.locator(selector).first
                                                loc.wait_for(state="visible", timeout=3000)
                                                loc.click()
                                                page.wait_for_timeout(2000)
                                                logging.info(f"ASR: Accepted consent with {selector}")
                                                break
                                            except Exception:
                                                continue
                                    except Exception:
                                        pass  # Consent handling is optional

                                    # Trigger video playback immediately after page navigation (Requirements 3.5, 3.6)
                                    # HLS/MPD listeners are already active from page setup above
                                    try:
                                        self._trigger_asr_playback(page)
                                    except Exception as playback_error:
                                        # Log playback initiation failure but continue with capture attempt
                                        evt("asr_playback_initiation_error", 
                                            error_type=type(playback_error).__name__,
                                            error=str(playback_error)[:100])
                                        logging.warning(f"ASR playback initiation failed: {playback_error}")
                                        # Continue anyway - HLS/MPD streams might still be captured
                                    
                                    # Give more time for stream/manifest to load
                                    page.wait_for_timeout(8000)  # Increased from 5s to 8s

                                    if captured_url["url"]:
                                        _pw_register_success()
                                        logging.info(f"ASR audio URL captured successfully on attempt {retry + 1}")
                                        return captured_url["url"]
                                    
                                    # If no URL captured, this attempt failed
                                    if retry < max_retries - 1:
                                        logging.warning(f"ASR attempt {retry + 1} failed to capture audio URL for {url}, retrying...")
                                        continue
                                    else:
                                        logging.warning(f"ASR failed to capture audio URL for {url} after {max_retries} attempts")
                                        break

                                except Exception as e:
                                    error_type = type(e).__name__
                                    if "TimeoutError" in error_type:
                                        logging.warning(f"ASR timeout on attempt {retry + 1} for {url}: {e}")
                                        if retry < max_retries - 1:
                                            continue
                                        else:
                                            _pw_register_timeout(now_ms)
                                    else:
                                        logging.warning(f"ASR error on attempt {retry + 1} for {url}: {e}")
                                        if retry < max_retries - 1:
                                            continue
                                    break

                        # If we captured a URL with this strategy, return it
                        if captured_url["url"]:
                            _pw_register_success()
                            logging.info(f"ASR audio URL captured using {strategy_name} strategy")
                            return captured_url["url"]

                    except Exception as e:
                        strategy_name = "direct" if pw_proxy is None else "proxy"
                        if "TimeoutError" in str(type(e)):
                            logging.warning(f"ASR {strategy_name} strategy timeout: {e}")
                            _pw_register_timeout(now_ms)
                        else:
                            logging.warning(f"ASR {strategy_name} strategy error: {e}")

                    finally:
                        try:
                            if browser:
                                browser.close()
                        except Exception:
                            pass
                    
                    # If this wasn't the last strategy, continue to next one
                    if strategy_index < len(proxy_strategies) - 1:
                        logging.info(f"ASR {strategy_name} strategy failed, trying next strategy")
                        continue

        return ""

    def _build_ffmpeg_headers(self, headers: list) -> str:
        """
        Build FFmpeg headers string with proper CRLF formatting and validation.
        
        Requirements:
        - 9.1: CRLF-joined header string formatting
        - 9.4: Validation to prevent "No trailing CRLF" errors
        """
        if not headers:
            return ""
        
        try:
            # Join headers with proper CRLF (actual \r\n characters, not escaped strings)
            headers_str = "\r\n".join(headers)
            
            # Ensure trailing CRLF to prevent "No trailing CRLF" errors
            if not headers_str.endswith("\r\n"):
                headers_str += "\r\n"
            
            # Validate that we have proper CRLF formatting
            if "\\r\\n" in headers_str:
                logging.error("Headers contain escaped CRLF sequences instead of actual CRLF characters")
                return ""
            
            # Validate that headers end with CRLF
            if not headers_str.endswith("\r\n"):
                logging.error("Headers do not end with proper CRLF sequence")
                return ""
            
            return headers_str
            
        except Exception as e:
            logging.error(f"Failed to build FFmpeg headers: {e}")
            return ""

    def _mask_ffmpeg_command_for_logging(self, cmd: list) -> list:
        """
        Create a safe version of FFmpeg command for logging with masked cookie values.
        
        Requirements:
        - 9.3: Cookie value masking in all log output
        """
        safe_cmd = cmd.copy()
        
        for i, arg in enumerate(safe_cmd):
            if isinstance(arg, str) and "Cookie:" in arg:
                # Mask the entire headers argument that contains cookies
                safe_cmd[i] = "[HEADERS_WITH_MASKED_COOKIES]"
            elif isinstance(arg, str) and any(cookie_indicator in arg.lower() for cookie_indicator in ["cookie=", "session=", "auth="]):
                # Mask any other arguments that might contain cookie-like data
                safe_cmd[i] = "[MASKED_COOKIE_DATA]"
        
        return safe_cmd

    def _extract_audio_to_wav(self, audio_url: str, wav_path: str) -> bool:
        """Extract audio from HLS stream to WAV using ffmpeg with WebM/Opus hardening and proxy support"""
        max_retries = 2
        
        for attempt in range(max_retries):
            start_time = time.time()
            try:
                # Pass headers to avoid 403 on googlevideo domains (UA/Referer) and include Cookie if available
                headers = [f"User-Agent: {_CHROME_UA}", "Referer: https://www.youtube.com/"]
                ck = _cookie_header_from_env_or_file()
                if ck:
                    headers.append(f"Cookie: {ck}")
                
                # Build headers with proper CRLF formatting and validation
                headers_arg = self._build_ffmpeg_headers(headers)
                if not headers_arg:
                    logging.error("Failed to build valid FFmpeg headers")
                    return False
                
                # Enhanced FFmpeg command with WebM/Opus tolerance and format detection
                # Place -headers parameter before -i parameter as required
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-loglevel", "error",
                    "-headers", headers_arg,
                ]
                
                # Get proxy environment variables for subprocess
                proxy_env = {}
                if self.proxy_manager:
                    proxy_env = self.proxy_manager.proxy_env_for_subprocess()
                    if proxy_env:
                        logging.info("Using proxy environment variables for FFmpeg subprocess")
                        # Verify proxy configuration immediately
                        if not self._verify_proxy_configuration(proxy_env):
                            logging.error("Proxy configuration verification failed - aborting FFmpeg extraction")
                            return False
                elif ENFORCE_PROXY_ALL:
                    # Fallback to legacy proxy URL method if proxy_manager not available
                    proxy_url = _ffmpeg_proxy_url(shared_managers.get_proxy_manager())
                    if proxy_url:
                        cmd += ["-http_proxy", proxy_url]
                
                # Continue building command
                cmd += [
                    # Add input format tolerance for WebM/Opus streams
                    "-analyzeduration", "10M",
                    "-probesize", "50M",
                    "-i", audio_url,
                    # Force audio codec and format conversion
                    "-c:a", "pcm_s16le",  # Force PCM WAV output
                    "-ar", "16000",       # 16kHz sample rate
                    "-ac", "1",           # Mono
                    "-f", "wav",          # Force WAV format output
                    # Add error resilience for corrupted streams
                    "-err_detect", "ignore_err",
                    "-fflags", "+genpts",
                    wav_path,
                ]

                # Log the exact command for debugging (with masked sensitive headers)
                safe_cmd = self._mask_ffmpeg_command_for_logging(cmd)
                logging.info(f"FFmpeg command (attempt {attempt + 1}): {' '.join(safe_cmd)}")

                # Prepare environment for subprocess - inherit current env and add proxy vars
                subprocess_env = os.environ.copy()
                if proxy_env:
                    subprocess_env.update(proxy_env)
                    # Log proxy usage without exposing credentials
                    logging.info("FFmpeg subprocess will use proxy environment variables")

                # Run ffmpeg with stderr capture to memory buffer
                result = subprocess.run(cmd, check=True, capture_output=True, timeout=120, env=subprocess_env)

                # Calculate duration for success logging
                duration_ms = int((time.time() - start_time) * 1000)
                
                if os.path.exists(wav_path) and os.path.getsize(wav_path) > 0:
                    file_size = os.path.getsize(wav_path)
                    # Structured logging for ffmpeg success with byte counts and duration
                    from log_events import evt
                    evt("stage_result", 
                        stage="ffmpeg", 
                        outcome="success", 
                        dur_ms=duration_ms,
                        detail=f"extracted {file_size} bytes")
                    return True
                else:
                    # Empty file produced
                    evt("stage_result", 
                        stage="ffmpeg", 
                        outcome="error", 
                        dur_ms=duration_ms,
                        detail="empty file produced")
                    if attempt < max_retries - 1:
                        logging.info(f"Retrying audio extraction (attempt {attempt + 2})")
                        continue
                    return False

            except subprocess.TimeoutExpired as e:
                # Calculate duration for timeout logging
                duration_ms = int((time.time() - start_time) * 1000)
                
                # Extract stderr tail if available
                stderr_tail = None
                if hasattr(e, 'stderr') and e.stderr:
                    stderr_tail = self._extract_stderr_tail(e.stderr, 40)
                
                # Structured logging for ffmpeg timeout with duration
                from log_events import evt
                evt("stage_result", 
                    stage="ffmpeg", 
                    outcome="timeout", 
                    dur_ms=duration_ms,
                    detail=f"timeout after {duration_ms}ms",
                    stderr_tail=stderr_tail)
                
                if attempt < max_retries - 1:
                    logging.info(f"Retrying after timeout (attempt {attempt + 2})")
                    continue
                return False
                
            except subprocess.CalledProcessError as e:
                # Calculate duration for error logging
                duration_ms = int((time.time() - start_time) * 1000)
                
                # Extract stderr tail (last 40 lines) on failure
                stderr_tail = self._extract_stderr_tail(e.stderr, 40) if e.stderr else None
                
                # Structured logging for ffmpeg failure with stderr tail
                from log_events import evt
                evt("stage_result", 
                    stage="ffmpeg", 
                    outcome="error", 
                    dur_ms=duration_ms,
                    detail=f"exit_code={e.returncode}",
                    stderr_tail=stderr_tail)
                
                # Check for specific WebM/Opus errors and retry with different approach
                if stderr_tail and "Invalid data found when processing input" in stderr_tail and attempt < max_retries - 1:
                    logging.info("Detected WebM/Opus format issue, retrying with enhanced tolerance")
                    continue
                elif attempt < max_retries - 1:
                    logging.info(f"Retrying after ffmpeg error (attempt {attempt + 2})")
                    continue
                return False
                
            except Exception as e:
                # Calculate duration for general error logging
                duration_ms = int((time.time() - start_time) * 1000)
                
                # Structured logging for general errors
                from log_events import evt
                evt("stage_result", 
                    stage="ffmpeg", 
                    outcome="error", 
                    dur_ms=duration_ms,
                    detail=f"general_error: {str(e)}")
                
                if attempt < max_retries - 1:
                    logging.info(f"Retrying after general error (attempt {attempt + 2})")
                    continue
                return False
        
        return False

    def _extract_stderr_tail(self, stderr_bytes: bytes, max_lines: int = 40) -> str:
        """
        Extract the last N lines from stderr output for logging.
        
        Args:
            stderr_bytes: Raw stderr bytes from subprocess
            max_lines: Maximum number of lines to extract (default 40)
            
        Returns:
            String containing the last N lines of stderr, or empty string if no stderr
        """
        if not stderr_bytes:
            return ""
        
        try:
            # Try to decode stderr to string
            stderr_text = stderr_bytes.decode('utf-8', errors='strict')
            
            # Split into lines and get the last N lines
            lines = stderr_text.strip().split('\n')
            tail_lines = lines[-max_lines:] if len(lines) > max_lines else lines
            
            # Join back into string
            return '\n'.join(tail_lines)
            
        except UnicodeDecodeError as e:
            # Handle decode errors explicitly
            return f"stderr_decode_error: {str(e)}"
        except Exception as e:
            # Fallback for any other errors
            return f"stderr_decode_error: {str(e)}"

    def _verify_proxy_configuration(self, proxy_env: Dict[str, str]) -> bool:
        """Verify proxy configuration by checking external IP changes"""
        if not proxy_env:
            return True  # No proxy to verify
            
        try:
            import requests
            
            # Get IP without proxy
            try:
                direct_response = requests.get("http://httpbin.org/ip", timeout=5)
                direct_ip = direct_response.json().get("origin", "").split(",")[0].strip()
            except Exception as e:
                logging.warning(f"Could not get direct IP for proxy verification: {e}")
                # If we can't get direct IP, assume proxy is working
                return True
            
            # Get IP with proxy environment
            try:
                # Create a new session with proxy environment
                proxies = {
                    "http": proxy_env.get("http_proxy"),
                    "https": proxy_env.get("https_proxy")
                }
                proxy_response = requests.get("http://httpbin.org/ip", proxies=proxies, timeout=10)
                proxy_ip = proxy_response.json().get("origin", "").split(",")[0].strip()
            except Exception as e:
                logging.error(f"Proxy verification failed - could not connect through proxy: {e}")
                return False
            
            # Verify IPs are different
            if direct_ip == proxy_ip:
                logging.error(f"Proxy verification failed - IP unchanged (both {direct_ip})")
                return False
            
            logging.info(f"Proxy verification successful - IP changed from {direct_ip} to {proxy_ip}")
            return True
            
        except Exception as e:
            logging.error(f"Proxy verification error: {e}")
            return False

    def _get_audio_duration_minutes(self, wav_path: str) -> float:
        """Get audio duration in minutes using ffprobe"""
        try:
            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                wav_path,
            ]

            result = subprocess.run(
                cmd, check=True, capture_output=True, text=True, timeout=10
            )
            duration_seconds = float(result.stdout.strip())
            return duration_seconds / 60.0

        except Exception as e:
            logging.warning(f"Could not determine audio duration: {e}")
            return 0.0

    def _transcribe_with_deepgram(self, wav_path: str, video_id: str) -> str:
        """Transcribe audio file with Deepgram API"""
        try:
            # Import Deepgram SDK
            try:
                from deepgram import DeepgramClient, PrerecordedOptions

                # Deepgram SDK v3+
                deepgram = DeepgramClient(self.deepgram_api_key)
            except ImportError:
                try:
                    from deepgram import Deepgram

                    # Deepgram SDK v2
                    deepgram = Deepgram(self.deepgram_api_key)
                except ImportError:
                    logging.error(
                        "Deepgram SDK not installed. Install with: pip install deepgram-sdk"
                    )
                    return ""

            # Read audio file
            with open(wav_path, "rb") as audio_file:
                buffer_data = audio_file.read()

            # Configure transcription options
            options = {"model": "nova-2", "smart_format": True, "language": "en"}

            # Call Deepgram API
            if hasattr(deepgram, "listen"):
                # SDK v3+
                payload = {"buffer": buffer_data}
                response = deepgram.listen.prerecorded.v("1").transcribe_file(
                    payload, options
                )
            else:
                # SDK v2
                source = {"buffer": buffer_data, "mimetype": "audio/wav"}
                response = deepgram.transcription.prerecorded(source, options)

            # Extract transcript text
            if hasattr(response, "results"):
                # SDK v3+
                alternatives = response.results.channels[0].alternatives
            else:
                # SDK v2
                alternatives = response["results"]["channels"][0]["alternatives"]

            transcript_parts = []
            for alt in alternatives:
                if hasattr(alt, "transcript"):
                    # SDK v3+
                    text = alt.transcript
                else:
                    # SDK v2
                    text = alt.get("transcript", "")

                if text and text.strip():
                    transcript_parts.append(text.strip())

            transcript = " ".join(transcript_parts).strip()

            if transcript:
                logging.info(
                    f"ASR transcription successful for {video_id}: {len(transcript)} characters"
                )
                return transcript
            else:
                logging.warning(
                    f"ASR transcription returned empty result for {video_id}"
                )
                return ""

        except Exception as e:
            logging.error(f"Deepgram transcription failed for {video_id}: {e}")
            return ""


def youtube_reachable(timeout_s=5) -> bool:
    """Preflight check: ping YouTube reachability before Playwright"""
    try:
        proxies = None
        if ENFORCE_PROXY_ALL:
            try:
                proxies = shared_managers.get_proxy_manager().proxy_dict_for("requests")
            except Exception:
                proxies = None
        r = HTTP.get("https://www.youtube.com/generate_204", timeout=(2, timeout_s), proxies=proxies)
        return r.status_code == 204
    except requests.RequestException:
        return False


def _pw_allowed(now_ms):
    """Check if Playwright is allowed (circuit breaker)"""
    return now_ms >= _PW_FAILS["until"]


def _pw_register_timeout(now_ms):
    """Register Playwright timeout for circuit breaker with exponential backoff"""
    _PW_FAILS["count"] += 1
    if _PW_FAILS["count"] >= 3:
        # Skip YouTubei for 1 hour after 3 consecutive failures
        _PW_FAILS["until"] = now_ms + 60 * 60 * 1000  # 1 hour
        _PW_FAILS["count"] = 0
        logging.warning(
            "YouTubei circuit breaker activated - skipping for 1 hour after 3 consecutive failures"
        )


def _pw_register_success():
    """Register Playwright success (reset circuit breaker)"""
    _PW_FAILS["count"] = 0
    _PW_FAILS["until"] = 0


def _convert_cookiejar_to_playwright_format(cookie_jar):
    """
    Convert cookie header string or dict into a Playwright cookies list.
    Handles __Host- cookies via 'url'; sets domain/path for normal cookies.
    """
    if not cookie_jar:
        return None
    pairs: List[Tuple[str, str]] = []
    if isinstance(cookie_jar, dict):
        pairs = [(k, v) for k, v in cookie_jar.items() if isinstance(k, str)]
    elif isinstance(cookie_jar, str):
        for kv in cookie_jar.split(";"):
            kv = kv.strip()
            if "=" in kv:
                name, value = kv.split("=", 1)
                name, value = name.strip(), value.strip()
                if name:
                    pairs.append((name, value))
    else:
        return None
    cookies = []
    for name, value in pairs:
        if name.startswith("__Host-"):
            cookies.append({"name": name, "value": value, "url": "https://www.youtube.com/", "path": "/", "secure": True})
            continue
        for domain in [".youtube.com", ".m.youtube.com"]:
            cookies.append({"name": name, "value": value, "domain": domain, "path": "/", "secure": name.startswith("__Secure-")})
    return cookies or None


class DeterministicTranscriptCapture:
    """Deterministic transcript capture using page.route() with Future resolution and DOM fallback."""
    
    def __init__(self, timeout_seconds: int = 25):
        self.timeout_seconds = timeout_seconds
        self.transcript_future = None
        self.transcript_data = None
        self.page = None  # Store page reference for DOM fallback
        
    async def setup_route_interception(self, page):
        """Setup deterministic route interception for /youtubei/v1/get_transcript"""
        import asyncio
        
        # Store page reference for DOM fallback
        self.page = page
        
        # Create a new Future for this capture session
        self.transcript_future = asyncio.Future()
        self.transcript_data = None
        
        async def handle_transcript_route(route):
            """Handle transcript route with Future resolution"""
            try:
                # Continue the request to let it proceed normally
                response = await route.fetch()
                
                # Check if this is the transcript endpoint
                url = route.request.url
                if "/youtubei/v1/get_transcript" in url:
                    try:
                        # Read response body
                        body = await response.body()
                        if body:
                            text_content = body.decode('utf-8', errors='ignore')
                            if text_content and not self.transcript_future.done():
                                self.transcript_data = text_content
                                self.transcript_future.set_result(text_content)
                                logging.info(f"YouTubei transcript captured via route interception: {len(text_content)} chars")
                    except Exception as e:
                        logging.warning(f"Error reading transcript response body: {e}")
                        if not self.transcript_future.done():
                            self.transcript_future.set_exception(e)
                
                # Fulfill the route with the response
                await route.fulfill(response=response)
                
            except Exception as e:
                logging.warning(f"Error in transcript route handler: {e}")
                if not self.transcript_future.done():
                    self.transcript_future.set_exception(e)
                # Continue with original request if route handling fails
                try:
                    await route.continue_()
                except:
                    pass
        
        # Set up route interception for transcript endpoints
        await page.route("**/youtubei/v1/get_transcript*", handle_transcript_route)
        logging.info(f"Route interception setup for /youtubei/v1/get_transcript with {self.timeout_seconds}s timeout")
    
    async def _dom_fallback_extraction(self):
        """
        DOM fallback extraction when network interception times out.
        Polls for transcript line selectors for 3-5 seconds and extracts text from DOM nodes.
        """
        if not self.page:
            logging.warning("DOM fallback: No page reference available")
            return None
        
        logging.info("DOM fallback: Starting transcript extraction from DOM after network timeout")
        
        # Transcript line selectors to poll for
        transcript_selectors = [
            # YouTube transcript panel selectors
            '[data-testid="transcript-segment"]',
            '.ytd-transcript-segment-renderer',
            '.segment-text',
            '.cue-group-renderer',
            '.transcript-cue-renderer',
            # Alternative selectors for different YouTube layouts
            '[role="button"][aria-label*="transcript"]',
            '.ytd-transcript-body-renderer .segment',
            '.ytd-transcript-renderer .cue',
            # Generic text content selectors
            '.transcript-text',
            '.caption-line',
            '.subtitle-line'
        ]
        
        import asyncio
        
        # Poll for 3-5 seconds (using 4 seconds as middle ground)
        poll_duration = 4.0
        poll_interval = 0.5
        max_attempts = int(poll_duration / poll_interval)
        
        for attempt in range(max_attempts):
            try:
                transcript_lines = []
                
                # Try each selector to find transcript content
                for selector in transcript_selectors:
                    try:
                        # Check if elements exist with this selector
                        elements = await self.page.query_selector_all(selector)
                        if elements:
                            logging.info(f"DOM fallback: Found {len(elements)} elements with selector '{selector}'")
                            
                            # Extract text from each element
                            for element in elements:
                                try:
                                    text_content = await element.text_content()
                                    if text_content and text_content.strip():
                                        transcript_lines.append(text_content.strip())
                                except Exception as e:
                                    logging.debug(f"DOM fallback: Error extracting text from element: {e}")
                                    continue
                            
                            # If we found content with this selector, return immediately
                            if transcript_lines:
                                transcript_text = "\n".join(transcript_lines)
                                logging.info(f"DOM fallback: Successfully extracted transcript from DOM: {len(transcript_text)} chars, {len(transcript_lines)} lines")
                                return transcript_text
                                
                    except Exception as e:
                        logging.debug(f"DOM fallback: Error with selector '{selector}': {e}")
                        continue
                
                # Wait before next polling attempt if no content found
                if attempt < max_attempts - 1:  # Don't wait on last attempt
                    await asyncio.sleep(poll_interval)
                    
            except Exception as e:
                logging.warning(f"DOM fallback: Error during polling attempt {attempt + 1}: {e}")
                if attempt < max_attempts - 1:
                    await asyncio.sleep(poll_interval)
                continue
        
        logging.info(f"DOM fallback: No transcript content found after {poll_duration}s of polling")
        return None
    
    async def wait_for_transcript(self):
        """Wait for transcript capture with timeout and DOM fallback"""
        import asyncio
        
        try:
            # Wait for transcript with timeout
            result = await asyncio.wait_for(self.transcript_future, timeout=self.timeout_seconds)
            return result
        except asyncio.TimeoutError:
            logging.info(f"YouTubei route interception timed out after {self.timeout_seconds}s - attempting DOM fallback")
            
            # Try DOM fallback when network interception times out
            dom_result = await self._dom_fallback_extraction()
            if dom_result:
                logging.info("DOM fallback: Successfully extracted transcript when network was blocked")
                return dom_result
            else:
                logging.info("DOM fallback: No transcript found via DOM - falling back to next method")
                return None
                
        except Exception as e:
            logging.warning(f"YouTubei route interception failed: {e} - attempting DOM fallback")
            
            # Try DOM fallback on other errors too
            try:
                dom_result = await self._dom_fallback_extraction()
                if dom_result:
                    logging.info("DOM fallback: Successfully extracted transcript after network error")
                    return dom_result
            except Exception as dom_error:
                logging.warning(f"DOM fallback also failed: {dom_error}")
            
            return None


def get_transcript_via_youtubei(
    video_id: str, proxy_manager=None, cookies=None, timeout_ms: int = None
) -> str:
    """
    Navigate a YouTube watch page and capture `/youtubei/v1/get_transcript` JSON via Playwright.
    Uses deterministic route interception with asyncio.Future resolution pattern.
    - Implements multi-client profile support: desktop(no-proxy → proxy) then mobile(no-proxy → proxy)
    - Uses browser context reuse with profile switching logic
    - Continues without storage_state if missing (no early returns).
    - Emits CloudWatch-friendly logs including the via_proxy flag and profile information.
    - Integrates with enhanced circuit breaker and tenacity retry logic.
    """
    
    def _youtubei_operation():
        """Internal operation function to be wrapped by circuit breaker and retry logic."""
        return _get_transcript_via_youtubei_internal(video_id, proxy_manager, cookies, timeout_ms)
    
    # Execute with circuit breaker integration and retry logic
    return _execute_youtubei_with_circuit_breaker(_youtubei_operation, video_id)


def _get_transcript_via_youtubei_internal(
    video_id: str, proxy_manager=None, cookies=None, timeout_ms: int = None
) -> str:
    """
    Internal YouTubei extraction implementation (wrapped by circuit breaker and retry logic).
    """
    import asyncio

    timeout_ms = timeout_ms or PLAYWRIGHT_NAVIGATION_TIMEOUT

    # Build multi-profile attempt sequence: desktop(no-proxy → proxy) then mobile(no-proxy → proxy)
    attempts = []
    
    # Get proxy configuration
    pw_proxy = None
    if proxy_manager:
        try:
            pw_proxy = _playwright_proxy(proxy_manager)
        except Exception:
            pw_proxy = None
    
    # Profile attempt sequence as per requirements
    for profile_name in ["desktop", "mobile"]:
        if ENFORCE_PROXY_ALL:
            # Only proxy attempts when enforcing
            attempts.append({
                "profile": profile_name,
                "use_proxy": True, 
                "proxy": pw_proxy
            })
        else:
            # No-proxy first, then proxy for each profile
            attempts.append({
                "profile": profile_name,
                "use_proxy": False, 
                "proxy": None
            })
            if pw_proxy:
                attempts.append({
                    "profile": profile_name,
                    "use_proxy": True, 
                    "proxy": pw_proxy
                })

    async def _create_profile_context(browser, playwright_manager, profile_name, proxy_dict):
        """Create browser context with profile-specific settings and storage state."""
        # Get profile configuration
        client_profile = PROFILES.get(profile_name, PROFILES["desktop"])
        
        # Ensure storage state is available (convert if needed)
        storage_state_available = playwright_manager.ensure_storage_state_available()
        
        # Prepare context arguments with profile-specific settings
        context_kwargs = {
            "user_agent": client_profile.user_agent,
            "viewport": client_profile.viewport,
            "locale": "en-US",
            "ignore_https_errors": True,
        }
        
        # Add proxy if provided
        if proxy_dict:
            context_kwargs["proxy"] = proxy_dict
            logging.info(f"[playwright] Creating {profile_name} context with proxy server={proxy_dict.get('server')}")
        else:
            logging.info(f"[playwright] Creating {profile_name} context WITHOUT proxy")
        
        # Add storage state if available
        if storage_state_available and playwright_manager.storage_state_path.exists():
            context_kwargs["storage_state"] = str(playwright_manager.storage_state_path)
            logging.info(f"Using Playwright storage_state from {playwright_manager.storage_state_path}")
            
            # Verify storage state contains cookies
            try:
                with open(playwright_manager.storage_state_path, 'r') as f:
                    state_data = json.load(f)
                    cookie_count = len(state_data.get("cookies", []))
                    logging.info(f"Storage state contains {cookie_count} cookies for {profile_name} profile")
            except Exception as e:
                logging.warning(f"Could not verify storage state contents: {e}")
        
        # Create context with profile settings
        context = await browser.new_context(**context_kwargs)
        logging.info(f"Created {profile_name} context with UA: {client_profile.user_agent[:50]}... viewport: {client_profile.viewport}")
        
        return context, storage_state_available

    async def run_youtubei_extraction():
        """Async function to run the YouTubei extraction with deterministic capture and multi-profile support"""
        
        async with async_playwright() as p:
            browser = None
            current_profile = None
            
            try:
                # Launch browser once and reuse for all attempts
                launch_kwargs = {"headless": True, "args": ["--no-sandbox"]}
                browser = await p.chromium.launch(**launch_kwargs)
                logging.info("[playwright] Browser launched for multi-profile attempts")
                
                # Initialize enhanced Playwright manager
                playwright_manager = EnhancedPlaywrightManager()
                
                for idx, attempt in enumerate(attempts, 1):
                    profile_name = attempt["profile"]
                    use_proxy = attempt["use_proxy"]
                    proxy = attempt["proxy"]
                    
                    # Import context management for attempt tracking
                    from logging_setup import set_job_ctx, get_job_ctx
                    from log_events import evt
                    
                    # Update context with attempt details
                    current_ctx = get_job_ctx()
                    set_job_ctx(
                        job_id=current_ctx.get('job_id'),
                        video_id=video_id
                    )
                    
                    # Log attempt start with context
                    evt("youtubei_attempt_start", 
                        attempt=idx, 
                        total_attempts=len(attempts),
                        profile=profile_name, 
                        use_proxy=use_proxy)
                    
                    context = None
                    page = None
                    try:
                        # Create deterministic transcript capture handler for this attempt
                        transcript_capture = DeterministicTranscriptCapture(timeout_seconds=25)
                        
                        # Create context with profile-specific settings
                        context, storage_state_loaded = await _create_profile_context(
                            browser, playwright_manager, profile_name, proxy if use_proxy else None
                        )
                        
                        # Pre-seed consent to reduce friction
                        try:
                            await context.add_cookies([
                                {"name": "CONSENT", "value": "YES+1", "domain": ".youtube.com", "path": "/"},
                                {"name": "CONSENT", "value": "YES+1", "domain": ".m.youtube.com", "path": "/"},
                            ])
                        except Exception:
                            pass

                        # Add user cookies if provided
                        if cookies:
                            pw_cookies = _convert_cookiejar_to_playwright_format(cookies)
                            if pw_cookies:
                                try:
                                    await context.add_cookies(pw_cookies)
                                except Exception:
                                    pass

                        page = await context.new_page()
                        page.set_default_navigation_timeout(timeout_ms * 1000 if timeout_ms < 1000 else timeout_ms)
                        
                        # Setup deterministic route interception
                        await transcript_capture.setup_route_interception(page)

                        url = f"https://www.youtube.com/watch?v={video_id}&hl=en"
                        await page.goto(url, wait_until="domcontentloaded", timeout=PW_NAV_TIMEOUT_MS)

                        # Light interaction helps trigger network calls
                        try:
                            await _try_click_any_async(
                                page,
                                [
                                    'button:has-text("Accept all")',
                                    'button:has-text("I agree")',
                                    '[aria-label*="Accept"]',
                                ],
                                wait_after=1000,
                            )
                        except Exception:
                            pass

                        try:
                            await page.keyboard.press("k")  # play/pause toggle
                        except Exception:
                            pass

                        # Wait for transcript capture with deterministic timeout
                        transcript_data = await transcript_capture.wait_for_transcript()

                        if transcript_data:
                            # Log successful attempt with context
                            evt("youtubei_attempt_success", 
                                attempt=idx,
                                profile=profile_name, 
                                use_proxy=use_proxy,
                                outcome="success")
                            
                            try:
                                data = json.loads(transcript_data)
                                # Very simple extractor: concatenate textRuns if present
                                out = []
                                def walk(node):
                                    if isinstance(node, dict):
                                        if "text" in node and isinstance(node["text"], str):
                                            out.append(node["text"])
                                        for v in node.values():
                                            walk(v)
                                    elif isinstance(node, list):
                                        for v in node:
                                            walk(v)
                                walk(data)
                                txt = "\n".join(t.strip() for t in out if isinstance(t, str) and t.strip())
                                if txt:
                                    return txt
                            except Exception:
                                # return raw as fallback
                                return transcript_data

                    except Exception as e:
                        # Log failed attempt with context
                        error_type = "timeout" if "TimeoutError" in type(e).__name__ else "error"
                        evt("youtubei_attempt_failed", 
                            attempt=idx,
                            profile=profile_name, 
                            use_proxy=use_proxy,
                            outcome=error_type,
                            detail=str(e)[:100])
                        
                        # Re-raise exception to be handled by retry logic
                        raise
                    finally:
                        if page:
                            await page.close()
                        if context:
                            await context.close()
                
                logging.info(f"All YouTubei attempts exhausted across profiles: {len(attempts)} attempts tried")
                
            finally:
                if browser:
                    await browser.close()
                    logging.info("[playwright] Browser closed after all profile attempts")

        return ""

    # Run the async extraction in a new event loop
    with _BROWSER_SEM:
        try:
            # Create new event loop for this thread if needed
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we're in an existing event loop, we need to run in a thread
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, run_youtubei_extraction())
                        return future.result(timeout=YOUTUBEI_HARD_TIMEOUT)
                else:
                    return loop.run_until_complete(run_youtubei_extraction())
            except RuntimeError:
                # No event loop exists, create one
                return asyncio.run(run_youtubei_extraction())
        except Exception as e:
            logging.error(f"YouTubei extraction failed: {e}")
            return ""


def get_transcript_via_youtubei_with_timeout(
    video_id: str, proxy_manager=None, cookies=None, max_duration_seconds: int = YOUTUBEI_HARD_TIMEOUT
) -> str:
    """Run get_transcript_via_youtubei with a hard timeout."""
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(get_transcript_via_youtubei, video_id, proxy_manager, cookies, PLAYWRIGHT_NAVIGATION_TIMEOUT)
        try:
            return fut.result(timeout=max_duration_seconds)
        except concurrent.futures.TimeoutError:
            handle_timeout_error(video_id, max_duration_seconds, "youtubei")
            return ""


def _parse_youtubei_transcript_json(data: dict) -> str:
    """Extract transcript lines from YouTubei JSON (handles common shapes)."""

    def runs_text(runs):
        return "".join((r or {}).get("text", "") for r in (runs or []))

    # Most common path:
    cues = []
    try:
        cues = data["actions"][0]["updateEngagementPanelAction"]["content"][
            "transcriptRenderer"
        ]["body"]["transcriptBodyRenderer"]["cueGroups"]
    except Exception:
        pass

    lines = []
    for cg in cues or []:
        runs = None
        try:
            runs = cg["transcriptCueGroupRenderer"]["cue"]["transcriptCueRenderer"][
                "cue"
            ]["simpleText"]["runs"]
        except Exception:
            try:
                runs = cg["transcriptCueGroupRenderer"]["cues"][0][
                    "transcriptCueRenderer"
                ]["cue"]["simpleText"]["runs"]
            except Exception:
                runs = None
        t = runs_text(runs).strip() if runs else ""
        if t:
            lines.append(t)
    return "\n".join(lines).strip()


def _extract_cues_from_youtubei(data: dict) -> List[Dict]:
    """
    Parse YouTubei JSON response to extract transcript cues with timing information.
    
    Args:
        data: YouTubei JSON response data
        
    Returns:
        List of transcript segments with text, start, and duration
    """
    segments = []
    
    try:
        # Extract cue groups from YouTubei response
        cues = data["actions"][0]["updateEngagementPanelAction"]["content"][
            "transcriptRenderer"
        ]["body"]["transcriptBodyRenderer"]["cueGroups"]
        
        for cue_group in cues:
            try:
                # Handle different cue group structures
                cue_renderer = None
                
                # Try primary structure
                try:
                    cue_renderer = cue_group["transcriptCueGroupRenderer"]["cues"][0]["transcriptCueRenderer"]
                except (KeyError, IndexError):
                    # Try alternative structure
                    try:
                        cue_renderer = cue_group["transcriptCueGroupRenderer"]["cue"]["transcriptCueRenderer"]
                    except (KeyError, IndexError):
                        continue
                
                if not cue_renderer:
                    continue
                
                # Extract text content
                cue_text = ""
                try:
                    # Try simpleText first
                    cue_text = cue_renderer["cue"]["simpleText"]
                except (KeyError, TypeError):
                    # Try runs format
                    try:
                        runs = cue_renderer["cue"]["simpleText"]["runs"]
                        cue_text = "".join((r or {}).get("text", "") for r in (runs or []))
                    except (KeyError, TypeError):
                        continue
                
                # Extract timing information
                start_offset_ms = cue_renderer.get("startOffsetMs", "0")
                duration_ms = cue_renderer.get("durationMs", "0")
                
                # Convert to float seconds
                try:
                    start_seconds = float(start_offset_ms) / 1000.0
                    duration_seconds = float(duration_ms) / 1000.0
                except (ValueError, TypeError):
                    start_seconds = 0.0
                    duration_seconds = 0.0
                
                # Add segment if text is not empty
                if cue_text and cue_text.strip():
                    segments.append({
                        'text': cue_text.strip(),
                        'start': start_seconds,
                        'duration': duration_seconds
                    })
                    
            except Exception as cue_error:
                # Log individual cue parsing errors but continue processing
                evt("youtubei_cue_parse_error", 
                    error=str(cue_error)[:100],
                    cue_index=len(segments))
                continue
                
    except Exception as parse_error:
        # Log parsing error and return empty list
        evt("youtubei_parse_error", 
            error_type=type(parse_error).__name__,
            error=str(parse_error)[:200])
        return []
    
    evt("youtubei_cues_extracted", 
        segments_count=len(segments),
        total_duration=sum(s['duration'] for s in segments))
    
    return segments


# --- Playwright Helper Functions ---


def _accept_consent(page: Page):
    selectors = [
        "button:has-text('Accept all')",
        "button:has-text('I agree')",
        "button:has-text('Estoy de acuerdo')",
        "button:has-text('Acepto todo')",
        "button:has-text('Aceptar todo')",
    ]
    for sel in selectors:
        try:
            if page.locator(sel).first.is_visible(timeout=5000):
                page.locator(sel).first.click()
                page.wait_for_load_state("networkidle", timeout=10000)
                logging.info("Accepted consent wall.")
                return
        except Exception:
            continue


def _open_transcript_panel(page: Page):
    try:
        page.get_by_role("button", name="More actions").click(timeout=5000)
    except Exception:
        page.keyboard.press("Shift+.")
    for label in [
        "Show transcript",
        "Open transcript",
        "Ver transcripción",
        "Mostrar transcripción",
    ]:
        try:
            page.get_by_text(label, exact=False).click(timeout=5000)
            logging.info(f"Opened transcript panel with label: '{label}'")
            return
        except Exception:
            continue
    logging.warning("Could not open transcript panel.")


def _pw_proxy(pm: Optional[ProxyManager]):
    if not pm:
        logging.info("Playwright proxy -> none (ProxyManager not available)")
        return None
    cfg = pm.proxy_dict_for("playwright")
    if cfg and cfg.get("server"):
        logging.info(f"Playwright proxy -> server={cfg['server']}")
    else:
        logging.info("Playwright proxy -> none (config not generated)")
    return cfg


# NOTE: legacy helper; not used by the main fallback chain.
def scrape_transcript_with_playwright(
    video_id: str, pm: Optional[ProxyManager] = None, cookies=None, timeout_ms=60000
) -> str:
    url = f"https://www.youtube.com/watch?v={video_id}"
    with sync_playwright() as p:
        launch_args = {"headless": True}
        proxy_config = _pw_proxy(pm)
        if proxy_config:
            launch_args["proxy"] = proxy_config

        browser = p.chromium.launch(**launch_args)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            timezone_id="Europe/Madrid",
            locale="en-US",
        )
        if cookies:
            context.add_cookies(cookies)

        page = context.new_page()
        page.route(
            "**/*",
            lambda r: (
                r.abort()
                if r.request.resource_type in {"image", "media", "font"}
                else r.continue_()
            ),
        )

        try:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            except Exception as e:
                logging.warning(
                    f"Initial page.goto failed for {url}: {e}. Retrying on mobile URL."
                )
                page.goto(
                    f"https://m.youtube.com/watch?v={video_id}",
                    wait_until="domcontentloaded",
                    timeout=timeout_ms,
                )
        except Exception as e:
            logging.error(f"Navigation attempts failed for {video_id}: {e}")
            if proxy_config:
                logging.warning("Final attempt: Retrying without proxy...")
                try:
                    browser.close()
                    browser = p.chromium.launch(headless=True)
                    context = browser.new_context()
                    page = context.new_page()
                    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                except Exception as final_e:
                    logging.error(f"Navigation without proxy also failed: {final_e}")
                    browser.close()
                    return ""
            else:
                browser.close()
                return ""

        _accept_consent(page)
        _open_transcript_panel(page)

        try:
            items = page.locator("ytd-transcript-segment-renderer #segment-text").all()
            text = "\n".join(
                i.inner_text().strip() for i in items if i.inner_text().strip()
            )
        except Exception as e:
            logging.error(f"Failed to scrape transcript segments: {e}")
            text = ""

        browser.close()
        return text


# --- TranscriptService Class ---


class TranscriptService:
    def __init__(self, use_shared_managers: bool = True):
        self.deepgram_api_key = os.environ.get("DEEPGRAM_API_KEY", "")
        self.proxy_manager = shared_managers.get_proxy_manager()
        self.user_agent_manager = shared_managers.get_user_agent_manager()
        logging.info("TranscriptService initialized with shared managers")
        self.cache = TranscriptCache(default_ttl_days=7)
        self._video_locks = {}
        self.current_user_id: Optional[int] = None
        # Cookies: prefer new COOKIE_DIR; keep back-compat with COOKIE_LOCAL_DIR
        self.cookies_path = _resolve_cookie_file_path()
        self.cookie_header = os.getenv(
            "COOKIES_HEADER"
        )  # optional full header or just cookie string

    def get_transcript(
        self,
        video_id: str,
        *,
        language_codes: Optional[list] = None,
        proxy_manager=None,
        cookies=None,
        user_id: Optional[int] = None,   # S3/env cookie fallback
        user_cookies: Optional[object] = None,  # NEW: explicit cookies from caller (header str or dict)
        **kwargs,  # absorb future/alias kwargs without crashing
    ) -> str:
        """
        Enhanced transcript pipeline with job-scoped sessions and comprehensive logging:
        youtube_transcript_api -> timedtext -> YouTubei -> ASR (Deepgram)
        """
        # Generate job ID for sticky proxy sessions
        job_id = generate_correlation_id()
        
        # Set job context for logging
        set_job_ctx(job_id=job_id, video_id=video_id)
        
        # Global job watchdog - enforce maximum job duration
        import concurrent.futures
        
        def _execute_pipeline():
            return self._execute_transcript_pipeline(
                video_id, job_id, language_codes, proxy_manager, 
                cookies, user_id, user_cookies, **kwargs
            )
        
        # Execute with global timeout
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_execute_pipeline)
            try:
                return future.result(timeout=GLOBAL_JOB_TIMEOUT)
            except concurrent.futures.TimeoutError:
                evt("global_job_timeout", 
                    job_id=job_id, 
                    video_id=video_id, 
                    timeout_seconds=GLOBAL_JOB_TIMEOUT)
                handle_timeout_error(video_id, GLOBAL_JOB_TIMEOUT, "global_watchdog")
                return ""
    
    def _execute_transcript_pipeline(
        self,
        video_id: str,
        job_id: str,
        language_codes: Optional[list],
        proxy_manager,
        cookies,
        user_id: Optional[int],
        user_cookies: Optional[object],
        **kwargs
    ) -> str:
        """
        Internal pipeline execution (wrapped by global timeout watchdog).
        Uses the new intelligent fallback strategy for smarter transcript extraction.
        """
        
        # ---- Cookie resolution (single source of truth) ----
        # Accept multiple inputs and aliases without breaking callers.
        # Precedence:
        #   1) user_cookies (explicit from caller)
        #   2) cookies (legacy kw)
        #   3) alias kwargs: cookies_header / cookie_header (header string)
        #   4) S3/env fallback via user_id / env files
        alias_cookie_header = None
        if "cookies_header" in kwargs and isinstance(kwargs["cookies_header"], str):
            alias_cookie_header = kwargs["cookies_header"].strip() or None
        elif "cookie_header" in kwargs and isinstance(kwargs["cookie_header"], str):
            alias_cookie_header = kwargs["cookie_header"].strip() or None
        # Handle playwright_cookies argument properly (Fix C)
        playwright_cookies = kwargs.get("playwright_cookies")
        
        # log any extra kwargs we're ignoring to aid future cleanup (but don't fail)
        if kwargs:
            extra_keys = [k for k in kwargs.keys() if k not in ("cookies_header", "cookie_header", "playwright_cookies")]
            if extra_keys:
                logging.info(f"Ignoring extra kwargs in get_transcript: {extra_keys}")

        cookie_header: Optional[str] = None
        if user_cookies is not None:
            if isinstance(user_cookies, str):
                cookie_header = (user_cookies or "").strip() or None
            elif isinstance(user_cookies, dict):
                cookie_header = "; ".join(f"{k}={v}" for k, v in user_cookies.items()) or None
        elif cookies is not None:
            if isinstance(cookies, str):
                cookie_header = (cookies or "").strip() or None
            elif isinstance(cookies, dict):
                cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items()) or None
        elif alias_cookie_header:
            cookie_header = alias_cookie_header
        else:
            # Try S3-first if user_id provided, else env/file
            cookie_header = get_user_cookies_with_fallback(user_id)

        # Dict form for libs expecting cookie jar/dict
        cookie_dict: Optional[Dict[str, str]] = None
        if cookie_header:
            try:
                cookie_dict = {
                    p.split("=", 1)[0].strip(): p.split("=", 1)[1].strip()
                    for p in cookie_header.split(";")
                    if "=" in p
                }
            except Exception:
                cookie_dict = None
        
        start_time = time.time()
        
        # Use provided proxy_manager or fall back to instance proxy_manager
        effective_proxy_manager = proxy_manager or self.proxy_manager
        
        # Set default language_codes with USER_LOCALE support
        if language_codes is None:
            language_codes = ["en", "en-US", "en-GB"]
            user_locale = os.getenv('USER_LOCALE')
            if user_locale and user_locale not in language_codes:
                language_codes.append(user_locale)

        if video_id in self._video_locks:
            logging.info(f"Video {video_id} already being processed, waiting...")

        self._video_locks[video_id] = True
        
        # Track pipeline stages for summary logging
        pipeline_stages = []
        stage_winner = None
        
        try:
            # Check cache first (use first language for cache key)
            primary_language = language_codes[0] if language_codes else "en"
            cached_transcript = self.cache.get(video_id, primary_language)
            if cached_transcript:
                evt("stage_result", stage="cache", outcome="success", dur_ms=0)
                stage_winner = "cache"
                return cached_transcript

            # Use the new intelligent fallback strategy
            transcript, source = get_transcript_with_intelligent_fallback(
                video_id, job_id, cookie_header
            )
            
            if transcript:
                stage_winner = source
                pipeline_stages.append((source, "success", int((time.time() - start_time) * 1000)))
                return transcript
            else:
                # No transcript found in any stage
                pipeline_stages.append(("none", "no_transcript", int((time.time() - start_time) * 1000)))
                return ""

        finally:
            # Clean up job session
            if effective_proxy_manager:
                try:
                    effective_proxy_manager.cleanup_job_session(job_id)
                except Exception:
                    pass
            
            # Log per-job summary
            total_duration = int((time.time() - start_time) * 1000)
            self._log_job_summary(
                job_id, video_id, stage_winner or "none", total_duration, 
                pipeline_stages, effective_proxy_manager, cookie_header
            )
            
            self._video_locks.pop(video_id, None)

    def _get_transcript_with_fallback(
        self, video_id: str, language: str, user_cookies=None, playwright_cookies=None
    ) -> Tuple[str, str]:
        """
        Execute hierarchical fallback strategy.
        Returns (transcript_text, source) where source indicates which method succeeded.
        """
        methods = [
            ("yt_api", ENABLE_YT_API, self.get_captions_via_api),
            (
                "timedtext",
                ENABLE_TIMEDTEXT,
                lambda vid, lang, cookies: get_captions_via_timedtext(
                    vid, self.proxy_manager, cookies, user_cookies=user_cookies
                ),
            ),
            (
                "youtubei",
                ENABLE_YOUTUBEI,
                lambda vid, lang, cookies: get_transcript_via_youtubei(
                    vid, self.proxy_manager, cookies
                ),
            ),
            (
                "asr",
                ENABLE_ASR_FALLBACK,
                lambda vid, lang, cookies: self.asr_from_intercepted_audio(
                    vid, self.proxy_manager, cookies
                ),
            ),
        ]
        
        # Log proxy strategy optimization
        proxy_available = self.proxy_manager is not None
        logging.info(f"Transcript pipeline for {video_id}: proxy_available={proxy_available}, "
                    f"yt_api=direct_first, timedtext=proxy_preferred, youtubei=proxy_preferred, asr=direct_first")

        for source, enabled, method in methods:
            if not enabled:
                logging.info(
                    f"transcript_attempt video_id={video_id} method={source} success=false reason=disabled"
                )
                continue

            start_time = time.time()
            
            # Determine proxy usage and profile for this stage
            proxy_used = False
            profile = None
            
            if source in ["timedtext", "youtubei"] and self.proxy_manager:
                proxy_used = True
            
            # For youtubei, we might have profile information from multi-client support
            if source == "youtubei":
                # Default to desktop profile if not specified
                profile = "desktop"
            
            # Get current circuit breaker state for logging
            circuit_breaker_state = _playwright_circuit_breaker.get_state() if source == "youtubei" else None
            
            try:
                if source == "yt_api":
                    result = method(video_id, (language, "en", "en-US"))
                elif source == "timedtext":
                    result = method(video_id, language, user_cookies)
                else:  # youtubei and asr use playwright cookies
                    result = method(video_id, language, playwright_cookies)

                duration_ms = int((time.time() - start_time) * 1000)

                if result and result.strip():
                    # Record comprehensive stage metrics with structured logging
                    from transcript_metrics import record_stage_metrics, log_successful_transcript_method
                    
                    record_stage_metrics(
                        video_id=video_id,
                        stage=source,
                        duration_ms=duration_ms,
                        success=True,
                        proxy_used=proxy_used,
                        profile=profile,
                        circuit_breaker_state=circuit_breaker_state
                    )
                    
                    # Log which method succeeded for this video
                    log_successful_transcript_method(video_id)
                    
                    # Legacy metrics for backward compatibility
                    log_performance_metrics(
                        operation=f"transcript_{source}",
                        duration_ms=duration_ms,
                        video_id=video_id,
                        transcript_length=len(result),
                        success=True,
                    )
                    inc_success(source)
                    return result, source
                else:
                    # Record failed stage metrics (empty result)
                    from transcript_metrics import record_stage_metrics
                    
                    record_stage_metrics(
                        video_id=video_id,
                        stage=source,
                        duration_ms=duration_ms,
                        success=False,
                        proxy_used=proxy_used,
                        profile=profile,
                        error_type="empty_result",
                        circuit_breaker_state=circuit_breaker_state
                    )
                    
                    # Legacy logging
                    log_performance_metrics(
                        operation=f"transcript_{source}",
                        duration_ms=duration_ms,
                        video_id=video_id,
                        success=False,
                        reason="empty_result",
                    )

            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                
                # Classify error type for structured logging
                error_type = classify_transcript_error(e, video_id, source)
                
                # Record failed stage metrics with error details
                from transcript_metrics import record_stage_metrics
                
                record_stage_metrics(
                    video_id=video_id,
                    stage=source,
                    duration_ms=duration_ms,
                    success=False,
                    proxy_used=proxy_used,
                    profile=profile,
                    error_type=error_type,
                    circuit_breaker_state=circuit_breaker_state
                )
                
                # Use structured error handling
                handle_transcript_error(video_id, source, e, duration_ms)
                inc_fail(source)
                continue

        inc_fail("none")
        return "", "none"

    def _list_transcripts_safe(self, video_id: str, cookies=None):
        """
        Safe wrapper for YouTubeTranscriptApi.list_transcripts that converts XML parse errors to blocking signals.
        
        Args:
            video_id: YouTube video ID
            cookies: Cookie data (optional)
            
        Returns:
            Transcript list object
            
        Raises:
            RequestBlocked: When empty/HTML response detected (converted from parse error)
        """
        try:
            return YouTubeTranscriptApi.list_transcripts(video_id, cookies=cookies)
        except YouTubeDataUnparsable as e:
            error_msg = str(e)
            # Convert specific XML parse error to blocking signal
            if "no element found: line 1, column 0" in error_msg.lower():
                evt("yt_api_parse_error_converted_to_blocking",
                    video_id=video_id,
                    original_error=error_msg[:200])
                # Treat as blocking/empty response and short-circuit to next method
                raise RequestBlocked(f"Empty or non-XML transcript list for {video_id} (converted from parse error)")
            # Re-raise other parse errors as-is
            raise
        except Exception as e:
            # Let other exceptions bubble up normally
            raise

    def get_captions_via_api(
        self, video_id: str, languages=("en", "en-US", "es")
    ) -> str:
        """
        First tier: YouTube Transcript API with human-captions-first logic.
        Enhanced with robust error handling for XML parsing and network issues.
        """
        try:
            # Log API version and method availability for debugging
            import youtube_transcript_api as yta_mod

            evt("yt_api_info", 
                version=getattr(yta_mod, '__version__', 'unknown'),
                has_get_transcript=hasattr(YouTubeTranscriptApi, 'get_transcript'))

            # Strategy 1: Try list_transcripts first (more robust) with blocking detection
            try:
                # Pass cookies to reduce 429 / "disabled" false negatives
                if self.cookies_path and os.path.exists(self.cookies_path):
                    transcripts = self._list_transcripts_safe(
                        video_id, cookies=self.cookies_path
                    )
                elif self.cookie_header:
                    transcripts = self._list_transcripts_safe(
                        video_id, cookies=self.cookie_header
                    )
                else:
                    transcripts = self._list_transcripts_safe(video_id)

                # Prefer human captions, then auto-generated
                preferred = ["en", "en-US", "en-GB", "es", "es-ES"]
                transcript_obj = None
                source_info = ""

                # Try preferred languages for manual transcripts first
                for lang in preferred:
                    try:
                        transcript_obj = transcripts.find_transcript([lang])
                        source_info = f"yt_api:{lang}:{'manual' if not transcript_obj.is_generated else 'auto'}"
                        logging.info(f"Found transcript for {video_id}: {source_info}")
                        break
                    except NoTranscriptFound:
                        continue

                # If no preferred manual transcript, try any manual transcript
                if not transcript_obj:
                    try:
                        for transcript in transcripts:
                            if not transcript.is_generated:
                                transcript_obj = transcript
                                source_info = (
                                    f"yt_api:{transcript.language_code}:manual"
                                )
                                logging.info(
                                    f"Found manual transcript for {video_id}: {source_info}"
                                )
                                break
                    except Exception:
                        pass

                # If no manual transcript, try auto-generated in preferred languages
                if not transcript_obj:
                    for lang in preferred:
                        try:
                            transcript_obj = transcripts.find_generated_transcript(
                                [lang]
                            )
                            source_info = f"yt_api:{lang}:auto"
                            logging.info(
                                f"Found auto transcript for {video_id}: {source_info}"
                            )
                            break
                        except NoTranscriptFound:
                            continue

                # Last resort: any available transcript
                if not transcript_obj:
                    transcript_obj = next((tr for tr in transcripts if tr), None)
                    if transcript_obj:
                        source_info = f"yt_api:{transcript_obj.language_code}:{'manual' if not transcript_obj.is_generated else 'auto'}"
                        logging.info(
                            f"Found fallback transcript for {video_id}: {source_info}"
                        )

                if transcript_obj:
                    # Use direct HTTP fetching instead of transcript.fetch() to support cookies
                    try:
                        # Prepare cookies for direct HTTP request
                        cookies = None
                        proxies = None
                        
                        if self.cookies_path and os.path.exists(self.cookies_path):
                            cookies = _cookie_header_from_env_or_file()
                        elif self.cookie_header:
                            cookies = self.cookie_header
                        
                        proxies = None
                        if ENFORCE_PROXY_ALL:
                            try:
                                proxies = shared_managers.get_proxy_manager().proxy_dict_for("requests")
                            except Exception:
                                proxies = None
                        
                        # Use direct HTTP transcript fetching
                        transcript_text = get_transcript_with_cookies(
                            video_id, 
                            [transcript_obj.language_code], 
                            cookies=cookies, 
                            proxies=proxies
                        )
                        
                        if transcript_text:
                            source_info = f"yt_api:{transcript_obj.language_code}:{'manual' if not transcript_obj.is_generated else 'auto'}"
                            logging.info(f"Direct HTTP transcript success for {video_id}: {source_info}")
                            return transcript_text
                        else:
                            # Fallback to original fetch method without cookies
                            segments = transcript_obj.fetch()
                            
                    except Exception as fetch_error:
                        logging.warning(f"Direct HTTP transcript fetch failed for {video_id}: {fetch_error}")
                        # Fallback to original fetch method without cookies
                        try:
                            segments = transcript_obj.fetch()
                        except Exception as fallback_error:
                            logging.warning(f"Fallback transcript fetch also failed for {video_id}: {fallback_error}")
                            raise fallback_error
                else:
                    raise NoTranscriptFound(video_id)

            except Exception as list_error:
                # Strategy 2: Fallback to direct get_transcript with enhanced error handling
                logging.info(
                    f"List transcripts failed for {video_id}, trying direct get_transcript: {list_error}"
                )

                # Try each language individually using direct HTTP method
                segments = None
                transcript_text = ""
                
                # Prepare cookies for direct HTTP request
                cookies = None
                proxies = None
                
                if self.cookies_path and os.path.exists(self.cookies_path):
                    cookies = _cookie_header_from_env_or_file()
                elif self.cookie_header:
                    cookies = self.cookie_header
                
                proxies = None
                if ENFORCE_PROXY_ALL:
                    try:
                        proxies = shared_managers.get_proxy_manager().proxy_dict_for("requests")
                    except Exception:
                        proxies = None
                
                for lang in languages:
                    try:
                        # Use direct HTTP transcript fetching
                        transcript_text = get_transcript_with_cookies(
                            video_id, 
                            [lang], 
                            cookies=cookies, 
                            proxies=proxies
                        )
                        
                        if transcript_text:
                            source_info = f"yt_api:{lang}:direct_http"
                            logging.info(f"Direct HTTP transcript success for {video_id} with {lang}")
                            return transcript_text
                        else:
                            # Fallback to original API without cookies
                            segments = YouTubeTranscriptApi.get_transcript(
                                video_id, languages=[lang]
                            )
                            source_info = f"yt_api:{lang}:direct"
                            logging.info(f"Direct transcript success for {video_id} with {lang}")
                            break
                            
                    except Exception as lang_error:
                        logging.debug(f"Direct transcript failed for {video_id} with {lang}: {lang_error}")
                        continue

                if not segments and not transcript_text:
                    # Final attempt with all languages using direct HTTP first
                    transcript_text = get_transcript_with_cookies(
                        video_id, 
                        list(languages), 
                        cookies=cookies, 
                        proxies=proxies
                    )
                    
                    if transcript_text:
                        source_info = "yt_api:multi:direct_http"
                        logging.info(f"Final direct HTTP transcript success for {video_id}")
                        return transcript_text
                    else:
                        # Fallback to original API without cookies
                        segments = YouTubeTranscriptApi.get_transcript(
                            video_id, languages=list(languages)
                        )
                        source_info = "yt_api:multi:direct"

            # Return transcript_text if already found via direct HTTP
            if transcript_text:
                return transcript_text
            
            # Serialize captions with robust text extraction
            if segments:
                lines = []
                for seg in segments:
                    text = seg.get("text", "")
                    if isinstance(text, str) and text.strip():
                        # Clean up common transcript artifacts
                        text = text.strip()
                        # Remove common YouTube auto-caption artifacts
                        if text not in [
                            "[Music]",
                            "[Applause]",
                            "[Laughter]",
                            "♪",
                            "♫",
                        ]:
                            lines.append(text)

                transcript_text = "\n".join(lines).strip()

                if transcript_text:
                    logging.info(
                        f"Successfully extracted transcript for {video_id} via {source_info}: {len(transcript_text)} chars"
                    )
                    return transcript_text
                else:
                    logging.warning(
                        f"Transcript extraction resulted in empty text for {video_id}"
                    )
                    return ""
            else:
                logging.warning(f"No segments returned for {video_id}")
                return ""

        except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable) as e:
            logging.info(f"No YT captions via API for {video_id}: {type(e).__name__}")
            return ""
        except Exception as e:
            # Enhanced error logging for debugging
            error_type = type(e).__name__
            error_msg = str(e)

            # Special handling for XML parsing errors
            if "no element found" in error_msg or "ParseError" in error_type:
                logging.warning(
                    f"YouTube Transcript API XML parsing error for {video_id}: {error_msg}"
                )
                logging.info(
                    f"This usually indicates YouTube is blocking requests or the video has no transcript"
                )
            else:
                logging.warning(
                    f"YouTubeTranscriptApi error for {video_id}: {error_type}: {error_msg}"
                )

            return ""

    def asr_from_intercepted_audio(
        self, video_id: str, pm: Optional[ProxyManager] = None, cookies=None
    ) -> str:
        """
        ASR fallback: Extract audio via HLS interception and transcribe with Deepgram.
        Includes cost controls and duration limits.
        """
        evt("stage_start", stage="asr")
        if not self.deepgram_api_key:
            evt("stage_result", stage="asr", outcome="no_key")
            return ""

        try:
            extractor = ASRAudioExtractor(self.deepgram_api_key, pm)
            return extractor.extract_and_transcribe(video_id, pm, cookies)
        except Exception as e:
            evt("stage_result", stage="asr", outcome="error", detail=f"{type(e).__name__}: {str(e)}")
            return ""

    def close(self):
        if hasattr(self, "http_client"):
            self.http_client.close()

    def get_proxy_stats(self):
        return self.proxy_manager.get_session_stats()

    def get_cache_stats(self):
        return self.cache.get_stats()

    def cleanup_cache(self):
        return self.cache.cleanup_expired()

    def _enhanced_yt_api_stage(
        self, 
        video_id: str, 
        language_codes: List[str], 
        cookie_header: Optional[str],
        proxy_manager,
        job_id: str
    ) -> Tuple[str, str]:
        """
        Enhanced YouTube Transcript API stage with explicit logging.
        
        Returns:
            Tuple of (transcript_text, selected_track_info)
        """
        # Log languages being tried and cookie usage
        cookie_source = "user_provided" if cookie_header else "none"
        evt("yt_api_languages_tried", 
            video_id=video_id, 
            languages=language_codes,
            job_id=job_id)
        
        evt("yt_api_cookie_usage", 
            video_id=video_id, 
            job_id=job_id, 
            cookie_source=cookie_source,
            has_cookies=bool(cookie_header))
        
        try:
            # Get job-scoped proxy if needed
            proxies = None
            if ENFORCE_PROXY_ALL and proxy_manager:
                try:
                    proxies = proxy_manager.proxy_dict_for_job(job_id, "requests")
                except Exception as e:
                    evt("yt_api_proxy_error", error=str(e), job_id=job_id)
                    if ENFORCE_PROXY_ALL:
                        return "", "proxy_error"
            
            # Try to get transcript using enhanced method
            for lang in language_codes:
                try:
                    # Use direct HTTP method with job-scoped proxy
                    transcript_text = get_transcript_with_cookies(
                        video_id, [lang], cookies=cookie_header, proxies=proxies
                    )
                    
                    if transcript_text:
                        # Determine if this is official or auto-generated
                        # This is a simplified heuristic - in practice, we'd need to check the track metadata
                        selected_track = f"{lang}:official"  # Assume official for direct HTTP success
                        
                        evt("yt_api_success",
                            video_id=video_id,
                            selected_language=lang,
                            selected_track=selected_track,
                            transcript_length=len(transcript_text),
                            job_id=job_id)
                        
                        return transcript_text, selected_track
                        
                except Exception as e:
                    error_class = type(e).__name__
                    evt("yt_api_language_failed",
                        video_id=video_id,
                        language=lang,
                        exception_class=error_class,
                        error_detail=str(e)[:200],
                        job_id=job_id)
                    continue
            
            # No transcript found for any language
            evt("yt_api_no_transcript", 
                video_id=video_id, 
                languages_tried=language_codes,
                job_id=job_id)
            
            return "", "NoTranscriptFound"
            
        except Exception as e:
            error_class = type(e).__name__
            evt("yt_api_stage_error",
                video_id=video_id,
                exception_class=error_class,
                error_detail=str(e)[:200],
                job_id=job_id)
            
            return "", error_class
    
    def _run_youtubei_with_timeout(
        self,
        video_id: str,
        job_id: str,
        proxy_manager,
        cookie_header: Optional[str]
    ) -> str:
        """
        Run YouTubei with fast-fail timeout detection for immediate ASR transition.
        
        Implements Requirements 3.4, 5.1:
        - Add timeout detection in YouTubei wrapper calls
        - Implement immediate ASR transition when navigation timeouts occur
        - Prevent retry loops on the same failed extraction path
        
        Args:
            video_id: YouTube video ID
            job_id: Job identifier
            proxy_manager: ProxyManager instance
            cookie_header: Cookie header string
            
        Returns:
            Transcript text if successful, empty string otherwise
            
        Raises:
            Exception: Re-raises navigation timeout exceptions for fast-fail detection
        """
        try:
            # Use the enhanced YouTubei stage with timeout monitoring
            return self._enhanced_youtubei_stage(video_id, job_id, proxy_manager, cookie_header)
            
        except Exception as e:
            # Check for navigation timeout errors that should trigger fast-fail (Requirement 3.4)
            if self._is_navigation_timeout_error(e):
                # Re-raise navigation timeout for fast-fail detection in pipeline
                raise e
            
            # For other errors, log and return empty string for normal fallback
            evt("youtubei_non_timeout_error",
                video_id=video_id,
                job_id=job_id,
                error_type=type(e).__name__,
                error_detail=str(e)[:200])
            return ""
    
    def _is_navigation_timeout_error(self, error: Exception) -> bool:
        """
        Detect navigation timeout errors that should trigger fast-fail to ASR.
        
        Implements Requirement 3.4:
        - Detect page.goto timeouts and route wait timeouts
        - Identify navigation-specific timeout conditions
        
        Args:
            error: Exception to check
            
        Returns:
            True if error is a navigation timeout, False otherwise
        """
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()
        
        # Navigation timeout indicators
        navigation_timeout_patterns = [
            "navigation timeout",
            "page.goto" in error_str and "timeout" in error_str,
            "timeout" in error_str and "navigation" in error_str,
            "timeouterror" in error_type and ("page" in error_str or "navigation" in error_str),
            "playwright" in error_str and "timeout" in error_str and "goto" in error_str,
            # Route wait timeouts that exceed the configured hard timeout
            "route" in error_str and "timeout" in error_str and "wait" in error_str,
            # Playwright-specific timeout errors during page operations
            "asyncio.timeouterror" in error_type and "page" in error_str,
            "concurrent.futures.timeouterror" in error_type
        ]
        
        is_nav_timeout = any(pattern if isinstance(pattern, bool) else pattern in error_str 
                           for pattern in navigation_timeout_patterns)
        
        if is_nav_timeout:
            evt("navigation_timeout_detected",
                error_type=type(error).__name__,
                error_preview=error_str[:100],
                will_fast_fail=True)
        
        return is_nav_timeout

    def _enhanced_youtubei_stage(
        self,
        video_id: str,
        job_id: str,
        proxy_manager,
        cookie_header: Optional[str]
    ) -> str:
        """
        Enhanced YouTubei stage with DOM interaction sequence integration.
        
        Uses the new _get_transcript_via_playwright method that integrates
        DOM helper methods for consent handling, description expansion,
        and transcript button discovery with scroll-and-retry logic.
        
        Returns:
            Transcript text if successful, empty string otherwise
        """
        try:
            # Use the new DOM-integrated Playwright method
            import asyncio
            
            # Run the async _get_transcript_via_playwright method
            segments = asyncio.run(self._get_transcript_via_playwright(
                video_id, job_id, proxy_manager, cookie_header
            ))
            
            if segments:
                # Convert segments back to text format for compatibility
                transcript_text = "\n".join(segment.get('text', '') for segment in segments)
                return transcript_text.strip()
            else:
                # No transcript found - return empty string for fallback
                return ""
                
        except Exception as e:
            evt("youtubei_stage_error",
                video_id=video_id,
                job_id=job_id,
                error_type=type(e).__name__,
                error_detail=str(e)[:200])
            # Re-raise the exception so timeout detection can work in _run_youtubei_with_timeout
            raise
    
    def _enhanced_asr_stage(
        self,
        video_id: str,
        job_id: str,
        proxy_manager,
        cookie_header: Optional[str]
    ) -> str:
        """
        Enhanced ASR stage with job-scoped proxy and hardened FFmpeg.
        
        Returns:
            Transcript text if successful, empty string otherwise
        """
        if not self.deepgram_api_key:
            evt("asr_no_key", video_id=video_id, job_id=job_id)
            return ""
        
        # Check ENFORCE_PROXY_ALL compliance
        if ENFORCE_PROXY_ALL and not (proxy_manager and proxy_manager.in_use):
            evt("asr_blocked", reason="enforce_proxy_no_proxy", job_id=job_id)
            return ""
        
        try:
            # Use enhanced ASR with job-scoped proxy
            extractor = ASRAudioExtractor(self.deepgram_api_key, proxy_manager)
            
            # Extract HLS audio URL using Playwright (existing implementation)
            audio_url = extractor._extract_hls_audio_url(video_id, proxy_manager, cookie_header)
            if not audio_url:
                evt("asr_no_audio_url", video_id=video_id, job_id=job_id)
                return ""
            
            # Extract audio using enhanced FFmpeg service
            with tempfile.TemporaryDirectory() as temp_dir:
                wav_path = os.path.join(temp_dir, "audio.wav")
                
                success, error_classification = extract_audio_with_job_proxy(
                    audio_url, wav_path, job_id, proxy_manager, cookie_header
                )
                
                if not success:
                    evt("asr_audio_extraction_failed",
                        video_id=video_id,
                        job_id=job_id,
                        error_classification=error_classification)
                    return ""
                
                # Check duration limits
                duration_minutes = extractor._get_audio_duration_minutes(wav_path)
                if duration_minutes > extractor.max_video_minutes:
                    evt("asr_duration_exceeded",
                        video_id=video_id,
                        job_id=job_id,
                        duration_minutes=duration_minutes,
                        limit_minutes=extractor.max_video_minutes)
                    return ""
                
                # Transcribe with Deepgram
                transcript = extractor._transcribe_with_deepgram(wav_path, video_id)
                
                if transcript:
                    evt("asr_success",
                        video_id=video_id,
                        job_id=job_id,
                        transcript_length=len(transcript),
                        duration_minutes=duration_minutes)
                else:
                    evt("asr_transcription_failed",
                        video_id=video_id,
                        job_id=job_id)
                
                return transcript
                
        except Exception as e:
            evt("asr_stage_error",
                video_id=video_id,
                job_id=job_id,
                error_type=type(e).__name__,
                error_detail=str(e)[:200])
            return ""
    
    def _log_job_summary(
        self,
        job_id: str,
        video_id: str,
        stage_winner: str,
        total_duration_ms: int,
        pipeline_stages: List[Tuple[str, str, int]],
        proxy_manager,
        cookie_header: Optional[str]
    ):
        """
        Log comprehensive per-job summary line.
        
        Args:
            job_id: Job identifier
            video_id: YouTube video ID
            stage_winner: Stage that succeeded ("yt_api", "timedtext", "youtubei", "asr", "none")
            total_duration_ms: Total pipeline duration in milliseconds
            pipeline_stages: List of (stage_name, outcome, duration_ms) tuples
            proxy_manager: ProxyManager instance
            cookie_header: Cookie header string
        """
        # Get proxy session hash for logging
        proxy_sessid_hash = "none"
        if proxy_manager and proxy_manager.in_use:
            try:
                session_id = proxy_manager.for_job(job_id)
                if session_id:
                    proxy_sessid_hash = session_id[:8] + "***"  # Mask for security
            except Exception:
                proxy_sessid_hash = "error"
        
        # Determine cookie source
        cookie_source = "none"
        if cookie_header:
            # Simple heuristic to determine cookie source
            if len(cookie_header) < 100 and ('SOCS=' in cookie_header or 'CONSENT=' in cookie_header):
                cookie_source = "synthetic"
            else:
                cookie_source = "user"  # Could be user or env, but we'll call it user for simplicity
        
        # Build attempts per stage summary
        attempts_per_stage = {}
        for stage_name, outcome, duration_ms in pipeline_stages:
            if stage_name not in attempts_per_stage:
                attempts_per_stage[stage_name] = 0
            attempts_per_stage[stage_name] += 1
        
        # Log comprehensive job summary
        evt("job_summary",
            job_id=job_id,
            video_id=video_id,
            pipeline_outcome=stage_winner,
            stage_winner=stage_winner,
            duration_ms=total_duration_ms,
            proxy_sessid_hash=proxy_sessid_hash,
            cookie_source=cookie_source,
            attempts_per_stage=attempts_per_stage,
            total_stages_tried=len(pipeline_stages))
        
        logger.info(f"Job {job_id} complete: video={video_id}, winner={stage_winner}, "
                   f"duration={total_duration_ms}ms, proxy_session={proxy_sessid_hash}, "
                   f"cookie_source={cookie_source}")

    async def _get_transcript_via_playwright(self, video_id: str, job_id: str = None, proxy_manager=None, cookie_header: Optional[str] = None) -> Optional[List[Dict]]:
        """
        Enhanced Playwright transcript extraction with DOM interaction sequence.
        
        Integrates DOM helper methods for consent handling, description expansion,
        and transcript button discovery with scroll-and-retry logic.
        
        Args:
            video_id: YouTube video ID
            job_id: Job identifier for proxy session
            proxy_manager: ProxyManager instance
            cookie_header: Cookie header string
            
        Returns:
            List of transcript segments if successful, None for fallback to next method
        """
        # Import DeterministicYouTubeiCapture for DOM interaction integration
        from youtubei_service import DeterministicYouTubeiCapture
        
        # Set job context if provided
        if job_id:
            set_job_ctx(job_id=job_id, video_id=video_id)
        
        # Determine metrics tags for filtering by root cause (Requirements 7.4, 13.1, 13.2)
        cookie_source = "user" if cookie_header else "env"
        proxy_mode = "on" if (proxy_manager and proxy_manager.in_use) else "off"
        
        try:
            # Create capture instance with DOM interaction capabilities
            capture = DeterministicYouTubeiCapture(
                job_id=job_id or f"playwright_{video_id}_{int(time.time())}",
                video_id=video_id,
                proxy_manager=proxy_manager
            )
            
            # Extract transcript using integrated DOM interaction sequence
            transcript_text = await capture.extract_transcript(cookie_header)
            
            # Graceful degradation: handle both None and empty string returns (Requirements 9.4, 9.5)
            if transcript_text and transcript_text.strip():
                # Parse transcript text into segments format
                # The DeterministicYouTubeiCapture returns raw text, but we need to convert
                # it to the expected list of dict format for consistency
                segments = self._parse_transcript_text_to_segments(transcript_text)
                
                if segments and len(segments) > 0:
                    evt("playwright_dom_success",
                        video_id=video_id,
                        job_id=job_id,
                        cookie_source=cookie_source,
                        proxy_mode=proxy_mode,
                        segments_count=len(segments))
                    
                    return segments
                else:
                    # Parsing failed - return None for fallback to next method
                    evt("playwright_dom_parse_failed",
                        video_id=video_id,
                        job_id=job_id,
                        cookie_source=cookie_source,
                        proxy_mode=proxy_mode)
                    return None
            else:
                # No transcript found or DOM interactions failed completely - return None for fallback to next method (Requirement 9.5)
                evt("playwright_dom_no_transcript",
                    video_id=video_id,
                    job_id=job_id,
                    cookie_source=cookie_source,
                    proxy_mode=proxy_mode,
                    reason="empty_or_none_result")
                return None
                
        except Exception as e:
            # Graceful degradation: DOM interaction failures should not break the transcript pipeline (Requirement 9.4)
            # Log error and return None for graceful fallback to next transcript method (Requirement 9.5)
            evt("playwright_dom_error",
                video_id=video_id,
                job_id=job_id,
                cookie_source=cookie_source,
                proxy_mode=proxy_mode,
                error_type=type(e).__name__,
                error_detail=str(e)[:200])
            
            # Classify error for better debugging
            error_class = classify_transcript_error(e, video_id, "playwright_dom")
            
            # Requirement 7.5: Add warning logs for failures without verbose dumps or stack traces
            logger.warning(f"playwright_dom_error: {type(e).__name__}")
            
            # Return None to trigger fallback to next transcript method (Requirement 9.5, 14.4)
            return None
    
    def _parse_transcript_text_to_segments(self, transcript_text: str) -> List[Dict]:
        """
        Parse raw transcript text into segments format using _extract_cues_from_youtubei method.
        
        Implements graceful degradation - never throws exceptions that break the transcript pipeline.
        
        Requirements: 9.4, 14.4
        
        Args:
            transcript_text: Raw transcript text or JSON data
            
        Returns:
            List of transcript segments with text, start, and duration
        """
        # Graceful degradation: handle None or empty input
        if not transcript_text or not transcript_text.strip():
            return []
        
        try:
            # Try to parse as JSON first (YouTubei format)
            import json
            data = json.loads(transcript_text)
            
            # Use the new _extract_cues_from_youtubei method for structured parsing
            if isinstance(data, dict) and 'actions' in data:
                try:
                    segments = _extract_cues_from_youtubei(data)
                    if segments and len(segments) > 0:
                        return segments
                except Exception as extract_error:
                    # Graceful degradation: extraction failure should not break parsing
                    evt("transcript_parse_extract_failed",
                        error_type=type(extract_error).__name__,
                        error=str(extract_error)[:100])
            
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as json_error:
            # Graceful degradation: JSON parsing failure should fall back to plain text
            evt("transcript_parse_json_failed",
                error_type=type(json_error).__name__,
                error=str(json_error)[:100])
        except Exception as parse_error:
            # Graceful degradation: any other parsing error should not break the pipeline
            evt("transcript_parse_unexpected_error",
                error_type=type(parse_error).__name__,
                error=str(parse_error)[:100])
        
        try:
            # Fallback: treat as plain text and create single segment
            if transcript_text.strip():
                return [{
                    'text': transcript_text.strip(),
                    'start': 0.0,
                    'duration': 0.0
                }]
        except Exception as fallback_error:
            # Graceful degradation: even fallback parsing should not break the pipeline
            evt("transcript_parse_fallback_failed",
                error_type=type(fallback_error).__name__,
                error=str(fallback_error)[:100])
        
        # Graceful degradation: return empty list if all parsing attempts fail
        return []

    def get_health_diagnostics(self):
        """Get diagnostic information for health checks"""
        return {
            "feature_flags": {
                "yt_api": ENABLE_YT_API,
                "timedtext": ENABLE_TIMEDTEXT,
                "youtubei": ENABLE_YOUTUBEI,
                "asr_fallback": ENABLE_ASR_FALLBACK,
            },
            "config": {
                "pw_nav_timeout_ms": PW_NAV_TIMEOUT_MS,
                "use_proxy_for_timedtext": USE_PROXY_FOR_TIMEDTEXT,
                "asr_max_video_minutes": ASR_MAX_VIDEO_MINUTES,
                "deepgram_api_key_configured": bool(self.deepgram_api_key),
            },
            "cache_stats": self.get_cache_stats(),
            "proxy_available": self.proxy_manager is not None,
        }


# --- Enhanced Fallback Strategy ---

def get_transcript_with_intelligent_fallback(video_id, job_id, user_cookies=None):
    """Smart fallback strategy based on error types"""
    
    # Try YouTube API first (fastest)
    try:
        transcript = get_captions_via_api(video_id, user_cookies)
        if transcript:
            return transcript, "youtube_api"
    except (TranscriptsDisabled, NoTranscriptFound):
        # Expected failure, continue to next method
        pass
    except Exception as e:
        # Unexpected error - log but continue
        logger.warning(f"YouTube API unexpected error: {e}")
    
    # Check if video might be age-restricted or blocked
    if _is_likely_age_restricted(video_id):
        # Skip to YouTubei which handles auth better
        return _try_youtubei_with_auth(video_id, job_id, user_cookies)
    
    # Try timedtext
    transcript = get_timedtext_with_retry(video_id)
    if transcript:
        return transcript, "timedtext"
    
    # Finally try YouTubei with enhanced DOM interaction
    transcript = get_transcript_via_youtubei_enhanced(video_id, job_id, user_cookies)
    if transcript:
        return transcript, "youtubei"
    
    # Last resort: ASR
    if ENABLE_ASR_FALLBACK:
        transcript = asr_from_intercepted_audio(video_id, user_cookies)
        if transcript:
            return transcript, "asr"
    
    return None, "none"


def _is_likely_age_restricted(video_id):
    """Heuristic to detect age-restricted videos"""
    # Check video metadata or previous error patterns
    # This can be implemented based on historical data
    # For now, return False - this can be enhanced with actual detection logic
    return False


def _try_youtubei_with_auth(video_id, job_id, user_cookies):
    """Try YouTubei with enhanced authentication handling for age-restricted videos"""
    try:
        # Use enhanced YouTubei with authentication focus
        transcript = get_transcript_via_youtubei_enhanced(video_id, job_id, user_cookies)
        if transcript:
            return transcript, "youtubei_auth"
    except Exception as e:
        logger.warning(f"YouTubei with auth failed for {video_id}: {e}")
    
    return None, "none"


def get_timedtext_with_retry(video_id, max_retries=2):
    """Enhanced timedtext with retry logic"""
    for attempt in range(max_retries):
        try:
            transcript = get_captions_via_timedtext(video_id)
            if transcript:
                return transcript
        except Exception as e:
            logger.warning(f"Timedtext attempt {attempt + 1} failed for {video_id}: {e}")
            if attempt < max_retries - 1:
                time.sleep(1 + attempt)  # Exponential backoff
    return None


def get_captions_via_api(video_id, user_cookies):
    """Wrapper function for the enhanced fallback strategy"""
    # Create a temporary TranscriptService instance to use the method
    service = TranscriptService()
    return service.get_captions_via_api(video_id, ("en", "en-US", "es"))


def asr_from_intercepted_audio(video_id, user_cookies):
    """Wrapper function for ASR fallback"""
    # Create a temporary TranscriptService instance to use the method
    service = TranscriptService()
    return service.asr_from_intercepted_audio(video_id, None, user_cookies)


def get_transcript_via_youtubei_enhanced(video_id, job_id, user_cookies=None):
    """Enhanced YouTubei extraction with better error handling"""
    try:
        # Use the existing YouTubei extraction with enhanced settings
        return get_transcript_via_youtubei(video_id, None, user_cookies)
    except Exception as e:
        logger.warning(f"Enhanced YouTubei failed for {video_id}: {e}")
        return None
