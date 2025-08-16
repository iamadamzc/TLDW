import os
import json
import time
import logging
import hashlib
import re
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from urllib.parse import quote, unquote
import boto3
from botocore.exceptions import ClientError

# Regex pattern for AWS ARN validation
ARN_PATTERN = re.compile(r"^arn:aws:secretsmanager:[\w-]+:\d{12}:secret:[\w+=,.@/-]+$")

def _normalize_credential(value: str) -> str:
    """
    Normalize potentially URL-encoded credentials by decoding once if needed.
    
    Heuristic: if the value contains any %XX sequence, try one decode pass.
    Safety: only decode if the result contains printable ASCII characters.
    
    This handles cases where credentials were mistakenly stored URL-encoded
    in AWS Secrets Manager, preventing double-encoding in proxy URLs.
    """
    if not value or '%' not in value:
        return value
    
    try:
        decoded = unquote(value)
        # Safety check: ensure decoded result contains only printable ASCII
        # Allow common whitespace chars (tab, newline, carriage return)
        if all(31 < ord(c) < 127 or c in '\t\n\r' for c in decoded):
            return decoded
    except Exception:
        # If decoding fails for any reason, return original value
        pass
    
    return value

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
        """Generate deterministic session ID from sanitized video_id (capped at 16 chars)"""
        # Sanitize to alphanumeric only and cap at 16 chars for proxy compatibility
        sanitized = re.sub(r'[^a-zA-Z0-9]', '', self.video_id)
        session_id = sanitized[:16]
        
        # Log the final session ID (never log password/URL)
        logging.debug(f"Generated session ID for video {self.video_id}: {session_id}")
        return session_id
    
    def _sanitize_video_id(self, video_id: str) -> str:
        """Sanitize video_id to alphanumeric only for sticky session"""
        return re.sub(r'[^a-zA-Z0-9]', '', video_id)
    
    def _build_proxy_url(self) -> str:
        """
        Build Oxylabs sticky session proxy URL with proper encoding
        Format: customer-<SUBUSER>-cc-<country>-sessid-<SESSION_ID>
        Note: -cc-<country> is omitted entirely when geo_enabled is False or country unspecified
        Hardcoded to residential entrypoint pr.oxylabs.io:7777
        """
        if not self.proxy_config:
            return ""
        
        # Get credentials from config
        subuser = self.proxy_config.get('username', '')  # SUBUSER from AWS Secrets Manager
        password = self.proxy_config.get('password', '')
        geo_enabled = self.proxy_config.get('geo_enabled', False)
        country = self.proxy_config.get('country', 'us')
        
        # Build sticky username - omit -cc-<country> segment entirely if not geo-enabled
        if geo_enabled:
            sticky_username = f"customer-{subuser}-cc-{country}-sessid-{self.session_id}"
        else:
            sticky_username = f"customer-{subuser}-sessid-{self.session_id}"
        
        # URL encode credentials (NEVER log password or full URL)
        encoded_username = quote(sticky_username, safe="")
        encoded_password = quote(password, safe="")
        
        # Build proxy URL with hardcoded residential entrypoint
        proxy_url = f"http://{encoded_username}:{encoded_password}@pr.oxylabs.io:7777"
        
        # Log only the sticky username (no password/full URL)
        logging.debug(f"Built sticky proxy for video {self.video_id}: {sticky_username}@pr.oxylabs.io:7777")
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
    
    @property
    def sticky_username(self) -> str:
        """Returns the sticky username without password for logging"""
        if not self.proxy_config:
            return ""
        
        subuser = self.proxy_config.get('username', '')
        geo_enabled = self.proxy_config.get('geo_enabled', False)
        country = self.proxy_config.get('country', '')
        
        # Build sticky username - omit -cc-<country> segment entirely if not geo-enabled
        if geo_enabled:
            return f"customer-{subuser}-cc-{country}-sessid-{self.session_id}"
        else:
            return f"customer-{subuser}-sessid-{self.session_id}"

class ProxyManager:
    """Manages sticky proxy sessions for YouTube transcript fetching"""
    
    def __init__(self):
        self.sessions: Dict[str, ProxySession] = {}
        self.proxy_config = None
        self.enabled = os.getenv('USE_PROXIES', 'true').lower() == 'true'
        self.config_source = "unknown"  # Track how config was loaded for diagnostics
        
        if self.enabled:
            self._load_proxy_config()
            logging.info("ProxyManager initialized with Oxylabs proxy")
        else:
            logging.info("ProxyManager initialized but proxies disabled")
    
    def _is_json(self, value: str) -> bool:
        """Check if a string looks like JSON"""
        return value and value.strip().startswith(("{", "["))
    
    def _is_arn(self, value: str) -> bool:
        """Check if a string is a valid AWS ARN"""
        return bool(ARN_PATTERN.match(value))
    
    def _load_proxy_config(self) -> None:
        """Load proxy configuration with App Runner RuntimeEnvironmentSecrets support"""
        try:
            # Get the raw value from environment variable
            raw_config = os.getenv('OXYLABS_PROXY_CONFIG', '').strip()
            
            if not raw_config:
                raise ValueError("OXYLABS_PROXY_CONFIG environment variable is empty")
            
            # Normalize accidental quotes that might wrap the value
            if raw_config.startswith(("'", '"')) and raw_config.endswith(("'", '"')):
                raw_config = raw_config[1:-1].strip()
            
            # Detect the type of configuration we received
            if self._is_json(raw_config):
                # App Runner RuntimeEnvironmentSecrets case: env var contains the secret value (JSON)
                logging.info("ProxyManager: using inline JSON from App Runner RuntimeEnvironmentSecrets")
                self.proxy_config = json.loads(raw_config)
                
            elif self._is_arn(raw_config):
                # Manual ARN case: fetch from Secrets Manager
                logging.info("ProxyManager: fetching proxy config via ARN from Secrets Manager")
                region = os.getenv('AWS_REGION', 'us-west-2')
                client = boto3.Session().client('secretsmanager', region_name=region)
                response = client.get_secret_value(SecretId=raw_config)
                self.proxy_config = json.loads(response['SecretString'])
                
            elif raw_config and all(c.isalnum() or c in "-/_+=.@!" for c in raw_config):
                # Secret name case: fetch from Secrets Manager by name
                logging.info("ProxyManager: fetching proxy config by name from Secrets Manager")
                region = os.getenv('AWS_REGION', 'us-west-2')
                client = boto3.Session().client('secretsmanager', region_name=region)
                response = client.get_secret_value(SecretId=raw_config)
                self.proxy_config = json.loads(response['SecretString'])
                
            elif raw_config.startswith(("http://", "https://")):
                # Direct URL case: use as proxy URL
                logging.info("ProxyManager: using direct proxy URL from environment")
                self.proxy_config = {"url": raw_config}
                
            else:
                raise ValueError(f"OXYLABS_PROXY_CONFIG format not recognized. Provide JSON, ARN, secret name, or URL. Got: {raw_config[:50]}...")
            
            # Set config source for diagnostics
            if self._is_json(raw_config):
                self.config_source = "env_json"
            elif self._is_arn(raw_config):
                self.config_source = "arn"
            elif raw_config.startswith(("http://", "https://")):
                self.config_source = "url"
            else:
                self.config_source = "name"
            
            # Handle URL-only configuration
            if "url" in self.proxy_config and len(self.proxy_config) == 1:
                logging.info(f"Using direct proxy URL configuration (source: {self.config_source})")
                return
            
            # Validate required fields for credential-based configuration
            required_fields = ['username', 'password']
            for field in required_fields:
                if field not in self.proxy_config:
                    raise ValueError(f"Missing required field '{field}' in proxy configuration")
            
            # Normalize credentials if they appear to be URL-encoded
            raw_user = self.proxy_config.get('username', '')
            raw_pass = self.proxy_config.get('password', '')
            
            # Apply normalization to detect and fix URL-encoded credentials
            normalized_user = _normalize_credential(raw_user)
            normalized_pass = _normalize_credential(raw_pass)
            
            # Log if normalization changed values (mask sensitive data)
            if normalized_user != raw_user:
                user_prefix = normalized_user[:3] + "***" if len(normalized_user) > 3 else "***"
                logging.info(f"Detected percent-encoded proxy username; applied single decode pass: {user_prefix}")
            
            if normalized_pass != raw_pass:
                logging.info("Detected percent-encoded proxy password; applied single decode pass before URL-encoding")
            
            # Update config with normalized credentials
            self.proxy_config['username'] = normalized_user
            self.proxy_config['password'] = normalized_pass
            
            # Set defaults for optional fields
            self.proxy_config.setdefault('session_ttl_minutes', 30)
            self.proxy_config.setdefault('timeout_seconds', 15)
            
            # Configure geo settings - enable by default for MVP reliability
            # Check environment variable first, then config, then default to enabled with 'us'
            env_country = os.getenv('PROXY_COUNTRY')
            if env_country:
                self.proxy_config['geo_enabled'] = True
                self.proxy_config['country'] = env_country
                logging.info(f"Using geo country from environment: {env_country}")
            else:
                # Enable geo by default for MVP reliability (avoid "hot" random IPs)
                self.proxy_config.setdefault('geo_enabled', True)
                self.proxy_config.setdefault('country', 'us')
            
            # Store SUBUSER for easy access
            self.subuser = self.proxy_config['username']
            self.geo_enabled = self.proxy_config['geo_enabled']
            self.country = self.proxy_config.get('country', 'us')
            
            # Log with masked username for troubleshooting (show first 4 chars)
            masked_username = self.subuser[:4] + "***" if len(self.subuser) > 4 else "***"
            logging.info(f"Loaded proxy config - source: {self.config_source}, username: {masked_username}, geo_enabled: {self.geo_enabled}, country: {self.country}")
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'ResourceNotFoundException':
                logging.error(f"Proxy secret not found: {raw_config[:50]}... (detected as {self.config_source})")
            elif error_code in ['AccessDenied', 'UnauthorizedOperation']:
                logging.error(f"IAM access denied for proxy secret - check instance role permissions")
            elif error_code == 'ValidationException':
                logging.error(f"Secret name validation failed - this suggests the env var contains secret value, not ARN/name")
                logging.error(f"Raw config (first 50 chars): {raw_config[:50]}...")
                logging.error("If using App Runner RuntimeEnvironmentSecrets, the env var should contain JSON, not ARN")
            else:
                logging.error(f"AWS Secrets Manager error ({error_code}): {e}")
            self.enabled = False
            raise
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse proxy configuration JSON: {e}")
            logging.error(f"Raw config (first 50 chars): {raw_config[:50]}...")
            self.enabled = False
            raise
        except ValueError as e:
            logging.error(f"Invalid proxy configuration: {e}")
            self.enabled = False
            raise
        except Exception as e:
            logging.error(f"Unexpected error loading proxy configuration: {e}")
            logging.error(f"Raw config (first 50 chars): {raw_config[:50]}...")
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
        """
        Rotate (recreate) the session for a video_id after blocking
        Note: With deterministic session IDs, rotation creates a new session with timestamp suffix
        """
        if not self.enabled or not self.proxy_config:
            return None
        
        # Remove existing session if it exists
        if video_id in self.sessions:
            old_session = self.sessions[video_id]
            logging.info(f"Rotating session {old_session.session_id} for video {video_id}")
            del self.sessions[video_id]
        
        # For rotation, append timestamp to video_id to create different session ID
        rotation_video_id = f"{video_id}_{int(time.time())}"
        
        # Create new session with modified video_id for different session ID
        session = ProxySession(rotation_video_id, self.proxy_config)
        # But store it under original video_id
        session.video_id = video_id  # Keep original video_id for reference
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
    
    def handle_407_error(self, video_id: str) -> bool:
        """
        Handle 407 Proxy Authentication Required error
        Returns True if secrets were refreshed and retry should be attempted
        """
        logging.error(f"407 Proxy Authentication Required for video {video_id} - "
                     f"hint='check URL-encoding or secret password'")
        
        # Attempt one-time secrets refresh for resilience
        try:
            logging.info("Attempting to refresh proxy credentials from AWS Secrets Manager")
            old_config = self.proxy_config.copy() if self.proxy_config else {}
            
            # Reload configuration
            self._load_proxy_config()
            
            # Check if credentials actually changed
            if (old_config.get('username') != self.proxy_config.get('username') or 
                old_config.get('password') != self.proxy_config.get('password')):
                logging.info("Proxy credentials refreshed - retry may succeed")
                return True
            else:
                logging.warning("Proxy credentials unchanged after refresh - likely secret is misformatted (e.g., already URL-encoded). See runbook: store RAW creds in secret JSON.")
                return False
                
        except Exception as e:
            logging.error(f"Failed to refresh proxy credentials: {e}")
            return False
    
    def validate_proxy_config(self) -> bool:
        """Validate proxy configuration and credentials"""
        if not self.proxy_config:
            return False
        
        required_fields = ['username', 'password']
        for field in required_fields:
            if not self.proxy_config.get(field):
                logging.error(f"Proxy configuration missing required field: {field}")
                return False
        
        # Validate username format (should not contain spaces or invalid chars)
        username = self.proxy_config['username']
        if ' ' in username or '@' in username:
            logging.warning(f"Proxy username may need URL encoding: {username}")
        
        return True
    
    def get_proxy_health_info(self) -> Dict[str, Any]:
        """Get proxy configuration health info for diagnostics (no sensitive data)"""
        if not self.enabled:
            return {"enabled": False, "status": "disabled", "source": "disabled"}
        
        if not self.proxy_config:
            return {"enabled": True, "status": "not_configured", "source": "unknown"}
        
        # Basic health info without exposing credentials
        health_info = {
            "enabled": True,
            "status": "configured",
            "source": getattr(self, 'config_source', 'unknown'),
            "has_username": bool(self.proxy_config.get('username')),
            "has_password": bool(self.proxy_config.get('password')),
            "geo_enabled": getattr(self, 'geo_enabled', False),
            "country": getattr(self, 'country', 'unknown'),
            "session_ttl_minutes": self.proxy_config.get('session_ttl_minutes', 30)
        }
        
        # Add masked username for troubleshooting
        if hasattr(self, 'subuser') and self.subuser:
            health_info["username_prefix"] = self.subuser[:4] + "***" if len(self.subuser) > 4 else "***"
        
        # Add diagnostic field for credential encoding detection
        if self.proxy_config.get('username') and self.proxy_config.get('password'):
            # Check if original credentials (before normalization) looked percent-encoded
            # This is purely for diagnostics - we don't store the original values
            raw_user = self.proxy_config.get('username', '')
            raw_pass = self.proxy_config.get('password', '')
            
            # Heuristic: if credentials contain common URL-encoded sequences, flag for diagnostics
            looks_encoded = (
                '%' in raw_user or '%' in raw_pass or
                any(seq in raw_user + raw_pass for seq in ['%40', '%3A', '%2B', '%5F', '%21'])
            )
            health_info["looks_percent_encoded_password"] = looks_encoded
        
        # Handle URL-only configuration
        if "url" in self.proxy_config and len(self.proxy_config) == 1:
            health_info.update({
                "has_username": True,  # URL contains credentials
                "has_password": True,
                "geo_enabled": False,
                "country": "unknown",
                "looks_percent_encoded_password": False  # URL format doesn't apply
            })
        
        return health_info
    
    def test_proxy_connectivity(self) -> Dict[str, Any]:
        """Test proxy connectivity without exposing credentials"""
        if not self.enabled or not self.proxy_config:
            return {"test_performed": False, "reason": "proxy_disabled_or_not_configured"}
        
        try:
            # Create a test session
            test_session = ProxySession("test_connectivity", self.proxy_config)
            
            # Test with a simple HTTP request (not YouTube to avoid blocking)
            import requests
            test_url = "http://httpbin.org/ip"
            
            response = requests.get(
                test_url,
                proxies={"http": test_session.proxy_url, "https": test_session.proxy_url},
                timeout=10
            )
            
            if response.status_code == 200:
                return {
                    "test_performed": True,
                    "status": "success",
                    "response_code": response.status_code,
                    "proxy_ip": response.json().get("origin", "unknown")
                }
            else:
                return {
                    "test_performed": True,
                    "status": "failed",
                    "response_code": response.status_code
                }
                
        except Exception as e:
            return {
                "test_performed": True,
                "status": "error",
                "error": str(e)
            }
