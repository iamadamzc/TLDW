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

from playwright.sync_api import sync_playwright, Page

# Startup sanity check to catch local module shadowing
assert (
    importlib.util.find_spec("youtube_transcript_api") is not None
), "youtube-transcript-api not installed"
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)

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
            logging.warning("Playwright circuit breaker activated - skipping for 10 minutes")
        else:
            logging.info(f"Playwright failure recorded: {self.failure_count}/{self.FAILURE_THRESHOLD}")


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


def classify_transcript_error(error: Exception, video_id: str, method: str) -> str:
    """Classify transcript errors for better debugging and monitoring."""
    error_type = type(error).__name__
    error_msg = str(error)
    
    # Timeout errors
    if "TimeoutError" in error_type or "timeout" in error_msg.lower():
        handle_timeout_error(video_id, 0.0, method)  # elapsed_time would need to be passed in
        return "timeout"
    
    # YouTube blocking detection
    if detect_youtube_blocking(error_msg):
        logging.warning(f"YouTube blocking detected for {video_id} in {method}: {error_msg}")
        return "youtube_blocking"
    
    # Authentication issues
    if any(auth_indicator in error_msg.lower() for auth_indicator in ["unauthorized", "forbidden", "401", "403"]):
        logging.warning(f"Authentication issue for {video_id} in {method}: {error_msg}")
        return "auth_failure"
    
    # Network issues
    if any(net_indicator in error_msg.lower() for net_indicator in ["connection", "network", "dns", "resolve"]):
        logging.warning(f"Network issue for {video_id} in {method}: {error_msg}")
        return "network_error"
    
    # Content issues
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
                if "no element found" in str(e) or "ParseError" in type(e).__name__:
                    logging.warning(f"YouTube blocking detected for {video_id}: XML parsing error")
                else:
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

        with _BROWSER_SEM:
            with sync_playwright() as p:
                browser = None
                try:
                    # Use proxy at launch if available
                    pw_proxy = None
                    try:
                        if proxy_manager:
                            pw_proxy = proxy_manager.proxy_dict_for("playwright")
                    except Exception:
                        pw_proxy = None
                    browser = p.chromium.launch(
                        headless=True,
                        proxy=pw_proxy if pw_proxy else None,
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

                    # Try desktop first, then mobile, then embed
                    urls = [
                        f"https://www.youtube.com/watch?v={video_id}&hl=en",
                        f"https://m.youtube.com/watch?v={video_id}&hl=en",
                        f"https://www.youtube.com/embed/{video_id}?autoplay=1&hl=en",
                    ]

                    for url in urls:
                        try:
                            # YouTube rarely reaches "networkidle"; use domcontentloaded to avoid timeouts
                            page.goto(url, wait_until="domcontentloaded", timeout=60000)

                            # ensure the player has focus, then play (muted to satisfy any policy)
                            try:
                                page.click("video", timeout=3000)
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
                            page.wait_for_timeout(
                                5000
                            )  # give time for stream/manifest to load

                            if captured_url["url"]:
                                _pw_register_success()
                                return captured_url["url"]

                        except Exception as e:
                            logging.warning(
                                f"ASR audio extraction failed for {url}: {e}"
                            )
                            continue

                except Exception as e:
                    if "TimeoutError" in str(type(e)):
                        _pw_register_timeout(now_ms)
                    logging.error(f"ASR Playwright error: {e}")

                finally:
                    try:
                        if browser:
                            browser.close()
                    except Exception:
                        pass

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
                headers_arg = "\\r\\n".join(headers) + "\\r\\n"
                
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
    """Check if Playwright is allowed (circuit breaker) - legacy compatibility"""
    return not _playwright_circuit_breaker.is_open()


def _pw_register_timeout(now_ms):
    """Register Playwright timeout for circuit breaker - legacy compatibility"""
    _playwright_circuit_breaker.record_failure()


def _pw_register_success():
    """Register Playwright success (reset circuit breaker) - legacy compatibility"""
    _playwright_circuit_breaker.record_success()


def _convert_cookiejar_to_playwright_format(cookie_jar):
    """Convert cookie jar to Playwright format"""
    if not cookie_jar:
        return None

    # This is a placeholder - implement based on your cookie format
    # For now, assume cookies are already in the right format
    return cookie_jar


def get_transcript_via_youtubei_with_timeout(
    video_id: str, proxy_manager=None, cookies=None, max_duration_seconds: int = YOUTUBEI_HARD_TIMEOUT
) -> str:
    """
    YouTubei with strict timeout enforcement and circuit breaker integration.
    Enhanced with 150-second maximum operation time and proper resource cleanup.
    """
    logging.info(f"transcript_stage_start video_id={video_id} stage=youtubei_timeout_protected")
    
    # Check circuit breaker status
    if _playwright_circuit_breaker.is_open():
        logging.info(f"Circuit breaker blocking YouTubei operation for {video_id}")
        return ""
    
    start_time = time.time()
    operation_deadline = start_time + max_duration_seconds
    
    # Non-fatal probe: log and proceed regardless
    try:
        if not youtube_reachable():
            logging.info("YouTube ping failed; proceeding with YouTubei anyway")
    except Exception:
        logging.info("YouTube ping check error; proceeding anyway")

    # Convert cookies to Playwright format
    pw_cookies = _convert_cookiejar_to_playwright_format(cookies)

    urls = [
        f"https://www.youtube.com/watch?v={video_id}&hl=en",
        f"https://m.youtube.com/watch?v={video_id}&hl=en",
        f"https://www.youtube.com/embed/{video_id}?autoplay=1&hl=en",
    ]

    # Only add proxy=True branch if a proxy config exists
    use_proxy_order = [False]
    if proxy_manager and proxy_manager.proxy_dict_for("playwright"):
        use_proxy_order.append(True)
    captured = {"json": None}

    cleanup_manager = ResourceCleanupManager()
    
    with _BROWSER_SEM:
        with sync_playwright() as p:
            for use_proxy in use_proxy_order:
                for url in urls:
                    # Check timeout before each attempt
                    elapsed_time = time.time() - start_time
                    remaining_time = max_duration_seconds - elapsed_time
                    
                    if time.time() > operation_deadline:
                        logging.warning(f"YouTubei operation aborted due to timeout for {video_id}: {elapsed_time:.1f}s elapsed")
                        _playwright_circuit_breaker.record_failure()
                        return ""
                    
                    if remaining_time < 30:  # Less than 30 seconds remaining
                        logging.warning(f"YouTubei timeout approaching for {video_id}: {remaining_time:.1f}s remaining")
                    
                    browser = None
                    context = None
                    page = None
                    
                    try:
                        # Use Oxylabs proxy if available (Playwright proxy must be set at launch)
                        pw_proxy = None
                        try:
                            if proxy_manager:
                                pw_proxy = proxy_manager.proxy_dict_for("playwright")
                        except Exception:
                            pw_proxy = None
                            
                        browser = p.chromium.launch(
                            headless=True,
                            proxy=pw_proxy if pw_proxy else None,
                            args=["--no-sandbox"],
                        )
                        
                        context = browser.new_context(
                            user_agent=(
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36"
                            ),
                            viewport={"width": 1366, "height": 900},
                            locale="en-US",
                            ignore_https_errors=True,
                        )
                        
                        # Pre-bypass consent on both hosts to avoid interstitials
                        context.add_cookies([
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
                        ])

                        if pw_cookies:
                            context.add_cookies(pw_cookies)

                        page = context.new_page()
                        
                        # Set shorter navigation timeout to respect overall deadline
                        nav_timeout = min(PLAYWRIGHT_NAVIGATION_TIMEOUT * 1000, int(remaining_time * 1000))
                        page.set_default_navigation_timeout(nav_timeout)
                        page.set_default_timeout(nav_timeout)

                        # Reduce weight but allow YouTube CSS for proper UI rendering
                        def route_handler(route):
                            url_lower = route.request.url.lower()
                            resource_type = route.request.resource_type

                            # Allow CSS from YouTube and Google domains
                            if resource_type == "stylesheet" and any(
                                domain in url_lower
                                for domain in ["youtube.com", "google.com", "gstatic.com"]
                            ):
                                route.continue_()
                            # Block heavy resources but keep essential ones
                            elif resource_type in {"image", "font", "media"}:
                                route.abort()
                            else:
                                route.continue_()

                        page.route("**/*", route_handler)

                        def on_response(resp):
                            try:
                                if (
                                    ("get_transcript" in resp.url)
                                    or ("timedtext" in resp.url)
                                ) and resp.request.method in ("POST", "GET"):
                                    captured["json"] = resp.json()
                                    logging.info(f"youtubei_response video_id={video_id} status={resp.status} url={resp.url}")
                            except Exception as e:
                                logging.warning(f"youtubei_response_parse_failed video_id={video_id} error={e}")

                        # Attach listener *before* navigation
                        page.on("response", on_response)
                        
                        # Check timeout before navigation
                        if time.time() > operation_deadline:
                            logging.warning(f"YouTubei timeout reached before navigation for {video_id}")
                            break
                            
                        page.goto(url, wait_until="domcontentloaded", timeout=nav_timeout)

                        # Explicitly trigger the transcript panel so the XHR fires
                        try:
                            # Desktop overflow menu → "Show transcript"
                            page.locator(
                                "button[aria-label*='More actions'],#button[aria-label*='More actions']"
                            ).first.click(timeout=2500)
                            page.locator(
                                "tp-yt-paper-item:has-text('Show transcript'), ytd-menu-navigation-item-renderer:has-text('Show transcript')"
                            ).first.click(timeout=4000)
                        except Exception:
                            try:
                                # Mobile menu variant
                                page.locator("button:has-text('More')").first.click(timeout=2500)
                                page.locator(
                                    "ytm-menu-navigation-item-renderer:has-text('Show transcript')"
                                ).first.click(timeout=4000)
                            except Exception:
                                pass

                        # Handle consent (best effort)
                        _try_click_any(
                            page,
                            [
                                "button:has-text('Accept all')",
                                "button:has-text('I agree')",
                                "button:has-text('Acepto todo')",
                                "button:has-text('Estoy de acuerdo')",
                            ],
                            wait_after=800,
                        )

                        # Check timeout before scrolling
                        if time.time() > operation_deadline:
                            logging.warning(f"YouTubei timeout reached before scrolling for {video_id}")
                            break

                        # Scroll down to make the Transcript section render
                        def transcript_button_visible():
                            selectors = [
                                "button:has-text('Show transcript')",
                                "[aria-label*='Show transcript']",
                                "ytd-transcript-renderer button",
                                "#transcript button",
                                "button[aria-label*='transcript']",
                            ]
                            for sel in selectors:
                                try:
                                    if page.locator(sel).first.is_visible():
                                        return True
                                except Exception:
                                    continue
                            return False

                        _scroll_until(page, transcript_button_visible, max_steps=50, dy=3000, pause_ms=120)

                        # Enhanced transcript button detection with more selectors
                        opened = _try_click_any(
                            page,
                            [
                                "ytd-transcript-renderer tp-yt-paper-button:has-text('Show transcript')",
                                "button:has-text('Show transcript')",
                                "tp-yt-paper-button:has-text('Show transcript')",
                                "[aria-label*='Show transcript']",
                                "ytd-transcript-renderer button",
                                "#transcript button",
                                "button[aria-label*='transcript']",
                                "button:has-text('Transcript')",
                                "button:has-text('Show Transcript')",
                                "[role='button']:has-text('Show transcript')",
                                ".transcript-button",
                                "[data-target-id='transcript']",
                            ],
                            wait_after=1000,
                        )

                        # Fallback: old ⋯ menu path with enhanced selectors
                        if not opened:
                            menu_opened = _try_click_any(
                                page,
                                [
                                    "button[aria-label*='More actions']",
                                    "button[aria-label*='More options']",
                                    "button[aria-label*='Show more']",
                                    "#menu-button",
                                    ".dropdown-trigger",
                                    "[role='button'][aria-haspopup='true']",
                                ],
                                wait_after=500,
                            )

                            if menu_opened:
                                opened = _try_click_any(
                                    page,
                                    [
                                        "tp-yt-paper-item:has-text('Show transcript')",
                                        "yt-formatted-string:has-text('Show transcript')",
                                        "[role='menuitem']:has-text('transcript')",
                                        ".menu-item:has-text('transcript')",
                                        "a:has-text('Show transcript')",
                                        "button:has-text('Show transcript')",
                                    ],
                                    wait_after=1000,
                                )

                        data = captured["json"]
                        if data is None:
                            try:
                                remaining_timeout = max(5000, int((operation_deadline - time.time()) * 1000))
                                with page.expect_response(
                                    lambda r: (
                                        ("get_transcript" in r.url) or ("timedtext" in r.url)
                                    ) and r.request.method in ("POST", "GET"),
                                    timeout=remaining_timeout,
                                ) as tr_resp:
                                    page.wait_for_timeout(400)
                                if tr_resp.value.ok:
                                    data = tr_resp.value.json()
                            except Exception as e:
                                logging.warning(f"youtubei_expect_response_failed video_id={video_id} error={e}")

                        text = _parse_youtubei_transcript_json(data) if data else ""

                        if text:
                            elapsed_time = time.time() - start_time
                            logging.info(f"YouTubei transcript captured: {'proxy' if use_proxy else 'no-proxy'}, {url}, elapsed={elapsed_time:.1f}s")
                            _playwright_circuit_breaker.record_success()
                            return text

                    except Exception as e:
                        elapsed_time = time.time() - start_time
                        if "TimeoutError" in str(type(e)):
                            logging.warning(f"YouTubei timeout: {'proxy' if use_proxy else 'no-proxy'}, {url}, elapsed={elapsed_time:.1f}s")
                            _playwright_circuit_breaker.record_failure()
                        else:
                            logging.warning(f"YouTubei error: {e}, elapsed={elapsed_time:.1f}s")

                    finally:
                        cleanup_manager.cleanup_playwright_resources(browser, context, page)

    elapsed_time = time.time() - start_time
    logging.info(f"YouTubei transcript: no capture successful for {video_id}, total_elapsed={elapsed_time:.1f}s")
    return ""


# Keep the original function for backward compatibility
def get_transcript_via_youtubei(
    video_id: str, proxy_manager=None, cookies=None, timeout_ms: int = None
) -> str:
    """
    Legacy function - redirects to timeout-protected version.
    """
    return get_transcript_via_youtubei_with_timeout(video_id, proxy_manager, cookies)


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

    def set_current_user_id(self, user_id: int) -> None:
        """Set the current user ID for cookie loading operations."""
        self.current_user_id = user_id
        logging.debug(f"Set current user ID to {user_id}")

    def get_transcript(
        self,
        video_id: str,
        language: str = "en",
        user_cookies=None,
        playwright_cookies=None,
        user_id: Optional[int] = None,
    ) -> str:
        """
        Hierarchical transcript acquisition with comprehensive fallback.
        Returns transcript text or empty string if all methods fail.
        """
        correlation_id = generate_correlation_id()
        start_time = time.time()
        
        # Set current user ID for cookie loading
        if user_id:
            self.set_current_user_id(user_id)

        if video_id in self._video_locks:
            logging.info(f"Video {video_id} already being processed, waiting...")

        self._video_locks[video_id] = True
        try:
            # Check cache first
            cached_transcript = self.cache.get(video_id, language)
            if cached_transcript:
                logging.info(
                    f"transcript_attempt video_id={video_id} method=cache success=true duration_ms=0"
                )
                return cached_transcript

            # YouTube-specific preflight: probe + rotate session; do NOT globally disable proxy
            if self.proxy_manager and hasattr(self.proxy_manager, "youtube_preflight"):
                try:
                    ok = self.proxy_manager.youtube_preflight()
                    if not ok and hasattr(self.proxy_manager, "rotate_session"):
                        logging.warning(
                            "YouTube preflight blocked; rotating proxy session and retrying"
                        )
                        self.proxy_manager.rotate_session()
                        ok = self.proxy_manager.youtube_preflight()
                    if not ok:
                        logging.warning(
                            "YouTube preflight still blocked; will attempt both direct and proxy paths in fallbacks"
                        )
                except (ProxyAuthError, ProxyConfigError) as e:
                    logging.warning(
                        f"YouTube preflight error; proceeding with both direct and proxy fallbacks: {e}"
                    )

            # Hierarchical fallback with feature flags
            transcript_text, source = self._get_transcript_with_fallback(
                video_id, language, user_cookies, playwright_cookies
            )

            # Cache successful result
            if transcript_text and transcript_text.strip():
                self.cache.set(
                    video_id, transcript_text, language, source=source, ttl_days=7
                )

            # Log final result
            total_duration_ms = int((time.time() - start_time) * 1000)
            logging.info(
                f"transcript_final video_id={video_id} source={source} "
                f"success={bool(transcript_text)} duration_ms={total_duration_ms}"
            )

            return transcript_text

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

    def get_captions_via_api(self, video_id: str, languages=("en", "en-US", "es")) -> str:
        """
        Enhanced YouTube Transcript API with proper cookie support.
        Uses direct HTTP method when library fails due to cookie limitations.
        """
        try:
            # Strategy 1: Try direct HTTP with user cookies first
            if self.current_user_id:
                logging.info(f"Attempting direct HTTP transcript fetch with user {self.current_user_id} cookies")
                transcript_text = get_transcript_with_cookies_fixed(
                    video_id, 
                    list(languages), 
                    user_id=self.current_user_id,
                    proxies=self.proxy_manager.proxy_dict_for("requests") if self.proxy_manager else None
                )
                if transcript_text:
                    logging.info(f"Direct HTTP transcript success for {video_id}")
                    return transcript_text

            # Strategy 2: Try original library approach (may work for some videos)
            logging.info(f"Attempting library-based transcript fetch for {video_id}")
            
            # Log API version for debugging
            import youtube_transcript_api as yta_mod
            logging.info(f"yt-transcript-api version={getattr(yta_mod, '__version__', 'unknown')}")

            try:
                # Try list_transcripts approach
                transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
                
                # Find the best available transcript
                transcript_obj = None
                source_info = ""
                
                # Prefer manual transcripts in preferred languages
                for lang in languages:
                    try:
                        transcript_obj = transcripts.find_transcript([lang])
                        if not transcript_obj.is_generated:
                            source_info = f"yt_api:{lang}:manual"
                            logging.info(f"Found manual transcript for {video_id}: {source_info}")
                            break
                    except NoTranscriptFound:
                        continue
                
                # If no manual transcript found, try auto-generated
                if not transcript_obj:
                    for lang in languages:
                        try:
                            transcript_obj = transcripts.find_generated_transcript([lang])
                            source_info = f"yt_api:{lang}:auto"
                            logging.info(f"Found auto transcript for {video_id}: {source_info}")
                            break
                        except NoTranscriptFound:
                            continue
                
                # If still no transcript, take any available
                if not transcript_obj:
                    available = list(transcripts)
                    if available:
                        transcript_obj = available[0]
                        source_info = f"yt_api:{transcript_obj.language_code}:{'auto' if transcript_obj.is_generated else 'manual'}"
                        logging.info(f"Found fallback transcript for {video_id}: {source_info}")
                
                if transcript_obj:
                    # Fetch transcript segments (this should work without cookies for public videos)
                    segments = transcript_obj.fetch()
                    
                    if segments:
                        # Convert to text
                        lines = []
                        for seg in segments:
                            text = seg.get("text", "").strip()
                            if text and text not in ["[Music]", "[Applause]", "[Laughter]"]:
                                lines.append(text)
                        
                        transcript_text = "\n".join(lines).strip()
                        if transcript_text:
                            logging.info(f"Library transcript success for {video_id}: {len(transcript_text)} chars")
                            return transcript_text
                            
            except Exception as library_error:
                logging.info(f"Library approach failed for {video_id}: {library_error}")
                
                # Strategy 3: Try direct get_transcript as final fallback
                try:
                    segments = YouTubeTranscriptApi.get_transcript(video_id, languages=list(languages))
                    if segments:
                        lines = [seg.get("text", "").strip() for seg in segments if seg.get("text", "").strip()]
                        transcript_text = "\n".join(lines).strip()
                        if transcript_text:
                            logging.info(f"Direct get_transcript success for {video_id}")
                            return transcript_text
                except Exception as direct_error:
                    logging.warning(f"Direct get_transcript also failed for {video_id}: {direct_error}")

            return ""

        except Exception as e:
            error_classification = classify_transcript_error(e, video_id, "transcript_api")
            
            if error_classification == "youtube_blocking":
                logging.warning(f"YouTube Transcript API blocking detected for {video_id}: {str(e)}")
                logging.info("This usually indicates YouTube is blocking requests or the video has no transcript")
            elif error_classification == "timeout":
                logging.warning(f"YouTube Transcript API timeout for {video_id}: {str(e)}")
            else:
                logging.warning(f"YouTube Transcript API error for {video_id} ({error_classification}): {type(e).__name__}: {str(e)}")
            
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
        # Check S3 cookie availability
        s3_available = S3_AVAILABLE and bool(COOKIE_S3_BUCKET)
        
        # Get circuit breaker status
        circuit_breaker_status = "closed" if not _playwright_circuit_breaker.is_open() else "open"
        
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
                "youtubei_hard_timeout": YOUTUBEI_HARD_TIMEOUT,
                "playwright_navigation_timeout": PLAYWRIGHT_NAVIGATION_TIMEOUT,
            },
            "cookie_loading": {
                "s3_available": s3_available,
                "s3_bucket_configured": bool(COOKIE_S3_BUCKET),
                "boto3_available": S3_AVAILABLE,
                "current_user_id": self.current_user_id,
                "environment_cookies_available": bool(self.cookie_header or self.cookies_path),
            },
            "timeout_protection": {
                "circuit_breaker_status": circuit_breaker_status,
                "circuit_breaker_failure_count": _playwright_circuit_breaker.failure_count,
                "circuit_breaker_last_failure": _playwright_circuit_breaker.last_failure_time,
                "timeout_enforcement_enabled": True,
            },
            "cache_stats": self.get_cache_stats(),
            "proxy_available": self.proxy_manager is not None,
        }
