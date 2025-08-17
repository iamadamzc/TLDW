import os
import time
import logging
import tempfile
import requests
import mimetypes
import re
from typing import Optional
from youtube_transcript_api import YouTubeTranscriptApi
from proxy_manager import ProxyManager
from proxy_http import ProxyHTTPClient, YouTubeBlockingError
from transcript_cache import TranscriptCache
from user_agent_manager import UserAgentManager
from yt_download_helper import download_audio_with_retry

class TranscriptService:
    def __init__(self):
        self.deepgram_api_key = os.environ.get("DEEPGRAM_API_KEY", "")
        self.proxy_manager = ProxyManager()
        self.http_client = ProxyHTTPClient(self.proxy_manager)
        self.cache = TranscriptCache(default_ttl_days=7)  # MVP: 7-day cache
        self._video_locks = {}  # Idempotency guard: in-memory lock per video_id
        
        # Initialize UserAgentManager with error handling
        try:
            self.user_agent_manager = UserAgentManager()
            logging.info("UserAgentManager initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize UserAgentManager: {e}")
            # Create a fallback manager that returns empty headers
            self.user_agent_manager = None
        
        # Allow route layer to set current user id directly if desired
        self.current_user_id: Optional[int] = None
        
        # Track cookie failures for staleness detection
        self._cookie_failures = {}  # user_id -> failure_count
        
        # Track last download attempt for health diagnostics
        self._last_download_used_cookies = False
        self._last_download_client = "unknown"

    def get_transcript(self, video_id, has_captions=None, language="en"):
        """
        Main transcript fetching with discovery gate and sticky sessions
        CONTRACT: ASR path uses same session for yt-dlp audio download
        """
        
        # Idempotency guard: prevent concurrent fetching of same video
        if video_id in self._video_locks:
            logging.info(f"Video {video_id} already being processed, waiting...")
            # In a real implementation, this would be a proper lock/semaphore
            # For MVP, we'll just log and proceed
        
        self._video_locks[video_id] = True
        
        try:
            # Step 0: Check cache first
            cached_transcript = self.cache.get(video_id, language)
            if cached_transcript:
                logging.info(f"Cache hit for video {video_id} (lang: {language})")
                self._log_structured("transcript", video_id, "ok", 1, 0, "cache_hit", False, "none")
                return cached_transcript
            
            start_time = time.time()
            
            # Discovery gate implementation - skip transcript scraping if no captions
            if has_captions is False:
                logging.info(f"Discovery gate: Video {video_id} has no captions, skipping to ASR")
                self._log_structured("transcript", video_id, "skip_no_captions", 1, 0, "no_captions", False, "none")
                transcript = self._transcribe_audio_with_proxy(video_id)
                if transcript:
                    self.cache.set(video_id, transcript, language, source="asr", ttl_days=30)
                return transcript
            
            # Attempt transcript fetch with sticky session
            session = self.proxy_manager.get_session_for_video(video_id)
            
            try:
                transcript_text = self._fetch_transcript_with_session(video_id, session, language, start_time)
                if transcript_text:
                    self.cache.set(video_id, transcript_text, language, source="transcript_api", ttl_days=7)
                    return transcript_text
                    
            except YouTubeBlockingError as e:
                logging.warning(f"YouTube blocking detected for transcript {video_id}: {e}")
                
                # Single retry with rotated session
                rotated_session = self.proxy_manager.rotate_session(video_id)
                if rotated_session:
                    try:
                        transcript_text = self._fetch_transcript_with_session(video_id, rotated_session, language, start_time)
                        if transcript_text:
                            self.cache.set(video_id, transcript_text, language, source="transcript_api", ttl_days=7)
                            return transcript_text
                    except YouTubeBlockingError as e2:
                        logging.error(f"YouTube blocking persists after rotation for video {video_id}: {e2}")
                
                # Fall back to ASR with SAME rotated session (critical for consistency)
                logging.info(f"Falling back to ASR for video {video_id} due to persistent blocking")
                transcript = self._transcribe_audio_with_proxy(video_id, rotated_session)
                if transcript:
                    self.cache.set(video_id, transcript, language, source="asr", ttl_days=30)
                return transcript
            
            # If no transcript found and no blocking, fall back to ASR
            logging.info(f"No existing transcript found for {video_id}, using ASR fallback")
            transcript = self._transcribe_audio_with_proxy(video_id, session)
            if transcript:
                self.cache.set(video_id, transcript, language, source="asr", ttl_days=30)
            return transcript
            
        finally:
            # Clean up idempotency lock
            self._video_locks.pop(video_id, None)



    def _fetch_transcript_with_session(self, video_id, session, language, start_time):
        """
        Fetch transcript using sticky session and User-Agent headers with 15s timeout
        """
        try:
            # Get transcript headers with User-Agent and Accept-Language
            headers = {}
            ua_applied = False
            if self.user_agent_manager is not None:
                try:
                    headers = self.user_agent_manager.get_transcript_headers()
                    ua_applied = True
                    logging.debug(f"Transcript headers generated successfully for {video_id}")
                except Exception as e:
                    logging.warning(f"Failed to generate transcript headers for {video_id}: {e}")
                    headers = {}
            else:
                logging.debug(f"UserAgentManager not available for {video_id}")
            
            # Apply sticky proxy
            proxies = {}
            if session and session.proxy_url:
                proxies = {"http": session.proxy_url, "https": session.proxy_url}
            
            # Log structured attempt
            session_id = session.session_id if session else "none"
            self._log_structured("transcript", video_id, "attempt", 1, 0, "transcript_api", ua_applied, session_id)
            
            # Use YouTubeTranscriptApi directly with proxies (headers not supported in 0.6.2)
            chunks = YouTubeTranscriptApi.get_transcript(video_id, languages=[language], proxies=proxies)
            transcript_text = " ".join(item["text"] for item in chunks if item.get("text"))
            
            # Mark session as successful
            if session:
                session.mark_used()
            
            # Log success
            latency_ms = int((time.time() - start_time) * 1000)
            self._log_structured("transcript", video_id, "ok", 1, latency_ms, "transcript_api", ua_applied, session_id)
            logging.info(f"Transcript fetch successful for {video_id}")
            
            return transcript_text
            
        except Exception as e:
            error_msg = str(e).lower()
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Classify error types for structured logging
            if '407' in error_msg or 'proxy authentication' in error_msg:
                # 407 errors: fail fast with guidance
                if session:
                    session.mark_failed()
                self._log_structured("transcript", video_id, "proxy_407", 1, latency_ms, "transcript_api", ua_applied, session_id)
                
                # Try to handle 407 error with secrets refresh
                if self.proxy_manager.handle_407_error(video_id):
                    logging.info(f"Proxy credentials refreshed for {video_id}, but not retrying (fail fast)")
                
                raise YouTubeBlockingError(f"407 Proxy Authentication Required: {e}")
                
            elif any(indicator in error_msg for indicator in ['blocked', 'captcha', 'unusual traffic', 'sign in to confirm']):
                # Bot detection errors
                if session:
                    session.mark_blocked()
                self._log_structured("transcript", video_id, "bot_check", 1, latency_ms, "transcript_api", ua_applied, session_id)
                raise YouTubeBlockingError(f"Bot detection: {e}")
                
            elif any(indicator in error_msg for indicator in ['403', 'forbidden']):
                # 403 errors
                if session:
                    session.mark_blocked()
                self._log_structured("transcript", video_id, "blocked_403", 1, latency_ms, "transcript_api", ua_applied, session_id)
                raise YouTubeBlockingError(f"403 Forbidden: {e}")
                
            elif any(indicator in error_msg for indicator in ['429', 'rate limit']):
                # 429 errors
                if session:
                    session.mark_blocked()
                self._log_structured("transcript", video_id, "blocked_429", 1, latency_ms, "transcript_api", ua_applied, session_id)
                raise YouTubeBlockingError(f"429 Rate Limited: {e}")
                
            elif any(indicator in error_msg for indicator in ['timeout', 'connection']):
                # Timeout errors
                if session:
                    session.mark_failed()
                self._log_structured("transcript", video_id, "timeout", 1, latency_ms, "transcript_api", ua_applied, session_id)
                raise YouTubeBlockingError(f"Timeout: {e}")
                
            else:
                # Other errors - don't retry
                if session:
                    session.mark_failed()
                logging.warning(f"Could not get transcript for {video_id}: {e}")
                return None

    def _transcribe_audio_with_proxy(self, video_id, session=None):
        """
        ASR fallback using yt-dlp with sticky proxy, bot-check detection, and retry logic
        Uses same session as transcript attempt for IP consistency
        """
        if not self.deepgram_api_key:
            logging.error("Deepgram API key not provided")
            self._log_structured("ytdlp", video_id, "neterr", 1, 0, "no_deepgram_key", False, "none")
            return None

        # Use provided session or get new one
        if not session:
            session = self.proxy_manager.get_session_for_video(video_id)
        
        # First attempt
        result = self._attempt_ytdlp_download(video_id, session, attempt=1)
        
        # Check if bot-check was detected and retry is needed
        if result['status'] == 'bot_check' and result['attempt'] == 1:
            logging.info(f"Bot-check detected for video {video_id}, rotating session and retrying")
            
            # Rotate session for retry
            rotated_session = self.proxy_manager.rotate_session(video_id)
            if rotated_session:
                # Second attempt with rotated session
                result = self._attempt_ytdlp_download(video_id, rotated_session, attempt=2)
                
                # If second attempt also hits bot-check, mark as hard failure
                if result['status'] == 'bot_check':
                    result['status'] = 'bot_check_hard'
                    logging.warning(f"Bot-check persists after rotation for video {video_id}")
        
        return result.get('transcript_text')
    
    def _attempt_ytdlp_download(self, video_id, session, attempt=1):
        """
        Single attempt at yt-dlp download using helper with bot-check detection
        Returns dict with status, transcript_text, and attempt info
        """
        start_time = time.time()
        session_id = session.session_id if session else "none"
        
        # Check for environment proxy collision
        self._handle_env_proxy_collision()
        
        # Extract parameters for helper
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        # Get User-Agent
        user_agent_applied = False
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"  # fallback
        if self.user_agent_manager is not None:
            try:
                ua = self.user_agent_manager.get_yt_dlp_user_agent()
                user_agent_applied = True
                logging.info(f"Using User-Agent for yt-dlp download of video {video_id} (attempt {attempt})")
            except Exception as e:
                logging.warning(f"Failed to set User-Agent for yt-dlp: {e}")
        else:
            logging.debug(f"UserAgentManager not available for yt-dlp download of {video_id}")
        
        # Get proxy URL and validate credentials
        proxy_url = session.proxy_url if session and session.proxy_url else ""
        if proxy_url:
            # Log sanitized proxy info for debugging
            if '@' in proxy_url:
                # Extract host:port for logging (mask credentials)
                proxy_parts = proxy_url.split('@')
                if len(proxy_parts) == 2:
                    creds_part = proxy_parts[0].split('//')[-1]  # Extract user:pass
                    host_part = proxy_parts[1]
                    user_part = creds_part.split(':')[0] if ':' in creds_part else creds_part
                    logging.info(f"Using sticky proxy for yt-dlp download of video {video_id}: {session_id} (attempt {attempt}) - http://{user_part}:***@{host_part}")
                else:
                    logging.warning(f"Proxy URL format unexpected for video {video_id}: missing credentials")
            else:
                logging.warning(f"Proxy URL for video {video_id} missing authentication credentials - this may cause 407 errors")
            logging.info(f"Using sticky proxy for yt-dlp download of video {video_id}: {session_id} (attempt {attempt})")
        
        # Get ffmpeg path
        ffmpeg_path = os.environ.get('FFMPEG_LOCATION', '/usr/bin')
        
        # Resolve per-user cookiefile (optional) - respect kill-switch
        cookiefile, tmp_cookie = None, None
        if os.getenv("DISABLE_COOKIES", "false").lower() != "true":
            try:
                user_id = self._resolve_current_user_id()
                if user_id:
                    cookiefile, tmp_cookie = self._get_user_cookiefile(user_id)
                    if cookiefile:
                        logging.info(f"Using user cookiefile for yt-dlp (user={user_id})")
            except Exception as e:
                logging.warning(f"Cookiefile unavailable: {e}")
        else:
            logging.debug("Cookie functionality disabled via DISABLE_COOKIES environment variable")

        # Compute cookies flag for logging closure
        cookies_used_flag = bool(cookiefile)
        
        # Update health diagnostics tracking
        self._last_download_used_cookies = cookies_used_flag
        self._last_download_client = "web"  # We use stable web client only

        # Status tracking for logging integration
        last_status = {"status": "unknown", "attempt": attempt}
        
        def _log_adapter(status_msg: str):
            """Adapt helper log messages to existing structured logging"""
            nonlocal cookies_used_flag  # Allow updating the actual cookie usage
            
            # Parse helper attempt lines for structured logging
            import re
            attempt_line_re = re.compile(
                r"^yt_dlp_attempt=(\d+)\s+use_cookies=(true|false)(?:\s+(reason|retry_reason)=([a-z_0-9]+))?$",
                re.I,
            )
            m = attempt_line_re.match(status_msg.strip())
            if m:
                attempt = int(m.group(1))
                use_cookies = (m.group(2).lower() == "true")
                key = (m.group(3) or "").lower()
                val = (m.group(4) or "").lower() or None
                latency_ms = int((time.time() - start_time) * 1000)
                
                # Keep cookies_used_flag in sync with the actual attempt
                cookies_used_flag = use_cookies
                
                if attempt == 1:
                    self._log_structured(
                        "ytdlp",
                        video_id=video_id,
                        status="attempt",
                        attempt=attempt,
                        latency_ms=latency_ms,
                        source="asr",
                        ua_applied=user_agent_applied,
                        session_id=session_id,
                        cookies_used=cookies_used_flag,
                        reason=val if key == "reason" else None,
                    )
                elif attempt == 2:
                    self._log_structured(
                        "ytdlp",
                        video_id=video_id,
                        status="attempt",
                        attempt=attempt,
                        latency_ms=latency_ms,
                        source="asr",
                        ua_applied=user_agent_applied,
                        session_id=session_id,
                        cookies_used=cookies_used_flag,  # should be False
                        retry_reason=val if key == "retry_reason" else None,
                    )
                return
            
            # Existing step result parsing
            if status_msg.startswith("yt_step1_ok"):
                last_status.update(status="ok", attempt=1)
                # Extract path and size from message for additional logging
                if "path=" in status_msg and "size=" in status_msg:
                    path_part = status_msg.split("path=")[1].split(" ")[0]
                    size_part = status_msg.split("size=")[1].split(" ")[0]
                    logging.info(f"ASR input ready: file={path_part} size={size_part}")
            elif status_msg.startswith("yt_step1_fail_step2_ok"):
                last_status.update(status="ok", attempt=2)
                # Extract path and size from message for additional logging
                if "path=" in status_msg and "size=" in status_msg:
                    path_part = status_msg.split("path=")[1].split(" ")[0]
                    size_part = status_msg.split("size=")[1].split(" ")[0]
                    logging.info(f"ASR input ready: file={path_part} size={size_part}")
            elif status_msg.startswith("yt_step1_download_error") or status_msg.startswith("yt_step2_download_error"):
                last_status.update(status="ytdlp_error", attempt=max(1, last_status["attempt"]))
            else:
                last_status.update(status="ytdlp_info", attempt=max(1, last_status["attempt"]))
            
            # Log structured attempt/result for non-attempt lines
            latency_ms = int((time.time() - start_time) * 1000)
            self._log_structured("ytdlp", video_id, last_status["status"], 
                               last_status["attempt"], latency_ms, "asr", 
                               user_agent_applied, session_id, cookies_used_flag)

        # Log initial attempt
        self._log_structured("ytdlp", video_id, "attempt", attempt, 0, "asr", user_agent_applied, session_id, cookies_used_flag)
        logging.info(f"yt-dlp config: session={session_id} ua_applied={user_agent_applied} ffmpeg_location={ffmpeg_path}")
        
        try:
            # Get user_id for enhanced retry logic
            user_id = self._resolve_current_user_id()
            
            # Call the enhanced helper function with retry logic
            audio_path = download_audio_with_retry(
                video_url, ua, proxy_url, ffmpeg_path, _log_adapter, cookiefile=cookiefile, user_id=user_id
            )
            
            # Send to Deepgram for transcription
            transcript_text = self._send_to_deepgram(audio_path)
            
            # Clean up temp file
            try:
                os.unlink(audio_path)
            except Exception:
                pass
            
            if transcript_text:
                # Mark session as successful
                if session:
                    session.mark_used()
                logging.info(f"ASR transcription successful for {video_id} (attempt {attempt})")
                return {
                    'status': last_status['status'],
                    'attempt': last_status['attempt'],
                    'transcript_text': transcript_text
                }
            else:
                latency_ms = int((time.time() - start_time) * 1000)
                self._log_structured("ytdlp", video_id, "neterr", attempt, latency_ms, "asr_failed", user_agent_applied, session_id, cookies_used_flag)
                return {
                    'status': 'neterr',
                    'attempt': attempt,
                    'transcript_text': None
                }
                
        except RuntimeError as e:
            # Helper failed - check for bot detection in error message
            error_msg = str(e).lower()
            latency_ms = int((time.time() - start_time) * 1000)
            
            if '407' in error_msg or 'proxy authentication' in error_msg:
                # 407 errors: fail fast and rotate proxy
                status = "proxy_407"
                if session:
                    session.mark_failed()
                
                # Try to handle 407 error with secrets refresh
                if self.proxy_manager.handle_407_error(video_id):
                    logging.info(f"Proxy credentials refreshed for yt-dlp {video_id}, but not retrying (fail fast)")
                
                logging.warning(f"407 Proxy Authentication Required in yt-dlp for {video_id}")
                
            elif self._detect_bot_check(error_msg):
                status = "bot_check"
                if session:
                    session.mark_blocked()
                
                # Track cookie staleness if cookies were used
                if cookiefile:
                    user_id = self._resolve_current_user_id()
                    if user_id:
                        self._track_cookie_failure(user_id, "bot_check")
                        
            elif any(indicator in error_msg for indicator in ['timeout', 'connection', 'network']):
                status = "timeout"
                if session:
                    session.mark_failed()
            else:
                status = "yt_both_steps_fail"
                if session:
                    session.mark_failed()
            
            logging.error(f"Error in yt-dlp download for {video_id} (attempt {attempt}): {e}")
            self._log_structured("ytdlp", video_id, status, attempt, latency_ms, "asr_error", user_agent_applied, session_id, cookies_used_flag)
            
            return {
                'status': status,
                'attempt': attempt,
                'transcript_text': None
            }
        
        except Exception as e:
            # Unexpected error
            latency_ms = int((time.time() - start_time) * 1000)
            logging.error(f"Unexpected error in yt-dlp download for {video_id} (attempt {attempt}): {e}")
            self._log_structured("ytdlp", video_id, "neterr", attempt, latency_ms, "asr_error", user_agent_applied, session_id, cookies_used_flag)
            
            if session:
                session.mark_failed()
            
            return {
                'status': 'neterr',
                'attempt': attempt,
                'transcript_text': None
            }
        finally:
            # If we downloaded a temp cookiefile copy (e.g., from S3), remove it
            if tmp_cookie:
                try:
                    os.unlink(tmp_cookie)
                except Exception:
                    pass
    
    def _detect_bot_check(self, text):
        """
        Detect bot-check patterns in yt-dlp output/errors (case-insensitive)
        """
        if not text:
            return False
        
        text_lower = text.lower()
        bot_check_patterns = [
            'sign in to confirm you\'re not a bot',
            'sign in to confirm youre not a bot',
            'confirm you\'re not a bot',
            'confirm youre not a bot',
            'not a bot',
            'unusual traffic',
            'automated requests',
            'captcha'
        ]
        
        return any(pattern in text_lower for pattern in bot_check_patterns)
    
    def _handle_env_proxy_collision(self):
        """Check and warn about HTTP_PROXY/HTTPS_PROXY conflicts"""
        env_proxies = []
        if os.getenv('HTTP_PROXY'):
            env_proxies.append('HTTP_PROXY')
        if os.getenv('HTTPS_PROXY'):
            env_proxies.append('HTTPS_PROXY')
        
        if env_proxies:
            logging.warning(f"Ignoring environment proxy variables {env_proxies} - using sticky proxy configuration")

    def _handle_407_error(self, video_id: str, session) -> bool:
        """Handle 407 errors with fast rotation and optional no-proxy fallback"""
        logging.warning(f"407 Proxy Authentication Required for {video_id}, rotating proxy")
        if session:
            session.mark_failed()
        
        # Optional no-proxy fallback (disabled by default for security)
        if os.getenv("ALLOW_NO_PROXY_ON_407", "false").lower() == "true":
            logging.warning(f"ALLOW_NO_PROXY_ON_407 enabled - attempting no-proxy fallback for {video_id}")
            return True
        
        return False

    def _send_to_deepgram(self, audio_file_path):
        """Send audio file to Deepgram for transcription with correct Content-Type"""
        try:
            # Explicit MIME type mapping for common audio formats
            EXT_MIME_MAP = {
                ".m4a": "audio/mp4",
                ".mp4": "audio/mp4", 
                ".mp3": "audio/mpeg"
            }
            
            # Get file extension and use explicit mapping first
            _, ext = os.path.splitext(audio_file_path.lower())
            content_type = EXT_MIME_MAP.get(ext)
            
            # Fallback to mimetypes.guess_type() if not in explicit map
            if not content_type:
                mime, _ = mimetypes.guess_type(audio_file_path)
                content_type = mime or "application/octet-stream"
            
            headers = {
                'Authorization': f'Token {self.deepgram_api_key}',
                'Content-Type': content_type
            }
            
            logging.debug(f"Sending to Deepgram with Content-Type: {content_type} for file: {audio_file_path}")
            
            with open(audio_file_path, 'rb') as audio_file:
                response = requests.post(
                    'https://api.deepgram.com/v1/listen',
                    headers=headers,
                    data=audio_file,
                    params={'punctuate': 'true', 'model': 'nova'}
                )
            
            if response.status_code == 200:
                result = response.json()
                transcript = result['results']['channels'][0]['alternatives'][0]['transcript']
                return transcript
            else:
                logging.error(f"Deepgram API error: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logging.error(f"Error sending to Deepgram: {e}")
            return None
    def close(self):
        """Clean up resources"""
        if hasattr(self, 'http_client'):
            self.http_client.close()
    
    def get_proxy_stats(self):
        """Get proxy usage statistics"""
        return self.proxy_manager.get_session_stats()
    
    def get_cache_stats(self):
        """Get cache statistics"""
        return self.cache.get_stats()
    
    def cleanup_cache(self):
        """Clean up expired cache entries"""
        return self.cache.cleanup_expired()
    
    def get_health_diagnostics(self):
        """Get health diagnostic information for monitoring"""
        return {
            'last_download_used_cookies': self._last_download_used_cookies,
            'last_download_client': self._last_download_client
        }
    
    def _resolve_current_user_id(self) -> Optional[int]:
        """
        Prefer an explicitly set self.current_user_id.
        Otherwise, try Flask-Login's current_user if available.
        """
        if getattr(self, "current_user_id", None):
            return self.current_user_id  # set by route layer
        try:
            from flask_login import current_user  # lazy import to avoid circulars
            if getattr(current_user, "is_authenticated", False):
                return getattr(current_user, "id", None)
        except Exception:
            pass
        return None

    def _get_user_cookiefile(self, user_id: int) -> tuple[Optional[str], Optional[str]]:
        """
        Returns (cookiefile_path, tmp_path_for_cleanup).
        Strategy:
          1) If COOKIE_S3_BUCKET is set and boto3 available: download s3://<bucket>/cookies/<user_id>.txt to a temp file.
          2) Else check local COOKIE_LOCAL_DIR or /app/cookies for <user_id>.txt.
        If not found, returns (None, None).
        """
        # S3 path
        bucket = os.getenv("COOKIE_S3_BUCKET")
        if bucket:
            try:
                import boto3  # optional dependency
                from botocore.exceptions import ClientError
                s3 = boto3.client("s3")
                key = f"cookies/{user_id}.txt"
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".cookies.txt")
                tmp_path = tmp.name
                tmp.close()
                s3.download_file(bucket, key, tmp_path)
                if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                    logging.debug(f"Cookie source: s3 for user {user_id}")
                    return tmp_path, tmp_path  # tmp file to cleanup later
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                if error_code in ['403', 'AccessDenied']:
                    logging.warning(f"S3 cookie download failed for user {user_id} from {bucket}/cookies/{user_id}.txt: {e}. Check s3:GetObject and (if SSE-KMS) kms:Decrypt on the instance role.")
                else:
                    logging.warning(f"S3 cookie download failed for user {user_id} from {bucket}/cookies/{user_id}.txt: {e}")
            except Exception as e:
                logging.warning(f"S3 cookie download failed for user {user_id} from {bucket}/cookies/{user_id}.txt: {e}")

        # Local path
        local_dir = os.getenv("COOKIE_LOCAL_DIR", "/app/cookies")
        local_path = os.path.join(local_dir, f"{user_id}.txt")
        if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
            logging.debug(f"Cookie source: local for user {user_id}")
            return local_path, None  # persistent file; don't delete
        return None, None

    def _track_cookie_failure(self, user_id: int, failure_type: str):
        """Track cookie failures for staleness detection"""
        if user_id not in self._cookie_failures:
            self._cookie_failures[user_id] = 0
        
        self._cookie_failures[user_id] += 1
        failure_count = self._cookie_failures[user_id]
        
        logging.warning(f"Cookie failure for user {user_id}: {failure_type} (count: {failure_count})")
        
        # Suggest re-upload after multiple failures
        if failure_count >= 3:
            logging.warning(f"User {user_id} cookies may be stale - suggest re-upload (failures: {failure_count})")
            # Reset counter to avoid spam
            self._cookie_failures[user_id] = 0

    def _log_structured(self, step, video_id, status, attempt, latency_ms, source="", ua_applied=False, session_id="none", cookies_used=False, reason=None, retry_reason=None):
        """
        Structured logging with standardized keys for extraction hardening
        Never logs password or full proxy URL; only logs session ID
        Enhanced with unified attempt logging keys for consistent grep/alerting
        """
        # Convert boolean flags to lowercase strings for consistency
        ua_status = "true" if ua_applied else "false"
        cookie_status = "true" if cookies_used else "false"
        
        # Build base log data with standardized keys
        log_data = {
            "component": step,
            "video_id": video_id,
            "status": status,
            "yt_dlp_attempt": attempt,
            "use_cookies": cookie_status,
            "latency_ms": latency_ms,
            "method": source,
            "ua_applied": ua_status,
            "session_id": session_id
        }
        
        # Add reason for attempt 1 or retry_reason for attempt 2
        if attempt == 1 and reason:
            log_data["reason"] = reason
        elif attempt == 2 and retry_reason:
            log_data["retry_reason"] = retry_reason
        
        # Legacy download step for backward compatibility
        download_step = "unknown"
        if step == "ytdlp" and status == "ok":
            if attempt == 1:
                download_step = "step1_success"
            elif attempt == 2:
                download_step = "step2_success"
        elif step == "ytdlp" and status in ["bot_check", "timeout", "yt_both_steps_fail"]:
            download_step = f"step{attempt}_fail"
        log_data["download_step"] = download_step
        
        # Log as structured JSON for easy parsing
        import json
        logging.info(json.dumps(log_data))
