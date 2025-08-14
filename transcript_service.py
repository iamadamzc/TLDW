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

    def get_transcript(self, video_id, has_captions=None, language="en"):
        """
        MVP transcript generation with caching and proxy support:
        1. Check cache first
        2. Check if video has captions (skip transcript if no captions)
        3. Try youtube-transcript-api with proxy (one retry on blocking)
        4. Fallback to yt-dlp + Deepgram if blocked after retry
        5. Cache successful results
        """
        
        # Step 0: Check cache first
        cached_transcript = self.cache.get(video_id, language)
        if cached_transcript:
            logging.info(f"Cache hit for video {video_id} (lang: {language})")
            self._log_structured("transcript", video_id, "ok", 1, 0, "cache_hit", "not_applicable")
            return cached_transcript
        
        start_time = time.time()
        attempt = 1
        
        # MVP: If we know video has no captions, skip directly to ASR
        if has_captions is False:
            logging.info(f"Video {video_id} has no captions, skipping to ASR")
            self._log_structured("transcript", video_id, "skip_no_captions", attempt, 0, "no_captions", "not_applicable")
            transcript = self._transcribe_audio(video_id)
            if transcript:
                self.cache.set(video_id, transcript, language, source="asr", ttl_days=30)
            return transcript
        
        # Step 1: Try to get existing transcript with proxy support
        try:
            transcript_text = self._get_existing_transcript_with_proxy(video_id, language)
            if transcript_text:
                latency_ms = int((time.time() - start_time) * 1000)
                logging.info(f"Got existing transcript for video {video_id}")
                self._log_structured("transcript", video_id, "ok", attempt, latency_ms, "transcript_api", "applied")
                
                # Cache successful transcript
                self.cache.set(video_id, transcript_text, language, source="transcript_api", ttl_days=7)
                return transcript_text
                
        except YouTubeBlockingError as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logging.warning(f"YouTube blocking detected for transcript {video_id}: {e}")
            self._log_structured("transcript", video_id, "blocked", attempt, latency_ms, "transcript_api", "applied_but_blocked")
            
            # Fallback to ASR after blocking
            logging.info(f"Falling back to ASR for video {video_id} due to blocking")
            transcript = self._transcribe_audio(video_id)
            if transcript:
                self.cache.set(video_id, transcript, language, source="asr", ttl_days=30)
            return transcript
        
        # Step 2: Fallback to audio transcription
        logging.info(f"No existing transcript found for {video_id}, using Deepgram fallback")
        transcript = self._transcribe_audio(video_id)
        if transcript:
            self.cache.set(video_id, transcript, language, source="asr", ttl_days=30)
        return transcript

    def _get_transcript_with_headers(self, video_id, headers=None, **kwargs):
        """
        Wrapper around YouTubeTranscriptApi.fetch that lets you pass headers.
        Uses temporary monkey-patching to inject User-Agent headers.
        """
        original_get = requests.sessions.Session.get
        
        def custom_get(self, url, **req_kwargs):
            req_headers = req_kwargs.pop("headers", {})
            if headers:
                req_headers.update(headers)
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

    def _get_existing_transcript_with_proxy(self, video_id, language="en"):
        """Try to get existing transcript using youtube-transcript-api with proxy support and User-Agent headers"""
        try:
            # Get User-Agent headers for anti-bot protection with error handling
            headers = {}
            if self.user_agent_manager is not None:
                try:
                    headers = self.user_agent_manager.get_headers()
                    logging.debug(f"User-Agent headers generated successfully for {video_id}")
                except Exception as e:
                    logging.warning(f"Failed to generate User-Agent headers for {video_id}: {e}")
                    # Continue without User-Agent headers - graceful degradation
                    headers = {}
            else:
                logging.debug(f"UserAgentManager not available, proceeding without User-Agent for {video_id}")
            
            # Log the attempt
            session = self.proxy_manager.get_session_for_video(video_id)
            if session:
                ua_status = "with User-Agent" if headers and 'User-Agent' in headers else "without User-Agent"
                logging.info(f"Attempting transcript fetch for {video_id} with session {session.session_id} {ua_status}")
            else:
                ua_status = "with User-Agent" if headers and 'User-Agent' in headers else "without User-Agent"
                logging.info(f"Attempting transcript fetch for {video_id} {ua_status} (no proxy session)")
            
            # Use wrapper method to pass headers (with or without User-Agent)
            transcript = self._get_transcript_with_headers(video_id, headers=headers)
            transcript_text = ' '.join([snippet.text for snippet in transcript])
            
            # Mark session as successful if we have one
            if session:
                session.mark_used()
                logging.info(f"Transcript fetch successful for {video_id}")
            
            return transcript_text
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Check if this looks like YouTube blocking
            if any(indicator in error_msg for indicator in ['blocked', 'captcha', 'unusual traffic', 'not available']):
                # Mark session as blocked and try rotation
                if session:
                    self.proxy_manager.mark_session_blocked(video_id)
                
                # Try one rotation
                rotated_session = self.proxy_manager.rotate_session(video_id)
                if rotated_session:
                    logging.info(f"Retrying transcript fetch for {video_id} with rotated session {rotated_session.session_id}")
                    try:
                        # Use User-Agent headers for retry as well
                        transcript = self._get_transcript_with_headers(video_id, headers=headers)
                        transcript_text = ' '.join([snippet.text for snippet in transcript])
                        rotated_session.mark_used()
                        logging.info(f"Transcript fetch successful after rotation for {video_id}")
                        return transcript_text
                    except Exception as e2:
                        logging.error(f"Transcript fetch failed after rotation for {video_id}: {e2}")
                        rotated_session.mark_failed()
                        raise YouTubeBlockingError(f"Persistent blocking after rotation: {e2}")
                
                # If no rotation possible, raise blocking error
                raise YouTubeBlockingError(f"YouTube blocking detected: {e}")
            
            # For other errors, just log and return None
            logging.warning(f"Could not get existing transcript for {video_id}: {e}")
            if session:
                session.mark_failed()
            return None

    def _transcribe_audio(self, video_id):
        """Fallback: Download audio and transcribe with Deepgram using proxy"""
        if not self.deepgram_api_key:
            logging.error("Deepgram API key not provided")
            self._log_structured("ytdlp", video_id, "neterr", 1, 0, "no_deepgram_key", "not_applicable")
            return None

        start_time = time.time()
        attempt = 1
        
        try:
            # Get proxy session for consistent IP usage
            session = self.proxy_manager.get_session_for_video(video_id)
            proxy_dict = self.proxy_manager.get_proxy_dict(session) if session else {}
            
            # Download audio using yt-dlp with proxy
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                temp_filename = temp_file.name

            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': temp_filename,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
            
            # Add User-Agent to yt-dlp for anti-bot protection
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
                logging.debug(f"UserAgentManager not available, proceeding without User-Agent for yt-dlp download of {video_id}")
            
            # Add proxy to yt-dlp if available
            if proxy_dict and 'https' in proxy_dict:
                ydl_opts['proxy'] = proxy_dict['https']
                logging.info(f"Using proxy for yt-dlp download of video {video_id}")

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
                ua_status = "applied" if user_agent_applied else "failed"
                self._log_structured("ytdlp", video_id, "ok", attempt, latency_ms, "asr", ua_status)
            else:
                latency_ms = int((time.time() - start_time) * 1000)
                ua_status = "applied" if user_agent_applied else "failed"
                self._log_structured("ytdlp", video_id, "neterr", attempt, latency_ms, "asr_failed", ua_status)
            
            return transcript_text

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            error_msg = str(e).lower()
            
            # Determine error type for structured logging
            if any(indicator in error_msg for indicator in ['blocked', 'captcha', 'unusual traffic']):
                status = "blocked"
            elif any(indicator in error_msg for indicator in ['timeout', 'connection', 'network']):
                status = "neterr"
            else:
                status = "neterr"
            
            logging.error(f"Error transcribing audio for {video_id}: {e}")
            ua_status = "applied" if user_agent_applied else "failed"
            self._log_structured("ytdlp", video_id, status, attempt, latency_ms, "asr_error", ua_status)
            
            if session:
                session.mark_failed()
            return None

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
    
    def _log_structured(self, step, video_id, status, attempt, latency_ms, source="", user_agent_status="unknown"):
        """Structured logging for MVP observability with User-Agent information"""
        logging.info(f"STRUCTURED_LOG: step={step}, video_id={video_id}, status={status}, "
                    f"attempt={attempt}, latency_ms={latency_ms}, source={source}, "
                    f"user_agent_status={user_agent_status}")
