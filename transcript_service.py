import os
import logging
from typing import Optional, Tuple
import xml.etree.ElementTree as ET
import json
import requests
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import sys
import importlib.util
import inspect

from playwright.sync_api import sync_playwright, Page

# Startup sanity check to catch local module shadowing
assert importlib.util.find_spec("youtube_transcript_api") is not None, "youtube-transcript-api not installed"
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable

# Guard against local-file shadowing (e.g., youtube_transcript_api.py in repo)
try:
    source_file = inspect.getsourcefile(YouTubeTranscriptApi)
    assert source_file and ("youtube_transcript_api" in source_file), \
        f"Shadowed import detected: {source_file}"
    logging.info(f"YouTube Transcript API loaded from: {source_file}")
except Exception as e:
    logging.warning(f"YouTube Transcript API import validation failed: {e}")

from proxy_manager import ProxyManager, ProxyAuthError, ProxyConfigError, generate_correlation_id, error_response
from transcript_cache import TranscriptCache
from shared_managers import shared_managers
from error_handler import StructuredLogger, handle_transcript_error, log_performance_metrics, log_resource_cleanup
from transcript_metrics import inc_success, inc_fail

_CHROME_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")

# Feature flags for operational safety
ENABLE_YT_API = os.getenv("ENABLE_YT_API", "1") == "1"
ENABLE_TIMEDTEXT = os.getenv("ENABLE_TIMEDTEXT", "1") == "1"
ENABLE_YOUTUBEI = os.getenv("ENABLE_YOUTUBEI", "1") == "1"  # Enable by default for better fallback
ASR_DISABLED = os.getenv("ASR_DISABLED", "false").lower() in ("1", "true", "yes")
ENABLE_ASR_FALLBACK = not ASR_DISABLED  # Enable ASR by default unless explicitly disabled

# Performance and safety controls
PW_NAV_TIMEOUT_MS = int(os.getenv("PW_NAV_TIMEOUT_MS", "45000"))
USE_PROXY_FOR_TIMEDTEXT = os.getenv("USE_PROXY_FOR_TIMEDTEXT", "0") == "1"
ASR_MAX_VIDEO_MINUTES = int(os.getenv("ASR_MAX_VIDEO_MINUTES", "20"))

def make_http_session():
    """Create HTTP session with retry logic for timed-text requests"""
    session = requests.Session()
    retry = Retry(
        total=2, connect=1, read=2, backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
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

def _fetch_timedtext(video_id: str, lang: str, kind=None, cookies=None, proxies=None, timeout_s=15) -> str:
    """Try json3 first, then XML; return plain text or ''."""
    headers = {"Accept-Language": "en-US,en;q=0.8"}
    params = {"v": video_id, "lang": lang}
    if kind:
        params["kind"] = kind

    # 1) Try json3 on youtube.com
    r = HTTP.get("https://www.youtube.com/api/timedtext",
                 params={**params, "fmt": "json3"},
                 headers=headers, cookies=cookies, proxies=proxies,
                 timeout=(5, timeout_s), allow_redirects=True)
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
            texts = [("".join(node.itertext())).strip() for node in root.findall(".//text")]
            if texts:
                return "\n".join(texts)
        except Exception:
            pass

    # 3) Try alternate host (older endpoint) with XML
    r2 = HTTP.get("https://video.google.com/timedtext",
                  params=params, headers=headers, cookies=cookies, proxies=proxies,
                  timeout=(5, timeout_s), allow_redirects=True)
    if r2.status_code == 200 and r2.text.strip():
        try:
            root = ET.fromstring(r2.text)
            texts = [("".join(node.itertext())).strip() for node in root.findall(".//text")]
            if texts:
                return "\n".join(texts)
        except Exception:
            pass

    return ""

def get_captions_via_timedtext(video_id: str, proxy_manager=None, cookie_jar=None) -> str:
    """Robust timed-text with no-proxy-first strategy and backoff."""
    languages = ["en", "en-US", "es", "es-419"]
    kinds = [None, "asr"]  # prefer official, then auto
    proxies = proxy_manager.proxy_dict_for("requests") if (proxy_manager and USE_PROXY_FOR_TIMEDTEXT) else None

    # No-proxy first (2 attempts with backoff)
    for attempt in range(2):
        try:
            for lang in languages:
                for kind in kinds:
                    txt = _fetch_timedtext(video_id, lang, kind, cookies=cookie_jar, proxies=None, timeout_s=15)
                    if txt:
                        logging.info(f"Timedtext hit (no-proxy): lang={lang}, kind={kind or 'caption'}")
                        return txt
        except (requests.ReadTimeout, requests.ConnectTimeout, requests.RequestException):
            logging.warning(f"Timedtext no-proxy attempt {attempt + 1} failed; backing off...")
        time.sleep(1 + attempt)

    # Then proxy if enabled and available
    if proxies:
        for attempt in range(2):
            try:
                for lang in languages:
                    for kind in kinds:
                        txt = _fetch_timedtext(video_id, lang, kind, cookies=cookie_jar, proxies=proxies, timeout_s=15)
                        if txt:
                            logging.info(f"Timedtext hit (proxy): lang={lang}, kind={kind or 'caption'}")
                            return txt
            except (requests.ReadTimeout, requests.ConnectTimeout, requests.RequestException):
                logging.warning(f"Timedtext proxy attempt {attempt + 1} failed; backing off...")
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
    
    def extract_and_transcribe(self, video_id: str, proxy_manager=None, cookies=None) -> str:
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
                logging.warning(f"Video {video_id} duration {duration_minutes}min exceeds limit {self.max_video_minutes}min")
                return ""
            
            # Step 4: Transcribe with Deepgram
            return self._transcribe_with_deepgram(wav_path, video_id)
    
    def _extract_hls_audio_url(self, video_id: str, proxy_manager=None, cookies=None) -> str:
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
            """Capture HLS audio stream URLs"""
            url = response.url.lower()
            if url.endswith(".m3u8") or ".m3u8?" in url:
                if ("audio" in url) or ("mime=audio" in url):
                    captured_url["url"] = response.url
                    logging.info(f"Captured HLS audio URL: {response.url[:100]}...")
        
        with _BROWSER_SEM:
            with sync_playwright() as p:
                browser = None
                try:
                    # Launch browser
                    launch_args = {
                        "headless": True,
                        "args": [
                            "--no-sandbox",
                            "--disable-dev-shm-usage",
                            "--autoplay-policy=no-user-gesture-required"
                        ]
                    }
                    if proxy_manager:
                        cfg = proxy_manager.proxy_dict_for("playwright")
                        if cfg:
                            launch_args["proxy"] = cfg
                    
                    browser = p.chromium.launch(**launch_args)
                    ctx = browser.new_context(locale="en-US")
                    
                    if cookies:
                        pw_cookies = _convert_cookiejar_to_playwright_format(cookies)
                        if pw_cookies:
                            ctx.add_cookies(pw_cookies)
                    
                    page = ctx.new_page()
                    page.set_default_navigation_timeout(timeout_ms)
                    page.on("response", capture_m3u8_response)
                    
                    # Try desktop first, then mobile
                    urls = [
                        f"https://www.youtube.com/watch?v={video_id}&hl=en",
                        f"https://m.youtube.com/watch?v={video_id}&hl=en"
                    ]
                    
                    for url in urls:
                        try:
                            page.goto(url, wait_until="networkidle", timeout=60000)
                            
                            # ensure the player has focus, then play
                            try:
                                page.click("video", timeout=3000)
                            except Exception:
                                pass
                            page.keyboard.press("k")  # play
                            page.wait_for_timeout(3500)  # Wait for stream to start
                            
                            if captured_url["url"]:
                                _pw_register_success()
                                return captured_url["url"]
                                
                        except Exception as e:
                            logging.warning(f"ASR audio extraction failed for {url}: {e}")
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
        """Extract audio from HLS stream to WAV using ffmpeg"""
        try:
            cmd = [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", audio_url,
                "-vn",  # No video
                "-ac", "1",  # Mono
                "-ar", "16000",  # 16kHz sample rate
                wav_path
            ]
            
            result = subprocess.run(cmd, check=True, capture_output=True, timeout=120)
            
            if os.path.exists(wav_path) and os.path.getsize(wav_path) > 0:
                logging.info(f"Audio extracted successfully: {os.path.getsize(wav_path)} bytes")
                return True
            else:
                logging.error("Audio extraction produced empty file")
                return False
                
        except subprocess.TimeoutExpired:
            logging.error("Audio extraction timed out after 120 seconds")
            return False
        except subprocess.CalledProcessError as e:
            logging.error(f"ffmpeg failed: {e.stderr.decode() if e.stderr else str(e)}")
            return False
        except Exception as e:
            logging.error(f"Audio extraction error: {e}")
            return False
    
    def _get_audio_duration_minutes(self, wav_path: str) -> float:
        """Get audio duration in minutes using ffprobe"""
        try:
            cmd = [
                "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                "-of", "csv=p=0", wav_path
            ]
            
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=10)
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
                    logging.error("Deepgram SDK not installed. Install with: pip install deepgram-sdk")
                    return ""
            
            # Read audio file
            with open(wav_path, "rb") as audio_file:
                buffer_data = audio_file.read()
            
            # Configure transcription options
            options = {
                "model": "nova-2",
                "smart_format": True,
                "language": "en"
            }
            
            # Call Deepgram API
            if hasattr(deepgram, 'listen'):
                # SDK v3+
                payload = {"buffer": buffer_data}
                response = deepgram.listen.prerecorded.v("1").transcribe_file(payload, options)
            else:
                # SDK v2
                source = {"buffer": buffer_data, "mimetype": "audio/wav"}
                response = deepgram.transcription.prerecorded(source, options)
            
            # Extract transcript text
            if hasattr(response, 'results'):
                # SDK v3+
                alternatives = response.results.channels[0].alternatives
            else:
                # SDK v2
                alternatives = response["results"]["channels"][0]["alternatives"]
            
            transcript_parts = []
            for alt in alternatives:
                if hasattr(alt, 'transcript'):
                    # SDK v3+
                    text = alt.transcript
                else:
                    # SDK v2
                    text = alt.get("transcript", "")
                
                if text and text.strip():
                    transcript_parts.append(text.strip())
            
            transcript = " ".join(transcript_parts).strip()
            
            if transcript:
                logging.info(f"ASR transcription successful for {video_id}: {len(transcript)} characters")
                return transcript
            else:
                logging.warning(f"ASR transcription returned empty result for {video_id}")
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
    """Register Playwright timeout for circuit breaker"""
    _PW_FAILS["count"] += 1
    if _PW_FAILS["count"] >= 3:
        _PW_FAILS["until"] = now_ms + 10*60*1000  # 10 minutes
        _PW_FAILS["count"] = 0
        logging.warning("Playwright circuit breaker activated - skipping for 10 minutes")

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

def get_transcript_via_youtubei(video_id: str, proxy_manager=None, cookies=None, timeout_ms: int = None) -> str:
    """
    Open watch page (EN), scroll to the Transcript section, click 'Show transcript',
    capture /youtubei/v1/get_transcript JSON, parse lines to plain text.
    Enhanced with safety controls: preflight check, circuit breaker, no-proxy-first.
    """
    logging.info(f"transcript_stage_start video_id={video_id} stage=youtubei")
    timeout_ms = timeout_ms or PW_NAV_TIMEOUT_MS
    now_ms = int(time.time() * 1000)
    
    # Circuit breaker check
    if not _pw_allowed(now_ms):
        logging.info("Playwright circuit breaker active - skipping YouTubei capture")
        return ""
    
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
    ]
    
    # Only add proxy=True branch if a proxy config exists
    use_proxy_order = [False]
    if proxy_manager and proxy_manager.proxy_dict_for("playwright"):
        use_proxy_order.append(True)
    captured = {"json": None}

    deadline = time.time() + 60  # hard cap ~60s for all YT-i attempts per video
    with _BROWSER_SEM:
        with sync_playwright() as p:
            for use_proxy in use_proxy_order:
                for url in urls:
                    if time.time() > deadline:
                        logging.warning("YouTubei global cap reached; aborting to allow ASR fallback")
                        return ""
                    browser = None
                    try:
                        # Launch browser with or without proxy
                        launch_args = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
                        if use_proxy and proxy_manager:
                            cfg = proxy_manager.proxy_dict_for("playwright")
                            if cfg:
                                launch_args["proxy"] = cfg
                        
                        browser = p.chromium.launch(**launch_args)
                        ctx = browser.new_context(
                            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36"),
                            viewport={"width": 1366, "height": 900},
                            locale="en-US",
                            ignore_https_errors=True,
                        )
                        # Pre-bypass consent on both hosts to avoid interstitials
                        ctx.add_cookies([
                            {"name": "CONSENT", "value": "YES+1", "domain": ".youtube.com", "path": "/"},
                            {"name": "CONSENT", "value": "YES+1", "domain": ".m.youtube.com", "path": "/"},
                        ])
                        
                        if pw_cookies:
                            ctx.add_cookies(pw_cookies)
                        
                        page = ctx.new_page()
                        page.set_default_navigation_timeout(timeout_ms)
                        page.set_default_timeout(timeout_ms)

                        # Reduce weight but allow YouTube CSS for proper UI rendering
                        def route_handler(route):
                            url = route.request.url.lower()
                            resource_type = route.request.resource_type
                            
                            # Allow CSS from YouTube and Google domains
                            if resource_type == "stylesheet" and any(domain in url for domain in ["youtube.com", "google.com", "gstatic.com"]):
                                route.continue_()
                            # Block heavy resources but keep essential ones
                            elif resource_type in {"image", "font", "media"}:
                                route.abort()
                            else:
                                route.continue_()
                        
                        page.route("**/*", route_handler)

                        def on_response(resp):
                            try:
                                if "/youtubei/v1/get_transcript" in resp.url and resp.request.method == "POST":
                                    logging.info(f"youtubei_response video_id={video_id} url={resp.url} status={resp.status}")
                                    captured["json"] = resp.json()
                            except Exception as e:
                                logging.warning(f"youtubei_response_parse_failed video_id={video_id} error={e}")

                        # Attach listener *before* navigation
                        page.on("response", on_response)
                        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

                        # Handle consent (best effort)
                        _try_click_any(page, [
                            "button:has-text('Accept all')", "button:has-text('I agree')",
                            "button:has-text('Acepto todo')", "button:has-text('Estoy de acuerdo')"
                        ], wait_after=800)

                        # Scroll down to make the Transcript section render
                        def transcript_button_visible():
                            # Check for multiple possible transcript button selectors
                            selectors = [
                                "button:has-text('Show transcript')",
                                "[aria-label*='Show transcript']",
                                "ytd-transcript-renderer button",
                                "#transcript button",
                                "button[aria-label*='transcript']"
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
                        opened = _try_click_any(page, [
                            # New YouTube UI selectors
                            "ytd-transcript-renderer tp-yt-paper-button:has-text('Show transcript')",
                            "button:has-text('Show transcript')",
                            "tp-yt-paper-button:has-text('Show transcript')",
                            "[aria-label*='Show transcript']",
                            "ytd-transcript-renderer button",
                            "#transcript button",
                            "button[aria-label*='transcript']",
                            # Alternative text variations
                            "button:has-text('Transcript')",
                            "button:has-text('Show Transcript')",
                            "[role='button']:has-text('Show transcript')",
                            # Mobile selectors
                            ".transcript-button",
                            "[data-target-id='transcript']"
                        ], wait_after=1000)

                        # Fallback: old ⋯ menu path with enhanced selectors
                        if not opened:
                            # Try to open the more actions menu
                            menu_opened = _try_click_any(page, [
                                "button[aria-label*='More actions']",
                                "button[aria-label*='More options']",
                                "button[aria-label*='Show more']",
                                "#menu-button",
                                ".dropdown-trigger",
                                "[role='button'][aria-haspopup='true']"
                            ], wait_after=500)
                            
                            if menu_opened:
                                # Try to click transcript option in menu
                                opened = _try_click_any(page, [
                                    "tp-yt-paper-item:has-text('Show transcript')",
                                    "yt-formatted-string:has-text('Show transcript')",
                                    "[role='menuitem']:has-text('transcript')",
                                    ".menu-item:has-text('transcript')",
                                    "a:has-text('Show transcript')",
                                    "button:has-text('Show transcript')"
                                ], wait_after=1000)

                        data = captured["json"]
                        if data is None:
                            try:
                                with page.expect_response(
                                    lambda r: "/youtubei/v1/get_transcript" in r.url and r.request.method == "POST",
                                    timeout=timeout_ms
                                ) as tr_resp:
                                    logging.info(f"youtubei_expect_response waiting video_id={video_id}")
                                if tr_resp.value.ok:
                                    data = tr_resp.value.json()
                            except Exception as e:
                                logging.warning(f"youtubei_expect_response_failed video_id={video_id} error={e}")

                        text = _parse_youtubei_transcript_json(data) if data else ""
                        
                        if text:
                            logging.info(f"YouTubei transcript captured: {'proxy' if use_proxy else 'no-proxy'}, {url}")
                            _pw_register_success()
                            return text
                    
                    except Exception as e:
                        if "TimeoutError" in str(type(e)):
                            logging.warning(f"YouTubei timeout: {'proxy' if use_proxy else 'no-proxy'}, {url}")
                            _pw_register_timeout(now_ms)
                        else:
                            logging.warning(f"YouTubei error: {e}")
                    
                    finally:
                        try:
                            if browser:
                                browser.close()
                        except Exception:
                            pass

    logging.info("YouTubei transcript: no capture successful")
    return ""

def _parse_youtubei_transcript_json(data: dict) -> str:
    """Extract transcript lines from YouTubei JSON (handles common shapes)."""
    def runs_text(runs): return "".join((r or {}).get("text","") for r in (runs or []))

    # Most common path:
    cues = []
    try:
        cues = (data["actions"][0]["updateEngagementPanelAction"]["content"]
                ["transcriptRenderer"]["body"]["transcriptBodyRenderer"]["cueGroups"])
    except Exception:
        pass

    lines = []
    for cg in cues or []:
        runs = None
        try:
            runs = (cg["transcriptCueGroupRenderer"]["cue"]["transcriptCueRenderer"]
                    ["cue"]["simpleText"]["runs"])
        except Exception:
            try:
                runs = (cg["transcriptCueGroupRenderer"]["cues"][0]["transcriptCueRenderer"]
                        ["cue"]["simpleText"]["runs"])
            except Exception:
                runs = None
        t = runs_text(runs).strip() if runs else ""
        if t:
            lines.append(t)
    return "\n".join(lines).strip()


# --- Playwright Helper Functions ---

def _accept_consent(page: Page):
    selectors = [
        "button:has-text('Accept all')", "button:has-text('I agree')",
        "button:has-text('Estoy de acuerdo')", "button:has-text('Acepto todo')",
        "button:has-text('Aceptar todo')"
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
    for label in ["Show transcript", "Open transcript", "Ver transcripción", "Mostrar transcripción"]:
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
def scrape_transcript_with_playwright(video_id: str, pm: Optional[ProxyManager] = None, cookies=None, timeout_ms=60000) -> str:
    url = f"https://www.youtube.com/watch?v={video_id}"
    with sync_playwright() as p:
        launch_args = {"headless": True}
        proxy_config = _pw_proxy(pm)
        if proxy_config:
            launch_args["proxy"] = proxy_config

        browser = p.chromium.launch(**launch_args)
        context = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"),
            viewport={"width": 1280, "height": 800},
            timezone_id="Europe/Madrid",
            locale="en-US"
        )
        if cookies:
            context.add_cookies(cookies)

        page = context.new_page()
        page.route("**/*", lambda r: r.abort() if r.request.resource_type in
                   {"image", "media", "font"} else r.continue_())

        try:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            except Exception as e:
                logging.warning(f"Initial page.goto failed for {url}: {e}. Retrying on mobile URL.")
                page.goto(f"https://m.youtube.com/watch?v={video_id}",
                          wait_until="domcontentloaded", timeout=timeout_ms)
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
            text = "\n".join(i.inner_text().strip() for i in items if i.inner_text().strip())
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

    def get_transcript(self, video_id: str, language: str = "en",
                       user_cookies=None, playwright_cookies=None) -> str:
        """
        Hierarchical transcript acquisition with comprehensive fallback.
        Returns transcript text or empty string if all methods fail.
        """
        correlation_id = generate_correlation_id()
        start_time = time.time()
        
        if video_id in self._video_locks:
            logging.info(f"Video {video_id} already being processed, waiting...")
        
        self._video_locks[video_id] = True
        try:
            # Check cache first
            cached_transcript = self.cache.get(video_id, language)
            if cached_transcript:
                logging.info(f"transcript_attempt video_id={video_id} method=cache success=true duration_ms=0")
                return cached_transcript

            # YouTube-specific preflight: probe + rotate session; do NOT globally disable proxy
            if self.proxy_manager and hasattr(self.proxy_manager, "youtube_preflight"):
                try:
                    ok = self.proxy_manager.youtube_preflight()
                    if not ok and hasattr(self.proxy_manager, "rotate_session"):
                        logging.warning("YouTube preflight blocked; rotating proxy session and retrying")
                        self.proxy_manager.rotate_session()
                        ok = self.proxy_manager.youtube_preflight()
                    if not ok:
                        logging.warning("YouTube preflight still blocked; will attempt both direct and proxy paths in fallbacks")
                except (ProxyAuthError, ProxyConfigError) as e:
                    logging.warning(f"YouTube preflight error; proceeding with both direct and proxy fallbacks: {e}")

            # Hierarchical fallback with feature flags
            transcript_text, source = self._get_transcript_with_fallback(video_id, language, user_cookies, playwright_cookies)
            
            # Cache successful result
            if transcript_text and transcript_text.strip():
                self.cache.set(video_id, transcript_text, language, source=source, ttl_days=7)
            
            # Log final result
            total_duration_ms = int((time.time() - start_time) * 1000)
            logging.info(f"transcript_final video_id={video_id} source={source} "
                        f"success={bool(transcript_text)} duration_ms={total_duration_ms}")
            
            return transcript_text

        finally:
            self._video_locks.pop(video_id, None)

    def _get_transcript_with_fallback(self, video_id: str, language: str, user_cookies=None, playwright_cookies=None) -> Tuple[str, str]:
        """
        Execute hierarchical fallback strategy.
        Returns (transcript_text, source) where source indicates which method succeeded.
        """
        methods = [
            ("yt_api", ENABLE_YT_API, self.get_captions_via_api),
            ("timedtext", ENABLE_TIMEDTEXT, lambda vid, lang, cookies: get_captions_via_timedtext(vid, self.proxy_manager, cookies)),
            ("youtubei", ENABLE_YOUTUBEI, lambda vid, lang, cookies: get_transcript_via_youtubei(vid, self.proxy_manager, cookies)),
            ("asr", ENABLE_ASR_FALLBACK, lambda vid, lang, cookies: self.asr_from_intercepted_audio(vid, self.proxy_manager, cookies))
        ]
        
        for source, enabled, method in methods:
            if not enabled:
                logging.info(f"transcript_attempt video_id={video_id} method={source} success=false reason=disabled")
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
                        success=True
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
                        reason="empty_result"
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
                transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
                
                # Prefer human captions, then auto-generated
                preferred = ['en', 'en-US', 'en-GB', 'es', 'es-ES']
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
                                source_info = f"yt_api:{transcript.language_code}:manual"
                                logging.info(f"Found manual transcript for {video_id}: {source_info}")
                                break
                    except Exception:
                        pass
                
                # If no manual transcript, try auto-generated in preferred languages
                if not transcript_obj:
                    for lang in preferred:
                        try:
                            transcript_obj = transcripts.find_generated_transcript([lang])
                            source_info = f"yt_api:{lang}:auto"
                            logging.info(f"Found auto transcript for {video_id}: {source_info}")
                            break
                        except NoTranscriptFound:
                            continue
                
                # Last resort: any available transcript
                if not transcript_obj:
                    transcript_obj = next((tr for tr in transcripts if tr), None)
                    if transcript_obj:
                        source_info = f"yt_api:{transcript_obj.language_code}:{'manual' if not transcript_obj.is_generated else 'auto'}"
                        logging.info(f"Found fallback transcript for {video_id}: {source_info}")
                
                if transcript_obj:
                    # Fetch with error handling for XML parsing issues
                    try:
                        segments = transcript_obj.fetch()
                    except Exception as fetch_error:
                        logging.warning(f"Transcript fetch failed for {video_id}: {fetch_error}")
                        # Try alternative approach
                        raise fetch_error
                else:
                    raise NoTranscriptFound(video_id)
                    
            except Exception as list_error:
                # Strategy 2: Fallback to direct get_transcript with enhanced error handling
                logging.info(f"List transcripts failed for {video_id}, trying direct get_transcript: {list_error}")
                
                # Try each language individually to isolate issues
                segments = None
                for lang in languages:
                    try:
                        segments = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
                        source_info = f"yt_api:{lang}:direct"
                        logging.info(f"Direct transcript success for {video_id} with {lang}")
                        break
                    except Exception as lang_error:
                        logging.debug(f"Direct transcript failed for {video_id} with {lang}: {lang_error}")
                        continue
                
                if not segments:
                    # Final attempt with all languages
                    segments = YouTubeTranscriptApi.get_transcript(video_id, languages=list(languages))
                    source_info = "yt_api:multi:direct"
            
            # Serialize captions with robust text extraction
            if segments:
                lines = []
                for seg in segments:
                    text = seg.get("text", "")
                    if isinstance(text, str) and text.strip():
                        # Clean up common transcript artifacts
                        text = text.strip()
                        # Remove common YouTube auto-caption artifacts
                        if text not in ["[Music]", "[Applause]", "[Laughter]", "♪", "♫"]:
                            lines.append(text)
                
                transcript_text = "\n".join(lines).strip()
                
                if transcript_text:
                    logging.info(f"Successfully extracted transcript for {video_id} via {source_info}: {len(transcript_text)} chars")
                    return transcript_text
                else:
                    logging.warning(f"Transcript extraction resulted in empty text for {video_id}")
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
                logging.warning(f"YouTube Transcript API XML parsing error for {video_id}: {error_msg}")
                logging.info(f"This usually indicates YouTube is blocking requests or the video has no transcript")
            else:
                logging.warning(f"YouTubeTranscriptApi error for {video_id}: {error_type}: {error_msg}")
            
            return ""

    def asr_from_intercepted_audio(self, video_id: str, pm: Optional[ProxyManager] = None, cookies=None) -> str:
        """
        ASR fallback: Extract audio via HLS interception and transcribe with Deepgram.
        Includes cost controls and duration limits.
        """
        logging.info(f"transcript_stage_start video_id={video_id} stage=asr")
        if not self.deepgram_api_key:
            logging.warning(f"transcript_attempt video_id={video_id} method=asr success=false reason=no_key")
            return ""
        
        try:
            extractor = ASRAudioExtractor(self.deepgram_api_key)
            return extractor.extract_and_transcribe(video_id, pm, cookies)
        except Exception as e:
            logging.error(f"ASR fallback failed for {video_id}: {e}")
            return ""

    def close(self):
        if hasattr(self, 'http_client'):
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
                "asr_fallback": ENABLE_ASR_FALLBACK
            },
            "config": {
                "pw_nav_timeout_ms": PW_NAV_TIMEOUT_MS,
                "use_proxy_for_timedtext": USE_PROXY_FOR_TIMEDTEXT,
                "asr_max_video_minutes": ASR_MAX_VIDEO_MINUTES,
                "deepgram_api_key_configured": bool(self.deepgram_api_key)
            },
            "cache_stats": self.get_cache_stats(),
            "proxy_available": self.proxy_manager is not None
        }
