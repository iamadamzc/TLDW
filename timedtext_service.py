"""
Enhanced timedtext service with discovery flow, tenacity retry, and comprehensive logging.

This module implements robust timedtext extraction with:
- A discovery-first workflow: list tracks, then fetch the best one.
- Multiple endpoint support (youtube.com/api/timedtext and video.google.com/timedtext)
- Language preference (en, en-US, en-GB) and track type preference (official then ASR).
- Tenacity retry with exponential backoff and jitter for all HTTP requests.
- Strict pre-parsing validation to prevent parse errors on empty or invalid content.
- Comprehensive logging with security masking and clear outcome summaries.
- HTML content detection to cleanly hand off to other services like Playwright.
"""

import os
import json
import time
import logging
import xml.etree.ElementTree as ET
from typing import Optional, Dict, List, Tuple, Any
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs

import requests
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from logging_setup import get_logger, set_job_ctx
from log_events import evt

# --- Configuration ---
TIMEDTEXT_TIMEOUT = 15
TIMEDTEXT_RETRY_ATTEMPTS = 3
TIMEDTEXT_BACKOFF_MIN = 0.5
TIMEDTEXT_BACKOFF_MAX = 2.0
TIMEDTEXT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)
PREFERRED_LANGS = ["en", "en-US", "en-GB"]

logger = get_logger(__name__)


# --- Helper Functions ---

def _mask_url_for_logging(url: str) -> str:
    """Mask sensitive query parameters in URLs for logging."""
    try:
        parsed = urlparse(url)
        if not parsed.query:
            return url
        params = parse_qs(parsed.query, keep_blank_values=True)
        sensitive_params = {'key', 'token', 'auth', 'session', 'sig', 'signature'}
        masked_params = {
            key: ['***MASKED***'] * len(values) if key.lower() in sensitive_params else values
            for key, values in params.items()
        }
        masked_query = urlencode(masked_params, doseq=True)
        return urlunparse(parsed._replace(query=masked_query))
    except Exception:
        return f"{url.split('?')[0]}?***MASKED_QUERY***" if '?' in url else url

def _determine_cookie_source(cookies: Optional[Any]) -> str:
    """Determine the source of cookies for logging."""
    if not cookies:
        return 'none'
    if isinstance(cookies, str):
        return 'user' if cookies else 'none'
    if isinstance(cookies, dict):
        return 'user' if cookies else 'none'
    return 'user'

def _create_timedtext_session(proxy_dict: Optional[Dict[str, str]] = None) -> requests.Session:
    """Create an HTTP session optimized for timedtext requests."""
    session = requests.Session()
    retry_strategy = Retry(
        total=TIMEDTEXT_RETRY_ATTEMPTS,
        backoff_factor=0.6,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": TIMEDTEXT_USER_AGENT,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
    })
    if proxy_dict:
        session.proxies.update(proxy_dict)
    return session

# --- Parsing and Validation ---

def _parse_track_list_xml(xml_string: str) -> List[Dict[str, str]]:
    """Parse the XML response from a `type=list` call."""
    try:
        # Import validation function from transcript_service
        from transcript_service import _validate_xml_content
        
        # Validate content before parsing
        is_valid, error_reason = _validate_xml_content(xml_string)
        if not is_valid:
            evt("timedtext_track_list_validation_failed", reason=error_reason)
            logger.debug(f"Track list XML validation failed: {error_reason}")
            return []
        
        root = ET.fromstring(xml_string)
        tracks = []
        for track in root.findall('track'):
            track_data = track.attrib
            if 'lang_code' in track_data and 'id' in track_data:
                tracks.append({
                    "id": track_data['id'],
                    "lang": track_data['lang_code'],
                    "kind": track_data.get('kind', ''),
                })
        return tracks
    except ET.ParseError as e:
        evt("timedtext_track_list_parse_failed", error=str(e)[:100])
        logger.debug(f"Failed to parse track list XML: {e}")
        return []

def _parse_transcript(response_text: str, content_type: str) -> str:
    """Parse JSON3 or XML transcript."""
    if "json" in content_type:
        try:
            data = json.loads(response_text)
            events = data.get("events", [])
            parts = [
                "".join(seg.get("utf8", "") for seg in event.get("segs", []))
                for event in events
            ]
            return "\n".join(p.strip() for p in parts if p.strip())
        except json.JSONDecodeError:
            evt("timedtext_json_parse_failed", content_preview=response_text[:100])
            return ""
    elif "xml" in content_type:
        try:
            # Import validation function from transcript_service
            from transcript_service import _validate_xml_content
            
            # Validate content before parsing
            is_valid, error_reason = _validate_xml_content(response_text)
            if not is_valid:
                evt("timedtext_transcript_validation_failed", reason=error_reason)
                return ""
            
            root = ET.fromstring(response_text)
            parts = ["".join(elem.itertext()).strip() for elem in root.findall(".//text")]
            return "\n".join(p for p in parts if p)
        except ET.ParseError as e:
            evt("timedtext_transcript_parse_failed", error=str(e)[:100])
            return ""
    return ""

def _validate_response(resp: requests.Response) -> Tuple[bool, str, str]:
    """
    Enhanced guard before parsing. Checks status, content-type, and length with better error classification.
    Returns (is_valid, reason, preview).
    """
    ct = (resp.headers.get("content-type") or "").lower()
    body = resp.text or ""
    
    # Check HTTP status first
    if not resp.ok:
        return False, f"status={resp.status_code}", body[:80]
    
    # Check for empty body (common when YouTube blocks requests)
    if len(body) == 0:
        evt("timedtext_empty_body", status_code=resp.status_code, content_type=ct)
        return False, "content_length=0", ""
    
    # Check content-type to avoid parsing HTML as XML
    if "xml" not in ct and "json" not in ct:
        if "html" in ct or body.lstrip().startswith("<"):
            # Specific check for consent/age walls
            if "before you continue to youtube" in body.lower():
                evt("timedtext_consent_wall_detected", content_preview=body[:100])
                return False, "html_consent_page", body[:80]
            # Generic HTML response (likely blocking)
            evt("timedtext_html_response", content_type=ct, content_preview=body[:100])
            return False, "html_response", body[:80]
        # Non-HTML but also not XML/JSON
        evt("timedtext_bad_content_type", content_type=ct, expected="xml or json")
        return False, f"invalid_content_type={ct}", body[:80]
    
    # Additional validation for very small responses that might be error messages
    if len(body) < 50:  # Suspiciously small for a real transcript
        evt("timedtext_suspiciously_small", content_length=len(body), content_preview=body)
        return False, f"suspiciously_small={len(body)}", body[:80]
        
    return True, "valid", ""

# --- Core Logic ---

@retry(
    stop=stop_after_attempt(TIMEDTEXT_RETRY_ATTEMPTS),
    wait=wait_exponential_jitter(initial=TIMEDTEXT_BACKOFF_MIN, max=TIMEDTEXT_BACKOFF_MAX),
    retry=retry_if_exception_type(requests.exceptions.RequestException),
    before_sleep=lambda s: logger.info(f"Request failed, retrying in {s.next_action.sleep:.2f}s...")
)
def _execute_request(session: requests.Session, url: str, cookies: Optional[Any], vid: str) -> requests.Response:
    """Execute an HTTP GET request with session, cookies, and referer."""
    headers = {"Referer": f"https://www.youtube.com/watch?v={vid}"}
    
    # Handle different cookie formats
    request_cookies = None
    if cookies:
        if isinstance(cookies, str):
            # Convert cookie header string to dict format for requests
            try:
                request_cookies = {}
                for pair in cookies.split(';'):
                    if '=' in pair:
                        name, value = pair.split('=', 1)
                        request_cookies[name.strip()] = value.strip()
            except Exception:
                # If parsing fails, add as Cookie header instead
                headers['Cookie'] = cookies
        elif isinstance(cookies, dict):
            request_cookies = cookies
        else:
            # For other formats (like RequestsCookieJar), pass directly
            request_cookies = cookies
    
    return session.get(url, headers=headers, cookies=request_cookies, timeout=TIMEDTEXT_TIMEOUT)

def _fetch_track_list(session: requests.Session, vid: str, cookies: Optional[Any]) -> List[Dict[str, str]]:
    """Fetch available tracks from both YouTube and Google Video endpoints."""
    list_urls = [
        f"https://www.youtube.com/api/timedtext?type=list&v={vid}&hl=en",
        f"https://video.google.com/timedtext?type=list&v={vid}&hl=en",
    ]
    
    for url in list_urls:
        try:
            resp = _execute_request(session, url, cookies, vid)
            is_valid, reason, preview = _validate_response(resp)
            
            if is_valid:
                tracks = _parse_track_list_xml(resp.text)
                if tracks:
                    evt("timedtext_track_list_success", video_id=vid, url=url, count=len(tracks))
                    return tracks
            else:
                evt("timedtext_track_list_invalid", video_id=vid, url=url, reason=reason, preview=preview)
        except requests.exceptions.RequestException as e:
            evt("timedtext_track_list_failed", video_id=vid, url=url, error=str(e))
            
    return []

def _pick_best_track(tracks: List[Dict[str, str]], langs: List[str]) -> Optional[Dict[str, str]]:
    """Pick the best track, preferring official tracks over ASR for preferred languages."""
    tracks_by_lang = {t['lang']: [] for t in tracks}
    for t in tracks:
        tracks_by_lang[t['lang']].append(t)

    for lang in langs:
        if lang in tracks_by_lang:
            lang_tracks = tracks_by_lang[lang]
            # Prefer official track (kind is not 'asr')
            official = next((t for t in lang_tracks if t.get("kind") != "asr"), None)
            if official:
                return official
            # Fallback to ASR
            asr = next((t for t in lang_tracks if t.get("kind") == "asr"), None)
            if asr:
                return asr
    return None

def timedtext_attempt(
    video_id: str,
    cookies: Optional[Any] = None,
    proxy_dict: Optional[Dict[str, str]] = None,
    job_id: Optional[str] = None
) -> Optional[str]:
    """
    Main function to extract transcript via timedtext discovery flow.
    Returns transcript text on success, None on failure.
    """
    if job_id:
        set_job_ctx(job_id=job_id, video_id=video_id)
    
    cookie_source = _determine_cookie_source(cookies)
    session = _create_timedtext_session(proxy_dict)
    
    evt("timedtext_start", video_id=video_id, cookie_source=cookie_source, proxy_enabled=bool(proxy_dict))

    # 1. Discovery: List tracks
    tracks = _fetch_track_list(session, video_id, cookies)
    if not tracks:
        evt("timedtext_exhausted", video_id=video_id, reason="no_tracks_found", cookie_source=cookie_source)
        logger.info(f"Timedtext for {video_id}: No tracks found after checking all list endpoints.")
        return None

    # 2. Pick best track
    best_track = _pick_best_track(tracks, PREFERRED_LANGS)
    if not best_track:
        evt("timedtext_exhausted", video_id=video_id, reason="no_suitable_track", cookie_source=cookie_source)
        logger.info(f"Timedtext for {video_id}: No suitable English track found.")
        return None
    
    evt("timedtext_track_picked", video_id=video_id, track=best_track)

    # 3. Fetch track
    base = "https://www.youtube.com/api/timedtext"
    q = {"type": "track", "v": video_id, "id": best_track["id"], "lang": best_track["lang"], "fmt": "json3"}
    if best_track.get("kind") == "asr":
        q["kind"] = "asr"
    
    # Try fetching json3 first, then fall back to XML
    formats_to_try = ["json3", "xml"]
    last_response_summary = {}

    for fmt in formats_to_try:
        q["fmt"] = fmt
        url = base + "?" + urlencode(q)
        
        try:
            resp = _execute_request(session, url, cookies, video_id)
            last_response_summary = {
                "status_last": resp.status_code,
                "content_type_last": resp.headers.get("content-type", "unknown"),
                "bytes_last": len(resp.content),
            }
            
            is_valid, reason, preview = _validate_response(resp)
            
            if not is_valid:
                evt("timedtext_fetch_invalid", video_id=video_id, url=url, reason=reason, preview=preview)
                if "html_consent_page" in reason:
                    logger.warning(f"Timedtext for {video_id}: Detected HTML consent page. Handing off.")
                    # Special return value or signal could be used here if the caller supports it.
                    # For now, we log and fail cleanly.
                    return None 
                continue

            transcript = _parse_transcript(resp.text, resp.headers.get("content-type", ""))
            if transcript:
                evt("timedtext_success", video_id=video_id, format=fmt, length=len(transcript))
                logger.info(f"Timedtext success for {video_id} using format {fmt}.")
                return transcript

        except requests.exceptions.RequestException as e:
            last_response_summary = {"status_last": "error", "content_type_last": "n/a", "bytes_last": 0}
            evt("timedtext_fetch_failed", video_id=video_id, url=url, error=str(e))
            continue

    evt("timedtext_exhausted", video_id=video_id, reason="fetch_failed", cookie_source=cookie_source, **last_response_summary)
    logger.info(f"Timedtext for {video_id}: All fetch attempts failed. Last status: {last_response_summary.get('status_last')}")
    return None

def timedtext_with_job_proxy(
    video_id: str,
    job_id: str,
    proxy_manager,
    cookies: Optional[object] = None
) -> Optional[str]:
    """
    Extract transcript using timedtext with job-scoped proxy session.
    """
    proxy_dict = None
    if proxy_manager and proxy_manager.in_use:
        try:
            proxy_dict = proxy_manager.proxy_dict_for_job(job_id, "requests")
        except Exception as e:
            logger.warning(f"Failed to get job proxy for timedtext: {e}")

    return timedtext_attempt(video_id, cookies, proxy_dict, job_id)
