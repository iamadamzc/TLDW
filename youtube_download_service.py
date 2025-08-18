"""
YouTube Download Service with new proxy validation integration
"""

import os
import json
import logging
from typing import Dict, Optional
from proxy_manager import ProxyManager, ProxyAuthError, ProxyConfigError, generate_correlation_id, error_response, BLOCK_STATUSES, extract_session_from_proxies
from yt_download_helper import download_audio_with_retry

class YouTubeDownloadService:
    def __init__(self):
        """Initialize YouTube download service with proxy validation"""
        # Initialize ProxyManager with strict validation
        try:
            self.proxy_manager = self._create_proxy_manager()
        except Exception as e:
            logging.error(f"Failed to initialize ProxyManager: {e}")
            self.proxy_manager = None
    
    def _create_proxy_manager(self):
        """Create ProxyManager with loaded secret and validation"""
        # Load secret from environment
        raw_config = os.getenv('OXYLABS_PROXY_CONFIG', '').strip()
        if not raw_config:
            raise ValueError("OXYLABS_PROXY_CONFIG environment variable is empty")
        
        # Parse JSON secret
        secret_data = json.loads(raw_config)
        
        # Diagnostic logging to prove secret is RAW (as suggested)
        username = secret_data.get('username', '')
        password = secret_data.get('password', '')
        masked_username = username[:4] + "***" + username[-2:] if len(username) > 6 else username[:2] + "***"
        
        # Quick pre-encoding check before ProxyManager validation
        has_encoded_chars = '%2B' in password or '%25' in password or '%21' in password or '%40' in password
        
        logging.info(f"🔍 YouTubeDownloadService: Loading proxy secret for username={masked_username}")
        logging.info(f"🔍 Secret pre-encoding check: has_encoded_chars={has_encoded_chars}")
        
        if has_encoded_chars:
            logging.error(f"❌ CRITICAL: Proxy secret appears to be URL-encoded!")
            logging.error(f"💡 Fix RuntimeEnvironmentSecrets in AWS to use RAW password (with + literally)")
            logging.error(f"🚨 This WILL cause 407 errors - stop and fix secret before proceeding")
            # Fail fast - don't even try to create ProxyManager
            raise ValueError("Proxy secret is URL-encoded - fix RuntimeEnvironmentSecrets to use RAW password")
        
        logger = logging.getLogger(__name__)
        return ProxyManager(secret_data, logger)
    
    def download_with_ytdlp(self, video_id: str, user_id: Optional[int] = None) -> Dict:
        """Download video with yt-dlp using validated proxy"""
        correlation_id = generate_correlation_id()
        
        # Step 1: Preflight validation - FAIL FAST if proxy unhealthy
        if self.proxy_manager:
            try:
                if not self.proxy_manager.preflight():
                    logging.error(f"Proxy preflight failed for video {video_id}")
                    return error_response('PROXY_AUTH_FAILED', correlation_id)
            except ProxyAuthError as e:
                logging.error(f"Proxy auth error for video {video_id}: {e}")
                return error_response('PROXY_AUTH_FAILED', correlation_id, str(e))
            except ProxyConfigError as e:
                logging.error(f"Proxy config error for video {video_id}: {e}")
                return error_response('PROXY_MISCONFIGURED', correlation_id, str(e))
        
        # Step 2: Get proxy config with unique session
        proxies = self.proxy_manager.proxies_for(video_id) if self.proxy_manager else {}
        session_token = extract_session_from_proxies(proxies)
        
        try:
            # Step 3: Attempt download with proxy
            result = self._attempt_download(video_id, proxies, user_id, correlation_id)
            return result
            
        except Exception as e:
            # Check for auth/blocking status codes and rotate session
            error_msg = str(e).lower()
            if any(str(status) in error_msg for status in BLOCK_STATUSES):
                # Blacklist this session
                if self.proxy_manager:
                    self.proxy_manager.rotate_session(session_token)
                    logging.warning(f"Session rotated for video {video_id} due to auth/blocking error")
                
                # ENHANCED: Re-preflight the new session before proceeding
                try:
                    if not self.proxy_manager.preflight():
                        logging.error(f"Rotated session still unhealthy for video {video_id}")
                        return error_response('PROXY_AUTH_FAILED', correlation_id, "Session rotation failed - proxy still unhealthy")
                except (ProxyAuthError, ProxyConfigError) as preflight_error:
                    logging.error(f"Rotated session preflight failed for video {video_id}: {preflight_error}")
                    return error_response('PROXY_AUTH_FAILED', correlation_id, f"Rotated session preflight failed: {preflight_error}")
                
                # Preflight passed - proceed with fresh session
                try:
                    fresh_proxies = self.proxy_manager.proxies_for(video_id) if self.proxy_manager else {}
                    result = self._attempt_download(video_id, fresh_proxies, user_id, correlation_id)
                    return result
                except Exception as retry_e:
                    logging.error(f"Retry failed for video {video_id}: {retry_e}")
                    return error_response('PROXY_AUTH_FAILED', correlation_id, str(retry_e))
            
            # Non-auth error, return as-is
            logging.error(f"Download failed for video {video_id}: {e}")
            return {"error": str(e), "correlation_id": correlation_id}
    
    def _attempt_download(self, video_id: str, proxies: Dict, user_id: Optional[int], correlation_id: str) -> Dict:
        """Attempt single download with given proxies"""
        # Fast-fail cookie check
        cookiefile = self._get_valid_cookiefile(user_id)
        cookies_valid = self._validate_cookiefile(cookiefile)
        
        logging.info(f"Starting yt-dlp download for video {video_id}, cookies_valid={cookies_valid}")
        
        # Configure yt-dlp options
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        proxy_url = proxies.get('https', '') if proxies else ''
        
        # Use download_audio_with_retry from helper
        try:
            audio_path = download_audio_with_retry(
                video_url=video_url,
                ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
                proxy_url=proxy_url,
                ffmpeg_path=os.environ.get('FFMPEG_LOCATION', '/usr/bin/ffmpeg'),
                cookiefile=cookiefile if cookies_valid else None,
                user_id=user_id
            )
            
            if audio_path and os.path.exists(audio_path):
                return {
                    "success": True,
                    "audio_path": audio_path,
                    "video_id": video_id,
                    "cookies_used": cookies_valid,
                    "correlation_id": correlation_id
                }
            else:
                return {
                    "success": False,
                    "error": "No audio file produced",
                    "correlation_id": correlation_id
                }
                
        except Exception as e:
            # Check for specific error types
            error_msg = str(e).lower()
            if any(str(status) in error_msg for status in BLOCK_STATUSES):
                raise  # Re-raise for session rotation handling
            
            return {
                "success": False,
                "error": str(e),
                "correlation_id": correlation_id
            }
    
    def _get_valid_cookiefile(self, user_id: Optional[int]) -> Optional[str]:
        """Get valid cookie file path for user"""
        if not user_id or os.getenv("DISABLE_COOKIES", "false").lower() == "true":
            return None
        
        # Construct cookie file path
        cookie_dir = os.getenv("COOKIE_DIR", "/tmp/cookies")
        cookiefile = os.path.join(cookie_dir, f"cookies_{user_id}.txt")
        
        return cookiefile if os.path.exists(cookiefile) else None
    
    def _validate_cookiefile(self, cookiefile: Optional[str]) -> bool:
        """Quick cookie sanity check"""
        if not cookiefile:
            return False
            
        try:
            if not os.path.exists(cookiefile):
                return False
            
            # Check file size (>1KB)
            if os.path.getsize(cookiefile) < 1024:
                return False
                
            # Check for essential YouTube cookies
            with open(cookiefile, 'r') as f:
                content = f.read()
                return any(cookie in content for cookie in ['SID', 'SAPISID', 'HSID'])
                
        except Exception:
            return False