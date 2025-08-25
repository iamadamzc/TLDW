import os
import logging
from typing import Optional, Tuple, Dict, List
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

from playwright.sync_api import sync_playwright, Page

# --- Version marker for deployed image provenance ---
APP_VERSION = "playwright-fix-2025-08-24T1"

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
    logging.info(f"YouTube Transcript API loaded from: {source_file}")
except Exception as e:
    logging.warning(f"YouTube Transcript API import validation failed: {e}")

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
from transcript_metrics import inc_success, inc_fail

_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)

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

# Performance and safety controls
PW_NAV_TIMEOUT_MS = int(os.getenv("PW_NAV_TIMEOUT_MS", "120000"))  # Increased to 120s for better reliability
USE_PROXY_FOR_TIMEDTEXT = os.getenv("USE_PROXY_FOR_TIMEDTEXT", "1") == "1"  # Default to using proxy for timedtext
ASR_MAX_VIDEO_MINUTES = int(os.getenv("ASR_MAX_VIDEO_MINUTES", "20"))

# Timeout configuration
YOUTUBEI_HARD_TIMEOUT = 150  # seconds maximum YouTubei operation time
PLAYWRIGHT_NAVIGATION_TIMEOUT = 60  # seconds for page navigation
CIRCUIT_BREAKER_RECOVERY = 600  # 10 minutes circuit breaker timeout


class PlaywrightCircuitBreaker:
    """Circuit breaker pattern for Playwright operations."""
    
    def __init__(self):
        self.failure_count = 0
        self.last_failure_time = None
        self.FAILURE_THRESHOLD = 3
        self.RECOVERY_TIME_SECONDS = CIRCUIT_BREAKER_RECOVERY
    
    def is_open(self) -> bool:
        """Check if circuit breaker is open (blocking operations)."""
        if self.failure_count < self.FAILURE_THRESHOLD:
            return False
        
        if self.last_failure_time is None:
            return False
        
        time_since_failure = time.time() - self.last_failure_time
        if time_since_failure > self.RECOVERY_TIME_SECONDS:
            # Reset circuit breaker after recovery time
            self.failure_count = 0
            self.last_failure_time = None
            logging.info("Playwright circuit breaker reset after recovery period")
            return False
        
        return True
    
    def record_success(self) -> None:
        """Reset failure count on successful operation."""
        if self.failure_count > 0:
            logging.info("Playwright circuit breaker reset due to successful operation")
        self.failure_count = 0
        self.last_failure_time = None

    def record_failure(self) -> None:
        """Increment failure count and activate if threshold reached."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.FAILURE_THRESHOLD:
            logging.warning(
                "Playwright circuit breaker activated - skipping for 10 minutes"
            )
        else:
            logging.info(
                f"Playwright failure recorded: {self.failure_count}/{self.FAILURE_THRESHOLD}"
            )


# Global circuit breaker instance
_playwright_circuit_breaker = PlaywrightCircuitBreaker()


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
    logging.error(f"Timeout in {method} for {video_id}: {elapsed_time:.1f}s elapsed")
    
    # Update circuit breaker for Playwright timeouts
    if method in ["youtubei", "playwright", "asr"]:
        _playwright_circuit_breaker.record_failure()
    
    # Log timeout details for monitoring
    logging.info(f"timeout_event video_id={video_id} method={method} elapsed_time={elapsed_time:.1f}")


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
        logging.info(f"No transcript available for {video_id} in {method}: {error_msg}")
        return "no_transcript"
    
    elif isinstance(error, (VideoUnavailable, VideoUnplayable, InvalidVideoId)):
        logging.info(f"Video unavailable for {video_id} in {method}: {error_msg}")
        return "video_unavailable"
    
    elif isinstance(error, AgeRestricted):
        logging.warning(f"Age-restricted video {video_id} in {method}: {error_msg}")
        return "age_restricted"
    
    elif isinstance(error, (CookieError, CookieInvalid, CookiePathInvalid, FailedToCreateConsentCookie)):
        logging.warning(f"Cookie issue for {video_id} in {method}: {error_msg}")
        return "cookie_error"
    
    elif isinstance(error, (IpBlocked, RequestBlocked)):
        logging.warning(f"Request blocked for {video_id} in {method}: {error_msg}")
        return "request_blocked"
    
    elif isinstance(error, PoTokenRequired):
        logging.warning(f"PoToken required for {video_id} in {method}: {error_msg}")
        return "po_token_required"
    
    elif isinstance(error, (HTTPError, YouTubeRequestFailed)):
        logging.warning(f"HTTP/Request error for {video_id} in {method}: {error_msg}")
        return "http_error"
    
    elif isinstance(error, (NotTranslatable, TranslationLanguageNotAvailable)):
        logging.info(f"Translation issue for {video_id} in {method}: {error_msg}")
        return "translation_error"
    
    elif isinstance(error, YouTubeDataUnparsable):
        logging.warning(f"YouTube data parsing error for {video_id} in {method}: {error_msg}")
        return "parsing_error"
    
    elif isinstance(error, CouldNotRetrieveTranscript):
        logging.warning(f"Could not retrieve transcript for {video_id} in {method}: {error_msg}")
        return "retrieval_error"
    
    elif isinstance(error, YouTubeTranscriptApiException):
        logging.warning(f"General API error for {video_id} in {method}: {error_msg}")
        return "api_error"
    
    # Handle compatibility layer errors
    from youtube_transcript_api_compat import TranscriptApiError
    if isinstance(error, TranscriptApiError):
        if "Old API method" in error_msg:
            logging.error(f"API migration issue for {video_id} in {method}: {error_msg}")
            return "api_migration_error"
        else:
            logging.warning(f"Compatibility layer error for {video_id} in {method}: {error_msg}")
            return "compat_error"
    
    # Timeout errors (legacy handling)
    if "TimeoutError" in error_type or "timeout" in error_msg.lower():
        handle_timeout_error(video_id, 0.0, method)  # elapsed_time would need to be passed in
        return "timeout"
    
    # YouTube blocking detection (legacy handling)
    if detect_youtube_blocking(error_msg):
        logging.warning(f"YouTube blocking detected for {video_id} in {method}: {error_msg}")
        return "youtube_blocking"
    
    # Authentication issues (legacy handling)
    if any(auth_indicator in error_msg.lower() for auth_indicator in ["unauthorized", "forbidden", "401", "403"]):
        logging.warning(f"Authentication issue for {video_id} in {method}: {error_msg}")
        return "auth_failure"
    
    # Network issues (legacy handling)
    if any(net_indicator in error_msg.lower() for net_indicator in ["connection", "network", "dns", "resolve"]):
        logging.warning(f"Network issue for {video_id} in {method}: {error_msg}")
        return "network_error"
    
    # Content issues (legacy handling)
    if any(content_indicator in error_msg.lower() for content_indicator in ["not found", "unavailable", "private", "deleted"]):
        logging.info(f"Content issue for {video_id} in {method}: {error_msg}")
        return "content_unavailable"
    
    # Generic error
    logging.warning(f"Unclassified error for {video_id} in {method}: {error_type}: {error_msg}")
    return "unknown"


class ResourceCleanupManager:
    """Ensures proper cleanup of resources on timeout or failure."""
    
    @staticmethod
    def cleanup_playwright_resources(browser, context=None, page=None):
        """Clean up Playwright resources in proper order."""
        try:
            if page:
                page.close()
                logging.debug("Playwright page closed")
        except Exception as e:
            logging.warning(f"Error closing Playwright page: {e}")
        
        try:
            if context:
                context.close()
                logging.debug("Playwright context closed")
        except Exception as e:
            logging.warning(f"Error closing Playwright context: {e}")
        
        try:
            if browser:
                browser.close()
                logging.debug("Playwright browser closed")
        except Exception as e:
            logging.warning(f"Error closing Playwright browser: {e}")
    
    @staticmethod
    def cleanup_temp_files(temp_dir_path: str):
        """Clean up temporary files from ASR processing."""
        try:
            import shutil
            if os.path.exists(temp_dir_path):
                shutil.rmtree(temp_dir_path)
                logging.debug(f"Cleaned up temporary directory: {temp_dir_path}")
        except Exception as e:
            logging.warning(f"Error cleaning up temp directory {temp_dir_path}: {e}")
    
    @staticmethod
    def cleanup_network_connections(session):
        """Close HTTP sessions and network connections."""
        try:
            if hasattr(session, 'close'):
                session.close()
                logging.debug("HTTP session closed")
        except Exception as e:
            logging.warning(f"Error closing HTTP session: {e}")


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
    logging.info("boto3 not available - S3 cookie loading disabled")

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
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers["User-Agent"] = _CHROME_UA
    return session


# Global HTTP session for timed-text requests
HTTP = make_http_session()


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


def _fetch_timedtext(
    video_id: str, lang: str, kind=None, cookies=None, proxies=None, timeout_s=15
) -> str:
    """Try json3 first, then XML; return plain text or ''."""
    headers = {"Accept-Language": "en-US,en;q=0.8"}
    params = {"v": video_id, "lang": lang}
    if kind:
        params["kind"] = kind

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
            root = ET.fromstring(r.text)
            texts = [
                ("".join(node.itertext())).strip() for node in root.findall(".//text")
            ]
            if texts:
                return "\n".join(texts)
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
            root = ET.fromstring(r2.text)
            texts = [
                ("".join(node.itertext())).strip() for node in root.findall(".//text")
            ]
            if texts:
                return "\n".join(texts)
        except Exception:
            pass

    return ""


def _fetch_timedtext_json3(video_id: str, proxy_manager=None) -> str:
    """Timedtext with Cookie header first, json3 parse; falls back by lang/kind."""
    headers = {"Accept-Language": "en-US,en;q=0.8"}
    ck = _cookie_header_from_env_or_file()
    if ck:
        headers["Cookie"] = ck

    languages = ["en", "en-US", "en-GB", "es", "es-ES", "es-419"]
    kinds = [None, "asr"]
    proxies = (
        proxy_manager.proxy_dict_for("requests")
        if (proxy_manager and USE_PROXY_FOR_TIMEDTEXT)
        else None
    )

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
                root = ET.fromstring(response.text)
                
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
                            # Parse the transcript XML
                            transcript_root = ET.fromstring(transcript_response.text)
                            texts = []
                            for text_elem in transcript_root.findall('.//text'):
                                text_content = ''.join(text_elem.itertext()).strip()
                                if text_content and text_content not in ['[Music]', '[Applause]', '[Laughter]']:
                                    texts.append(text_content)
                            
                            if texts:
                                transcript_text = '\n'.join(texts)
                                logging.info(f"Direct HTTP transcript success for {video_id}, lang={lang}, kind={track['kind'] or 'manual'}")
                                return transcript_text
                                
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
                import xml.etree.ElementTree as ET
                root = ET.fromstring(response.text)
                
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
                            # Parse the transcript XML
                            transcript_root = ET.fromstring(transcript_response.text)
                            texts = []
                            for text_elem in transcript_root.findall('.//text'):
                                text_content = ''.join(text_elem.itertext()).strip()
                                if text_content and text_content not in ['[Music]', '[Applause]', '[Laughter]']:
                                    texts.append(text_content)
                            
                            if texts:
                                transcript_text = '\n'.join(texts)
                                logging.info(f"Direct HTTP transcript success for {video_id}, lang={lang}, kind={track['kind'] or 'manual'}")
                                return transcript_text
                                
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
    video_id: str, proxy_manager=None, cookie_jar=None
) -> str:
    """Robust timed-text with no-proxy-first strategy and backoff."""
    languages = ["en", "en-US", "en-GB", "es", "es-ES", "es-419"]
    kinds = [None, "asr"]  # prefer official, then auto
    proxies = (
        proxy_manager.proxy_dict_for("requests")
        if (proxy_manager and USE_PROXY_FOR_TIMEDTEXT)
        else None
    )

    # First: try JSON3 with explicit Cookie header from env/file (works even when cookie_jar is None)
    try:
        txt0 = _fetch_timedtext_json3(video_id, proxy_manager=proxy_manager)
        if txt0:
            logging.info("Timedtext hit via json3+Cookie header")
            return txt0
    except Exception:
        pass

    # Build a cookie jar dict if not provided (from env/file) for requests 'cookies=' parameter
    if cookie_jar is None:
        ck = _cookie_header_from_env_or_file()
        if ck:
            cookie_jar = {
                p.split("=", 1)[0]: p.split("=", 1)[1]
                for p in ck.split("; ")
                if "=" in p
            }

    # No-proxy first (2 attempts with backoff)
    for attempt in range(2):
        try:
            for lang in languages:
                for kind in kinds:
                    txt = _fetch_timedtext(
                        video_id,
                        lang,
                        kind,
                        cookies=cookie_jar,
                        proxies=None,
                        timeout_s=15,
                    )
                    if txt:
                        logging.info(
                            f"Timedtext hit (no-proxy): lang={lang}, kind={kind or 'caption'}"
                        )
                        return txt
        except (
            requests.ReadTimeout,
            requests.ConnectTimeout,
            requests.RequestException,
        ):
            logging.warning(
                f"Timedtext no-proxy attempt {attempt + 1} failed; backing off..."
            )
        time.sleep(1 + attempt)

    # Then proxy if enabled and available
    if proxies:
        for attempt in range(2):
            try:
                for lang in languages:
                    for kind in kinds:
                        txt = _fetch_timedtext(
                            video_id,
                            lang,
                            kind,
                            cookies=cookie_jar,
                            proxies=proxies,
                            timeout_s=15,
                        )
                        if txt:
                            logging.info(
                                f"Timedtext hit (proxy): lang={lang}, kind={kind or 'caption'}"
                            )
                            return txt
            except (
                requests.ReadTimeout,
                requests.ConnectTimeout,
                requests.RequestException,
            ):
                logging.warning(
                    f"Timedtext proxy attempt {attempt + 1} failed; backing off..."
                )
            time.sleep(1 + attempt)

    logging.info("Timedtext: no captions found")
    return ""


def _try_click_any(page, selectors, wait_after=0):
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.is_visible():
                loc.click()
                if wait_after:
                    page.wait_for_timeout(wait_after)
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

    def __init__(self, deepgram_api_key: str):
        self.deepgram_api_key = deepgram_api_key
        self.max_video_minutes = ASR_MAX_VIDEO_MINUTES

    def extract_and_transcribe(
        self, video_id: str, proxy_manager=None, cookies=None
    ) -> str:
        """
        Extract audio via HLS interception and transcribe with Deepgram.
        Includes cost controls and duration limits.
        """
        logging.info(f"Starting ASR extraction for video {video_id}")

        # Step 1: Extract HLS audio URL using Playwright
        audio_url = self._extract_hls_audio_url(video_id, proxy_manager, cookies)
        if not audio_url:
            logging.warning(f"No HLS audio URL found for {video_id}")
            return ""

        # Step 2: Convert audio to WAV using ffmpeg
        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = os.path.join(temp_dir, "audio.wav")

            if not self._extract_audio_to_wav(audio_url, wav_path):
                logging.warning(f"Audio extraction failed for {video_id}")
                return ""

            # Step 3: Check duration limits
            duration_minutes = self._get_audio_duration_minutes(wav_path)
            if duration_minutes > self.max_video_minutes:
                logging.warning(
                    f"Video {video_id} duration {duration_minutes}min exceeds limit {self.max_video_minutes}min"
                )
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
            logging.info("Playwright circuit breaker active - skipping ASR")
            return ""

        # Non-fatal preflight check: log only
        try:
            if not youtube_reachable():
                logging.info("YouTube preflight failed - continuing with ASR anyway")
        except Exception as e:
            logging.info(f"YouTube preflight error ({e}); continuing with ASR")

        captured_url = {"url": None}

        def capture_m3u8_response(response):
            """Capture audio stream URLs: HLS (.m3u8), DASH (.mpd), or direct 'videoplayback?mime=audio'."""
            url = response.url.lower()
            if (url.endswith(".m3u8") or ".m3u8?" in url) and (
                "audio" in url or "mime=audio" in url
            ):
                captured_url["url"] = response.url
                logging.info(f"Captured HLS audio URL: {response.url[:140]}...")
            elif url.endswith(".mpd") or ".mpd?" in url:
                # DASH manifest; ffmpeg can handle most mpd manifests
                if "audio" in url or "mime=audio" in url:
                    captured_url["url"] = response.url
                    logging.info(f"Captured DASH audio MPD: {response.url[:140]}...")
            elif "videoplayback" in url and (
                "mime=audio" in url or "mime=audio%2F" in url
            ):
                captured_url["url"] = response.url
                logging.info(f"Captured direct audio stream: {response.url[:140]}...")

        # ASR strategy: try direct first, then proxy if available
        proxy_strategies = [None]  # Start with no proxy
        if proxy_manager:
            try:
                pw_proxy_config = proxy_manager.proxy_dict_for("playwright")
                if pw_proxy_config:
                    proxy_strategies.append(pw_proxy_config)  # Add proxy as fallback
            except Exception:
                pass

        with _BROWSER_SEM:
            with sync_playwright() as p:
                for strategy_index, pw_proxy in enumerate(proxy_strategies):
                    browser = None
                    try:
                        strategy_name = "direct" if pw_proxy is None else "proxy"
                        logging.info(f"ASR attempting {strategy_name} strategy for {video_id}")
                        
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
                                                if page.locator(selector).first.is_visible(timeout=3000):
                                                    page.locator(selector).first.click()
                                                    page.wait_for_timeout(2000)
                                                    logging.info(f"ASR: Accepted consent with {selector}")
                                                    break
                                            except:
                                                continue
                                    except Exception:
                                        pass  # Consent handling is optional

                                    # ensure the player has focus, then play (muted to satisfy any policy)
                                    try:
                                        page.click("video", timeout=5000)  # Increased timeout
                                    except Exception:
                                        pass
                                    try:
                                        page.keyboard.press("k")  # toggle play
                                    except Exception:
                                        pass
                                    try:
                                        page.evaluate(
                                            """() => {
                                            const v = document.querySelector('video');
                                            if (v) { v.muted = true; v.play().catch(()=>{}); }
                                        }"""
                                        )
                                    except Exception:
                                        pass
                                    
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

    def _extract_audio_to_wav(self, audio_url: str, wav_path: str) -> bool:
        """Extract audio from HLS stream to WAV using ffmpeg with WebM/Opus hardening"""
        max_retries = 2
        
        for attempt in range(max_retries):
            try:
                # Pass headers to avoid 403 on googlevideo domains (UA/Referer) and include Cookie if available
                headers = [f"User-Agent: {_CHROME_UA}", "Referer: https://www.youtube.com/"]
                ck = _cookie_header_from_env_or_file()
                if ck:
                    headers.append(f"Cookie: {ck}")
                headers_arg = "\r\n".join(headers) + "\r\n"
                
                # Enhanced FFmpeg command with WebM/Opus tolerance and format detection
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-loglevel", "error",
                    "-headers", headers_arg,
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

                # Log the exact command for debugging (without sensitive headers)
                safe_cmd = cmd.copy()
                for i, arg in enumerate(safe_cmd):
                    if "Cookie:" in arg:
                        safe_cmd[i] = "-headers [REDACTED_COOKIES]"
                logging.info(f"FFmpeg command (attempt {attempt + 1}): {' '.join(safe_cmd)}")

                result = subprocess.run(cmd, check=True, capture_output=True, timeout=120)

                if os.path.exists(wav_path) and os.path.getsize(wav_path) > 0:
                    logging.info(
                        f"Audio extracted successfully: {os.path.getsize(wav_path)} bytes"
                    )
                    return True
                else:
                    logging.error("Audio extraction produced empty file")
                    if attempt < max_retries - 1:
                        logging.info(f"Retrying audio extraction (attempt {attempt + 2})")
                        continue
                    return False

            except subprocess.TimeoutExpired:
                logging.error(f"Audio extraction timed out after 120 seconds (attempt {attempt + 1})")
                if attempt < max_retries - 1:
                    logging.info(f"Retrying after timeout (attempt {attempt + 2})")
                    continue
                return False
                
            except subprocess.CalledProcessError as e:
                stderr_output = e.stderr.decode() if e.stderr else str(e)
                logging.error(f"ffmpeg failed (attempt {attempt + 1}): {stderr_output}")
                
                # Check for specific WebM/Opus errors and retry with different approach
                if "Invalid data found when processing input" in stderr_output and attempt < max_retries - 1:
                    logging.info("Detected WebM/Opus format issue, retrying with enhanced tolerance")
                    continue
                elif attempt < max_retries - 1:
                    logging.info(f"Retrying after ffmpeg error (attempt {attempt + 2})")
                    continue
                return False
                
            except Exception as e:
                logging.error(f"Audio extraction error (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    logging.info(f"Retrying after general error (attempt {attempt + 2})")
                    continue
                return False
        
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
        r = HTTP.get("https://www.youtube.com/generate_204", timeout=(2, timeout_s))
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
    """Convert cookie jar to Playwright format"""
    if not cookie_jar:
        return None

    # This is a placeholder - implement based on your cookie format
    # For now, assume cookies are already in the right format
    return cookie_jar


def get_transcript_via_youtubei(
    video_id: str, proxy_manager=None, cookies=None, timeout_ms: int = None
) -> str:
    """
    Navigate a YouTube watch page and capture `/youtubei/v1/get_transcript` JSON via Playwright.
    - Honors per-attempt proxy toggle (no-proxy first, then proxy if available).
    - Continues without storage_state if missing (no early returns).
    - Emits CloudWatch-friendly logs including the via_proxy flag.
    """
    from pathlib import Path
    from playwright.sync_api import sync_playwright

    timeout_ms = timeout_ms or PLAYWRIGHT_NAVIGATION_TIMEOUT
    now_ms = int(time.time() * 1000)
    if not _pw_allowed(now_ms):
        logging.info("YouTubei circuit breaker active - skipping")
        return ""

    # Build attempt order: direct first, then proxy (if any)
    attempts = []
    attempts.append({"use_proxy": False, "proxy": None})
    pw_proxy = None
    if proxy_manager:
        try:
            pw_proxy = proxy_manager.proxy_dict_for("playwright")
        except Exception:
            pw_proxy = None
    if pw_proxy:
        attempts.append({"use_proxy": True, "proxy": pw_proxy})

    with _BROWSER_SEM:
        with sync_playwright() as p:
            for idx, a in enumerate(attempts, 1):
                use_proxy = a["use_proxy"]
                launch_kwargs = {"headless": True, "args": ["--no-sandbox"]}
                if use_proxy and pw_proxy:
                    launch_kwargs["proxy"] = pw_proxy
                    logging.info(f"[playwright] launching with proxy server={pw_proxy.get('server')}")
                else:
                    logging.info("[playwright] launching WITHOUT proxy for this attempt")

                browser = None
                context = None
                page = None
                try:
                    youtubei_payload = {"raw_json": None}

                    def on_response(resp):
                        url = resp.url
                        if "/youtubei/v1/get_transcript" in url:
                            try:
                                text = resp.text()
                                if text:
                                    youtubei_payload["raw_json"] = text
                            except Exception as e:
                                logging.warning(f"youtubei response read error: {e}")

                    browser = p.chromium.launch(**launch_kwargs)
                    # storage_state is optional; proceed if missing
                    cookie_dir = Path(os.getenv("COOKIE_DIR", "/app/cookies"))
                    storage_state_path = cookie_dir / "youtube_session.json"

                    context_kwargs = dict(
                        user_agent=_CHROME_UA,
                        viewport={"width": 1366, "height": 900},
                        locale="en-US",
                        ignore_https_errors=True,
                    )
                    if storage_state_path.exists():
                        context_kwargs["storage_state"] = str(storage_state_path)
                        logging.info(f"Using Playwright storage_state at {storage_state_path}")
                    else:
                        logging.warning(
                            f"Playwright storage_state missing at {storage_state_path} - proceeding without storage_state"
                        )

                    context = browser.new_context(**context_kwargs)
                    # Pre-seed consent to reduce friction
                    try:
                        context.add_cookies(
                            [
                                {"name": "CONSENT", "value": "YES+1", "domain": ".youtube.com", "path": "/"},
                                {"name": "CONSENT", "value": "YES+1", "domain": ".m.youtube.com", "path": "/"},
                            ]
                        )
                    except Exception:
                        pass

                    if cookies:
                        pw_cookies = _convert_cookiejar_to_playwright_format(cookies)
                        if pw_cookies:
                            try:
                                context.add_cookies(pw_cookies)
                            except Exception:
                                pass

                    page = context.new_page()
                    page.set_default_navigation_timeout(timeout_ms * 1000 if timeout_ms < 1000 else timeout_ms)
                    page.on("response", on_response)

                    url = f"https://www.youtube.com/watch?v={video_id}&hl=en"
                    logging.info(f"youtubei_attempt video_id={video_id} url={url} via_proxy={use_proxy}")
                    page.goto(url, wait_until="domcontentloaded", timeout=PW_NAV_TIMEOUT_MS)

                    # Light interaction helps trigger network calls
                    try:
                        _try_click_any(
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
                        page.keyboard.press("k")  # play/pause toggle
                    except Exception:
                        pass

                    # Allow network to settle and the transcript endpoint to fire (YT throttles)
                    page.wait_for_timeout(7000)

                    if youtubei_payload["raw_json"]:
                        _pw_register_success()
                        try:
                            data = json.loads(youtubei_payload["raw_json"])
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
                            return youtubei_payload["raw_json"]

                except Exception as e:
                    if "TimeoutError" in type(e).__name__:
                        logging.warning(f"YouTubei timeout on attempt {idx}: {e}")
                        _pw_register_timeout(now_ms)
                    else:
                        logging.warning(f"YouTubei error on attempt {idx}: {e}")
                finally:
                    ResourceCleanupManager.cleanup_playwright_resources(browser, context, page)

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
        user_id: Optional[int] = None,   # NEW: allow caller to provide user_id for S3 cookies
    ) -> str:
        """
        Orchestrate the transcript pipeline:
        youtube_transcript_api -> timedtext -> YouTubei -> ASR (Deepgram)
        """
        # Resolve cookie header once:
        cookie_header: Optional[str]
        if isinstance(cookies, str):
            cookie_header = cookies.strip() or None
        elif isinstance(cookies, dict):
            cookie_header = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        else:
            # Try S3-first if user_id provided, else env/file
            cookie_header = get_user_cookies_with_fallback(user_id)

        # Convenience: dict form for libs expecting cookie jar/dict
        cookie_dict = None
        if cookie_header:
            try:
                cookie_dict = {
                    p.split("=", 1)[0].strip(): p.split("=", 1)[1].strip()
                    for p in cookie_header.split(";")
                    if "=" in p
                }
            except Exception:
                cookie_dict = None
        correlation_id = generate_correlation_id()
        start_time = time.time()
        
        # Use provided proxy_manager or fall back to instance proxy_manager
        effective_proxy_manager = proxy_manager or self.proxy_manager
        
        # Set default language_codes if not provided
        if language_codes is None:
            language_codes = ["en", "en-US", "en-GB"]

        if video_id in self._video_locks:
            logging.info(f"Video {video_id} already being processed, waiting...")

        self._video_locks[video_id] = True
        try:
            # Check cache first (use first language for cache key)
            primary_language = language_codes[0] if language_codes else "en"
            cached_transcript = self.cache.get(video_id, primary_language)
            if cached_transcript:
                logging.info(
                    f"transcript_attempt video_id={video_id} method=cache success=true duration_ms=0"
                )
                return cached_transcript

            # 1) youtube_transcript_api (manual captions preferred)
            try:
                if ENABLE_YT_API:
                    # Note: the compat layer may not accept cookies; leave as-is.
                    txt = get_transcript(video_id, language_codes=language_codes)
                    if txt:
                        return txt
            except Exception as e:
                logging.info(f"YouTube Transcript API failed for {video_id}: {e}")

            # 2) timedtext (json3, xml, then alternate host)
            txt = get_captions_via_timedtext(
                video_id,
                proxy_manager=effective_proxy_manager,
                cookie_jar=cookie_dict  # pass cookies to requests where supported
            )
            if txt:
                return txt

            # 3) YouTubei via Playwright network capture
            txt = get_transcript_via_youtubei_with_timeout(
                video_id,
                proxy_manager=effective_proxy_manager,
                cookies=cookie_dict or cookie_header  # function accepts cookie jar OR header; internal converter present
            )
            if txt:
                return txt

            # 4) ASR fallback (Deepgram)
            if ENABLE_ASR_FALLBACK:
                try:
                    dg_key = os.getenv("DEEPGRAM_API_KEY", "")
                    if dg_key:
                        asr = ASRAudioExtractor(dg_key)
                        txt = asr.extract_and_transcribe(
                            video_id,
                            proxy_manager=effective_proxy_manager,
                            cookies=cookie_dict or cookie_header
                        )
                        if txt:
                            return txt
                except Exception as e:
                    logging.error(f"ASR fallback failed for {video_id}: {e}")

            return ""

        finally:
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
                    vid, self.proxy_manager, cookies
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
            try:
                if source == "yt_api":
                    result = method(video_id, (language, "en", "en-US"))
                elif source == "timedtext":
                    result = method(video_id, language, user_cookies)
                else:  # youtubei and asr use playwright cookies
                    result = method(video_id, language, playwright_cookies)

                duration_ms = int((time.time() - start_time) * 1000)

                if result and result.strip():
                    # Log successful transcript acquisition
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
                    # Log empty result
                    log_performance_metrics(
                        operation=f"transcript_{source}",
                        duration_ms=duration_ms,
                        video_id=video_id,
                        success=False,
                        reason="empty_result",
                    )

            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                # Use structured error handling
                handle_transcript_error(video_id, source, e, duration_ms)
                inc_fail(source)
                continue

        inc_fail("none")
        return "", "none"

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

            logging.info(
                f"yt-transcript-api version={getattr(yta_mod, '__version__', 'unknown')}, "
                f"get_transcript_hasattr={hasattr(YouTubeTranscriptApi, 'get_transcript')}"
            )

            # Strategy 1: Try list_transcripts first (more robust)
            try:
                # Pass cookies to reduce 429 / "disabled" false negatives
                if self.cookies_path and os.path.exists(self.cookies_path):
                    transcripts = YouTubeTranscriptApi.list_transcripts(
                        video_id, cookies=self.cookies_path
                    )
                elif self.cookie_header:
                    transcripts = YouTubeTranscriptApi.list_transcripts(
                        video_id, cookies=self.cookie_header
                    )
                else:
                    transcripts = YouTubeTranscriptApi.list_transcripts(video_id)

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
                        
                        # For youtube-transcript-api: try direct first (usually works better without proxy)
                        proxies = None  # Start without proxy for better success rate
                        
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
                
                # For youtube-transcript-api: try direct first (usually works better without proxy)
                proxies = None  # Start without proxy for better success rate
                
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
        logging.info(f"transcript_stage_start video_id={video_id} stage=asr")
        if not self.deepgram_api_key:
            logging.warning(
                f"transcript_attempt video_id={video_id} method=asr success=false reason=no_key"
            )
            return ""

        try:
            extractor = ASRAudioExtractor(self.deepgram_api_key)
            return extractor.extract_and_transcribe(video_id, pm, cookies)
        except Exception as e:
            logging.error(f"ASR fallback failed for {video_id}: {e}")
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
