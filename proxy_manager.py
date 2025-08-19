# Core Python modules
import os
import json
import uuid
import time
import random
import secrets
import hashlib
import logging
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote, unquote, urlparse
from typing import Dict, Optional, Tuple

# Third-party modules
import boto3
import requests

# Exception hierarchy
class ProxyError(Exception):
    """Base proxy error"""
    pass

class ProxyConfigError(ProxyError):
    """Local proxy configuration issues"""
    pass

class ProxyAuthError(ProxyError):
    """Proxy authentication failure (401/407)"""
    pass

class ProxyValidationError(ProxyError):
    """Secret validation failure"""
    pass

def looks_preencoded(pw: str) -> bool:
    """Detect if password was already URL-encoded"""
    try:
        # If unquoting and re-quoting gives the same result, it was pre-encoded
        decoded = unquote(pw)
        re_encoded = quote(decoded, safe="")
        return re_encoded == pw and decoded != pw
    except Exception:
        return False

@dataclass
class ProxySecret:
    provider: str
    host: str
    port: int
    username: str          # base username, no -sessid-
    password: str          # RAW (not URL-encoded)
    geo_enabled: bool = False
    country: Optional[str] = None
    version: int = 1
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'ProxySecret':
        """Validate and create ProxySecret from dict with diagnostic logging"""
        req = ["provider", "host", "port", "username", "password"]
        for k in req:
            v = d.get(k)
            if v is None or (isinstance(v, str) and not v.strip()):
                raise ProxyValidationError(f"proxy_secret_missing_{k}")
        
        host = str(d["host"])
        if host.startswith(("http://", "https://")):
            raise ProxyValidationError("proxy_secret_host_contains_scheme")
        
        # Enhanced diagnostic logging for password validation
        pw = str(d["password"])
        username = str(d["username"])
        
        # Mask username for logging (show first 4 + last 2 chars)
        masked_username = username[:4] + "***" + username[-2:] if len(username) > 6 else username[:2] + "***"
        
        # Check for pre-encoding with detailed diagnostics
        is_preencoded = looks_preencoded(pw)
        has_common_encoded = any(encoded in pw for encoded in ['%2B', '%25', '%21', '%40', '%3A'])
        
        # Log diagnostic information
        import logging
        logging.info(f"🔍 Proxy secret validation: username={masked_username}, "
                    f"password_looks_preencoded={is_preencoded}, "
                    f"has_common_encoded_chars={has_common_encoded}")
        
        if is_preencoded:
            logging.error(f"❌ PROXY SECRET VALIDATION FAILED: Password appears to be URL-encoded!")
            logging.error(f"💡 Fix: Store RAW password in AWS Secrets Manager (the one with + literally, not %2B)")
            logging.error(f"🔧 Current password contains encoded characters - this will cause 407 errors")
            raise ProxyValidationError("proxy_secret_password_looks_urlencoded")
        
        if has_common_encoded:
            logging.warning(f"⚠️  Password contains %-encoded sequences but passed validation check")
            logging.warning(f"💡 If you see 407 errors, verify password is truly RAW in AWS Secrets Manager")
        
        logging.info(f"✅ Proxy secret validation passed: RAW format confirmed")
        
        return cls(
            provider=str(d["provider"]).lower(),
            host=host,
            port=int(d["port"]),
            username=str(d["username"]),
            password=pw,
            geo_enabled=bool(d.get("geo_enabled", False)),
            country=str(d.get("country")) if d.get("country") else None,
            version=int(d.get("version", 1)),
        )
        
    def build_username_with_session(self, session_token: str) -> str:
        """Create session-specific username"""
        base = self.username.split("-sessid-")[0]
        return f"{base}-sessid-{session_token}"
        
    def build_proxy_url(self, session_token: Optional[str] = None) -> str:
        """Build proxy URL with runtime password encoding"""
        user = self.username
        return f"http://{user}:{quote(self.password, safe='')}@{self.host}:{self.port}"

@dataclass
class PreflightResult:
    healthy: bool
    timestamp: datetime
    ttl_seconds: int
    error_message: Optional[str] = None
    
class PreflightCache:
    def __init__(self, default_ttl: int = int(os.getenv("OXY_PREFLIGHT_TTL_SECONDS", "300"))):
        self._cache: Optional[PreflightResult] = None
        self._jitter = 0.10
        self._default_ttl = default_ttl
        
    def get(self) -> Optional[PreflightResult]:
        """Get cached result if not expired"""
        return self._cache
        
    def set(self, healthy: bool, error_message: Optional[str] = None):
        """Cache new result with jittered TTL"""
        jitter_factor = 1 + random.uniform(-self._jitter, self._jitter)
        ttl = max(1, int(self._default_ttl * jitter_factor))  # Ensure minimum 1 second
        self._cache = PreflightResult(
            healthy=healthy, 
            timestamp=datetime.utcnow(), 
            ttl_seconds=ttl, 
            error_message=error_message
        )
        
    def is_expired(self) -> bool:
        """Check if cache needs refresh"""
        if not self._cache:
            return True
        age = (datetime.utcnow() - self._cache.timestamp).total_seconds()
        return age >= self._cache.ttl_seconds

class BoundedBlacklist:
    """Thread-safe bounded blacklist with TTL"""
    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        self.max_size = max_size
        self.ttl = ttl
        self._items = deque()
        self._lookup = set()
        self._lock = threading.Lock()
        
    def add(self, token: str):
        with self._lock:
            if token in self._lookup:
                return
            
            now = time.time()
            self._items.append((token, now))
            self._lookup.add(token)
            
            # Cleanup expired and enforce size limit
            self._cleanup(now)
            
    def __contains__(self, token: str) -> bool:
        """Check if token is blacklisted"""
        with self._lock:
            return token in self._lookup
            
    def _cleanup(self, now: float):
        # Remove expired items
        while self._items and time.time() - self._items[0][1] > self.ttl:
            old_token, _ = self._items.popleft()
            self._lookup.discard(old_token)
            
        # Enforce size limit
        while len(self._items) > self.max_size:
            old_token, _ = self._items.popleft()
            self._lookup.discard(old_token)

class SafeStructuredLogger:
    LEVELS = {"debug": 10, "info": 20, "warning": 30, "error": 40, "critical": 50}
    
    def __init__(self, base_logger):
        self.logger = base_logger
        
    def log_event(self, level: str, message: str, **kwargs):
        """Log structured event, using deny-list for sensitive fields"""
        try:
            # Convert string level to int
            log_level = self.LEVELS.get(level.lower(), 20)
            
            # Sanitize fields and wrap under 'evt' to avoid LogRecord collisions
            safe_data = self._sanitize_fields(kwargs)
            self.logger.log(log_level, message, extra={"evt": safe_data})
        except Exception:
            # Never crash the pipeline due to logging
            try:
                self.logger.error(f"Logging failed for: {message}")
            except:
                pass  # Ultimate fallback - never crash
            
    def _sanitize_fields(self, data: Dict) -> Dict:
        """Remove sensitive data using deny-list, ensure serializability"""
        deny_fields = {"password", "proxy_url", "username"}  # Strip sensitive fields
        result = {}
        
        for k, v in data.items():
            if k in deny_fields:
                continue  # Skip sensitive fields
                
            try:
                # Ensure value is JSON-serializable
                json.dumps(v)
                result[k] = v
            except (TypeError, ValueError):
                result[k] = str(v)  # Fallback to string representation
                
        return result

class ProxyManager:
    def __init__(self, secret_dict: Optional[Dict] = None, logger=None):
        """Initialize ProxyManager with resilient secret handling"""
        self.logger = SafeStructuredLogger(logger or logging.getLogger(__name__))
        self.in_use = False
        self.secret = None
        self.preflight_cache = PreflightCache()
        self.session_blacklist = BoundedBlacklist(max_size=1000, ttl=3600)
        self._preflight_lock = threading.Lock()
        self._preflight_count = 0
        self._preflight_window_start = time.time()
        self._healthy: Optional[bool] = None
        
        # Get secret name from environment variable for logging
        self.secret_name = os.getenv('PROXY_SECRET_NAME', 'proxy-secret')
        
        # Optional: allow disabling preflight for local dev
        self.preflight_disabled = os.getenv("OXY_PREFLIGHT_DISABLED", "false").lower() == "true"
        
        # Initialize proxy configuration with graceful error handling
        try:
            if secret_dict is None:
                secret_dict = self._fetch_secret()
            
            if self._validate_secret_schema(secret_dict):
                self.secret = ProxySecret.from_dict(secret_dict)
                self.in_use = True
                self.logger.log_event("info", f"ProxyManager initialized successfully", 
                                    secret_name=self.secret_name, provider=self.secret.provider)
            else:
                self.logger.log_event("warning", "Invalid proxy secret schema, continuing without proxies",
                                    secret_name=self.secret_name)
        except Exception as e:
            self.logger.log_event("error", f"Proxy initialization failed: {e}, continuing without proxies",
                                secret_name=self.secret_name, error_type=type(e).__name__)
    
    def _fetch_secret(self) -> Dict:
        """Fetch secret from AWS Secrets Manager"""
        secret_name = os.getenv("PROXY_SECRET_NAME")
        if not secret_name:
            self.logger.log_event("warning", "PROXY_SECRET_NAME environment variable not set")
            return {}

        region_name = os.getenv("AWS_REGION", "us-west-2")
        session = boto3.session.Session()
        client = session.client(service_name='secretsmanager', region_name=region_name)

        try:
            get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        except Exception as e:
            self.logger.log_event("error", f"Failed to fetch secret '{secret_name}' from AWS Secrets Manager: {e}")
            return {}
        else:
            if 'SecretString' in get_secret_value_response:
                secret = get_secret_value_response['SecretString']
                return json.loads(secret)
            else:
                self.logger.log_event("error", f"Secret '{secret_name}' does not contain a SecretString")
                return {}
    
    def _validate_secret_schema(self, secret_data: Dict) -> bool:
        """Validate that secret contains all required fields"""
        if not secret_data:
            self.logger.log_event("warning", "Proxy secret is empty", secret_name=self.secret_name)
            return False
            
        required_fields = ["provider", "host", "port", "username", "password"]
        missing_fields = [field for field in required_fields if field not in secret_data]
        
        if missing_fields:
            self.logger.log_event("warning", f"Proxy secret missing required fields: {missing_fields}",
                                secret_name=self.secret_name, missing_fields=missing_fields)
            return False
        
        # Validate field values are not empty
        empty_fields = [field for field in required_fields 
                       if not secret_data[field] or (isinstance(secret_data[field], str) and not secret_data[field].strip())]
        
        if empty_fields:
            self.logger.log_event("warning", f"Proxy secret has empty fields: {empty_fields}",
                                secret_name=self.secret_name, empty_fields=empty_fields)
            return False
            
        return True
        
    @property
    def healthy(self) -> Optional[bool]:
        """Get cached health status"""
        if self._healthy is not None:
            return self._healthy
        cached = self.preflight_cache.get()
        return cached.healthy if cached else None
        
    def preflight(self, timeout: float = 5.0) -> bool:
        """Perform cached preflight check with stampede control"""
        if not self.in_use or self.secret is None:
            self.logger.log_event("info", "Proxy not in use, skipping preflight")
            self._healthy = False
            return False
            
        if self.preflight_disabled:
            self.logger.log_event("info", "Proxy preflight disabled via OXY_PREFLIGHT_DISABLED")
            self._healthy = True
            return True
            
        # Rate limiting: max 10 preflights per minute
        now = time.time()
        if now - self._preflight_window_start > 60:
            self._preflight_count = 0
            self._preflight_window_start = now
        
        max_per_minute = int(os.getenv("OXY_PREFLIGHT_MAX_PER_MINUTE", "10"))
        if self._preflight_count >= max_per_minute:
            cached = self.preflight_cache.get()
            return cached.healthy if cached else False
            
        with self._preflight_lock:  # Single-flight
            cached = self.preflight_cache.get()
            if cached and not self.preflight_cache.is_expired():
                self._healthy = cached.healthy
                return cached.healthy
            
            self._preflight_count += 1
            
            # Perform actual preflight with enhanced out-of-band validation
            proxies = self.proxies_for(None)
            
            # --- ADD THESE TWO LINES FOR DEBUGGING ---
            full_proxy_user = urlparse(proxies.get("https", "")).username
            logging.info(f"DIAGNOSTIC_LOG: Full proxy username being sent is: {full_proxy_user}")
            # -----------------------------------------
            
            session_token = extract_session_from_proxies(proxies)
            
            # Enhanced: Test with httpbin.org/ip first for pure proxy validation
            try:
                r = requests.get("http://httpbin.org/ip", proxies=proxies, timeout=timeout)
                if r.status_code == 200:
                    # Log proxy validation success with masked username
                    proxy_username = extract_session_from_proxies(proxies)
                    masked_username = f"...{proxy_username[-4:]}" if len(proxy_username) > 4 else "***"
                    self.logger.log_event("info", f"Proxy out-of-band validation ok: httpbin returned 200, proxy_user={masked_username}")
                    
                    # Continue with YouTube-specific validation
                    for url in ("https://www.youtube.com/generate_204", "https://httpbin.org/status/204"):
                        try:
                            r = requests.get(url, proxies=proxies, timeout=timeout)
                            if r.status_code == 204:
                                self.preflight_cache.set(True)
                                self._healthy = True
                                self.logger.log_event("info", "Proxy preflight ok: status=204")
                                return True
                            if r.status_code in (401, 407):
                                self.preflight_cache.set(False, f"auth_{r.status_code}")
                                self._healthy = False
                                self.logger.log_event("warning", f"Proxy preflight auth failed: status={r.status_code}")
                                raise ProxyAuthError(f"proxy_auth_failed_{r.status_code}")
                            r.raise_for_status()
                        except requests.RequestException as e:
                            continue  # Try next URL
                    
                    # All YouTube URLs failed but httpbin worked - likely YouTube blocking
                    self.preflight_cache.set(False, "youtube_blocked")
                    self._healthy = False
                    raise ProxyConfigError("proxy_preflight_youtube_blocked")
                    
                elif r.status_code in (401, 407):
                    # Proxy auth failed at httpbin level - definitive failure
                    self.preflight_cache.set(False, f"httpbin_auth_{r.status_code}")
                    self._healthy = False
                    self.logger.log_event("warning", f"Proxy auth failed at httpbin: status={r.status_code}")
                    raise ProxyAuthError(f"proxy_auth_failed_{r.status_code}")
                else:
                    # Unexpected httpbin response
                    self.logger.log_event("warning", f"Unexpected httpbin response: {r.status_code}")
                    
            except requests.RequestException as e:
                self.logger.log_event("warning", f"Httpbin preflight failed: {e}")
                # Fall back to original YouTube-only validation
                pass
            
            # Fallback: Original validation if httpbin fails
            last_err = None
            for url in ("https://www.youtube.com/generate_204", "https://httpbin.org/status/204"):
                try:
                    r = requests.get(url, proxies=proxies, timeout=timeout)
                    if r.status_code == 204:
                        self.preflight_cache.set(True)
                        self._healthy = True
                        self.logger.log_event("info", "Proxy preflight ok: status=204 (fallback)")
                        return True
                    if r.status_code in (401, 407):
                        self.preflight_cache.set(False, f"auth_{r.status_code}")
                        self._healthy = False
                        self.logger.log_event("warning", f"Proxy preflight auth failed: status={r.status_code}")
                        raise ProxyAuthError(f"proxy_auth_failed_{r.status_code}")
                    r.raise_for_status()
                except requests.RequestException as e:
                    last_err = e
                    continue
            
            # All URLs failed
            self.preflight_cache.set(False, str(last_err) if last_err else "unknown")
            self._healthy = False
            raise ProxyConfigError(f"proxy_preflight_unreachable: {last_err}")
        
    def proxies_for(self, video_id: Optional[str] = None) -> Dict[str, str]:
        """Get proxy config with unique session"""
        if not self.in_use or self.secret is None:
            self.logger.log_event("debug", "Proxy not available, returning empty config")
            return {}
            
        token = self._generate_session_token(video_id)
        # Ensure we don't reuse blacklisted tokens
        while token in self.session_blacklist:
            token = self._generate_session_token(video_id)
        
        return {"http": self.secret.build_proxy_url(token), 
                "https": self.secret.build_proxy_url(token)}
        
    def _generate_session_token(self, video_id: Optional[str] = None) -> str:
        """Generate cryptographically secure session token"""
        base_token = secrets.token_urlsafe(12)
        if video_id:
            # Add short video hash for locality
            video_hash = hashlib.sha256(video_id.encode()).hexdigest()[:6]
            return f"{video_hash}{base_token}"
        return base_token
        
    def rotate_session(self, failed_token: str):
        """Blacklist failed session and force new token"""
        if not self.in_use or self.secret is None:
            self.logger.log_event("debug", "Proxy not in use, skipping session rotation")
            return
            
        # Only log last 4 chars to prevent token leakage
        self.logger.log_event("info", f"Blacklisting session: ...{failed_token[-4:]}")
        self.session_blacklist.add(failed_token)

# Helper functions for health endpoints and error responses
def generate_correlation_id() -> str:
    """Generate UUID for request correlation"""
    return str(uuid.uuid4())

def validate_raw_secret(secret_data: Dict) -> Tuple[bool, str]:
    """
    Validate that a secret is in RAW format (not pre-encoded)
    Returns (is_valid, diagnostic_message)
    """
    try:
        username = secret_data.get('username', '')
        password = secret_data.get('password', '')
        
        # Mask username for logging
        masked_username = username[:4] + "***" + username[-2:] if len(username) > 6 else username[:2] + "***"
        
        # Check for pre-encoding
        is_preencoded = looks_preencoded(password)
        has_common_encoded = any(encoded in password for encoded in ['%2B', '%25', '%21', '%40', '%3A'])
        
        if is_preencoded or has_common_encoded:
            return False, f"Secret for {masked_username} appears URL-encoded (has_encoded_chars={has_common_encoded})"
        
        return True, f"Secret for {masked_username} is RAW format"
        
    except Exception as e:
        return False, f"Secret validation error: {e}"

def extract_session_from_proxies(proxies: Dict[str, str]) -> str:
    """Extract session token from proxy URL"""
    try:
        username = urlparse(proxies["https"]).username or ""
        return username.split("-sessid-")[1]
    except Exception:
        return ""

def validate_raw_secret(secret_data: Dict) -> tuple:
    """
    Validate that a secret is in RAW format (not pre-encoded)
    Returns (is_valid, diagnostic_message)
    """
    try:
        username = secret_data.get('username', '')
        password = secret_data.get('password', '')
        
        # Mask username for logging
        masked_username = username[:4] + "***" + username[-2:] if len(username) > 6 else username[:2] + "***"
        
        # Check for pre-encoding
        is_preencoded = looks_preencoded(password)
        has_common_encoded = any(encoded in password for encoded in ['%2B', '%25', '%21', '%40', '%3A'])
        
        if is_preencoded or has_common_encoded:
            return False, f"Secret for {masked_username} appears URL-encoded (has_encoded_chars={has_common_encoded})"
        
        return True, f"Secret for {masked_username} is RAW format"
        
    except Exception as e:
        return False, f"Secret validation error: {e}"

# HTTP Status Code Mapping
HTTP_MAP = {
    "PROXY_AUTH_FAILED": 502,    # 401/407 upstream
    "PROXY_MISCONFIGURED": 502,  # Invalid secret format
    "PROXY_UNREACHABLE": 503,    # Network connectivity issues
}

def error_response(code: str, correlation_id: str, message: Optional[str] = None, details: Optional[Dict] = None):
    """Generate standardized error response"""
    body = {
        "code": code,
        "message": message or {
            "PROXY_AUTH_FAILED": "Proxy authentication failed. Ensure RAW creds (not URL-encoded) and host/port present.",
            "PROXY_MISCONFIGURED": "Proxy secret invalid. See required schema.",
            "PROXY_UNREACHABLE": "Proxy unreachable. Try again later.",
        }.get(code, "Unexpected error"),
        "correlation_id": correlation_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "details": details or {},
    }
    return body, HTTP_MAP.get(code, 500)

# Status codes that trigger session rotation
BLOCK_STATUSES = {401, 403, 407, 429}

# Legacy compatibility - keep existing interface for gradual migration
class ProxySession:
    """Legacy compatibility wrapper"""
    
    def __init__(self, video_id: str, proxy_config: Dict):
        self.video_id = video_id
        self.proxy_config = proxy_config
        self.created_at = datetime.now()
        self.last_used = datetime.now()
        self.request_count = 0
        self.failed_count = 0
        self.is_blocked = False
        
        # Create new ProxyManager for this session
        try:
            self._proxy_manager = ProxyManager(proxy_config, logging.getLogger(__name__))
            proxies = self._proxy_manager.proxies_for(video_id)
            self.proxy_url = proxies.get("https", "")
            self.session_id = extract_session_from_proxies(proxies)
        except Exception as e:
            logging.error(f"Failed to create proxy session: {e}")
            self.proxy_url = ""
            self.session_id = "error"
        
        self.expires_at = datetime.now()
        
    def mark_used(self):
        self.last_used = datetime.now()
        self.request_count += 1
    
    def mark_failed(self):
        self.failed_count += 1
        
    def mark_blocked(self):
        self.is_blocked = True
        self.failed_count += 1
        
    def is_expired(self, ttl_minutes: int = 30) -> bool:
        return False  # Let new system handle expiration
    
    @property
    def sticky_username(self) -> str:
        try:
            return urlparse(self.proxy_url).username or ""
        except:
            return ""
