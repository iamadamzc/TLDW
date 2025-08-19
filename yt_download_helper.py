# yt_download_helper.py
import os
import tempfile
import logging
import time
import random
from typing import Callable, Dict, Optional, Tuple
from urllib.parse import urlparse

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


def _file_ok(path: Optional[str]) -> bool:
    return bool(path and os.path.exists(path) and os.path.getsize(path) > 0)


def _maybe_cookie(cookiefile: Optional[str]) -> Optional[str]:
    """Validate cookie file exists and has content before use"""
    return cookiefile if (cookiefile and os.path.exists(cookiefile) and os.path.getsize(cookiefile) > 0) else None


def _mk_base_tmp() -> str:
    # No extension – lets us append .%(ext)s cleanly in step 1
    with tempfile.NamedTemporaryFile(suffix="", delete=True) as tf:
        return tf.name


def _track_download_metadata(cookies_used: bool, client_used: str, proxy_used: bool):
    """
    Track download attempt metadata for health endpoint exposure.
    Updates global app state without exposing sensitive data.
    """
    try:
        # Import here to avoid circular imports
        from app import update_download_metadata
        update_download_metadata(used_cookies=cookies_used, client_used=client_used)
    except ImportError:
        # App not available (e.g., in tests), skip tracking
        pass
    except Exception:
        # Don't fail downloads due to metadata tracking issues
        pass


def _combine_error_messages(step1_error: Optional[str], step2_error: Optional[str]) -> str:
    """
    Combine step1 and step2 error messages with proper separator.
    Cap the result to avoid jumbo log lines in App Runner.
    """
    MAX_ERROR_LENGTH = 10000  # 10k chars max to avoid jumbo lines
    
    if not step1_error and not step2_error:
        return "Unknown download error"
    
    if step1_error and step2_error:
        combined = f"{step1_error.strip()} || {step2_error.strip()}"
    else:
        combined = (step1_error or step2_error or "").strip()
    
    # Cap the error message length
    if len(combined) > MAX_ERROR_LENGTH:
        truncated_length = MAX_ERROR_LENGTH - 50  # Leave room for truncation message
        combined = combined[:truncated_length] + "... [truncated: error too long]"
    
    return combined


def _extract_proxy_username(proxy_url: str) -> str:
    """
    Extract proxy username from proxy URL for logging (no password, no host).
    Enhanced with minimal masking for security while preserving debuggability.
    """
    if not proxy_url:
        return "none"
    
    try:
        parsed = urlparse(proxy_url)
        if parsed.username:
            u = parsed.username
            # Mask username: show first 3 + last 2 for longer names, first 2 + *** for shorter
            return (u[:3] + "***" + u[-2:]) if len(u) > 6 else (u[:2] + "***")
    except Exception:
        pass
    
    return "unknown"


def _check_cookie_freshness(cookiefile: Optional[str]) -> bool:
    """
    Check if cookiefile is older than 12 hours and log warning if so.
    Returns True if fresh (or no cookiefile), False if stale.
    """
    if not cookiefile or not os.path.exists(cookiefile):
        return True
    
    try:
        file_age_hours = (time.time() - os.path.getmtime(cookiefile)) / 3600
        if file_age_hours > 12:
            logging.warning(f"⚠️ Cookiefile is older than 12 hours ({file_age_hours:.1f}h) and may be invalid. Please refresh.")
            return False
        return True
    except Exception as e:
        logging.warning(f"Could not check cookie freshness: {e}")
        return True


def _detect_cookie_invalidation(error_text: str) -> bool:
    """
    Detect cookie invalidation patterns in yt-dlp output/errors.
    Returns True if cookies appear to be invalid/expired.
    """
    if not error_text:
        return False
    
    error_lower = error_text.lower()
    cookie_invalid_patterns = [
        'cookies are no longer valid',
        'cookies no longer valid',
        'provided youtube account cookies are no longer valid',
        'cookie has expired',
        'invalid cookies',
        'cookies have expired'
    ]
    
    return any(pattern in error_lower for pattern in cookie_invalid_patterns)


def _detect_extraction_failure(error_text: str) -> bool:
    """
    Detect YouTube extraction failure patterns that may benefit from retry.
    Returns True if this looks like an extraction error (not network/proxy).
    Enhanced with modern YouTube error patterns for better detection.
    """
    if not error_text:
        return False
    
    error_lower = error_text.lower()
    extraction_patterns = [
        # Existing patterns (maintained for backward compatibility)
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


def _detect_http_throttling(error_text: str) -> bool:
    """Heuristic for throttling/forbidden cases that benefit from demotion."""
    if not error_text:
        return False
    t = error_text.lower()
    return (" 429 " in t) or ("http error 429" in t) or ("http 403" in t) or ("forbidden" in t)


def download_audio_with_fallback(
    video_url: str,
    ua: str,
    proxy_url: str,
    ffmpeg_path: str = "/usr/bin",
    logger: Optional[Callable[[str], None]] = None,
    cookiefile: Optional[str] = None,
) -> str:
    """
    Downloads audio from a YouTube (or other) video URL using yt-dlp with a two-step strategy.
    Step 1: Direct audio download (m4a preferred, no re-encode).
    Step 2 (fallback): Re-encode to mp3 using FFmpegExtractAudio.
    
    Returns: Path to the downloaded audio file, or raises RuntimeError if both attempts fail.
    """
    log = (logger or (lambda m: None))

    # Enhanced headers for better bot detection avoidance (Task 3 requirement)
    common_headers = {
        "User-Agent": ua,  # Use provided User-Agent for consistency
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,es;q=0.8,fr;q=0.7",  # Enhanced language preferences
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": "https://www.youtube.com/",
        "Origin": "https://www.youtube.com",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",  # More realistic for YouTube requests
        "Sec-Fetch-User": "?1",
        "Sec-Ch-Ua": '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Upgrade-Insecure-Requests": "1",
        "DNT": "1",  # Do Not Track header
    }
    
    # Enhanced base configuration with multi-client support and network resilience
    base_opts = {
        "proxy": proxy_url or None,
        "http_headers": common_headers,
        "noplaylist": True,
        # Network resilience settings (Task 3 requirement)
        "retries": 2,  # Retry failed downloads up to 2 times
        "fragment_retries": 2,  # Retry failed fragments up to 2 times
        "socket_timeout": 10,  # 10 second socket timeout for network resilience
        "nocheckcertificate": True,  # Bypass certificate issues for network resilience
        # Multi-client configuration for maximum compatibility (Task 3 requirement)
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web", "web_safari"]  # Multiple clients to avoid JSONDecodeError
            }
        },
        # Additional hardening options
        "concurrent_fragment_downloads": 1,  # Reduce detection risk
        "nopart": True,  # avoid leaving .part files around
        "geo_bypass": False,  # Avoid suspicious behavior patterns
        "ffmpeg_location": ffmpeg_path,
        "forceipv4": True,  # Some pools/targets behave better over IPv4
        "http_chunk_size": 10485760,  # 10 MB chunks
        "ratelimit": 100000,  # ~100 KB/s intentional rate limiting
        "restrictfilenames": True,  # Avoid surprise characters in temp names
        # Let service logs show details; don't silence warnings entirely
        "quiet": False,
        "no_warnings": False,
    }
    
    # Add cookiefile if provided and valid
    validated_cookiefile = _maybe_cookie(cookiefile)
    if validated_cookiefile:
        base_opts["cookiefile"] = validated_cookiefile

    # Enhanced logging per expert recommendation - show proxy usage and username
    if proxy_url:
        proxy_username = _extract_proxy_username(proxy_url)
        logging.info(f"yt_dlp.proxy.in_use=true proxy_username={proxy_username}")
    else:
        logging.info("yt_dlp.proxy.in_use=false")
    
    # Determine which client will be used (first in the list)
    extractor_args = base_opts.get("extractor_args", {})
    youtube_args = extractor_args.get("youtube", {})
    player_clients = youtube_args.get("player_client", ["unknown"])
    primary_client = player_clients[0] if player_clients else "unknown"

    # ---------- STEP 1: direct audio (m4a preferred) ----------
    base = _mk_base_tmp()
    final_path_holder: Dict[str, Optional[str]] = {"path": None}
    temp_files_to_cleanup = []

    def _hook_step1(d: Dict):
        # When yt-dlp finalizes the file, status == 'finished' and 'filename' is present.
        if d.get("status") == "finished":
            fp = d.get("filename")
            if fp:
                final_path_holder["path"] = fp

    ydl_opts_step1 = {
        **base_opts,
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": base + ".%(ext)s",
        "progress_hooks": [_hook_step1],
    }

    # Track Step 1 error for potential combination with Step 2
    err_step1: Optional[str] = None
    
    try:
        try:
            with YoutubeDL(ydl_opts_step1) as ydl:
                ydl.download([video_url])
            
            # After step 1 completes, verify the produced file really exists
            path1 = final_path_holder["path"]
            if path1:
                if os.path.exists(path1):
                    try:
                        size = os.path.getsize(path1)
                    except OSError:
                        size = -1
                    log(f"yt_step1_ok path={path1} size={size}")
                    
                    # Track successful download metadata
                    _track_download_metadata(
                        cookies_used=bool(validated_cookiefile),
                        client_used=primary_client,
                        proxy_used=bool(proxy_url)
                    )
                    
                    return os.path.abspath(path1)
                else:
                    log(f"yt_step1_finished_missing path={path1} (not found on disk)")
            else:
                log("yt_step1_no_path_from_hook")
        except DownloadError as e:
            log(f"yt_step1_download_error err={e}")
            # Record but DO NOT raise yet; allow fallback to run
            err_step1 = str(e)

        # ---------- STEP 2: fallback – re-encode to mp3 ----------
        # Use a fresh base (in case step1 created an .m4a with same stem)
        base2 = _mk_base_tmp()
        final_path_holder2: Dict[str, Optional[str]] = {"path": None}

        # We will predict the final path as base2 + ".mp3" but also try to read from hooks/info_dict
        predicted_mp3 = base2 + ".mp3"

        def _hook_step2(d: Dict):
            # Post-processor creates the final audio; status == 'finished' with 'filename'
            if d.get("status") == "finished":
                fp = d.get("filename")
                if fp:
                    final_path_holder2["path"] = fp

        ydl_opts_step2 = {
            **base_opts,
            "format": "bestaudio/best",
            "outtmpl": base2,  # no ext; postprocessor will output .mp3
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
            ],
            "progress_hooks": [_hook_step2],
        }

        try:
            with YoutubeDL(ydl_opts_step2) as ydl:
                ydl.download([video_url])

            # After step 2 completes, verify the final file exists
            path2 = final_path_holder2["path"] or predicted_mp3
            if path2:
                if os.path.exists(path2):
                    try:
                        size2 = os.path.getsize(path2)
                    except OSError:
                        size2 = -1
                    log(f"yt_step1_fail_step2_ok path={path2} size={size2}")
                    
                    # Track successful download metadata (step2 success)
                    _track_download_metadata(
                        cookies_used=bool(validated_cookiefile),
                        client_used=primary_client,
                        proxy_used=bool(proxy_url)
                    )
                    
                    return os.path.abspath(path2)
                else:
                    log(f"yt_step2_finished_missing path={path2} (not found on disk)")
            else:
                log("yt_step2_no_path_from_hook")
        except DownloadError as e:
            log(f"yt_step2_download_error err={e}")
            # Both attempts failed — raise with both messages for upstream detection
            step2_error = str(e)
            combined = _combine_error_messages(err_step1, step2_error)
            raise RuntimeError(combined)

        # Both steps completed but no valid file found
        combined = _combine_error_messages(err_step1, f"Audio download failed for {video_url}")
        raise RuntimeError(combined)
    
    finally:
        # Clean up any leftover temp files
        for temp_file in temp_files_to_cleanup:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except Exception:
                pass  # Ignore cleanup errors


def download_audio_with_retry(
    video_url: str,
    ua: str,
    proxy_url: str,
    ffmpeg_path: str = "/usr/bin",
    logger: Optional[Callable[[str], None]] = None,
    cookiefile: Optional[str] = None,
    user_id: Optional[int] = None,
) -> str:
    """
    Enhanced download with mandatory A/B testing for extraction failures.
    
    Retry strategy:
    1. First attempt: Use cookies if provided, fresh, and not disabled
    2. Mandatory retry: Always retry without cookies on ANY extraction failure (even with fresh cookies)
    3. Fail gracefully with "consider updating yt-dlp" message
    
    Returns: Path to downloaded audio file, or raises RuntimeError with detailed error info.
    """
    log = (logger or (lambda m: None))
    
    # Check environment disable flag
    cookies_disabled = os.getenv('DISABLE_COOKIES', 'false').lower() == 'true'
    
    # Check cookie freshness before first attempt
    cookies_fresh = _check_cookie_freshness(cookiefile)
    use_cookies_attempt1 = bool(cookiefile and cookies_fresh and not cookies_disabled)
    
    # Determine reason for attempt 1 cookie usage
    if cookiefile and not cookies_fresh:
        reason = "stale_cookiefile"
        use_cookies_attempt1 = False
    elif cookies_disabled:
        reason = "environment_disabled"
        use_cookies_attempt1 = False
    else:
        reason = "normal"
    
    # Log attempt 1 configuration
    log(f"yt_dlp_attempt=1 use_cookies={str(use_cookies_attempt1).lower()} reason={reason}")
    
    # First attempt
    attempt_cookiefile = cookiefile if use_cookies_attempt1 else None
    
    try:
        return download_audio_with_fallback(
            video_url, ua, proxy_url, ffmpeg_path, logger, attempt_cookiefile
        )
    except RuntimeError as e:
        error_text = str(e)
        log(f"yt_dlp_attempt=1 failed: {error_text}")
        
        # Check failure types for demotion decision
        cookie_invalid = _detect_cookie_invalidation(error_text)
        extraction_failure = _detect_extraction_failure(error_text)
        http_throttling = _detect_http_throttling(error_text)
        
        # Decide retry policy (MVP): demote to no-cookies when it can actually change outcome:
        #  - extraction failure AND attempt 1 used cookies, OR
        #  - explicit cookie invalidation, OR
        #  - throttling/forbidden hints (429/403)
        if (extraction_failure and use_cookies_attempt1) or cookie_invalid or http_throttling:
            # Determine retry reason
            if cookie_invalid:
                retry_reason = "cookie_invalid"
                if user_id:
                    logging.warning(f"⚠️ YouTube cookies invalid for user {user_id}, retrying without cookies")
                else:
                    logging.warning("⚠️ YouTube cookies invalid, retrying without cookies")
            elif extraction_failure:
                retry_reason = "extraction_failure"
                logging.info(f"Extraction failure detected for {video_url}, retrying without cookies")
            elif http_throttling:
                retry_reason = "http_throttling"
                logging.info(f"HTTP throttling detected for {video_url}, retrying without cookies")
            
            log(f"yt_dlp_attempt=2 use_cookies=false retry_reason={retry_reason}")
            
            # Short jitter to reduce burst retries
            time.sleep(1 + random.random())
            
            try:
                return download_audio_with_fallback(
                    video_url, ua, proxy_url, ffmpeg_path, logger, cookiefile=None
                )
            except RuntimeError as e2:
                error_text2 = str(e2)
                log(f"yt_dlp_attempt=2 failed: {error_text2}")
                
                # Both attempts failed - raise single final error with both messages
                combined_error = f"Attempt 1: {error_text} | Attempt 2: {error_text2} - consider updating yt-dlp"
                raise RuntimeError(combined_error)
        
        # Single attempt failure (no retry conditions met)
        final_error = f"{error_text} - consider updating yt-dlp"
        raise RuntimeError(final_error)
