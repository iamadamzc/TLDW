# yt_download_helper.py
import os
import tempfile
from typing import Callable, Dict, Optional

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

    # Enhanced headers for better bot detection avoidance
    common_headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.youtube.com/",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }
    
    # Base configuration with hardening options
    base_opts = {
        "proxy": proxy_url or None,
        "http_headers": common_headers,
        "noplaylist": True,
        "retries": 2,
        "fragment_retries": 2,
        "concurrent_fragment_downloads": 1,  # Reduce detection risk
        "nopart": True,  # avoid leaving .part files around
        "socket_timeout": 15,
        "geo_bypass": False,  # Avoid suspicious behavior patterns
        "ffmpeg_location": ffmpeg_path,
        "forceipv4": True,  # Some pools/targets behave better over IPv4
        "http_chunk_size": 10485760,  # 10 MB chunks
        "ratelimit": 100000,  # ~100 KB/s intentional rate limiting
        "extractor_args": {"youtube": {"player_client": ["web"]}},  # Stable web client only
        # Let service logs show details; don't silence warnings entirely
        "quiet": False,
        "no_warnings": False,
    }
    
    # Add cookiefile if provided and valid
    validated_cookiefile = _maybe_cookie(cookiefile)
    if validated_cookiefile:
        base_opts["cookiefile"] = validated_cookiefile

    # ---------- STEP 1: direct audio (m4a preferred) ----------
    base = _mk_base_tmp()
    final_path_holder: Dict[str, Optional[str]] = {"path": None}

    def _hook_step1(d: Dict):
        # 'finished' status occurs when the file is finalized (no .part)
        if d.get("status") == "finished":
            # yt-dlp >=2024 typically returns 'filename'; fallback to _filename if needed
            fp = d.get("filename") or d.get("info_dict", {}).get("_filename")
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
        with YoutubeDL(ydl_opts_step1) as ydl:
            ydl.download([video_url])
        path1 = final_path_holder["path"]
        if _file_ok(path1):
            log(f"yt_step1_ok path={path1} size={os.path.getsize(path1)}")
            return os.path.abspath(path1)
        else:
            log(f"yt_step1_no_file path={path1}")
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
        # Post-processor creates the MP3; capture the resulting filename if provided
        if d.get("status") == "finished":
            fp = d.get("filename") or d.get("info_dict", {}).get("_filename")
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

        # Prefer hook value; fallback to predicted_mp3
        path2 = final_path_holder2["path"] or predicted_mp3
        if _file_ok(path2):
            log(f"yt_step1_fail_step2_ok path={path2} size={os.path.getsize(path2)}")
            return os.path.abspath(path2)
        else:
            log(f"yt_step2_no_file path={path2}")
    except DownloadError as e:
        log(f"yt_step2_download_error err={e}")
        # Both attempts failed — raise with both messages for upstream detection
        combined = (err_step1 or "").strip()
        if combined:
            combined += " || "
        combined += str(e)
        raise RuntimeError(combined)

    raise RuntimeError(f"Audio download failed for {video_url}")
