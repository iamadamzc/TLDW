"""
Enhanced YouTubei service with deterministic transcript capture.

This module provides:
- Deterministic "More actions" → "Show transcript" click sequence
- Primary and fallback selectors for mobile/desktop layout variants
- 25s Future timeout for route interception
- Direct fetch fallback using ytcfg.INNERTUBE_API_KEY and INNERTUBE_CONTEXT
- Consent wall detection and recovery (re-inject SOCS/CONSENT + reload)
"""

import os
import json
import time
import logging
import asyncio
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

import httpx
from playwright.async_api import async_playwright, Page as AsyncPage

from logging_setup import get_logger, set_job_ctx, get_job_ctx
from log_events import evt
from storage_state_manager import get_storage_state_manager
from reliability_config import get_reliability_config

logger = get_logger(__name__)

# Get reliability configuration
_config = get_reliability_config()

# Configuration
YOUTUBEI_TIMEOUT = 25  # seconds for route interception
TRANSCRIPT_PANEL_WAIT = 12  # seconds to wait for transcript panel to load
CONSENT_DETECTION_TIMEOUT = 5  # seconds to check for consent wall
TRANSCRIPT_PANEL_SELECTOR = 'ytd-transcript-search-panel-renderer'

# Deterministic selectors for reliable DOM interaction (Requirement 1.4)
TITLE_ROW_MENU = "ytd-menu-renderer #button-shape button[aria-label*='More actions']"
SHOW_TRANSCRIPT_ITEM = "tp-yt-paper-listbox [role='menuitem']:has-text('Show transcript')"


class DeterministicYouTubeiCapture:
    """
    Deterministic YouTubei transcript capture with guaranteed storage state and consent handling.
    """
    
    def __init__(self, job_id: str, video_id: str, proxy_manager=None):
        """
        Initialize YouTubei capture service.
        
        Args:
            job_id: Job identifier for sticky proxy session
            video_id: YouTube video ID
            proxy_manager: ProxyManager instance
        """
        self.job_id = job_id
        self.video_id = video_id
        self.proxy_manager = proxy_manager
        self.transcript_future = None
        self.page = None
        self.consent_detected = False
        self.transcript_button_clicked = False
        self.route_fired = False
        self.direct_post_used = False
        
        # Get storage state manager
        self.storage_manager = get_storage_state_manager()
    
    async def extract_transcript(self, cookies: Optional[str] = None) -> str:
        """
        Extract transcript using deterministic YouTubei capture.
        
        Args:
            cookies: Cookie header string (optional)
            
        Returns:
            Transcript text if successful, empty string otherwise
        """
        # Set job context
        set_job_ctx(job_id=self.job_id, video_id=self.video_id)
        
        # Determine metrics tags for filtering by root cause (Requirements 7.4, 13.1, 13.2)
        cookie_source = "user" if cookies else "env"
        proxy_mode = "on" if (self.proxy_manager and self.proxy_manager.in_use) else "off"
        
        # Log start with metrics tags for filtering by root cause
        evt("youtubei_extraction_start",
            video_id=self.video_id,
            job_id=self.job_id,
            cookie_source=cookie_source,
            proxy_mode=proxy_mode)
        
        # Ensure storage state is available
        if not self.storage_manager.ensure_storage_state_available():
            evt("youtubei_storage_state_unavailable", 
                video_id=self.video_id, job_id=self.job_id)
            raise RuntimeError("Storage state unavailable - cannot proceed with YouTubei")
        
        # Get job-scoped proxy configuration
        proxy_dict = None
        if self.proxy_manager and self.proxy_manager.in_use:
            try:
                proxy_dict = self.proxy_manager.proxy_dict_for_job(self.job_id, "playwright")
            except Exception as e:
                evt("youtubei_proxy_setup_error", error=str(e), job_id=self.job_id)
                # Check proxy enforcement from centralized config
                if _config.enforce_proxy_all:
                    return ""
        
        async with async_playwright() as p:
            browser = None
            context = None
            page = None
            
            try:
                # Launch browser
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"]
                )
                
                # Create context with guaranteed storage state
                context_args = self.storage_manager.create_playwright_context_args(
                    proxy_dict=proxy_dict, profile="desktop"
                )
                context = await browser.new_context(**context_args)
                
                # Log context opened and increment active count
                evt("playwright_context_opened", 
                    video_id=self.video_id, 
                    job_id=self.job_id,
                    context_id=id(context))
                
                # Create page and setup route interception BEFORE navigation
                page = await context.new_page()
                self.page = page
                
                # Setup route interception for transcript capture BEFORE DOM interactions (Requirement 5.1)
                evt("youtubei_route_setup_start",
                    video_id=self.video_id,
                    job_id=self.job_id)
                await self._setup_route_interception()
                
                # Navigate to video page with networkidle wait for better metadata loading
                url = f"https://www.youtube.com/watch?v={self.video_id}&hl=en"
                try:
                    await page.goto(url, wait_until="networkidle", timeout=60000)
                except Exception:
                    # Proxy paths sometimes never reach 'networkidle'; fall back quickly.
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                
                evt("youtubei_navigation_complete", 
                    video_id=self.video_id, job_id=self.job_id, url=url)
                
                # Fast-path caption extraction from ytInitialPlayerResponse (Requirements 1.2, 1.3)
                fast_path_result = await self._extract_captions_from_player_response(cookies)
                if fast_path_result:
                    evt("youtubei_captiontracks_shortcircuit",
                        video_id=self.video_id,
                        job_id=self.job_id,
                        cookie_source=cookie_source,
                        proxy_mode=proxy_mode,
                        content_length=len(fast_path_result))
                    return fast_path_result
                
                # DOM interaction sequence AFTER route interception setup
                evt("youtubei_dom_sequence_start",
                    video_id=self.video_id,
                    job_id=self.job_id)
                
                # Graceful degradation: DOM helper methods never throw exceptions (Requirements 9.1, 9.2, 9.4)
                try:
                    await self._try_consent()
                    expanded = await self._expand_description()
                    if expanded: evt("youtubei_dom_expanded_description")
                    
                    # Use enhanced transcript panel opening with multiple strategies
                    opened = await self.open_transcript_panel_enhanced()
                    if opened: 
                        evt("youtubei_dom_clicked_transcript", method="enhanced")
                        self.transcript_button_clicked = True
                    else:
                        # Fallback: scroll and retry once if transcript button not found
                        evt("youtubei_dom_scroll_retry",
                            video_id=self.video_id,
                            job_id=self.job_id,
                            reason="enhanced_strategies_failed")
                        
                        try:
                            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                            await page.wait_for_timeout(1000)
                            
                            # Retry with enhanced strategies after scroll
                            opened = await self.open_transcript_panel_enhanced()
                            if not opened:
                                evt("youtubei_dom_transcript_retry_failed",
                                    video_id=self.video_id,
                                    job_id=self.job_id)
                                # Return empty string for fallback to next transcript method (Requirement 9.5)
                                return ""
                        except Exception as scroll_error:
                            # Graceful degradation: scroll failure should not break the pipeline
                            evt("youtubei_dom_scroll_failed",
                                video_id=self.video_id,
                                job_id=self.job_id,
                                error=str(scroll_error)[:100])
                            # Return empty string for fallback to next transcript method (Requirement 9.5)
                            return ""
                            
                except Exception as dom_error:
                    # Graceful degradation: DOM interaction failures should not break the pipeline (Requirement 9.4)
                    evt("youtubei_dom_sequence_failed",
                        video_id=self.video_id,
                        job_id=self.job_id,
                        error_type=type(dom_error).__name__,
                        error=str(dom_error)[:100])
                    
                    # Requirement 7.5: Add warning logs for failures without verbose dumps or stack traces
                    logger.warning("youtubei_dom: DOM interaction sequence failed")
                    
                    # Return empty string for fallback to next transcript method (Requirement 9.5)
                    return ""
                
                # Wait for the transcript side panel to appear (proves the click really worked)
                try:
                    await page.wait_for_selector(TRANSCRIPT_PANEL_SELECTOR, timeout=TRANSCRIPT_PANEL_WAIT * 1000)
                    evt("youtubei_transcript_panel_opened")
                except Exception:
                    evt("youtubei_transcript_panel_not_opened")
                    # Keep going; route may still have fired

                # Wait for transcript capture with enhanced timeout and cleanup
                transcript_data = await self._wait_for_transcript_with_fallback(cookies)
                
                if transcript_data:
                    # Parse and return transcript
                    result = self._parse_transcript_data(transcript_data)
                    
                    # Log successful end with metrics tags for filtering by root cause
                    evt("youtubei_extraction_success",
                        video_id=self.video_id,
                        job_id=self.job_id,
                        cookie_source=cookie_source,
                        proxy_mode=proxy_mode,
                        content_length=len(result) if result else 0)
                    
                    return result
                else:
                    # Log failed end with metrics tags for filtering by root cause
                    evt("youtubei_extraction_failed",
                        video_id=self.video_id,
                        job_id=self.job_id,
                        cookie_source=cookie_source,
                        proxy_mode=proxy_mode,
                        reason="no_transcript_data")
                    
                    return ""
                    
            except Exception as e:
                # Log error end with metrics tags for filtering by root cause
                evt("youtubei_extraction_error",
                    video_id=self.video_id,
                    job_id=self.job_id,
                    cookie_source=cookie_source,
                    proxy_mode=proxy_mode,
                    error_type=type(e).__name__,
                    error_detail=str(e)[:200])
                
                # Requirement 7.5: Add warning logs for failures without verbose dumps or stack traces
                logger.warning(f"youtubei_extraction_error: {type(e).__name__}")
                
                return ""
                
            finally:
                # Log final state
                evt("youtubei_final_state",
                    video_id=self.video_id,
                    job_id=self.job_id,
                    consent_detected=self.consent_detected,
                    transcript_button_clicked=self.transcript_button_clicked,
                    route_fired=self.route_fired,
                    direct_post_used=self.direct_post_used)
                
                # Clean up resources with logging
                if page:
                    await page.close()
                if context:
                    evt("playwright_context_closed", 
                        video_id=self.video_id, 
                        job_id=self.job_id,
                        context_id=id(context))
                    await context.close()
                if browser:
                    await browser.close()
    
    async def _extract_captions_from_player_response(self, cookies: Optional[str] = None) -> Optional[str]:
        """
        Extract captions directly from ytInitialPlayerResponse without DOM interaction.
        
        Implements Requirements 1.2, 1.3:
        - Extract captionTracks from page JavaScript immediately after page load
        - Prefer non-ASR English, fallback to first available
        - Log youtubei_captiontracks_shortcircuit with language and ASR flags
        
        Args:
            cookies: Optional cookie header string for authentication
        
        Returns:
            Transcript text if successful, None otherwise
        """
        try:
            evt("youtubei_captiontracks_probe_start",
                video_id=self.video_id,
                job_id=self.job_id)
            
            # Extract caption tracks from ytInitialPlayerResponse
            tracks_data = await self.page.evaluate("""
                () => {
                    try {
                        const pr = window.ytInitialPlayerResponse || {};
                        const captions = pr.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];
                        return captions.map(track => ({
                            baseUrl: track.baseUrl || '',
                            kind: track.kind || '',
                            languageCode: track.languageCode || '',
                            name: (track.name && track.name.simpleText) || '',
                            isTranslatable: track.isTranslatable || false
                        }));
                    } catch (e) {
                        console.error('Caption tracks extraction error:', e);
                        return [];
                    }
                }
            """)
            
            if not tracks_data or len(tracks_data) == 0:
                evt("youtubei_captiontracks_none_found",
                    video_id=self.video_id,
                    job_id=self.job_id)
                return None
            
            evt("youtubei_captiontracks_found",
                video_id=self.video_id,
                job_id=self.job_id,
                tracks_count=len(tracks_data))
            
            # Select best caption track (prefer non-ASR English, fallback to first available)
            best_track = self._select_best_caption_track(tracks_data)
            if not best_track or not best_track.get('baseUrl'):
                evt("youtubei_captiontracks_no_suitable",
                    video_id=self.video_id,
                    job_id=self.job_id)
                return None
            
            # Determine if track is ASR (auto-generated)
            is_asr = best_track.get('kind', '').lower() == 'asr'
            lang = best_track.get('languageCode', 'unknown')
            
            evt("youtubei_captiontracks_selected",
                video_id=self.video_id,
                job_id=self.job_id,
                lang=lang,
                asr=is_asr,
                track_name=best_track.get('name', ''))
            
            # Fetch transcript XML via HTTP requests with cookies
            transcript_result = await self._fetch_transcript_xml_via_requests(best_track['baseUrl'], cookies)
            
            if transcript_result:
                # Log successful shortcircuit with required fields (Requirement 1.3)
                evt("youtubei_captiontracks_shortcircuit",
                    video_id=self.video_id,
                    job_id=self.job_id,
                    lang=lang,
                    asr=is_asr)
                return transcript_result
            else:
                evt("youtubei_captiontracks_fetch_failed",
                    video_id=self.video_id,
                    job_id=self.job_id,
                    lang=lang,
                    asr=is_asr)
                return None
                
        except Exception as e:
            evt("youtubei_captiontracks_probe_failed",
                video_id=self.video_id,
                job_id=self.job_id,
                err=str(e)[:120])
            return None
    
    def _select_best_caption_track(self, tracks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Select the best caption track from available tracks.
        
        Priority:
        1. Non-ASR English tracks
        2. ASR English tracks  
        3. First available track
        
        Args:
            tracks: List of caption track dictionaries
            
        Returns:
            Best track dictionary or None
        """
        if not tracks:
            return None
        
        # Filter English tracks
        english_tracks = [t for t in tracks if t.get('languageCode', '').startswith('en')]
        
        # Prefer non-ASR English tracks
        non_asr_english = [t for t in english_tracks if t.get('kind', '').lower() != 'asr']
        if non_asr_english:
            return non_asr_english[0]
        
        # Fallback to ASR English tracks
        if english_tracks:
            return english_tracks[0]
        
        # Last resort: first available track
        return tracks[0]

    async def _fetch_transcript_xml_via_requests(self, base_url: str, cookies: Optional[str] = None) -> Optional[str]:
        """
        Fetch transcript XML via HTTP requests with proxy support.
        
        Implements Requirements 1.6:
        - Respect ENFORCE_PROXY_ALL environment variable for proxy enforcement
        - Add proper error handling and logging for HTTP failures
        - Use job-specific proxy configuration
        
        Args:
            base_url: Caption track base URL
            cookies: Optional cookie header string for authentication
            
        Returns:
            Transcript XML content if successful, None otherwise
        """
        try:
            evt("youtubei_http_fetch_start",
                video_id=self.video_id,
                job_id=self.job_id,
                url=base_url[:100])  # Truncate URL for logging
            
            # Check proxy enforcement from centralized config
            enforce_proxy = _config.enforce_proxy_all
            
            # Get job-scoped proxy configuration
            proxy_dict = None
            if self.proxy_manager and self.proxy_manager.in_use:
                try:
                    proxy_dict = self.proxy_manager.proxy_dict_for_job(self.job_id, "requests")
                except Exception as e:
                    evt("youtubei_http_proxy_error",
                        video_id=self.video_id,
                        job_id=self.job_id,
                        error=str(e)[:100])
                    if enforce_proxy:
                        evt("youtubei_http_proxy_enforced_block",
                            video_id=self.video_id,
                            job_id=self.job_id)
                        return None
            
            # Block execution if proxy enforcement is enabled but no proxy available
            if enforce_proxy and not proxy_dict:
                evt("youtubei_http_proxy_enforced_block",
                    video_id=self.video_id,
                    job_id=self.job_id,
                    reason="no_proxy_available")
                return None
            
            # Prepare request configuration
            timeout = httpx.Timeout(30.0)  # 30 second timeout
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            # Add cookies if provided
            if cookies:
                headers['Cookie'] = cookies
                evt("youtubei_http_cookies_added",
                    video_id=self.video_id,
                    job_id=self.job_id,
                    cookie_count=len(cookies.split(';')) if cookies else 0)
            
            # Make HTTP request with optional proxy
            async with httpx.AsyncClient(
                proxies=proxy_dict,
                timeout=timeout,
                headers=headers,
                follow_redirects=True
            ) as client:
                response = await client.get(base_url)
                response.raise_for_status()
                
                xml_content = response.text
                
                # Basic validation - ensure we got XML content
                if not xml_content.strip().startswith('<'):
                    evt("youtubei_http_fetch_not_xml",
                        video_id=self.video_id,
                        job_id=self.job_id,
                        content_preview=xml_content[:100])
                    return None
                
                evt("youtubei_http_fetch_success",
                    video_id=self.video_id,
                    job_id=self.job_id,
                    content_length=len(xml_content),
                    status_code=response.status_code)
                
                # Convert XML to JSON format for compatibility with existing pipeline
                return self._convert_xml_to_json_format(xml_content)
                
        except httpx.TimeoutException:
            evt("youtubei_http_fetch_timeout",
                video_id=self.video_id,
                job_id=self.job_id)
            return None
        except httpx.HTTPStatusError as e:
            evt("youtubei_http_fetch_http_error",
                video_id=self.video_id,
                job_id=self.job_id,
                status_code=e.response.status_code,
                error=str(e)[:100])
            return None
        except Exception as e:
            evt("youtubei_http_fetch_error",
                video_id=self.video_id,
                job_id=self.job_id,
                error_type=type(e).__name__,
                error=str(e)[:100])
            return None
    
    def _convert_xml_to_json_format(self, xml_content: str) -> str:
        """
        Convert XML transcript content to JSON format compatible with existing pipeline.
        
        Args:
            xml_content: Raw XML transcript content
            
        Returns:
            JSON-formatted transcript data
        """
        try:
            # Import validation function from transcript_service
            from transcript_service import _validate_and_parse_xml
            
            # Create a mock response object for validation
            class MockResponse:
                def __init__(self, text):
                    self.text = text
            
            # Parse XML with validation
            root = _validate_and_parse_xml(MockResponse(xml_content), "youtubei_transcript")
            
            # Extract transcript segments
            segments = []
            for text_elem in root.findall('.//text'):
                start_time = float(text_elem.get('start', '0'))
                duration = float(text_elem.get('dur', '0'))
                text_content = text_elem.text or ''
                
                # Clean up text content
                text_content = text_content.strip()
                if text_content:
                    segments.append({
                        'text': text_content,
                        'start': start_time,
                        'duration': duration
                    })
            
            # Convert to YouTubei-compatible JSON format
            json_data = {
                "actions": [{
                    "updateEngagementPanelAction": {
                        "content": {
                            "transcriptRenderer": {
                                "body": {
                                    "transcriptBodyRenderer": {
                                        "cueGroups": []
                                    }
                                }
                            }
                        }
                    }
                }]
            }
            
            # Convert segments to cue groups
            cue_groups = []
            for segment in segments:
                cue_group = {
                    "transcriptCueGroupRenderer": {
                        "cues": [{
                            "transcriptCueRenderer": {
                                "cue": {
                                    "simpleText": segment["text"]
                                },
                                "startOffsetMs": str(int(segment["start"] * 1000)),
                                "durationMs": str(int(segment["duration"] * 1000))
                            }
                        }]
                    }
                }
                cue_groups.append(cue_group)
            
            json_data["actions"][0]["updateEngagementPanelAction"]["content"]["transcriptRenderer"]["body"]["transcriptBodyRenderer"]["cueGroups"] = cue_groups
            
            return json.dumps(json_data)
            
        except Exception as e:
            evt("youtubei_xml_conversion_error",
                video_id=self.video_id,
                job_id=self.job_id,
                error=str(e)[:100])
            # Return raw XML as fallback
            return xml_content

    async def _setup_route_interception(self):
        """
        Setup route interception for /youtubei/v1/get_transcript BEFORE DOM interactions.
        
        Implements Requirements 5.1, 5.2, 5.3:
        - Future-based route capture with (url, body) result handling
        - Route interception setup before DOM interactions
        - Proper error handling and logging
        """
        # Initialize Future for route capture (Requirement 5.1)
        self.transcript_future = asyncio.Future()
        
        async def handle_transcript_route(route):
            # IMPORTANT: never stall the page; always fulfill or continue after fetch.
            try:
                response = await route.fetch()
                url = route.request.url
                if "/youtubei/v1/get_transcript" in url:
                    self.route_fired = True
                    if response.status != 200:
                        evt("youtubei_direct_fetch_failed", video_id=self.video_id, job_id=self.job_id, status=response.status, url=url)
                        if not self.transcript_future.done():
                            self.transcript_future.set_result(None)
                    else:
                        body = await response.body()
                        if body and not self.transcript_future.done():
                            text_content = body.decode('utf-8', errors='ignore')
                            self.transcript_future.set_result((url, text_content))
                # Release request so panel can load
                try:
                    await route.fulfill(response=response)
                except Exception:
                    try:
                        await route.continue_()
                    except Exception:
                        pass
            except Exception as e:
                if not self.transcript_future.done():
                    self.transcript_future.set_exception(e)
        
        # Set up route interception BEFORE DOM interactions (Requirement 5.1)
        await self.page.route("**/youtubei/v1/get_transcript*", handle_transcript_route)
        
        evt("youtubei_route_setup",
            video_id=self.video_id,
            job_id=self.job_id,
            timeout_seconds=YOUTUBEI_TIMEOUT,
            pattern="**/youtubei/v1/get_transcript*")
    
    async def _try_consent(self) -> None:
        """
        Handle common consent dialogs if present using resilient selectors.
        
        Implements graceful degradation - never throws exceptions that break the transcript pipeline.
        Skips consent handling gracefully when no consent dialog is present.
        
        Requirements: 2.1, 2.2, 2.3, 9.2, 9.4, 14.4
        """
        consent_selectors = [
            'button:has-text("Accept all")',
            'button:has-text("I agree")',
            'button[aria-label*="accept" i]',
            'tp-yt-paper-button:has-text("Accept")',
            'button:has-text("Acepto todo")',
            'button:has-text("Estoy de acuerdo")',
            '[role="button"]:has-text("Accept")',
            '[role="button"]:has-text("I agree")'
        ]
        
        try:
            # Graceful degradation: ensure page is available before attempting consent handling
            if not self.page:
                evt("youtubei_dom_consent_no_page",
                    video_id=self.video_id,
                    job_id=self.job_id)
                return
            
            for selector in consent_selectors:
                try:
                    element = self.page.locator(selector).first
                    await element.wait_for(state="visible", timeout=2000)
                    await element.click(timeout=5000)
                    await self.page.wait_for_timeout(1000)  # Wait for dialog dismissal
                    
                    evt("youtubei_dom_consent_handled",
                        video_id=self.video_id,
                        job_id=self.job_id,
                        selector=selector)
                    return
                except Exception as selector_error:
                    # Graceful degradation: log individual selector failures but continue
                    evt("youtubei_dom_consent_selector_failed",
                        video_id=self.video_id,
                        job_id=self.job_id,
                        selector=selector,
                        error=str(selector_error)[:100])
                    continue  # Try next selector
            
            # No consent dialog found - continue without error (Requirement 9.2)
            evt("youtubei_dom_no_consent",
                video_id=self.video_id,
                job_id=self.job_id)
                
        except Exception as e:
            # Graceful degradation: never throw exceptions that break the transcript pipeline (Requirement 9.4)
            # Requirement 7.5: Add warning logs for failures without verbose dumps or stack traces
            logger.warning("youtubei_dom: consent handling failed")
            
            # Log failure but continue - consent handling should not block transcript extraction
            evt("youtubei_dom_consent_failed",
                video_id=self.video_id,
                job_id=self.job_id,
                error=str(e)[:100])
            
            # Graceful degradation: always return without raising exceptions

    async def _expand_description(self) -> bool:
        """
        Expand collapsed description using hierarchical selectors with enhanced robustness.
        
        Implements graceful degradation - never throws exceptions that break the transcript pipeline.
        Skips description expansion gracefully when expander is not found.
        
        Requirements: 3.1, 3.2, 3.3, 7.1, 9.1, 9.4, 14.4
        
        Returns:
            True if description was expanded, False otherwise
        """
        # Wait for metadata to load and scroll into view first
        try:
            await self.page.wait_for_selector('ytd-watch-metadata', timeout=15000)
            
            # Ensure description is in viewport
            await self.page.evaluate("""
              const md = document.querySelector('ytd-watch-metadata');
              if (md) md.scrollIntoView({behavior:'instant', block:'start'});
            """)
            await self.page.wait_for_timeout(500)
        except Exception as metadata_error:
            evt("youtubei_dom_metadata_wait_failed",
                video_id=self.video_id,
                job_id=self.job_id,
                error=str(metadata_error)[:100])
        
        # Enhanced expansion selectors with more variants
        expansion_selectors = [
            'ytd-text-inline-expander tp-yt-paper-button',                  # classic
            'ytd-watch-metadata tp-yt-paper-button#expand',                 # id-based
            'button[aria-label="Show more"]',                               # aria
            'tp-yt-paper-button:has-text("more")',                          # lowercase label
            'tp-yt-paper-button:has-text("More")',                          # capitalized label
            'ytd-text-inline-expander tp-yt-paper-button.more-button',      # Primary YouTube component
            'button[aria-label*="more"]'                                    # Accessibility fallback
        ]
        
        try:
            # Graceful degradation: ensure page is available before attempting description expansion
            if not self.page:
                evt("youtubei_dom_expansion_no_page",
                    video_id=self.video_id,
                    job_id=self.job_id)
                return
            
            for selector in expansion_selectors:
                try:
                    element = self.page.locator(selector).first
                    await element.wait_for(state="visible", timeout=3000)
                    await element.click(timeout=5000)
                    await self.page.wait_for_timeout(300)  # Wait for expansion
                    
                    # Requirement 7.1: Log "youtubei_dom: expanded description via [selector]" when description expansion succeeds
                    logger.info(f"youtubei_dom: expanded description via [{selector}]")
                    
                    evt("youtubei_dom_expanded_description",
                        video_id=self.video_id,
                        job_id=self.job_id,
                        selector=selector)
                    return True
                except Exception as selector_error:
                    # Graceful degradation: log individual selector failures but continue
                    evt("youtubei_dom_expansion_selector_failed",
                        video_id=self.video_id,
                        job_id=self.job_id,
                        selector=selector,
                        error=str(selector_error)[:100])
                    continue  # Try next selector
            
            # No expander found - description may already be expanded or not present (Requirement 9.1)
            evt("youtubei_dom_no_expander",
                video_id=self.video_id,
                job_id=self.job_id)
            return False
                
        except Exception as e:
            # Graceful degradation: never throw exceptions that break the transcript pipeline (Requirement 9.4)
            # Requirement 7.5: Add warning logs for failures without verbose dumps or stack traces
            logger.warning("youtubei_dom: description expansion failed")
            evt("youtubei_dom_expansion_failed",
                video_id=self.video_id,
                job_id=self.job_id,
                error=str(e)[:100])
            
            # Graceful degradation: always return without raising exceptions
            return False

    async def _open_transcript(self) -> bool:
        """
        Click 'Show transcript' button using robust selectors with panel confirmation and overflow menu fallback.
        
        Implements graceful degradation - never throws exceptions that break the transcript pipeline.
        Returns False when transcript button is not found to allow retry logic.
        
        Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 7.2, 9.3, 9.4, 14.4
        """
        # Primary transcript button selectors
        transcript_selectors = [
            'button:has-text("Show transcript")',                       # Primary direct button
            'tp-yt-paper-button:has-text("Show transcript")',           # YouTube paper button
            'tp-yt-paper-item:has-text("Show transcript")',             # Overflow menu variant
            'yt-button-shape:has-text("Transcript")',                   # New YouTube button format
            'button[aria-label*="transcript" i]',                       # Accessibility (case-insensitive)
            'tp-yt-paper-button[aria-label*="transcript" i]',          # YouTube accessibility
            'ytd-transcript-search-panel-renderer tp-yt-paper-button'   # Deep fallback
        ]
        
        try:
            # Graceful degradation: ensure page is available before attempting transcript button discovery
            if not self.page:
                evt("youtubei_dom_transcript_no_page",
                    video_id=self.video_id,
                    job_id=self.job_id)
                return False
            
            # Try direct transcript button selectors first
            for selector in transcript_selectors:
                try:
                    element = self.page.locator(selector).first
                    await element.wait_for(state="visible", timeout=3000)
                    await element.click(timeout=5000)
                    self.transcript_button_clicked = True
                    
                    # Wait for transcript panel to appear (panel-open confirmation)
                    try:
                        await self.page.wait_for_selector(
                            'ytd-transcript-search-panel-renderer',
                            timeout=7000,
                            state='visible'
                        )
                        evt("youtubei_transcript_panel_opened")
                        
                        # Requirement 7.2: Log "youtubei_dom: clicked transcript launcher ([selector])" when transcript button is clicked
                        logger.info(f"youtubei_dom: clicked transcript launcher ([{selector}])")
                        
                        evt("youtubei_dom_transcript_opened",
                            video_id=self.video_id,
                            job_id=self.job_id,
                            selector=selector)
                        return True
                        
                    except Exception as panel_error:
                        # Panel didn't appear, log and try next selector
                        evt("youtubei_dom_transcript_panel_failed",
                            video_id=self.video_id,
                            job_id=self.job_id,
                            selector=selector,
                            error=str(panel_error)[:100])
                        continue
                        
                except Exception as selector_error:
                    # Graceful degradation: log individual selector failures but continue
                    evt("youtubei_dom_transcript_selector_failed",
                        video_id=self.video_id,
                        job_id=self.job_id,
                        selector=selector,
                        error=str(selector_error)[:100])
                    continue  # Try next selector
            
            # Fallback: Try overflow menu (three dots) → Show transcript
            evt("youtubei_dom_overflow_menu_fallback",
                video_id=self.video_id,
                job_id=self.job_id)
            
            # Ensure actions area is visible; this often reveals the kebab
            try:
                await self.page.locator('ytd-watch-metadata, #actions, #menu').first.scroll_into_view_if_needed()
                await self.page.wait_for_timeout(350)
            except Exception:
                pass
            
            try:
                # Click "More actions" button (three dots)
                more_actions_selectors = [
                    'button[aria-label="More actions"]',
                    'button[aria-label*="More"]',
                    'tp-yt-paper-button[aria-label="More actions"]',
                    'yt-button-shape[aria-label="More actions"]'
                ]
                
                more_actions_clicked = False
                for more_selector in more_actions_selectors:
                    try:
                        more_element = self.page.locator(more_selector).first
                        await more_element.wait_for(state="visible", timeout=2000)
                        await more_element.scroll_into_view_if_needed()
                        await self.page.wait_for_timeout(150)
                        await more_element.click(timeout=3000)
                        await self.page.wait_for_timeout(200)  # Wait for menu to appear
                        more_actions_clicked = True
                        
                        evt("youtubei_dom_more_actions_clicked",
                            video_id=self.video_id,
                            job_id=self.job_id,
                            selector=more_selector)
                        break
                    except Exception as wait_error:
                        # Add error logging for wait failures to identify selector issues
                        evt("youtubei_dom_more_actions_wait_failed",
                            video_id=self.video_id,
                            job_id=self.job_id,
                            selector=more_selector,
                            error=str(wait_error)[:100])
                        continue
                
                if more_actions_clicked:
                    # Try to click "Show transcript" from overflow menu
                    overflow_transcript_selectors = [
                        'tp-yt-paper-item:has-text("Show transcript")',
                        'ytd-menu-service-item-renderer:has-text("Show transcript")',
                        '[role="menuitem"]:has-text("Show transcript")',
                        'yt-formatted-string:has-text("Show transcript")'
                    ]
                    
                    for overflow_selector in overflow_transcript_selectors:
                        try:
                            overflow_element = self.page.locator(overflow_selector).first
                            await overflow_element.wait_for(state="visible", timeout=2000)
                            await overflow_element.click(timeout=3000)
                            self.transcript_button_clicked = True
                            
                            # Wait for transcript panel to appear
                            try:
                                await self.page.wait_for_selector(
                                    'ytd-transcript-search-panel-renderer',
                                    timeout=7000,
                                    state='visible'
                                )
                                evt("youtubei_transcript_panel_opened")
                                
                                logger.info(f"youtubei_dom: clicked transcript launcher via overflow menu ([{overflow_selector}])")
                                
                                evt("youtubei_dom_transcript_opened_overflow",
                                    video_id=self.video_id,
                                    job_id=self.job_id,
                                    selector=overflow_selector)
                                return True
                                
                            except Exception as overflow_panel_error:
                                evt("youtubei_dom_overflow_panel_failed",
                                    video_id=self.video_id,
                                    job_id=self.job_id,
                                    selector=overflow_selector,
                                    error=str(overflow_panel_error)[:100])
                                continue
                                
                        except Exception as overflow_error:
                            # Add error logging for wait failures to identify selector issues
                            evt("youtubei_dom_overflow_selector_failed",
                                video_id=self.video_id,
                                job_id=self.job_id,
                                selector=overflow_selector,
                                error=str(overflow_error)[:100])
                            continue
                            
            except Exception as overflow_menu_error:
                evt("youtubei_dom_overflow_menu_error",
                    video_id=self.video_id,
                    job_id=self.job_id,
                    error=str(overflow_menu_error)[:100])
            
            # No transcript button found anywhere (Requirement 9.3)
            # Requirement 7.5: Add warning logs for failures without verbose dumps or stack traces
            logger.warning("youtubei_dom: transcript button not found")
            evt("youtubei_dom_transcript_not_found",
                video_id=self.video_id,
                job_id=self.job_id)
            return False
            
        except Exception as e:
            # Graceful degradation: never throw exceptions that break the transcript pipeline (Requirement 9.4)
            # Requirement 7.5: Add warning logs for failures without verbose dumps or stack traces
            logger.warning("youtubei_dom: transcript button click failed")
            evt("youtubei_dom_transcript_failed",
                video_id=self.video_id,
                job_id=self.job_id,
                error=str(e)[:100])
            return False

    async def open_transcript_panel_enhanced(self):
        """Multiple strategies to open transcript panel with better error handling"""
        
        strategies = [
            # Strategy 1: Direct transcript button click (new YouTube layout)
            lambda: self.page.click('button[aria-label*="transcript" i], button[aria-label*="Transcript" i]', timeout=5000),
            
            # Strategy 2: More actions menu → Show transcript
            lambda: self._open_via_more_actions(),
            
            # Strategy 3: Keyboard shortcuts
            lambda: self.page.keyboard.press("Shift+."),  # YouTube transcript shortcut
            
            # Strategy 4: JavaScript injection as last resort
            lambda: self.page.evaluate("""() => {
                const buttons = Array.from(document.querySelectorAll('button, [role="button"]'));
                const transcriptBtn = buttons.find(btn => 
                    btn.textContent && btn.textContent.match(/show transcript|transcript/i)
                );
                if (transcriptBtn) {
                    transcriptBtn.click();
                    return true;
                }
                return false;
            }""")
        ]
        
        for i, strategy in enumerate(strategies):
            try:
                result = await strategy()
                if result is not False:  # Allow strategies to return false to continue
                    return True
            except Exception as e:
                if i == len(strategies) - 1:  # Last strategy
                    raise e
                continue
        
        return False

    async def _open_via_more_actions(self):
        """Open transcript via More Actions menu with robust selectors"""
        more_actions_selectors = [
            'button[aria-label*="More actions" i]',
            'button[aria-label*="More" i]',
            'yt-button-shape[aria-label*="More" i]',
            'tp-yt-paper-button[aria-label*="More" i]',
            '#button-shape button[aria-haspopup="menu"]'
        ]
        
        for selector in more_actions_selectors:
            try:
                await self.page.click(selector, timeout=3000)
                await self.page.wait_for_timeout(1000)
                
                # Look for transcript option in the menu
                transcript_options = [
                    'div[role="menu"] [role="menuitem"]:has-text("Show transcript")',
                    'div[role="menu"] [role="menuitem"]:has-text("Transcript")',
                    'ytd-menu-popup-renderer [role="menuitem"]:has-text("transcript" i)'
                ]
                
                for option_selector in transcript_options:
                    try:
                        await self.page.click(option_selector, timeout=2000)
                        return True
                    except:
                        continue
                        
            except Exception:
                continue
        
        return False

    async def _open_transcript_via_title_menu(self) -> bool:
        """
        Open transcript panel using deterministic title-row menu.

        Implements Requirement 1.4:
        - Use title-row menu selector ytd-menu-renderer #button-shape button[aria-label*='More actions']
        - Confirm dropdown [opened] state before clicking transcript option
        - Add dropdown state verification before clicking transcript option

        Returns:
            True if transcript panel opened successfully, False otherwise
        """
        try:
            # Graceful degradation: ensure page is available
            if not self.page:
                evt("youtubei_title_menu_no_page",
                    video_id=self.video_id,
                    job_id=self.job_id)
                return False
            
            evt("youtubei_title_menu_attempt",
                video_id=self.video_id,
                job_id=self.job_id)
            
            # Wait for menu button to be visible using deterministic selector
            btn = self.page.locator(TITLE_ROW_MENU).first
            await btn.wait_for(state="visible", timeout=5000)
            await btn.click(timeout=5000)
            
            evt("youtubei_title_menu_clicked",
                video_id=self.video_id,
                job_id=self.job_id)
            
            # Wait for dropdown to open and verify [opened] state
            await self.page.wait_for_selector("tp-yt-iron-dropdown[opened] tp-yt-paper-listbox", timeout=5000)
            
            evt("youtubei_title_menu_dropdown_opened",
                video_id=self.video_id,
                job_id=self.job_id)
            
            # Click transcript item using deterministic selector
            item = self.page.locator(SHOW_TRANSCRIPT_ITEM).first
            await item.wait_for(state="visible", timeout=5000)
            await item.click(timeout=5000)
            
            # Mark transcript button as clicked
            self.transcript_button_clicked = True
            
            # Wait for transcript panel to appear to confirm success
            try:
                await self.page.wait_for_selector(
                    TRANSCRIPT_PANEL_SELECTOR,
                    timeout=TRANSCRIPT_PANEL_WAIT * 1000,
                    state='visible'
                )
                
                evt("youtubei_title_menu_success",
                    video_id=self.video_id,
                    job_id=self.job_id)
                
                logger.info("youtubei_dom: clicked transcript launcher via title menu")
                
                return True
                
            except Exception as panel_error:
                evt("youtubei_title_menu_panel_failed",
                    video_id=self.video_id,
                    job_id=self.job_id,
                    error=str(panel_error)[:100])
                return False
                
        except Exception as e:
            evt("youtubei_title_menu_open_failed", 
                video_id=self.video_id,
                job_id=self.job_id,
                err=str(e)[:120])
            return False

    async def _handle_consent_wall_if_detected(self):
        """Check for and handle consent wall if detected"""
        try:
            # Check for consent wall indicators
            consent_indicators = [
                "Before you continue to YouTube",
                "Accept all",
                "I agree",
                "Acepto todo"
            ]
            
            page_content = await self.page.content()
            page_title = await self.page.title()
            
            # Check if consent wall is present
            consent_wall_detected = any(
                indicator in page_content for indicator in consent_indicators
            )
            
            if consent_wall_detected:
                self.consent_detected = True
                evt("youtubei_consent_detected",
                    video_id=self.video_id,
                    job_id=self.job_id,
                    page_title=page_title)
                
                # Re-inject SOCS/CONSENT cookies and reload
                await self._reinject_consent_cookies_and_reload()
            else:
                evt("youtubei_no_consent_wall",
                    video_id=self.video_id,
                    job_id=self.job_id,
                    page_title=page_title)
                
        except Exception as e:
            evt("youtubei_consent_check_error",
                video_id=self.video_id,
                job_id=self.job_id,
                error=str(e))
    
    async def _reinject_consent_cookies_and_reload(self):
        """Re-inject SOCS/CONSENT cookies and reload page"""
        try:
            # Add fresh consent cookies
            consent_cookies = [
                {
                    "name": "SOCS",
                    "value": "CAESEwgDEgk0ODE3Nzk3MjQaAmVuIAEaBgiA_LyaBg",
                    "domain": ".youtube.com",
                    "path": "/",
                    "secure": True,
                    "httpOnly": False,
                    "sameSite": "None"
                },
                {
                    "name": "CONSENT",
                    "value": "YES+cb.20210328-17-p0.en+FX+1",
                    "domain": ".youtube.com",
                    "path": "/",
                    "secure": True,
                    "httpOnly": False,
                    "sameSite": "None"
                }
            ]
            
            await self.page.context.add_cookies(consent_cookies)
            
            evt("youtubei_consent_reinjected",
                video_id=self.video_id,
                job_id=self.job_id,
                cookies_added=len(consent_cookies))
            
            # Reload page
            await self.page.reload(wait_until="domcontentloaded", timeout=30000)
            
            evt("youtubei_consent_reload_complete",
                video_id=self.video_id,
                job_id=self.job_id)
            
        except Exception as e:
            evt("youtubei_consent_recovery_error",
                video_id=self.video_id,
                job_id=self.job_id,
                error=str(e))
    

    
    async def _wait_for_transcript_with_fallback(self, cookies: Optional[str] = None) -> Optional[str]:
        """
        Wait for transcript capture with route interception and DOM fallback.
        
        Implements Requirements 5.2, 5.3, 5.4, 5.5, 12.1, 12.2:
        - 25-second timeout for route capture with proper error logging
        - Future-based route capture with (url, body) result handling
        - 6-second timeout for HTTP response validation
        - DOM fallback scraping when response timeout expires
        - Proper route cleanup with unroute() after capture completion
        
        Args:
            cookies: Optional cookie header string for authentication
        
        Returns:
            Transcript data if successful, None otherwise
        """
        route_cleanup_completed = False
        
        try:
            # Wait for route interception with 25-second timeout (Requirement 12.1)
            evt("youtubei_route_wait_start",
                video_id=self.video_id,
                job_id=self.job_id,
                timeout_seconds=YOUTUBEI_TIMEOUT)
            
            route_result = await asyncio.wait_for(
                self.transcript_future, timeout=YOUTUBEI_TIMEOUT
            )
            
            # Handle Future-based route capture result (Requirement 5.2)
            if route_result is None:
                # Non-200 status code was received
                evt("youtubei_route_result_none",
                    video_id=self.video_id,
                    job_id=self.job_id,
                    reason="non_200_status")
                return None
                
            elif isinstance(route_result, tuple) and len(route_result) == 2:
                # Expected (url, body) tuple format (Requirement 5.2)
                url, transcript_data = route_result
                self.route_fired = True
                
                # Log successful route capture with URL (Requirement 5.3)
                evt("youtubei_route_captured_success",
                    video_id=self.video_id,
                    job_id=self.job_id,
                    url=url,
                    content_length=len(transcript_data))
                logger.info(f"youtubei_route_captured url={url}")
                
                # Wait for HTTP response with 6-second timeout for validation (Requirement 5.4, 12.2)
                try:
                    response = await self.page.wait_for_response(
                        lambda r: '/youtubei/v1/get_transcript' in r.url,
                        timeout=6000
                    )
                    
                    # Validate response status code (Requirement 5.4)
                    if response.status != 200:
                        evt("youtubei_direct_fetch_failed",
                            video_id=self.video_id,
                            job_id=self.job_id,
                            status=response.status,
                            url=url)
                        
                        # Requirement 7.5: Add warning logs for failures without verbose dumps or stack traces
                        logger.warning(f"youtubei_direct_fetch_failed status={response.status}")
                        
                        # Try DOM fallback when non-200 status received
                        return await self._scrape_transcript_from_panel()
                        
                    # Successful route capture and response validation
                    return transcript_data
                    
                except asyncio.TimeoutError:
                    # Response timeout expired - immediately try DOM fallback (Requirement 5.5)
                    evt("youtubei_response_timeout_dom_fallback",
                        video_id=self.video_id,
                        job_id=self.job_id,
                        timeout_seconds=6)
                    
                    # Requirement 7.5: Add warning logs for failures without verbose dumps or stack traces
                    logger.warning("youtubei_response_timeout - trying DOM fallback")
                    
                    # Immediately try DOM fallback scraping from transcript panel
                    return await self._scrape_transcript_from_panel()
                    
                except Exception as response_error:
                    evt("youtubei_response_error",
                        video_id=self.video_id,
                        job_id=self.job_id,
                        error_type=type(response_error).__name__,
                        error=str(response_error)[:100])
                    
                    # Try DOM fallback on response errors
                    return await self._scrape_transcript_from_panel()
                    
            else:
                # Unexpected result format - log and handle gracefully
                evt("youtubei_route_result_unexpected",
                    video_id=self.video_id,
                    job_id=self.job_id,
                    result_type=type(route_result).__name__,
                    result_preview=str(route_result)[:100])
                
                # Try to use the result as-is for backward compatibility
                return route_result if isinstance(route_result, str) else None
                
        except asyncio.TimeoutError:
            # 25-second timeout exceeded (Requirement 12.1)
            evt("youtubei_route_timeout",
                video_id=self.video_id,
                job_id=self.job_id,
                timeout_seconds=YOUTUBEI_TIMEOUT,
                route_fired=self.route_fired)
            
            # Requirement 7.5: Add warning logs for failures without verbose dumps or stack traces
            logger.warning(f"youtubei_route_timeout after {YOUTUBEI_TIMEOUT}s")
        
        except Exception as route_error:
            # Other route interception errors (Requirement 5.3)
            evt("youtubei_route_error",
                video_id=self.video_id,
                job_id=self.job_id,
                error_type=type(route_error).__name__,
                error_detail=str(route_error)[:200])
            
            # Requirement 7.5: Add warning logs for failures without verbose dumps or stack traces
            logger.warning(f"youtubei_route_error: {type(route_error).__name__}")
        
        finally:
            # Proper route cleanup with unroute() after capture completion (Requirement 5.3)
            try:
                await self.page.unroute("**/youtubei/v1/get_transcript*")
                route_cleanup_completed = True
                evt("youtubei_route_cleanup",
                    video_id=self.video_id,
                    job_id=self.job_id,
                    pattern="**/youtubei/v1/get_transcript*")
                    
            except Exception as cleanup_error:
                evt("youtubei_route_cleanup_error",
                    video_id=self.video_id,
                    job_id=self.job_id,
                    error_type=type(cleanup_error).__name__,
                    error=str(cleanup_error)[:100])
                
                # Requirement 7.5: Add warning logs for failures without verbose dumps or stack traces
                logger.warning("youtubei_route_cleanup_error")
        
        # Log final cleanup status
        evt("youtubei_route_cleanup_status",
            video_id=self.video_id,
            job_id=self.job_id,
            cleanup_completed=route_cleanup_completed)
        
        # Route interception failed - try direct fetch fallback with cookies
        return await self._direct_fetch_fallback(cookies)
    
    async def _scrape_transcript_from_panel(self) -> Optional[str]:
        """
        DOM fallback scraping helper - extract transcript directly from transcript panel.
        
        Implements deterministic Plan B when route capture fails by parsing DOM elements
        from ytd-transcript-search-panel-renderer into standard format.
        
        Implements graceful degradation - never throws exceptions that break the transcript pipeline.
        
        Requirements: 9.1, 9.2, 9.3, 9.4, 9.5
        
        Returns:
            Transcript data in JSON format if successful, None otherwise
        """
        try:
            evt("youtubei_dom_fallback_start",
                video_id=self.video_id,
                job_id=self.job_id)
            
            # Graceful degradation: ensure page is available before attempting DOM scraping
            if not self.page:
                evt("youtubei_dom_fallback_no_page",
                    video_id=self.video_id,
                    job_id=self.job_id)
                return None
            
            # Wait for transcript panel to be visible
            try:
                await self.page.wait_for_selector(
                    'ytd-transcript-search-panel-renderer',
                    timeout=5000,
                    state='visible'
                )
            except Exception as panel_error:
                # Graceful degradation: panel not found should not break the pipeline
                evt("youtubei_dom_fallback_panel_not_found",
                    video_id=self.video_id,
                    job_id=self.job_id,
                    error=str(panel_error)[:100])
                return None
            
            # Extract transcript segments from DOM
            transcript_segments = await self.page.evaluate("""
                () => {
                    const segments = [];
                    
                    // Find all transcript cue elements
                    const cueElements = document.querySelectorAll(
                        'ytd-transcript-search-panel-renderer ytd-transcript-segment-renderer'
                    );
                    
                    for (const cueElement of cueElements) {
                        try {
                            // Extract text content
                            const textElement = cueElement.querySelector('.segment-text');
                            const text = textElement ? textElement.textContent.trim() : '';
                            
                            // Extract timestamp
                            const timestampElement = cueElement.querySelector('.segment-timestamp');
                            const timestampText = timestampElement ? timestampElement.textContent.trim() : '0:00';
                            
                            // Convert timestamp to seconds
                            let startSeconds = 0;
                            if (timestampText) {
                                const parts = timestampText.split(':').reverse();
                                for (let i = 0; i < parts.length; i++) {
                                    startSeconds += parseInt(parts[i] || '0') * Math.pow(60, i);
                                }
                            }
                            
                            if (text) {
                                segments.push({
                                    text: text,
                                    start: startSeconds,
                                    duration: 0  // Duration not available from DOM
                                });
                            }
                        } catch (segmentError) {
                            console.warn('Error parsing transcript segment:', segmentError);
                        }
                    }
                    
                    return segments;
                }
            """)
            
            if transcript_segments and len(transcript_segments) > 0:
                # Convert to JSON format similar to YouTubei response
                dom_transcript_data = {
                    "actions": [{
                        "updateEngagementPanelAction": {
                            "content": {
                                "transcriptRenderer": {
                                    "body": {
                                        "transcriptBodyRenderer": {
                                            "cueGroups": []
                                        }
                                    }
                                }
                            }
                        }
                    }]
                }
                
                # Convert segments to YouTubei-like format
                cue_groups = []
                for segment in transcript_segments:
                    cue_group = {
                        "transcriptCueGroupRenderer": {
                            "cues": [{
                                "transcriptCueRenderer": {
                                    "cue": {
                                        "simpleText": segment["text"]
                                    },
                                    "startOffsetMs": str(int(segment["start"] * 1000)),
                                    "durationMs": str(int(segment["duration"] * 1000))
                                }
                            }]
                        }
                    }
                    cue_groups.append(cue_group)
                
                dom_transcript_data["actions"][0]["updateEngagementPanelAction"]["content"]["transcriptRenderer"]["body"]["transcriptBodyRenderer"]["cueGroups"] = cue_groups
                
                evt("youtubei_dom_fallback_success",
                    video_id=self.video_id,
                    job_id=self.job_id,
                    segments_count=len(transcript_segments))
                
                # Return as JSON string to match expected format
                import json
                return json.dumps(dom_transcript_data)
                
            else:
                evt("youtubei_dom_fallback_no_segments",
                    video_id=self.video_id,
                    job_id=self.job_id)
                return None
                
        except Exception as e:
            # Graceful degradation: never throw exceptions that break the transcript pipeline (Requirement 9.4)
            evt("youtubei_dom_fallback_error",
                video_id=self.video_id,
                job_id=self.job_id,
                error_type=type(e).__name__,
                error=str(e)[:200])
            
            # Requirement 7.5: Add warning logs for failures without verbose dumps or stack traces
            logger.warning("youtubei_dom: DOM fallback scraping failed")
            
            # Graceful degradation: always return None without raising exceptions
            return None

    async def _direct_fetch_fallback(self, cookies: Optional[str] = None) -> Optional[str]:
        """
        Direct POST to youtubei API using real page context.
        
        Implements Requirements 1.5:
        - Extract real INNERTUBE_API_KEY and INNERTUBE_CONTEXT from ytcfg
        - Get params from captured requests or DOM
        - Add validation to ensure all required context is available before POST
        
        Args:
            cookies: Optional cookie header string for authentication
        
        Returns:
            Transcript data if successful, None otherwise
        """
        try:
            evt("youtubei_direct_fetch_start",
                video_id=self.video_id,
                job_id=self.job_id)
            
            # Extract real API context from page (Requirement 1.5)
            api_key = await self.page.evaluate("() => (window.ytcfg && ytcfg.get && ytcfg.get('INNERTUBE_API_KEY')) || null")
            context = await self.page.evaluate("() => (window.ytcfg && ytcfg.get && ytcfg.get('INNERTUBE_CONTEXT')) || null")
            
            # Extract params from captured requests or DOM (Requirement 1.5)
            params = await self._extract_transcript_params()
            
            # Validate all required context is available before POST (Requirement 1.5)
            if not (api_key and context and params):
                evt("youtubei_direct_missing_ctx", 
                    video_id=self.video_id,
                    job_id=self.job_id,
                    has_key=bool(api_key), 
                    has_ctx=bool(context), 
                    has_params=bool(params))
                return None
            
            # Make authenticated direct POST request with cookies
            return await self._make_direct_transcript_request(api_key, context, params, cookies)
                
        except Exception as e:
            evt("youtubei_direct_exception", 
                video_id=self.video_id,
                job_id=self.job_id,
                err=str(e)[:160])
            return None
    
    async def _extract_transcript_params(self) -> Optional[str]:
        """
        Extract transcript params from captured requests or DOM.
        
        Implements Requirement 1.5:
        - Get params from either captured /youtubei/v1/get_transcript request body
        - Or extract from ytInitialData JSON on the page
        
        Returns:
            Transcript params string if successful, None otherwise
        """
        try:
            evt("youtubei_params_extraction_start",
                video_id=self.video_id,
                job_id=self.job_id)
            
            # Method 1: Try to extract from ytInitialData on the page
            params_from_dom = await self.page.evaluate("""
                () => {
                    try {
                        // Look for transcript-related data in ytInitialData
                        const ytInitialData = window.ytInitialData || {};
                        
                        // Navigate through the data structure to find transcript params
                        const contents = ytInitialData.contents?.twoColumnWatchNextResults?.results?.results?.contents || [];
                        
                        for (const content of contents) {
                            if (content.videoPrimaryInfoRenderer) {
                                const videoActions = content.videoPrimaryInfoRenderer.videoActions;
                                if (videoActions && videoActions.menuRenderer) {
                                    const items = videoActions.menuRenderer.items || [];
                                    for (const item of items) {
                                        if (item.menuServiceItemRenderer && 
                                            item.menuServiceItemRenderer.serviceEndpoint &&
                                            item.menuServiceItemRenderer.serviceEndpoint.getTranscriptEndpoint) {
                                            return item.menuServiceItemRenderer.serviceEndpoint.getTranscriptEndpoint.params;
                                        }
                                    }
                                }
                            }
                        }
                        
                        // Alternative: look in engagement panels
                        const panels = ytInitialData.engagementPanels || [];
                        for (const panel of panels) {
                            if (panel.engagementPanelSectionListRenderer &&
                                panel.engagementPanelSectionListRenderer.panelIdentifier === 'engagement-panel-transcript') {
                                const content = panel.engagementPanelSectionListRenderer.content;
                                if (content && content.transcriptRenderer && content.transcriptRenderer.params) {
                                    return content.transcriptRenderer.params;
                                }
                            }
                        }
                        
                        return null;
                    } catch (e) {
                        console.error('Params extraction error:', e);
                        return null;
                    }
                }
            """)
            
            if params_from_dom:
                evt("youtubei_params_extracted_from_dom",
                    video_id=self.video_id,
                    job_id=self.job_id,
                    params_length=len(params_from_dom))
                return params_from_dom
            
            # Method 2: Fallback to building basic params
            evt("youtubei_params_fallback_to_basic",
                video_id=self.video_id,
                job_id=self.job_id)
            
            return self._build_basic_transcript_params()
            
        except Exception as e:
            evt("youtubei_params_extraction_error",
                video_id=self.video_id,
                job_id=self.job_id,
                error=str(e)[:100])
            
            # Fallback to basic params
            return self._build_basic_transcript_params()
    
    def _build_basic_transcript_params(self) -> str:
        """
        Build basic transcript request parameters as fallback.
        
        Returns:
            Base64-encoded parameters for transcript request
        """
        import base64
        
        # Basic transcript request parameters
        params_dict = {
            "videoId": self.video_id,
            "lang": "en"
        }
        
        # Convert to base64
        params_json = json.dumps(params_dict)
        params_b64 = base64.b64encode(params_json.encode()).decode()
        
        return params_b64
    
    async def _make_direct_transcript_request(self, api_key: str, context: Dict[str, Any], params: str, cookies: Optional[str] = None) -> Optional[str]:
        """
        Make authenticated direct POST request to youtubei API.
        
        Implements Requirements 1.5, 1.6:
        - Create authenticated request with proper headers
        - Add JSON response parsing to extract transcript text
        - Implement proxy support for direct POST requests
        
        Args:
            api_key: YouTube InnerTube API key
            context: YouTube InnerTube context object
            params: Transcript request parameters
            cookies: Optional cookie header string for authentication
            
        Returns:
            Transcript data if successful, None otherwise
        """
        try:
            evt("youtubei_direct_request_start",
                video_id=self.video_id,
                job_id=self.job_id)
            
            # Check proxy enforcement from centralized config (Requirement 1.6)
            enforce_proxy = _config.enforce_proxy_all
            
            # Get job-scoped proxy configuration (Requirement 1.6)
            proxy_dict = None
            if self.proxy_manager and self.proxy_manager.in_use:
                try:
                    proxy_dict = self.proxy_manager.proxy_dict_for_job(self.job_id, "requests")
                except Exception as e:
                    evt("youtubei_direct_proxy_error",
                        video_id=self.video_id,
                        job_id=self.job_id,
                        error=str(e)[:100])
                    if enforce_proxy:
                        evt("youtubei_direct_proxy_enforced_block",
                            video_id=self.video_id,
                            job_id=self.job_id)
                        return None
            
            # Block execution if proxy enforcement is enabled but no proxy available
            if enforce_proxy and not proxy_dict:
                evt("youtubei_direct_proxy_enforced_block",
                    video_id=self.video_id,
                    job_id=self.job_id,
                    reason="no_proxy_available")
                return None
            
            # Build request URL
            fetch_url = f"https://www.youtube.com/youtubei/v1/get_transcript?key={api_key}"
            
            # Build request payload with proper authentication context
            payload = {
                "context": context,
                "params": params
            }
            
            # Prepare authenticated request headers
            headers = {
                'Content-Type': 'application/json',
                'X-YouTube-Client-Name': '1',
                'X-YouTube-Client-Version': '2.0',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Origin': 'https://www.youtube.com',
                'Referer': f'https://www.youtube.com/watch?v={self.video_id}'
            }
            
            # Add cookies if provided
            if cookies:
                headers['Cookie'] = cookies
                evt("youtubei_direct_cookies_added",
                    video_id=self.video_id,
                    job_id=self.job_id,
                    cookie_count=len(cookies.split(';')) if cookies else 0)
            
            # Make authenticated direct POST request with proxy support
            timeout = httpx.Timeout(30.0)  # 30 second timeout
            
            async with httpx.AsyncClient(
                proxies=proxy_dict,
                timeout=timeout,
                headers=headers,
                follow_redirects=True
            ) as client:
                response = await client.post(fetch_url, json=payload)
                response.raise_for_status()
                
                # Parse JSON response to extract transcript text (Requirement 1.5)
                response_data = response.json()
                
                if response_data:
                    self.direct_post_used = True
                    
                    evt("youtubei_direct_request_success",
                        video_id=self.video_id,
                        job_id=self.job_id,
                        status_code=response.status_code,
                        content_length=len(response.text))
                    
                    # Return JSON response for downstream processing
                    return response.text
                else:
                    evt("youtubei_direct_request_empty_response",
                        video_id=self.video_id,
                        job_id=self.job_id,
                        status_code=response.status_code)
                    return None
                    
        except httpx.TimeoutException:
            evt("youtubei_direct_request_timeout",
                video_id=self.video_id,
                job_id=self.job_id)
            return None
        except httpx.HTTPStatusError as e:
            evt("youtubei_direct_request_http_error",
                video_id=self.video_id,
                job_id=self.job_id,
                status_code=e.response.status_code,
                error=str(e)[:100])
            return None
        except Exception as e:
            evt("youtubei_direct_request_error",
                video_id=self.video_id,
                job_id=self.job_id,
                error_type=type(e).__name__,
                error=str(e)[:100])
            return None
    
    def _parse_transcript_data(self, transcript_data: str) -> str:
        """
        Parse transcript data from YouTubei response using _extract_cues_from_youtubei method.
        
        Args:
            transcript_data: Raw transcript JSON data
            
        Returns:
            Parsed transcript data in JSON format for compatibility
        """
        try:
            data = json.loads(transcript_data)
            
            # Use the new _extract_cues_from_youtubei method for structured parsing
            from transcript_service import _extract_cues_from_youtubei
            segments = _extract_cues_from_youtubei(data)
            
            if segments:
                evt("youtubei_parse_success",
                    video_id=self.video_id,
                    job_id=self.job_id,
                    segments_count=len(segments))
                
                # Return the original JSON data for downstream processing
                # The _extract_cues_from_youtubei method will be called again in transcript_service
                return transcript_data
            else:
                # Fallback: return raw data if parsing fails
                evt("youtubei_parse_fallback",
                    video_id=self.video_id,
                    job_id=self.job_id)
                return transcript_data
                
        except json.JSONDecodeError:
            # Return raw data if not valid JSON
            evt("youtubei_parse_raw_fallback",
                video_id=self.video_id,
                job_id=self.job_id)
            return transcript_data
            
        except Exception as e:
            evt("youtubei_parse_error",
                video_id=self.video_id,
                job_id=self.job_id,
                error=str(e))
            return transcript_data  # Return raw data as last resort


def extract_transcript_with_job_proxy(
    video_id: str,
    job_id: str,
    proxy_manager,
    cookies: Optional[str] = None
) -> str:
    """
    Extract transcript using YouTubei with job-scoped proxy session.
    
    Args:
        video_id: YouTube video ID
        job_id: Job identifier for sticky proxy session
        proxy_manager: ProxyManager instance
        cookies: Cookie header string (optional)
        
    Returns:
        Transcript text if successful, empty string otherwise
    """
    async def _async_extract():
        capture = DeterministicYouTubeiCapture(job_id, video_id, proxy_manager)
        return await capture.extract_transcript(cookies)
    
    # Run async extraction with robust event loop handling
    try:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're in an existing event loop, we need to run in a thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _async_extract)
                    return future.result(timeout=60)  # 60 second timeout
            else:
                return loop.run_until_complete(_async_extract())
        except RuntimeError:
            # No event loop exists, create one
            return asyncio.run(_async_extract())
    except Exception as e:
        evt("youtubei_async_error",
            video_id=video_id,
            job_id=job_id,
            error_type=type(e).__name__,
            error_detail=str(e))
        return ""
