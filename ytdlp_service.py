"""
yt-dlp service for extracting audio URLs from YouTube videos.

This module provides deterministic audio URL extraction using yt-dlp,
bypassing Playwright navigation timeouts for ASR reliability.

Features:
- Proxy enforcement via ProxyManager integration
- Fail_class error categorization
- Comprehensive logging via evt()
- Kill-switches for safety (DISABLE_YTDLP, ASR_AUDIO_EXTRACTOR)
"""

import os
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlparse

# Import structured logging
from log_events import evt
from logging_setup import get_logger

logger = get_logger(__name__)

try:
    import yt_dlp
except ImportError:
    yt_dlp = None
    logger.warning("yt-dlp not installed. ytdlp_service will not be available.")


def _sanitize_proxy_url(proxy_url: str) -> Dict[str, str]:
    """
    Sanitize proxy URL for logging by extracting profile and host.
    
    Args:
        proxy_url: Full proxy URL (may contain credentials)
        
    Returns:
        Dict with proxy_host and proxy_profile (sanitized)
    """
    try:
        parsed = urlparse(proxy_url)
        # Extract host and port without credentials
        proxy_host = f"{parsed.hostname}:{parsed.port}" if parsed.port else parsed.hostname
        
        # Determine profile from URL scheme or path
        proxy_profile = "unknown"
        if "residential" in proxy_url.lower():
            proxy_profile = "residential"
        elif "datacenter" in proxy_url.lower():
            proxy_profile = "datacenter"
        elif parsed.scheme in ["http", "https", "socks5"]:
            proxy_profile = parsed.scheme
            
        return {
            "proxy_host": proxy_host,
            "proxy_profile": proxy_profile
        }
    except Exception as e:
        logger.warning(f"Failed to sanitize proxy URL: {e}")
        return {"proxy_host": "unknown", "proxy_profile": "unknown"}


def _classify_ytdlp_error(exception: Exception) -> str:
    """
    Classify yt-dlp errors into fail_class categories.
    
    Args:
        exception: Exception raised by yt-dlp
        
    Returns:
        fail_class string for logging
    """
    error_str = str(exception).lower()
    error_type = type(exception).__name__
    
    # Video unavailable patterns
    if any(pattern in error_str for pattern in [
        "video unavailable",
        "video not available",
        "this video is unavailable",
        "private video",
        "deleted",
        "removed"
    ]):
        return "video_unavailable"
    
    # Geo-blocking patterns
    if any(pattern in error_str for pattern in [
        "not available in your country",
        "blocked in your country",
        "geo",
        "region"
    ]):
        return "geo_blocked"
    
    # Age restriction patterns
    if any(pattern in error_str for pattern in [
        "age",
        "restricted",
        "sign in to confirm your age"
    ]):
        return "age_restricted"
    
    # Network errors
    if any(pattern in error_str for pattern in [
        "network",
        "connection",
        "timeout",
        "timed out",
        "failed to establish"
    ]):
        return "network_error"
    
    # Extraction errors
    if any(pattern in error_str for pattern in [
        "unable to extract",
        "unsupported url",
        "no video formats found",
        "extraction failed"
    ]):
        return "extraction_error"
    
    # Format not found
    if any(pattern in error_str for pattern in [
        "requested format not available",
        "no suitable formats",
        "format not found"
    ]):
        return "format_not_found"
    
    return "unknown"


def _select_best_audio_format(formats: list) -> Optional[Dict[str, Any]]:
    """
    Select the best audio format from available formats.
    
    Priority:
    1. Audio-only formats with highest ABR (audio bitrate)
    2. Video formats with audio streams, highest ABR
    3. First available format as fallback
    
    Args:
        formats: List of format dictionaries from yt-dlp
        
    Returns:
        Best audio format dict or None
    """
    if not formats:
        return None
    
    audio_only = []
    video_with_audio = []
    
    for fmt in formats:
        # Check if format has audio
        acodec = fmt.get('acodec', 'none')
        vcodec = fmt.get('vcodec', 'none')
        
        if acodec != 'none':
            abr = fmt.get('abr', 0) or 0  # Audio bitrate
            
            if vcodec == 'none':
                # Audio-only format
                audio_only.append((abr, fmt))
            else:
                # Video with audio
                video_with_audio.append((abr, fmt))
    
    # Prefer audio-only formats with highest ABR
    if audio_only:
        audio_only.sort(reverse=True, key=lambda x: x[0])
        return audio_only[0][1]
    
    # Fallback to video with audio
    if video_with_audio:
        video_with_audio.sort(reverse=True, key=lambda x: x[0])
        return video_with_audio[0][1]
    
    # Last resort: first format
    return formats[0]


def extract_best_audio_url(
    youtube_url: str,
    proxy_manager=None,
    job_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extract best audio URL from YouTube video using yt-dlp.
    
    Args:
        youtube_url: Full YouTube URL or video ID
        proxy_manager: ProxyManager instance for job-scoped proxy
        job_id: Job identifier for proxy session
        
    Returns:
        Dict with keys:
        - success: bool
        - url: str (audio stream URL)
        - ext: str (file extension)
        - format_id: str (yt-dlp format ID)
        - abr: float (audio bitrate)
        - proxy_used: bool
        - fail_class: str (if failed)
        - error: str (if failed)
    """
    # Kill-switch: DISABLE_YTDLP=1
    if os.getenv("DISABLE_YTDLP", "0") == "1":
        evt("ytdlp_disabled_by_killswitch", extractor="yt_dlp")
        return {
            "success": False,
            "fail_class": "disabled",
            "error": "yt-dlp disabled by DISABLE_YTDLP=1 kill-switch"
        }
    
    # Check if yt-dlp is installed
    if yt_dlp is None:
        evt("ytdlp_not_installed", extractor="yt_dlp")
        return {
            "success": False,
            "fail_class": "not_installed",
            "error": "yt-dlp module not installed"
        }
    
    # Normalize URL (handle bare video IDs)
    if not youtube_url.startswith("http"):
        youtube_url = f"https://www.youtube.com/watch?v={youtube_url}"
    
    # Fetch proxy URL from ProxyManager if available
    proxy_url = None
    proxy_enabled = False
    proxy_info = {"proxy_host": None, "proxy_profile": None}
    
    if proxy_manager and job_id:
        try:
            # Use correct ProxyManager API for requests client
            proxy_dict = proxy_manager.proxy_dict_for_job(job_id, "requests")
            if proxy_dict:
                # Prefer https proxy if available, else http
                proxy_url = proxy_dict.get("https") or proxy_dict.get("http")
                
                if proxy_url:
                    proxy_enabled = True
                    proxy_info = _sanitize_proxy_url(proxy_url)
                    evt("ytdlp_proxy_acquired",
                        extractor="yt_dlp",
                        proxy_enabled=True,
                        **proxy_info)
        except Exception as e:
            evt("ytdlp_proxy_fetch_failed",
                extractor="yt_dlp",
                error=str(e))
    
    # ENFORCE_PROXY_ALL safety check
    enforce_proxy = os.getenv("ENFORCE_PROXY_ALL", "0") == "1"
    if enforce_proxy and not proxy_url:
        evt("ytdlp_audio_extraction_failed",
            extractor="yt_dlp",
            fail_class="proxy_unavailable",
            error="ENFORCE_PROXY_ALL=1 but no proxy available",
            proxy_enabled=False)
        return {
            "success": False,
            "fail_class": "proxy_unavailable",
            "error": "ENFORCE_PROXY_ALL=1 but ProxyManager returned no proxy URL",
            "proxy_used": False,
            "proxy_enabled": False,
            "proxy_host": None,
            "proxy_profile": None
        }
    
    # Configure yt-dlp options
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'noplaylist': True,
        'format': 'bestaudio/best',
        'extract_flat': False,
    }
    
    # Add proxy if available
    if proxy_url:
        ydl_opts['proxy'] = proxy_url
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info without downloading
            info = ydl.extract_info(youtube_url, download=False)
            
            if not info:
                raise Exception("yt-dlp returned no info")
            
            # Get formats list
            formats = info.get('formats', [])
            if not formats:
                raise Exception("No formats available")
            
            # Select best audio format
            best_format = _select_best_audio_format(formats)
            if not best_format:
                raise Exception("Could not select audio format")
            
            # Extract audio URL and metadata
            audio_url = best_format.get('url')
            if not audio_url:
                raise Exception("Selected format has no URL")
            
            result = {
                "success": True,
                "url": audio_url,
                "ext": best_format.get('ext', 'unknown'),
                "format_id": best_format.get('format_id', 'unknown'),
                "abr": best_format.get('abr', 0),
                "proxy_used": proxy_enabled,
                "proxy_enabled": proxy_enabled,
                "proxy_host": proxy_info.get("proxy_host"),
                "proxy_profile": proxy_info.get("proxy_profile")
            }
            
            # Log success
            evt("ytdlp_audio_extraction_success",
                extractor="yt_dlp",
                format_id=result["format_id"],
                ext=result["ext"],
                abr=result["abr"],
                proxy_enabled=proxy_enabled,
                **proxy_info)
            
            return result
            
    except Exception as e:
        # Classify error
        fail_class = _classify_ytdlp_error(e)
        
        # Log failure
        evt("ytdlp_audio_extraction_failed",
            extractor="yt_dlp",
            fail_class=fail_class,
            error=str(e)[:200],
            proxy_enabled=proxy_enabled,
            **proxy_info)
        
        return {
            "success": False,
            "fail_class": fail_class,
            "error": str(e),
            "proxy_used": proxy_enabled,
            "proxy_enabled": proxy_enabled,
            "proxy_host": proxy_info.get("proxy_host"),
            "proxy_profile": proxy_info.get("proxy_profile")
        }
