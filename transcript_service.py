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
import subprocess
from datetime import datetime
from http.cookies import SimpleCookie
from pathlib import Path
from dataclasses import dataclass
import tenacity

# Import new structured logging components
from log_events import evt, StageTimer
from logging_setup import set_job_ctx, get_job_ctx

# Import enhanced services
from storage_state_manager import get_storage_state_manager
from reliability_config import get_reliability_config

from playwright.sync_api import sync_playwright, Page
from playwright.async_api import async_playwright

# --- Version marker for deployed image provenance ---
# --- Version marker for deployed image provenance ---
APP_VERSION = "asr-fallthrough-debug-v2"
evt("build_marker", marker="asr-fallthrough-debug-v2")

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

# Import YouTubei service functions - DECISION: Use centralized service
from youtubei_service import extract_transcript_with_job_proxy, DeterministicYouTubeiCapture

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

logger = get_logger(__name__)

_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)

# --- Configuration and Constants ---

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
GLOBAL_JOB_TIMEOUT = 1800  # 30 minutes maximum job duration (allows ASR fallback for long videos)

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


# --- Circuit Breaker Implementation ---

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


# --- Helper Functions ---

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
        "compat_error": f"Compatibility layer error for video {video_id}. Please report this issue.",
    }
    
    return error_messages.get(error_classification, f"An error occurred while processing video {video_id}. Please try again later.")


def classify_transcript_error(error: Exception, video_id: str, method: str) -> str:
    """Classify transcript errors for better debugging and monitoring with API 1.2.2 support."""
    error_type = type(error).__name__
    error_message = str(error).lower()
    
    # API 1.2.2 specific error classifications
    if isinstance(error, AgeRestricted):
        return "age_restricted"
    elif isinstance(error, CookieError) or isinstance(error, CookieInvalid) or isinstance(error, CookiePathInvalid):
        return "cookie_error"
    elif isinstance(error, PoTokenRequired):
        return "po_token_required"
    elif isinstance(error, RequestBlocked) or isinstance(error, IpBlocked):
        return "request_blocked"
    elif isinstance(error, HTTPError):
        return "http_error"
    elif isinstance(error, TranslationLanguageNotAvailable) or isinstance(error, NotTranslatable):
        return "translation_error"
    elif isinstance(error, VideoUnplayable) or isinstance(error, VideoUnavailable):
        return "video_unavailable"
    elif isinstance(error, InvalidVideoId):
        return "video_unavailable"
    elif isinstance(error, YouTubeDataUnparsable):
        return "parsing_error"
    elif isinstance(error, CouldNotRetrieveTranscript):
        return "retrieval_error"
    elif isinstance(error, FailedToCreateConsentCookie):
        return "cookie_error"
    elif isinstance(error, YouTubeRequestFailed):
        return "http_error"
    elif isinstance(error, TranscriptApiError):
        return "compat_error"
    
    # Legacy error classifications
    elif isinstance(error, (TranscriptsDisabled, NoTranscriptFound)):
        return "no_transcript"
    elif "timeout" in error_message or "timeouterror" in error_type.lower():
        return "timeout"
    elif detect_youtube_blocking(error_message):
        return "youtube_blocking"
    elif "migration" in error_message or "api" in error_message:
        return "api_migration_error"
    else:
        return "retrieval_error"


# --- Resource Management ---

class ResourceCleanupManager:
    """Ensures proper cleanup of resources on timeout or failure."""
    
    def __init__(self):
        self.resources = []
    
    def register(self, resource, cleanup_func):
        """Register a resource with its cleanup function."""
        self.resources.append((resource, cleanup_func))
    
    def cleanup_all(self):
        """Clean up all registered resources."""
        for resource, cleanup_func in self.resources:
            try:
                cleanup_func(resource)
            except Exception as e:
                logger.warning(f"Failed to cleanup resource: {e}")
        self.resources.clear()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup_all()


# --- Cookie Management ---

def _resolve_cookie_file_path() -> Optional[str]:
    """Prefer COOKIE_DIR/cookies.txt, then latest .txt in COOKIE_DIR, then legacy COOKIE_LOCAL_DIR, finally COOKIES_FILE_PATH."""
    explicit = os.getenv("COOKIES_FILE_PATH")
    if explicit and os.path.isfile(explicit):
        return explicit
    
    cookie_dir = os.getenv("COOKIE_DIR", "/app/cookies")
    if os.path.isdir(cookie_dir):
        cookies_txt = os.path.join(cookie_dir, "cookies.txt")
        if os.path.isfile(cookies_txt):
            return cookies_txt
        
        txt_files = [f for f in os.listdir(cookie_dir) if f.endswith('.txt')]
        if txt_files:
            latest = max(txt_files, key=lambda f: os.path.getmtime(os.path.join(cookie_dir, f)))
            return os.path.join(cookie_dir, latest)
    
    return None


def _cookie_header_from_env_or_file() -> Optional[str]:
    """
    Return a 'name=value; name2=value2' cookie string from COOKIES_HEADER (preferred) or cookies.txt.
    """
    # Prefer explicit header
    header = os.getenv("COOKIES_HEADER")
    if header and header.strip():
        return header.strip()
    
    # Fall back to file
    cookie_path = _resolve_cookie_file_path()
    if not cookie_path:
        return None
    
    try:
        with open(cookie_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        if not content:
            return None
        
        # Convert Netscape format to header format
        lines = [line.strip() for line in content.split('\n') if line.strip() and not line.startswith('#')]
        cookie_pairs = []
        
        for line in lines:
            parts = line.split('\t')
            if len(parts) >= 7:
                name, value = parts[5], parts[6]
                if name and value:
                    cookie_pairs.append(f"{name}={value}")
        
        return "; ".join(cookie_pairs) if cookie_pairs else None
        
    except Exception as e:
        logger.warning(f"Failed to read cookie file {cookie_path}: {e}")
        return None


class CookieSecurityManager:
    """Secure cookie handling with validation and sanitization."""
    
    @staticmethod
    def sanitize_cookie_value(value: str) -> str:
        """Remove potentially dangerous characters from cookie values."""
        if not value:
            return ""
        # Remove newlines, carriage returns, and other control characters
        sanitized = ''.join(char for char in value if ord(char) >= 32 and char not in [';', '\n', '\r'])
        return sanitized[:1000]  # Limit length
    
    @staticmethod
    def validate_cookie_format(cookie_string: str) -> bool:
        """Validate cookie string format."""
        if not cookie_string or len(cookie_string) > 8192:  # Reasonable size limit
            return False
        
        # Basic format validation
        try:
            SimpleCookie(cookie_string)
            return True
        except Exception:
            return False


class EnhancedPlaywrightManager:
    """Enhanced Playwright context management with automatic storage state loading and Netscape conversion."""
    
    def __init__(self):
        self.storage_state_path = Path("/app/cookies/storage_state.json")
        self.netscape_cookie_path = Path("/app/cookies/cookies.txt")
        self.storage_state_manager = get_storage_state_manager()
    
    def ensure_storage_state_available(self) -> bool:
        """
        Ensure storage_state.json is available, converting from Netscape format if needed.
        
        Returns:
            bool: True if storage state is available, False otherwise
        """
        try:
            # Check if storage_state.json already exists and is recent
            if (self.storage_state_path.exists() and 
                self.storage_state_path.stat().st_mtime > time.time() - 3600):  # 1 hour freshness
                return True
            
            # Check if Netscape cookies.txt exists
            if not self.netscape_cookie_path.exists():
                logger.info("No Netscape cookie file found, proceeding without storage state")
                return False
            
            # Convert Netscape to storage state format
            logger.info(f"Converting Netscape cookies from {self.netscape_cookie_path} to storage state")
            
            # Read Netscape format
            with open(self.netscape_cookie_path, 'r', encoding='utf-8') as f:
                netscape_content = f.read().strip()
            
            if not netscape_content:
                logger.warning("Netscape cookie file is empty")
                return False
            
            # Parse Netscape format and convert to Playwright storage state
            cookies = []
            lines = [line.strip() for line in netscape_content.split('\n') 
                    if line.strip() and not line.startswith('#')]
            
            for line in lines:
                parts = line.split('\t')
                if len(parts) >= 7:
                    domain = parts[0]
                    path = parts[2]
                    secure = parts[3].lower() == 'true'
                    expires = parts[4]
                    name = parts[5]
                    value = parts[6]
                    
                    # Convert to Playwright cookie format
                    cookie = {
                        "name": name,
                        "value": value,
                        "domain": domain,
                        "path": path,
                        "secure": secure,
                        "httpOnly": False,  # Default for Netscape format
                        "sameSite": "Lax"   # Default
                    }
                    
                    # Add expiry if present
                    if expires and expires != "0":
                        try:
                            cookie["expires"] = int(expires)
                        except ValueError:
                            pass
                    
                    cookies.append(cookie)
            
            if not cookies:
                logger.warning("No valid cookies found in Netscape file")
                return False
            
            # Create storage state structure
            storage_state = {
                "cookies": cookies,
                "origins": []
            }
            
            # Ensure directory exists
            self.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write storage state
            with open(self.storage_state_path, 'w', encoding='utf-8') as f:
                json.dump(storage_state, f, indent=2)
            
            logger.info(f"Successfully converted {len(cookies)} cookies to storage state format")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to ensure storage state availability: {e}")
            return False
    
    def _convert_cookiejar_to_playwright_format(self, cookie_jar) -> List[Dict]:
        """Convert requests CookieJar to Playwright cookie format."""
        if not cookie_jar:
            return []
        
        cookies = []
        for cookie in cookie_jar:
            playwright_cookie = {
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain,
                "path": cookie.path,
                "secure": cookie.secure,
                "httpOnly": getattr(cookie, 'has_nonstandard_attr', lambda x: False)('HttpOnly'),
                "sameSite": "Lax"  # Default
            }
            
            if cookie.expires:
                playwright_cookie["expires"] = cookie.expires
            
            cookies.append(playwright_cookie)
        
        return cookies


def load_user_cookies_from_s3(user_id: int) -> Optional[Dict[str, str]]:
    """
    Load user cookies from S3 bucket with error handling.
    
    Args:
        user_id: User ID for cookie lookup
        
    Returns:
        Dict of cookie name-value pairs, or None if not found/error
    """
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
        
        # Get S3 configuration
        bucket_name = os.getenv("S3_COOKIE_BUCKET")
        if not bucket_name:
            logger.debug("S3_COOKIE_BUCKET not configured, skipping S3 cookie lookup")
            return None
        
        # Create S3 client
        s3_client = boto3.client('s3')
        
        # Construct S3 key
        s3_key = f"user_cookies/{user_id}/cookies.json"
        
        # Fetch from S3
        response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
        cookie_data = json.loads(response['Body'].read().decode('utf-8'))
        
        logger.info(f"Successfully loaded cookies for user {user_id} from S3")
        return cookie_data
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey':
            logger.debug(f"No cookies found in S3 for user {user_id}")
        else:
            logger.warning(f"S3 error loading cookies for user {user_id}: {error_code}")
        return None
    except NoCredentialsError:
        logger.warning("AWS credentials not configured for S3 cookie access")
        return None
    except Exception as e:
        logger.warning(f"Unexpected error loading cookies from S3 for user {user_id}: {e}")
        return None


def get_user_cookies_with_fallback(user_id: Optional[int] = None) -> Optional[str]:
    """
    Get user cookies with S3-first, environment-fallback strategy.
    
    Args:
        user_id: Optional user ID for S3 lookup
        
    Returns:
        Cookie header string or None
    """
    # Try S3 first if user_id provided
    if user_id:
        s3_cookies = load_user_cookies_from_s3(user_id)
        if s3_cookies:
            # Convert dict to cookie header format
            cookie_pairs = [f"{name}={value}" for name, value in s3_cookies.items()]
            return "; ".join(cookie_pairs)
    
    # Fallback to environment/file
    return _cookie_header_from_env_or_file()


# --- HTTP Session and Proxy Management ---

def make_http_session():
    """Create HTTP session with retry logic for timed-text requests"""
    session = requests.Session()
    
    # Configure retry strategy
    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],  # urllib3 2.0+ (was method_whitelist)
        backoff_factor=1
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session


def _requests_proxies(pm) -> Optional[Dict[str, str]]:
    if not pm:
        return None
    proxy_dict = pm.proxy_dict_for("requests")
    if not proxy_dict:
        return None
    return proxy_dict


def _playwright_proxy(pm) -> Optional[Dict[str, str]]:
    if not pm:
        return None
    proxy_dict = pm.proxy_dict_for("playwright")
    if not proxy_dict:
        return None
    return proxy_dict


def _ffmpeg_proxy_url(pm) -> Optional[str]:
    """
    Build an http(s) proxy URL for ffmpeg. Prefer requests-style https proxy URL.
    """
    if not pm:
        return None
    
    proxy_dict = pm.proxy_dict_for("requests")
    if not proxy_dict:
        return None
    
    # Prefer https proxy, fall back to http
    proxy_url = proxy_dict.get("https") or proxy_dict.get("http")
    if proxy_url:
        logger.info(f"ffmpeg proxy URL: {proxy_url}")
        return proxy_url
    
    return None


def _convert_cookiejar_to_playwright_format(cookie_jar) -> List[Dict]:
    """Convert requests CookieJar to Playwright cookie format."""
    if not cookie_jar:
        return []
    
    cookies = []
    for cookie in cookie_jar:
        playwright_cookie = {
            "name": cookie.name,
            "value": cookie.value,
            "domain": cookie.domain,
            "path": cookie.path,
            "secure": cookie.secure,
            "httpOnly": getattr(cookie, 'has_nonstandard_attr', lambda x: False)('HttpOnly'),
            "sameSite": "Lax"  # Default
        }
        
        if cookie.expires:
            playwright_cookie["expires"] = cookie.expires
        
        cookies.append(playwright_cookie)
    
    return cookies


def validate_config():
    """Validate configuration for ASR only (email is validated in EmailService)."""
    if ENABLE_ASR_FALLBACK and not os.getenv("DEEPGRAM_API_KEY"):
        logger.warning(
            "ASR fallback is enabled but DEEPGRAM_API_KEY is not set. "
            "ASR transcription will fail if needed."
        )
        return False
    return True


# --- Playwright Helper Functions ---

def _try_click_any(page, selectors, wait_after=0):
    for sel in selectors:
        try:
            page.locator(sel).first.click(timeout=5000)
            if wait_after > 0:
                page.wait_for_timeout(wait_after)
            return True
        except Exception:
            continue
    return False


async def _try_click_any_async(page, selectors, wait_after=0):
    """Async version of _try_click_any for use with async Playwright"""
    for sel in selectors:
        try:
            await page.locator(sel).first.click(timeout=5000)
            if wait_after > 0:
                await page.wait_for_timeout(wait_after)
            return True
        except Exception:
            continue
    return False


def _launch_args_with_proxy(proxy_manager):
    args = {"headless": True}
    if proxy_manager:
        proxy_config = _playwright_proxy(proxy_manager)
        if proxy_config:
            args["proxy"] = proxy_config
    return args


def _scroll_until(page, is_ready, max_steps=40, dy=3000, pause_ms=200):
    """Scrolls until is_ready() returns True or steps exhausted."""
    for _ in range(max_steps):
        if is_ready():
            return True
        try:
            page.evaluate(f"window.scrollBy(0, {dy})")
            page.wait_for_timeout(pause_ms)
        except Exception:
            break
    return is_ready()


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


def youtube_reachable(timeout_s=5) -> bool:
    """Preflight check: ping YouTube reachability before Playwright"""
    try:
        response = requests.get("https://www.youtube.com", timeout=timeout_s)
        return response.status_code == 200
    except Exception:
        return False


# --- Timedtext Path ---

def _fetch_timedtext_xml(
    video_id: str, lang: str, kind=None, cookies=None, proxies=None, timeout_s=15
) -> str:
    """Fetch timedtext XML with enhanced error handling and validation."""
    
    # Build timedtext URL
    base_url = "https://www.youtube.com/api/timedtext"
    params = {
        "v": video_id,
        "lang": lang,
        "fmt": "srv3"  # XML format
    }
    
    if kind:
        params["kind"] = kind
    
    # Prepare headers
    headers = {
        "User-Agent": _CHROME_UA,
        "Accept-Language": "en-US,en;q=0.8"
    }
    
    if cookies:
        headers["Cookie"] = cookies
    
    try:
        session = make_http_session()
        
        # Make request with validation
        response = session.get(
            base_url,
            params=params,
            headers=headers,
            proxies=proxies,
            timeout=timeout_s
        )
        
        response.raise_for_status()
        
        # Validate and parse XML response
        try:
            root = _validate_and_parse_xml(response, context="timedtext_xml")
            
            # Extract text from XML
            transcript_parts = []
            for text_elem in root.findall(".//text"):
                text_content = text_elem.text
                if text_content and text_content.strip():
                    transcript_parts.append(text_content.strip())
            
            return "\n".join(transcript_parts)
            
        except ContentValidationError as e:
            if e.should_retry_with_cookies:
                evt("timedtext_xml_validation_failed_retry_suggested", 
                    video_id=video_id, lang=lang, reason=e.error_reason)
            else:
                evt("timedtext_xml_validation_failed", 
                    video_id=video_id, lang=lang, reason=e.error_reason)
            return ""
        
    except requests.exceptions.RequestException as e:
        evt("timedtext_xml_request_failed", 
            video_id=video_id, lang=lang, error=str(e)[:100])
        return ""
    except Exception as e:
        evt("timedtext_xml_unexpected_error", 
            video_id=video_id, lang=lang, error=str(e)[:100])
        return ""


def _fetch_timedtext_json3(video_id: str, proxy_manager=None, cookies=None) -> str:
    """Timedtext with Cookie header first, json3 parse; falls back by lang/kind."""
    headers = {"Accept-Language": "en-US,en;q=0.8"}
    
    if cookies:
        headers["Cookie"] = cookies
    
    proxies = _requests_proxies(proxy_manager) if USE_PROXY_FOR_TIMEDTEXT else None
    
    # Try multiple language/kind combinations
    attempts = [
        ("en", "asr"),      # Auto-generated English
        ("en", None),       # Manual English
        ("en-US", "asr"),   # Auto-generated US English
        ("en-US", None),    # Manual US English
    ]
    
    for lang, kind in attempts:
        try:
            base_url = "https://www.youtube.com/api/timedtext"
            params = {
                "v": video_id,
                "lang": lang,
                "fmt": "json3"
            }
            
            if kind:
                params["kind"] = kind
            
            session = make_http_session()
            response = session.get(
                base_url,
                params=params,
                headers=headers,
                proxies=proxies,
                timeout=15
            )
            
            response.raise_for_status()
            
            # Parse JSON3 format
            try:
                data = response.json()
                if "events" in data:
                    transcript_parts = []
                    for event in data["events"]:
                        if "segs" in event:
                            for seg in event["segs"]:
                                if "utf8" in seg:
                                    text = seg["utf8"].strip()
                                    if text:
                                        transcript_parts.append(text)
                    
                    if transcript_parts:
                        evt("timedtext_json3_success", 
                            video_id=video_id, lang=lang, kind=kind)
                        return "\n".join(transcript_parts)
                        
            except (json.JSONDecodeError, KeyError) as e:
                evt("timedtext_json3_parse_failed", 
                    video_id=video_id, lang=lang, kind=kind, error=str(e)[:100])
                continue
                
        except requests.exceptions.RequestException as e:
            evt("timedtext_json3_request_failed", 
                video_id=video_id, lang=lang, kind=kind, error=str(e)[:100])
            continue
        except Exception as e:
            evt("timedtext_json3_unexpected_error", 
                video_id=video_id, lang=lang, kind=kind, error=str(e)[:100])
            continue
    
    return ""


def _fetch_timedtext(
    video_id: str, lang: str, kind=None, cookies=None, proxies=None, timeout_s=15
) -> str:
    """Legacy timedtext fetch function for backward compatibility."""
    return _fetch_timedtext_xml(video_id, lang, kind, cookies, proxies, timeout_s)


def get_transcript_with_cookies_fixed(video_id: str, language_codes: list, user_id: int, proxies=None) -> str:
    """
    Fixed version with proper S3 cookie handling and error propagation.
    """
    try:
        # Get user cookies with S3-first strategy
        cookie_header = get_user_cookies_with_fallback(user_id)
        
        if not cookie_header:
            evt("transcript_cookies_not_available", video_id=video_id, user_id=user_id)
            return ""
        
        # Validate cookie format
        if not CookieSecurityManager.validate_cookie_format(cookie_header):
            evt("transcript_cookies_invalid_format", video_id=video_id, user_id=user_id)
            return ""
        
        # Try each language code
        for lang_code in language_codes:
            try:
                # Try JSON3 format first
                transcript = _fetch_timedtext_json3(video_id, None, cookie_header)
                if transcript:
                    evt("transcript_cookies_success", 
                        video_id=video_id, user_id=user_id, lang=lang_code, format="json3")
                    return transcript
                
                # Fallback to XML format
                transcript = _fetch_timedtext_xml(video_id, lang_code, None, cookie_header, proxies)
                if transcript:
                    evt("transcript_cookies_success", 
                        video_id=video_id, user_id=user_id, lang=lang_code, format="xml")
                    return transcript
                    
            except Exception as e:
                evt("transcript_cookies_lang_failed", 
                    video_id=video_id, user_id=user_id, lang=lang_code, error=str(e)[:100])
                continue
        
        evt("transcript_cookies_all_langs_failed", video_id=video_id, user_id=user_id)
        return ""
        
    except Exception as e:
        evt("transcript_cookies_unexpected_error", 
            video_id=video_id, user_id=user_id, error=str(e)[:100])
        return ""


def get_transcript_with_cookies(video_id: str, language_codes: list, cookies=None, proxies=None) -> str:
    """
    Direct HTTP transcript fetching with cookie support.
    """
    if not cookies:
        return ""
    
    # Validate cookie format
    if not CookieSecurityManager.validate_cookie_format(cookies):
        evt("transcript_cookies_invalid_format", video_id=video_id)
        return ""
    
    # Try each language code
    for lang_code in language_codes:
        try:
            # Try JSON3 format first
            transcript = _fetch_timedtext_json3(video_id, None, cookies)
            if transcript:
                evt("transcript_cookies_direct_success", 
                    video_id=video_id, lang=lang_code, format="json3")
                return transcript
            
            # Fallback to XML format
            transcript = _fetch_timedtext_xml(video_id, lang_code, None, cookies, proxies)
            if transcript:
                evt("transcript_cookies_direct_success", 
                    video_id=video_id, lang=lang_code, format="xml")
                return transcript
                
        except Exception as e:
            evt("transcript_cookies_direct_lang_failed", 
                video_id=video_id, lang=lang_code, error=str(e)[:100])
            continue
    
    evt("transcript_cookies_direct_all_langs_failed", video_id=video_id)
    return ""


def get_captions_via_timedtext(
    video_id: str, proxy_manager=None, cookie_jar=None, user_cookies=None
) -> str:
    """
    Enhanced timedtext extraction with multiple fallback strategies.
    """
    # Determine cookie source
    cookies = None
    if user_cookies:
        cookies = user_cookies
    elif cookie_jar:
        # Convert cookie jar to header format
        cookie_pairs = []
        for cookie in cookie_jar:
            cookie_pairs.append(f"{cookie.name}={cookie.value}")
        cookies = "; ".join(cookie_pairs)
    else:
        cookies = _cookie_header_from_env_or_file()
    
    # Try JSON3 format first (most reliable)
    transcript = _fetch_timedtext_json3(video_id, proxy_manager, cookies)
    if transcript:
        evt("timedtext_success", video_id=video_id, format="json3")
        return transcript
    
    # Try XML format with different language/kind combinations
    attempts = [
        ("en", "asr"),      # Auto-generated English
        ("en", None),       # Manual English
        ("en-US", "asr"),   # Auto-generated US English
        ("en-US", None),    # Manual US English
    ]
    
    proxies = _requests_proxies(proxy_manager) if USE_PROXY_FOR_TIMEDTEXT else None
    
    for lang, kind in attempts:
        try:
            transcript = _fetch_timedtext_xml(video_id, lang, kind, cookies, proxies)
            if transcript:
                evt("timedtext_success", video_id=video_id, format="xml", lang=lang, kind=kind)
                return transcript
        except Exception as e:
            evt("timedtext_attempt_failed", 
                video_id=video_id, lang=lang, kind=kind, error=str(e)[:100])
            continue
    
    evt("timedtext_all_attempts_failed", video_id=video_id)
    return ""


# --- ASR Fallback ---

import threading
_BROWSER_SEM = threading.Semaphore(2)  # Limit concurrent browser instances


class ASRAudioExtractor:
    """ASR fallback system with HLS audio extraction and Deepgram transcription"""

    def __init__(self, deepgram_api_key: str, proxy_manager=None):
        self.deepgram_api_key = deepgram_api_key
        self.proxy_manager = proxy_manager

    def extract_transcript(self, video_id: str, job_id: str = None) -> str:
        """
        Extract transcript using ASR fallback with audio extraction and Deepgram transcription.
        
        Supports two audio extraction methods:
        1. yt-dlp: Deterministic extraction (ASR_AUDIO_EXTRACTOR=yt_dlp)
        2. Playwright HLS: Browser-based extraction (default)
        
        Args:
            video_id: YouTube video ID
            job_id: Optional job ID for context tracking
            
        Returns:
            Transcript text or empty string if failed
        """
        # Circuit breaker check at the start of extraction
        if _playwright_circuit_breaker.is_open():
            recovery_time = _playwright_circuit_breaker.get_recovery_time_remaining()
            evt("asr_circuit_breaker", state="open", recovery=recovery_time, video_id=video_id)
            return ""
        
        if not self.deepgram_api_key:
            evt("asr_no_api_key", video_id=video_id)
            return ""
        
        # Check ENFORCE_PROXY_ALL compliance
        if ENFORCE_PROXY_ALL and not (self.proxy_manager and self.proxy_manager.in_use):
            evt("asr_blocked", reason="enforce_proxy_no_proxy", video_id=video_id)
            return ""
        
        try:
            # Set job context if provided
            if job_id:
                set_job_ctx(job_id=job_id, video_id=video_id)
            
            evt("asr_start", video_id=video_id)
            
            # Step 1: Extract audio URL
            # Check ASR_AUDIO_EXTRACTOR flag for yt-dlp support
            asr_audio_extractor = os.getenv("ASR_AUDIO_EXTRACTOR", "").lower()
            audio_url = None
            
            if asr_audio_extractor == "yt_dlp":
                # Use yt-dlp for audio URL extraction
                try:
                    from ytdlp_service import extract_best_audio_url
                    
                    evt("asr_audio_source_select", source="yt_dlp", video_id=video_id)
                    
                    result = extract_best_audio_url(
                        youtube_url=video_id,
                        proxy_manager=self.proxy_manager,
                        job_id=job_id
                    )
                    
                    if result.get("success"):
                        audio_url = result["url"]
                        evt("asr_audio_source_selected",
                            source="yt_dlp",
                            format_id=result.get("format_id"),
                            ext=result.get("ext"),
                            abr=result.get("abr"),
                            proxy_used=result.get("proxy_used"),
                            proxy_enabled=result.get("proxy_enabled"),
                            proxy_host=result.get("proxy_host"),
                            proxy_profile=result.get("proxy_profile"))
                    else:
                        # yt-dlp failed, log and fall back to Playwright
                        evt("asr_audio_source_failed",
                            source="yt_dlp",
                            fail_class=result.get("fail_class"),
                            error=result.get("error", "")[:200])
                        
                        # Graceful fallback to existing method
                        evt("asr_fallback_to_playwright", reason="ytdlp_failed", video_id=video_id)
                        audio_url = self._extract_hls_audio_url(video_id, self.proxy_manager, None)
                        
                except Exception as e:
                    # yt-dlp import or execution error, fall back to Playwright
                    evt("asr_ytdlp_error",
                        error=str(e)[:200],
                        video_id=video_id)
                    evt("asr_fallback_to_playwright", reason="ytdlp_exception", video_id=video_id)
                    audio_url = self._extract_hls_audio_url(video_id, self.proxy_manager, None)
            
            else:
                # Default: Use existing Playwright HLS extraction
                evt("asr_audio_source_select", source="playwright_hls", video_id=video_id)
                audio_url = self._extract_hls_audio_url(video_id, self.proxy_manager, None)
            
            if not audio_url:
                evt("asr_step", step="audio_url_extraction", outcome="no_url", video_id=video_id)
                return ""
            
            evt("asr_step", step="audio_url_extraction", outcome="success", video_id=video_id)
            
            # Step 2: Extract audio to WAV using ffmpeg
            import tempfile
            import os
            
            with tempfile.TemporaryDirectory() as temp_dir:
                wav_path = os.path.join(temp_dir, "audio.wav")
                
                if not self._extract_audio_to_wav(audio_url, wav_path):
                    evt("asr_step", step="audio_extraction", outcome="failed", video_id=video_id)
                    return ""
                
                evt("asr_step", step="audio_extraction", outcome="success", video_id=video_id)
                
                # Step 3: Transcribe with Deepgram
                with open(wav_path, "rb") as f:
                    audio_data = f.read()
                
                transcript = self._transcribe_with_deepgram(audio_data, video_id)
                
                if transcript:
                    evt("asr_transcription_success", 
                        video_id=video_id, transcript_length=len(transcript))
                    return transcript
                else:
                    evt("asr_transcription_failed", video_id=video_id)
                    return ""
                
        except Exception as e:
            evt("asr_extraction_error", 
                video_id=video_id, error=str(e)[:100])
            return ""

    def _transcribe_with_deepgram(self, audio_data: bytes, video_id: str) -> str:
        """
        Transcribe audio data using Deepgram API.
        
        Args:
            audio_data: Raw audio bytes
            video_id: Video ID for logging
            
        Returns:
            Transcript text or empty string if failed
        """
        try:
            import httpx
            
            # Prepare Deepgram API request
            url = "https://api.deepgram.com/v1/listen"
            headers = {
                "Authorization": f"Token {self.deepgram_api_key}",
                "Content-Type": "audio/wav"
            }
            
            params = {
                "model": "nova-2",
                "language": "en",
                "smart_format": "true",
                "punctuate": "true",
                "diarize": "false"
            }
            
            # Make API request
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    url,
                    headers=headers,
                    params=params,
                    content=audio_data
                )
                
                response.raise_for_status()
                result = response.json()
            
            # Extract transcript from response
            if "results" in result and "channels" in result["results"]:
                channels = result["results"]["channels"]
                if channels and "alternatives" in channels[0]:
                    alternatives = channels[0]["alternatives"]
                    if alternatives and "transcript" in alternatives[0]:
                        transcript = alternatives[0]["transcript"]
                        if transcript and transcript.strip():
                            return transcript.strip()
            
            evt("asr_deepgram_empty_response", video_id=video_id)
            return ""
            
        except httpx.HTTPStatusError as e:
            evt("asr_deepgram_http_error", 
                video_id=video_id, status_code=e.response.status_code)
            return ""
        except httpx.TimeoutException:
            evt("asr_deepgram_timeout", video_id=video_id)
            return ""
        except Exception as e:
            evt("asr_deepgram_error", 
                video_id=video_id, error=str(e)[:100])
            return ""

    def _extract_hls_audio_url(
        self, video_id: str, proxy_manager=None, cookies=None
    ) -> str:
        """Use Playwright to capture HLS audio stream URL"""
        timeout_ms = PW_NAV_TIMEOUT_MS

        # Circuit breaker check
        if _playwright_circuit_breaker.is_open():
            evt("asr_circuit_breaker", state="open",
                recovery=_playwright_circuit_breaker.get_recovery_time_remaining())
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
                                        logger.info(f"ASR retry {retry + 1} for {url} after {backoff_time}ms backoff")
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
                                                logger.info(f"ASR: Accepted consent with {selector}")
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
                                        logger.warning(f"ASR playback initiation failed: {playback_error}")
                                        # Continue anyway - HLS/MPD streams might still be captured
                                    
                                    # Give more time for stream/manifest to load
                                    page.wait_for_timeout(8000)  # Increased from 5s to 8s

                                    if captured_url["url"]:
                                        _playwright_circuit_breaker.record_success()
                                        logger.info(f"ASR audio URL captured successfully on attempt {retry + 1}")
                                        return captured_url["url"]
                                    
                                    # If no URL captured, this attempt failed
                                    if retry < max_retries - 1:
                                        logger.warning(f"ASR attempt {retry + 1} failed to capture audio URL for {url}, retrying...")
                                        continue
                                    else:
                                        logger.warning(f"ASR failed to capture audio URL for {url} after {max_retries} attempts")
                                        break

                                except Exception as e:
                                    error_type = type(e).__name__
                                    if "TimeoutError" in error_type:
                                        logger.warning(f"ASR timeout on attempt {retry + 1} for {url}: {e}")
                                        if retry < max_retries - 1:
                                            continue
                                    else:
                                        logger.warning(f"ASR error on attempt {retry + 1} for {url}: {e}")
                                        if retry < max_retries - 1:
                                            continue
                                    break

                        # If we captured a URL with this strategy, return it
                        if captured_url["url"]:
                            _playwright_circuit_breaker.record_success()
                            logger.info(f"ASR audio URL captured using {strategy_name} strategy")
                            return captured_url["url"]

                    except Exception as e:
                        strategy_name = "direct" if pw_proxy is None else "proxy"
                        if "TimeoutError" in str(type(e)):
                            logger.warning(f"ASR {strategy_name} strategy timeout: {e}")
                        else:
                            logger.warning(f"ASR {strategy_name} strategy error: {e}")

                    finally:
                        try:
                            if browser:
                                browser.close()
                        except Exception:
                            pass
                    
                    # If this wasn't the last strategy, continue to next one
                    if strategy_index < len(proxy_strategies) - 1:
                        logger.info(f"ASR {strategy_name} strategy failed, trying next strategy")
                        continue

        return ""

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

    def _extract_audio_to_wav(self, audio_url: str, wav_path: str) -> bool:
        """Extract audio from HLS stream to WAV using ffmpeg with WebM/Opus hardening and proxy support"""
        max_retries = 2
        
        for attempt in range(max_retries):
            start_time = time.time()
            try:
                # Pass headers to avoid 403 on googlevideo domains (UA/Referer) and include Cookie if available
                headers = [f"User-Agent: {_CHROME_UA}", "Referer: https://www.youtube.com/"]
                
                # Build headers with proper CRLF formatting and validation
                headers_arg = self._build_ffmpeg_headers(headers)
                if not headers_arg:
                    logger.error("Failed to build valid FFmpeg headers")
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
                        logger.info("Using proxy environment variables for FFmpeg subprocess")
                elif ENFORCE_PROXY_ALL:
                    # Fallback to legacy proxy URL method if proxy_manager not available
                    proxy_url = _ffmpeg_proxy_url(self.proxy_manager)
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
                logger.info(f"FFmpeg command (attempt {attempt + 1}): {' '.join(safe_cmd)}")

                # Prepare environment for subprocess - inherit current env and add proxy vars
                subprocess_env = os.environ.copy()
                if proxy_env:
                    subprocess_env.update(proxy_env)

                # Execute FFmpeg with timeout
                result = subprocess.run(
                    cmd,
                    env=subprocess_env,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )

                elapsed_time = time.time() - start_time
                
                if result.returncode == 0:
                    # Success
                    evt("asr_ffmpeg_success", attempt=attempt + 1, elapsed_time=elapsed_time)
                    logger.info(f"FFmpeg extraction successful on attempt {attempt + 1} ({elapsed_time:.1f}s)")
                    return True
                else:
                    # FFmpeg failed
                    error_output = result.stderr.strip() if result.stderr else "No error output"
                    evt("asr_ffmpeg_failed", 
                        attempt=attempt + 1, 
                        returncode=result.returncode,
                        error=error_output[:200])
                    
                    logger.warning(f"FFmpeg failed on attempt {attempt + 1}: {error_output}")
                    
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying FFmpeg extraction (attempt {attempt + 2}/{max_retries})")
                        continue
                    else:
                        logger.error(f"FFmpeg extraction failed after {max_retries} attempts")
                        return False

            except subprocess.TimeoutExpired:
                elapsed_time = time.time() - start_time
                evt("asr_ffmpeg_timeout", attempt=attempt + 1, elapsed_time=elapsed_time)
                logger.warning(f"FFmpeg timeout on attempt {attempt + 1} after {elapsed_time:.1f}s")
                
                if attempt < max_retries - 1:
                    continue
                else:
                    return False
                    
            except Exception as e:
                elapsed_time = time.time() - start_time
                evt("asr_ffmpeg_error", 
                    attempt=attempt + 1, 
                    elapsed_time=elapsed_time,
                    error=str(e)[:100])
                logger.error(f"FFmpeg error on attempt {attempt + 1}: {e}")
                
                if attempt < max_retries - 1:
                    continue
                else:
                    return False
        
        return False

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
                logger.error("Headers contain escaped CRLF sequences instead of actual CRLF characters")
                return ""
            
            # Validate that headers end with CRLF
            if not headers_str.endswith("\r\n"):
                logger.error("Headers do not end with proper CRLF sequence")
                return ""
            
            return headers_str
            
        except Exception as e:
            logger.error(f"Failed to build FFmpeg headers: {e}")
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


# --- YouTubei Path (Using Centralized Service) ---

class DeterministicTranscriptCapture:
    """Deterministic transcript capture using page.route() with Future resolution and DOM fallback."""
    
    def __init__(self, timeout_seconds=25):
        self.timeout_seconds = timeout_seconds
        self.transcript_future = None
        self.transcript_data = None
        
    async def setup_route_interception(self, page):
        """Setup route interception for YouTubei transcript API calls."""
        import asyncio
        self.transcript_future = asyncio.Future()
        
        async def handle_route(route):
            """Handle intercepted routes and capture transcript data."""
            request = route.request
            url = request.url
            
            # Check if this is a transcript API call
            if "/youtubei/v1/get_transcript" in url:
                try:
                    # Continue the request and get response
                    response = await route.fetch()
                    
                    if response.status == 200:
                        # Get response body
                        body = await response.body()
                        
                        try:
                            # Parse JSON response
                            data = json.loads(body.decode('utf-8'))
                            
                            # Set the transcript data
                            if not self.transcript_future.done():
                                self.transcript_future.set_result(body.decode('utf-8'))
                            
                            # Fulfill the route with the original response
                            await route.fulfill(response=response)
                            return
                            
                        except json.JSONDecodeError:
                            pass
                    
                    # Fulfill with original response if parsing failed
                    await route.fulfill(response=response)
                    
                except Exception as e:
                    # Continue route on error
                    await route.continue_()
            else:
                # Continue non-transcript routes
                await route.continue_()
        
        # Setup route interception
        await page.route("**/*", handle_route)
    
    async def wait_for_transcript(self):
        """Wait for transcript data to be captured."""
        import asyncio
        
        try:
            # Wait for transcript with timeout
            transcript_data = await asyncio.wait_for(
                self.transcript_future, 
                timeout=self.timeout_seconds
            )
            return transcript_data
        except asyncio.TimeoutError:
            return None
        except Exception:
            return None


def get_transcript_via_youtubei_enhanced(video_id: str, job_id: str = None, user_cookies=None, proxy_manager=None) -> str:
    """Enhanced YouTubei extraction using centralized service."""
    try:
        # Use the centralized YouTubei service with correct parameter order
        return extract_transcript_with_job_proxy(video_id, job_id, proxy_manager, user_cookies)
    except Exception as e:
        evt("youtubei_enhanced_error", 
            video_id=video_id, error=str(e)[:100])
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


# --- YouTube Transcript API Path ---

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


# --- Legacy Playwright Function (Not Used in Main Pipeline) ---

def scrape_transcript_with_playwright(
    video_id: str, pm: Optional[ProxyManager] = None, cookies=None, timeout_ms=60000
) -> str:
    """Legacy Playwright scraper - not used by main fallback chain."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    with sync_playwright() as p:
        launch_args = {"headless": True}
        proxy_config = _pw_proxy(pm)
        if proxy_config:
            launch_args["proxy"] = proxy_config

        browser = p.chromium.launch(**launch_args)
        context = browser.new_context(
            user_agent=_CHROME_UA,
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

        # Wait for transcript content
        try:
            page.wait_for_selector('[data-testid="transcript-segment"]', timeout=10000)
        except Exception:
            browser.close()
            return ""

        # Extract transcript text
        transcript_elements = page.query_selector_all('[data-testid="transcript-segment"]')
        transcript_parts = []
        for elem in transcript_elements:
            text = elem.inner_text()
            if text and text.strip():
                transcript_parts.append(text.strip())

        browser.close()
        return "\n".join(transcript_parts)


# --- Main TranscriptService Class ---

class TranscriptService:
    def __init__(self, use_shared_managers: bool = True):
        self.deepgram_api_key = os.environ.get("DEEPGRAM_API_KEY", "")
        
        # DIAGNOSTIC: Log DEEPGRAM_API_KEY availability at initialization
        deepgram_key_status = "configured" if self.deepgram_api_key else "MISSING"
        deepgram_key_length = len(self.deepgram_api_key) if self.deepgram_api_key else 0
        evt("transcript_service_init", 
            deepgram_key_status=deepgram_key_status,
            deepgram_key_length=deepgram_key_length,
            detail=f"TranscriptService initialized: DEEPGRAM_API_KEY={deepgram_key_status} (length={deepgram_key_length})")
        
        if use_shared_managers:
            self.proxy_manager = shared_managers.get_proxy_manager()
            self.cache = shared_managers.get_transcript_cache()
        else:
            self.proxy_manager = None
            self.cache = TranscriptCache()

    def get_transcript(
        self,
        video_id: str,
        language_codes: Optional[List[str]] = None,
        user_id: Optional[int] = None,
        job_id: Optional[str] = None,
        cookie_header: Optional[str] = None,
    ) -> List[Dict]:
        """
        Main transcript extraction method with hierarchical fallback.
        
        Args:
            video_id: YouTube video ID
            language_codes: Preferred language codes (default: ["en"])
            user_id: Optional user ID for S3 cookie lookup
            job_id: Optional job ID for context tracking
            cookie_header: Optional cookie header string
            
        Returns:
            List of transcript segments with text, start, and duration
        """
        if not video_id:
            return []
        
        # Set default language codes
        if not language_codes:
            language_codes = ["en"]
        
        # Set job context if provided
        if job_id:
            set_job_ctx(job_id=job_id, video_id=video_id)
        
        # Check cache first
        cached_result = self.cache.get(video_id)
        if cached_result:
            evt("transcript_cache_hit", video_id=video_id)
            return cached_result
        
        # Execute transcript pipeline
        result = self._execute_transcript_pipeline(
            video_id=video_id,
            language_codes=language_codes,
            user_id=user_id,
            job_id=job_id,
            cookie_header=cookie_header
        )
        
        # Cache successful results
        if result:
            self.cache.set(video_id, result)
            evt("transcript_cache_set", video_id=video_id, segments_count=len(result))
        
        return result

    def _execute_transcript_pipeline(
        self,
        video_id: str,
        language_codes: List[str],
        user_id: Optional[int] = None,
        job_id: Optional[str] = None,
        cookie_header: Optional[str] = None,
    ) -> List[Dict]:
        """
        Execute the hierarchical transcript extraction pipeline.
        
        Pipeline order:
        1. YouTube Transcript API (youtube-transcript-api)
        2. Timedtext endpoints (json3/xml)
        3. YouTubei capture (centralized service)
        4. ASR fallback (audio extraction + Deepgram)
        
        Returns:
            List of transcript segments or empty list if all methods fail
        """
        
        # Method 1: YouTube Transcript API
        if ENABLE_YT_API:
            try:
                evt("transcript_method_start", method="youtube_api", video_id=video_id)
                
                # Get user cookies for API if available
                user_cookies = get_user_cookies_with_fallback(user_id) if user_id else cookie_header
                
                # Try with compatibility layer
                transcript_list = get_transcript(video_id, language_codes, user_cookies)
                
                if transcript_list:
                    # Convert to standard format
                    segments = []
                    for entry in transcript_list:
                        segments.append({
                            'text': entry.get('text', ''),
                            'start': float(entry.get('start', 0)),
                            'duration': float(entry.get('duration', 0))
                        })
                    
                    if segments:
                        evt("transcript_method_success", method="youtube_api", video_id=video_id)
                        log_successful_transcript_method("youtube_api")
                        return segments
                        
            except Exception as e:
                error_class = classify_transcript_error(e, video_id, "youtube_api")
                evt("transcript_method_failed", 
                    method="youtube_api", video_id=video_id, 
                    error_class=error_class, error=str(e)[:100])
        
        # Method 2: Timedtext endpoints
        if ENABLE_TIMEDTEXT:
            try:
                evt("transcript_method_start", method="timedtext", video_id=video_id)
                
                # Get user cookies
                user_cookies = get_user_cookies_with_fallback(user_id) if user_id else cookie_header
                
                transcript_text = get_captions_via_timedtext(
                    video_id=video_id,
                    proxy_manager=self.proxy_manager,
                    user_cookies=user_cookies
                )
                
                if transcript_text and transcript_text.strip():
                    # Convert to segments format
                    segments = [{
                        'text': transcript_text.strip(),
                        'start': 0.0,
                        'duration': 0.0
                    }]
                    
                    evt("transcript_method_success", method="timedtext", video_id=video_id)
                    log_successful_transcript_method("timedtext")
                    return segments
                    
            except Exception as e:
                error_class = classify_transcript_error(e, video_id, "timedtext")
                evt("transcript_method_failed", 
                    method="timedtext", video_id=video_id, 
                    error_class=error_class, error=str(e)[:100])
        
        # Method 3: YouTubei capture (using centralized service)
        if ENABLE_YOUTUBEI:
            try:
                evt("transcript_method_start", method="youtubei", video_id=video_id)
                
                # Get user cookies
                user_cookies = get_user_cookies_with_fallback(user_id) if user_id else cookie_header
                
                # Use centralized YouTubei service
                transcript_text = get_transcript_via_youtubei_enhanced(
                    video_id=video_id,
                    job_id=job_id,
                    user_cookies=user_cookies,
                    proxy_manager=self.proxy_manager
                )
                
                if transcript_text and transcript_text.strip():
                    # Parse transcript text into segments
                    segments = self._parse_transcript_text_to_segments(transcript_text)
                    
                    if segments:
                        evt("transcript_method_success", method="youtubei", video_id=video_id)
                        log_successful_transcript_method("youtubei")
                        return segments
                        
            except Exception as e:
                error_class = classify_transcript_error(e, video_id, "youtubei")
                evt("transcript_method_failed", 
                    method="youtubei", video_id=video_id, 
                    error_class=error_class, error=str(e)[:100])
            finally:
                evt(
                    "transcript_method_exit",
                    method="youtubei",
                    video_id=video_id,
                    job_id=job_id,
                )
        
        # Method 4: ASR fallback
        
        # Step 2: ASR Block Entry Marker
        evt(
            "transcript_pipeline_enter_asr_block",
            video_id=video_id,
            job_id=job_id,
        )
        
        # Diagnostic logging for ASR eligibility (helps debug staging issues)
        asr_enabled = ENABLE_ASR_FALLBACK
        asr_key_configured = bool(self.deepgram_api_key)
        
        # Step 2: Prove ASR Gate
        evt("asr_eligibility_check",
            video_id=video_id,
            job_id=job_id,
            asr_enabled=asr_enabled,
            deepgram_key_configured=asr_key_configured,
            enabled_var=str(ENABLE_ASR_FALLBACK),
            key_var_present=bool(os.environ.get("DEEPGRAM_API_KEY")))
        
        # Step 3 & 4: Guarantee attempt and do not silently skip
        if asr_enabled and asr_key_configured:
            try:
                evt("transcript_method_start", method="asr", video_id=video_id, job_id=job_id)
                
                asr_extractor = ASRAudioExtractor(
                    deepgram_api_key=self.deepgram_api_key,
                    proxy_manager=self.proxy_manager
                )
                
                transcript_text = asr_extractor.extract_transcript(video_id, job_id)
                
                if transcript_text and transcript_text.strip():
                    # Convert to segments format
                    segments = [{
                        'text': transcript_text.strip(),
                        'start': 0.0,
                        'duration': 0.0
                    }]
                    
                    evt("transcript_method_success", method="asr", video_id=video_id, job_id=job_id)
                    log_successful_transcript_method("asr")
                    return segments
                else:
                    evt("transcript_method_failed",
                        method="asr", video_id=video_id, job_id=job_id,
                        error_class="extraction_failed", error="empty_result")
                    
            except Exception as e:
                error_class = classify_transcript_error(e, video_id, "asr")
                evt("transcript_method_failed", 
                    method="asr", video_id=video_id, job_id=job_id,
                    error_class=error_class, error=str(e)[:100])
        else:
            # Step 4: Explicit skip reason
            if not asr_enabled:
                evt("asr_skipped", reason="asr_disabled_env", video_id=video_id, job_id=job_id)
            elif not asr_key_configured:
                evt("asr_skipped", reason="no_deepgram_key_attr", video_id=video_id, job_id=job_id)
            else:
                evt("asr_skipped", reason="unknown_condition", video_id=video_id, job_id=job_id)
        
        # All methods failed
        evt(
            "transcript_pipeline_returning_empty",
            video_id=video_id,
            job_id=job_id,
        )
        evt("transcript_all_methods_failed", video_id=video_id)
        return []

    async def get_transcript_with_playwright_dom_integration(
        self, 
        video_id: str, 
        job_id: str = None, 
        proxy_manager: ProxyManager = None, 
        cookie_header: str = None
    ) -> Optional[List[Dict]]:
        """
        Enhanced transcript extraction with Playwright DOM interaction integration.
        
        This method integrates with the DeterministicYouTubeiCapture service for
        DOM-based transcript discovery and extraction.
        
        Requirements: 9.4, 9.5, 14.4
        
        Args:
            video_id: YouTube video ID
            job_id: Optional job ID for context tracking
            proxy_manager: Optional proxy manager for network requests
            cookie_header: Optional cookie header for authentication
            
        Returns:
            List of transcript segments or None for graceful fallback to next method
        """
        # Use already imported DeterministicYouTubeiCapture from module level
        
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
    
    def get_cache_stats(self):
        """Get cache statistics"""
        if hasattr(self.cache, 'get_stats'):
            return self.cache.get_stats()
        return {"cache_type": "basic", "stats_available": False}