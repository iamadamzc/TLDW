import os
import logging
from typing import Optional
import xml.etree.ElementTree as ET
import json
import requests

from playwright.sync_api import sync_playwright, Page
from youtube_transcript_api import YouTubeTranscriptApi as YTA
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

from proxy_manager import ProxyManager, ProxyAuthError, ProxyConfigError, generate_correlation_id, error_response
from transcript_cache import TranscriptCache
from shared_managers import shared_managers

import time

_CHROME_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")

def _fetch_timedtext(video_id: str, lang: str, kind=None, cookies=None, proxies=None, timeout_s=30) -> str:
    """Try json3 first, then XML; return plain text or ''."""
    headers = {"User-Agent": _CHROME_UA, "Accept-Language": "en-US,en;q=0.8"}
    params = {"v": video_id, "lang": lang}
    if kind:
        params["kind"] = kind

    # 1) Try json3 on youtube.com
    r = requests.get("https://www.youtube.com/api/timedtext",
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
    r2 = requests.get("https://video.google.com/timedtext",
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
    """Robust timed-text with backoff + proxy→no-proxy fallback."""
    languages = ["en", "en-US", "es", "es-419"]
    kinds = [None, "asr"]  # prefer official, then auto
    proxies = proxy_manager.proxy_dict_for("requests") if proxy_manager else None

    # Try with proxy (2 attempts with backoff)
    for attempt in range(2):
        try:
            for lang in languages:
                for kind in kinds:
                    txt = _fetch_timedtext(video_id, lang, kind, cookies=cookie_jar, proxies=proxies, timeout_s=30)
                    if txt:
                        logging.info(f"Timedtext hit via proxy: lang={lang}, kind={kind or 'caption'}")
                        return txt
        except (requests.ReadTimeout, requests.ConnectTimeout):
            logging.warning("Timedtext timed out via proxy; backing off...")
        time.sleep(1 + attempt)

    # Final attempt without proxy (sometimes exits stall)
    logging.info("Timedtext final attempt without proxy...")
    for lang in languages:
        for kind in kinds:
            try:
                txt = _fetch_timedtext(video_id, lang, kind, cookies=cookie_jar, proxies=None, timeout_s=30)
                if txt:
                    logging.info(f"Timedtext hit w/o proxy: lang={lang}, kind={kind or 'caption'}")
                    return txt
            except Exception as e:
                logging.warning(f"Timedtext no-proxy failed: {e}")

    logging.info("Timedtext: no captions found")
    return ""

# --- helper: click any of several selectors ---
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

def _playwright_launch_kwargs(proxy_manager):
    launch_args = {"headless": True}
    if proxy_manager:
        cfg = proxy_manager.proxy_dict_for("playwright")
        if cfg:
            launch_args["proxy"] = cfg
            logging.info(f"Playwright proxy -> server={cfg['server']}")
        else:
            logging.info("Playwright proxy -> none")
    return launch_args

def _parse_youtubei_transcript_json(data: dict) -> str:
    """Extract transcript lines from various YouTubei shapes."""
    def join_runs(runs):
        return "".join((r or {}).get("text", "") for r in (runs or []))

    # Common path:
    cues = []
    try:
        cues = (data["actions"][0]["updateEngagementPanelAction"]["content"]
                    ["transcriptRenderer"]["body"]["transcriptBodyRenderer"]["cueGroups"])
    except Exception:
        pass

    lines = []
    for cg in cues or []:
        # try several shapes seen in the wild
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
        text = join_runs(runs).strip() if runs else ""
        if text:
            lines.append(text)
    return "\n".join(lines).strip()

def get_transcript_via_youtubei(video_id: str, proxy_manager=None, cookies=None, timeout_ms=60000) -> str:
    """
    Open the watch page, trigger transcript, capture /youtubei/v1/get_transcript JSON, parse to text.
    Returns '' if not available.
    """
    url = f"https://www.youtube.com/watch?v={video_id}&hl=en"
    captured = {"json": None}

    with sync_playwright() as p:
        browser = p.chromium.launch(**_playwright_launch_kwargs(proxy_manager))
        context = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36"),
            viewport={"width": 1366, "height": 900},
            locale="en-US"
        )
        if cookies:
            context.add_cookies(cookies)
        page = context.new_page()

        # Reduce weight
        page.route("**/*", lambda r: r.abort() if r.request.resource_type in {"image","font","media"} else r.continue_())

        def on_response(resp):
            try:
                if "/youtubei/v1/get_transcript" in resp.url and resp.request.method == "POST":
                    captured["json"] = resp.json()
            except Exception:
                pass

        page.on("response", on_response)

        # Navigate
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

        # Handle consent if present (best-effort)
        _try_click_any(page, [
            "button:has-text('Accept all')",
            "button:has-text('I agree')",
            "button:has-text('Acepto todo')",
            "button:has-text('Estoy de acuerdo')"
        ], wait_after=1200)

        # NEW path first: built-in "Transcript" section
        opened = _try_click_any(page, [
            "ytd-transcript-renderer tp-yt-paper-button:has-text('Show transcript')",
            "tp-yt-paper-button:has-text('Show transcript')",
            "button:has-text('Show transcript')",
        ], wait_after=1200)

        # Fallback: old menu path
        if not opened:
            _try_click_any(page, [
                "button[aria-label*='More actions']",
                "button[aria-label*='More options']",
            ], wait_after=600)
            opened = _try_click_any(page, [
                "tp-yt-paper-item:has-text('Show transcript')",
                "yt-formatted-string:has-text('Show transcript')",
            ], wait_after=1200)

        # If still not opened, try m.youtube (lighter)
        if not opened and not captured["json"]:
            page.goto(f"https://m.youtube.com/watch?v={video_id}&hl=en",
                      wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(1000)
            opened = _try_click_any(page, ["button:has-text('Show transcript')"], wait_after=1200)

        # Give time for the network call to fire
        page.wait_for_timeout(2000)

        data = captured["json"]
        text = _parse_youtubei_transcript_json(data) if data else ""
        browser.close()

        if text:
            logging.info("YouTubei transcript JSON captured & parsed.")
        else:
            logging.info("YouTubei transcript JSON not available.")
        return text


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
                   {"image", "media", "font", "stylesheet"} else r.continue_())

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

    def get_transcript(self, video_id: str, language: str = "en", user_cookies=None) -> str:
        correlation_id = generate_correlation_id()
        if video_id in self._video_locks:
            logging.info(f"Video {video_id} already being processed, waiting...")
        
        self._video_locks[video_id] = True
        try:
            cached_transcript = self.cache.get(video_id, language)
            if cached_transcript:
                logging.info(f"Cache hit for video {video_id} (lang: {language})")
                return cached_transcript

            if self.proxy_manager:
                try:
                    if not self.proxy_manager.preflight():
                        return error_response('PROXY_AUTH_FAILED', correlation_id)
                except (ProxyAuthError, ProxyConfigError) as e:
                    return error_response('PROXY_ERROR', correlation_id, str(e))

            # 1) Timed-text (already implemented in our service)
            txt = get_captions_via_timedtext(video_id, proxy_manager=self.proxy_manager, cookie_jar=user_cookies)
            if txt:
                self.cache.set(video_id, txt, language, source="timedtext", ttl_days=7)
                return txt

            # 2) YouTubei JSON via Playwright (UI-agnostic)
            txt = get_transcript_via_youtubei(video_id, proxy_manager=self.proxy_manager, cookies=user_cookies)
            if txt:
                self.cache.set(video_id, txt, language, source="youtubei", ttl_days=7)
                return txt

            # 3) Optional ASR fallback (controlled by env ENABLE_ASR_FALLBACK)
            if os.getenv("ENABLE_ASR_FALLBACK", "0") == "1":
                txt = self.asr_from_intercepted_audio(video_id, pm=self.proxy_manager, cookies=user_cookies)
                if txt:
                    self.cache.set(video_id, txt, language, source="asr", ttl_days=7)
                    return txt

            return ""
        finally:
            self._video_locks.pop(video_id, None)

    def get_captions_via_api(self, video_id: str, languages=("en", "en-US")) -> str:
        try:
            listing = YTA.list_transcripts(video_id)
            try:
                t = listing.find_transcript(list(languages))
            except Exception:
                t = listing.find_generated_transcript(list(languages))
            segments = t.fetch()
            return "\n".join(s["text"] for s in segments if s["text"].strip())
        except (TranscriptsDisabled, NoTranscriptFound):
            return ""
        except AttributeError:
            try:
                segments = YTA.get_transcript(video_id, languages=list(languages))
                return "\n".join(s["text"] for s in segments if s["text"].strip())
            except Exception:
                return ""
        except Exception:
            return ""

    def asr_from_intercepted_audio(self, video_id: str, pm: Optional[ProxyManager] = None, cookies=None) -> str:
        logging.info(f"ASR fallback for video_id {video_id} is not fully implemented yet.")
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
