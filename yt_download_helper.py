# yt_download_helper.py
import os
import tempfile
from typing import Callable, Dict, Optional

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


def _file_ok(path: Optional[str]) -> bool:
    return bool(path and os.path.exists(path) and os.path.getsize(path) > 0)


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
) -> str:
    """
    Downloads audio from a YouTube (or other) video URL using yt-dlp with a two-step strategy.
    Step 1: Direct audio download (m4a preferred, no re-encode).
    Step 2 (fallback): Re-encode to mp3 using FFmpegExtractAudio.
    
    Returns: Path to the downloaded audio file, or raises RuntimeError if both attempts fail.
    """
    log = (logger or (lambda m: None))

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
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": base + ".%(ext)s",
        "proxy": proxy_url or None,
        "http_headers": {"User-Agent": ua, "Accept-Language": "en-US,en;q=0.9"},
        "noplaylist": True,
        "retries": 2,
        "fragment_retries": 2,
        "nopart": True,  # avoid leaving .part files around
        "socket_timeout": 15,
        "ffmpeg_location": ffmpeg_path,
        "progress_hooks": [_hook_step1],
        # Verbose=False keeps logs quieter; your service handles structured logs
        "quiet": False,
        "no_warnings": False,
    }

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
        "format": "bestaudio/best",
        "outtmpl": base2,  # no ext; postprocessor will output .mp3
        "proxy": proxy_url or None,
        "http_headers": {"User-Agent": ua, "Accept-Language": "en-US,en;q=0.9"},
        "noplaylist": True,
        "retries": 1,
        "fragment_retries": 1,
        "nopart": True,
        "socket_timeout": 15,
        "ffmpeg_location": ffmpeg_path,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "progress_hooks": [_hook_step2],
        "quiet": False,
        "no_warnings": False,
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

    raise RuntimeError(f"Audio download failed for {video_url}")
