import os
import time
import logging
import tempfile
import yt_dlp
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from proxy_manager import ProxyManager
from proxy_http import ProxyHTTPClient, YouTubeBlockingError
from transcript_cache import TranscriptCache
from user_agent_manager import UserAgentManager

class TranscriptService:
    def __init__(self):
        self.deepgram_api_key = os.environ.get("DEEPGRAM_API_KEY", "")
        self.proxy_manager = ProxyManager()
        self.http_client = ProxyHTTPClient(self.proxy_manager)
        self.cache = TranscriptCache(default_ttl_days=7)  # MVP: 7-day cache
        
        # Initialize UserAgentManager with error handling
        try:
            self.user_agent_manager = UserAgentManager()
            logging.info("UserAgentManager initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize UserAgentManager: {e}")
            # Create a fallback manager that returns empty headers
            self.user_agent_manager = None

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

    def _get_transcript_with_headers_and_timeout(self, video_id, headers=None, timeout=15, **kwargs):
        """
        Wrapper around YouTubeTranscriptApi.fetch with headers and timeout support.
        Uses temporary monkey-patching to inject User-Agent headers and timeout.
        """
        original_get = requests.sessions.Session.get
        
        def custom_get(self, url, **req_kwargs):
            req_headers = req_kwargs.pop("headers", {})
            if headers:
                req_headers.update(headers)
            # Add timeout to all requests
            req_kwargs.setdefault('timeout', timeout)
            return original_get(self, url, headers=req_headers, **req_kwargs)
        
        # Patch requests.get temporarily
        requests.sessions.Session.get = custom_get
        
        try:
            api = YouTubeTranscriptApi()
            transcript = api.fetch(video_id, **kwargs)
            return transcript
        finally:
            # Restore original method to avoid side effects
            requests.sessions.Session.get = original_get

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
            
            # Log structured attempt
            session_id = session.session_id if session else "none"
            self._log_structured("transcript", video_id, "attempt", 1, 0, "transcript_api", ua_applied, session_id)
            
            # Use wrapper method with 15-second timeout
            transcript = self._get_transcript_with_headers_and_timeout(video_id, headers, timeout=15)
            transcript_text = ' '.join([snippet.text for snippet in transcript])
            
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
        ASR fallback using yt-dlp with sticky proxy and 15s timeout
        Uses same session as transcript attempt for IP consistency
        """
        if not self.deepgram_api_key:
            logging.error("Deepgram API key not provided")
            self._log_structured("ytdlp", video_id, "neterr", 1, 0, "no_deepgram_key", False, "none")
            return None

        start_time = time.time()
        
        # Use provided session or get new one
        if not session:
            session = self.proxy_manager.get_session_for_video(video_id)
        
        session_id = session.session_id if session else "none"
        
        try:
            # Check for environment proxy collision
            self._handle_env_proxy_collision()
            
            # Download audio using yt-dlp with proxy
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                temp_filename = temp_file.name

            # Configure yt-dlp with sticky proxy and matching User-Agent
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': temp_filename,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'socket_timeout': 15  # Hard timeout to prevent hung jobs
            }
            
            # Add User-Agent to yt-dlp (same as transcript)
            user_agent_applied = False
            if self.user_agent_manager is not None:
                try:
                    user_agent = self.user_agent_manager.get_yt_dlp_user_agent()
                    ydl_opts['user_agent'] = user_agent
                    user_agent_applied = True
                    logging.info(f"Using User-Agent for yt-dlp download of video {video_id}")
                except Exception as e:
                    logging.warning(f"Failed to set User-Agent for yt-dlp: {e}")
            else:
                logging.debug(f"UserAgentManager not available for yt-dlp download of {video_id}")
            
            # Add sticky proxy to yt-dlp
            if session and session.proxy_url:
                ydl_opts['proxy'] = session.proxy_url
                logging.info(f"Using sticky proxy for yt-dlp download of video {video_id}: {session_id}")
            
            # Log structured attempt
            self._log_structured("ytdlp", video_id, "attempt", 1, 0, "asr", user_agent_applied, session_id)

            video_url = f"https://www.youtube.com/watch?v={video_id}"
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])

            # Send to Deepgram for transcription
            transcript_text = self._send_to_deepgram(temp_filename)
            
            # Clean up temp file
            if os.path.exists(temp_filename):
                os.unlink(temp_filename)
            
            if transcript_text:
                latency_ms = int((time.time() - start_time) * 1000)
                # Mark session as successful
                if session:
                    session.mark_used()
                logging.info(f"ASR transcription successful for {video_id}")
                self._log_structured("ytdlp", video_id, "ok", 1, latency_ms, "asr", user_agent_applied, session_id)
            else:
                latency_ms = int((time.time() - start_time) * 1000)
                self._log_structured("ytdlp", video_id, "neterr", 1, latency_ms, "asr_failed", user_agent_applied, session_id)
            
            return transcript_text

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            error_msg = str(e).lower()
            
            # Determine error type for structured logging
            if any(indicator in error_msg for indicator in ['blocked', 'captcha', 'unusual traffic']):
                status = "blocked"
            elif any(indicator in error_msg for indicator in ['timeout', 'connection', 'network']):
                status = "timeout"
            else:
                status = "neterr"
            
            logging.error(f"Error transcribing audio for {video_id}: {e}")
            self._log_structured("ytdlp", video_id, status, 1, latency_ms, "asr_error", user_agent_applied, session_id)
            
            if session:
                session.mark_failed()
            return None
    
    def _handle_env_proxy_collision(self):
        """Check and warn about HTTP_PROXY/HTTPS_PROXY conflicts"""
        env_proxies = []
        if os.getenv('HTTP_PROXY'):
            env_proxies.append('HTTP_PROXY')
        if os.getenv('HTTPS_PROXY'):
            env_proxies.append('HTTPS_PROXY')
        
        if env_proxies:
            logging.warning(f"Ignoring environment proxy variables {env_proxies} - using sticky proxy configuration")

    def _send_to_deepgram(self, audio_file_path):
        """Send audio file to Deepgram for transcription"""
        try:
            headers = {
                'Authorization': f'Token {self.deepgram_api_key}',
                'Content-Type': 'audio/mp3'
            }
            
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
    
    def _log_structured(self, step, video_id, status, attempt, latency_ms, source="", ua_applied=False, session_id="none"):
        """
        Structured logging with credential redaction and session tracking
        Never logs password or full proxy URL; only logs session ID
        """
        # Convert ua_applied boolean to string for consistency
        ua_status = "true" if ua_applied else "false"
        
        logging.info(f"STRUCTURED_LOG step={step} video_id={video_id} session={session_id} "
                    f"ua_applied={ua_status} latency_ms={latency_ms} status={status} "
                    f"attempt={attempt} source={source}")
