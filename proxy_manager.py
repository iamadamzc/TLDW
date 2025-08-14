import os
import json
import time
import logging
import hashlib
import re
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from urllib.parse import quote
import boto3
from botocore.exceptions import ClientError

class ProxySession:
    """Represents a sticky proxy session for a specific video_id"""
    
    def __init__(self, video_id: str, proxy_config: Dict[str, Any]):
        self.video_id = video_id
        self.proxy_config = proxy_config
        self.created_at = datetime.now()
        self.last_used = datetime.now()
        self.request_count = 0
        self.failed_count = 0
        self.is_blocked = False
        self.session_id = self._generate_session_id()
        # New properties for backward compatibility
        self.proxy_url = self._build_proxy_url()
        self.expires_at = self._calculate_expires_at()
        
    def _generate_session_id(self) -> str:
        """Generate a unique session ID based on video_id and timestamp"""
        import time
        # Include microseconds to ensure uniqueness on rotation
        data = f"{self.video_id}_{self.created_at.isoformat()}_{time.time()}"
        return hashlib.md5(data.encode()).hexdigest()[:8]
    
    def _sanitize_video_id(self, video_id: str) -> str:
        """Sanitize video_id to alphanumeric only for sticky session"""
        return re.sub(r'[^a-zA-Z0-9]', '', video_id)
    
    def _build_proxy_url(self) -> str:
        """Build Oxylabs sticky session proxy URL with proper encoding"""
        if not self.proxy_config:
            return ""
        
        # Get base username from config
        base_username = self.proxy_config.get('username', '')
        password = self.proxy_config.get('password', '')
        host = self.proxy_config.get('host', '')
        port = self.proxy_config.get('port', '')
        
        # Sanitize video_id for session
        sanitized_video_id = self._sanitize_video_id(self.video_id)
        
        # Build sticky session username: customer-<base_username>-cc-us-sessid-<video_id>
        sticky_username = f"customer-{base_username}-cc-us-sessid-{sanitized_video_id}"
        
        # URL encode username and password
        encoded_username = quote(sticky_username, safe="")
        encoded_password = quote(password, safe="")
        
        # Build proxy URL
        proxy_url = f"http://{encoded_username}:{encoded_password}@{host}:{port}"
        
        logging.debug(f"Built sticky proxy URL for video {self.video_id}: {sticky_username}@{host}:{port}")
        return proxy_url
    
    def _calculate_expires_at(self) -> datetime:
        """Calculate expiration time based on configurable TTL"""
        # Get TTL from environment variable or config, with fallback to 10 minutes
        ttl_seconds = int(os.getenv("PROXY_SESSION_TTL_SECONDS", 
                                   self.proxy_config.get("session_ttl_minutes", 10) * 60))
        return self.created_at + timedelta(seconds=ttl_seconds)
    
    def is_expired(self, ttl_minutes: int = 10) -> bool:
        """Check if session has expired based on TTL"""
        expiry_time = self.created_at + timedelta(minutes=ttl_minutes)
        return datetime.now() > expiry_time
    
    def mark_used(self):
        """Mark session as used and update counters"""
        self.last_used = datetime.now()
        self.request_count += 1
    
    def mark_failed(self):
        """Mark session as failed"""
        self.failed_count += 1
        
    def mark_blocked(self):
        """Mark session as blocked by YouTube"""
        self.is_blocked = True
        self.failed_count += 1
        logging.warning(f"Session {self.session_id} for video {self.video_id} marked as blocked")

class ProxyManager:
    """Manages sticky proxy sessions for YouTube transcript fetching"""
    
    def __init__(self):
        self.sessions: Dict[str, ProxySession] = {}
        self.proxy_config = None
        self.enabled = os.getenv('USE_PROXIES', 'true').lower() == 'true'
        
        if self.enabled:
            self._load_proxy_config()
            logging.info("ProxyManager initialized with Oxylabs proxy")
        else:
            logging.info("ProxyManager initialized but proxies disabled")
    
    def _load_proxy_config(self) -> None:
        """Load proxy configuration from AWS Secrets Manager"""
        try:
            # Initialize AWS Secrets Manager client
            session = boto3.Session()
            client = session.client('secretsmanager', region_name='us-west-2')
            
            # Get the secret value
            response = client.get_secret_value(SecretId='tldw-oxylabs-proxy-config')
            secret_string = response['SecretString']
            
            # Parse the JSON configuration
            self.proxy_config = json.loads(secret_string)
            
            logging.info(f"Loaded proxy config: {self.proxy_config['host']}:{self.proxy_config['port']}")
            
        except ClientError as e:
            logging.error(f"Failed to load proxy configuration from AWS Secrets Manager: {e}")
            self.enabled = False
            raise
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse proxy configuration JSON: {e}")
            self.enabled = False
            raise
        except Exception as e:
            logging.error(f"Unexpected error loading proxy configuration: {e}")
            self.enabled = False
            raise
    
    def get_session_for_video(self, video_id: str) -> Optional[ProxySession]:
        """Get or create a sticky session for a specific video_id"""
        if not self.enabled or not self.proxy_config:
            return None
        
        # Clean up expired sessions
        self._cleanup_expired_sessions()
        
        # Check if we have an existing session for this video
        if video_id in self.sessions:
            session = self.sessions[video_id]
            
            # Check if session is expired
            ttl_minutes = self.proxy_config.get('session_ttl_minutes', 10)
            if session.is_expired(ttl_minutes):
                logging.info(f"Session for video {video_id} expired, creating new session")
                del self.sessions[video_id]
            else:
                # Return existing session
                session.mark_used()
                logging.debug(f"Reusing session {session.session_id} for video {video_id}")
                return session
        
        # Create new session
        session = ProxySession(video_id, self.proxy_config)
        self.sessions[video_id] = session
        
        logging.info(f"Created new proxy session {session.session_id} for video {video_id}")
        return session
    
    def rotate_session(self, video_id: str) -> Optional[ProxySession]:
        """Rotate (recreate) the session for a video_id after blocking"""
        if not self.enabled or not self.proxy_config:
            return None
        
        # Remove existing session if it exists
        if video_id in self.sessions:
            old_session = self.sessions[video_id]
            logging.info(f"Rotating session {old_session.session_id} for video {video_id}")
            del self.sessions[video_id]
        
        # Create new session (this will be the one retry allowed)
        session = ProxySession(video_id, self.proxy_config)
        self.sessions[video_id] = session
        
        logging.info(f"Created rotated session {session.session_id} for video {video_id}")
        return session
    
    def mark_session_blocked(self, video_id: str) -> None:
        """Mark a session as blocked by YouTube"""
        if video_id in self.sessions:
            self.sessions[video_id].mark_blocked()
    
    def mark_session_failed(self, video_id: str) -> None:
        """Mark a session as failed"""
        if video_id in self.sessions:
            self.sessions[video_id].mark_failed()
    
    def get_proxy_dict(self, session: ProxySession) -> Dict[str, str]:
        """Get proxy configuration in format suitable for requests library"""
        if not session:
            return {}
        
        # Use the sticky session proxy URL
        return {
            'http': session.proxy_url,
            'https': session.proxy_url
        }
    
    def get_session(self, key: str) -> Optional[ProxySession]:
        """Future-proof alias for get_session_for_video"""
        return self.get_session_for_video(key)
    
    def _cleanup_expired_sessions(self) -> None:
        """Remove expired sessions from memory"""
        ttl_minutes = self.proxy_config.get('session_ttl_minutes', 10) if self.proxy_config else 10
        expired_videos = []
        
        for video_id, session in self.sessions.items():
            if session.is_expired(ttl_minutes):
                expired_videos.append(video_id)
        
        for video_id in expired_videos:
            logging.debug(f"Cleaning up expired session for video {video_id}")
            del self.sessions[video_id]
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get statistics about current sessions"""
        if not self.enabled:
            return {"enabled": False}
        
        active_sessions = len(self.sessions)
        total_requests = sum(session.request_count for session in self.sessions.values())
        total_failures = sum(session.failed_count for session in self.sessions.values())
        blocked_sessions = sum(1 for session in self.sessions.values() if session.is_blocked)
        
        return {
            "enabled": True,
            "active_sessions": active_sessions,
            "total_requests": total_requests,
            "total_failures": total_failures,
            "blocked_sessions": blocked_sessions,
            "success_rate": (total_requests - total_failures) / max(total_requests, 1) * 100
        }
    
    def log_session_stats(self) -> None:
        """Log current session statistics"""
        stats = self.get_session_stats()
        if stats["enabled"]:
            logging.info(f"Proxy stats: {stats['active_sessions']} active sessions, "
                        f"{stats['success_rate']:.1f}% success rate, "
                        f"{stats['blocked_sessions']} blocked sessions")
