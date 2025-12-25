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

# Job-scoped session management
_job_sessions: Dict[str, str] = {}
_job_sessions_lock = threading.Lock()

# YouTube preflight URLs for testing
_YT_PREFLIGHT_URLS = [
    "https://www.youtube.com/generate_204",
    "https://i.ytimg.com/generate_204",
    "https://redirector.googlevideo.com/generate_204",
]

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
    session_ttl_minutes: int = 10
    geo_enabled: bool = False
    country: Optional[str] = None
    version: int = 1
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'ProxySecret':
        """Validate and create ProxySecret from dict with diagnostic logging"""
        # Core fields that must not be empty
        core_req = ["provider", "host", "port"]
        for k in core_req:
            v = d.get(k)
            if v is None or (isinstance(v, str) and not v.strip()):
                raise ProxyValidationError(f"proxy_secret_missing_{k}")

        # Auth fields that must exist but can be empty for IP whitelisting
        auth_req = ["username", "password"]
        for k in auth_req:
            if d.get(k) is None:
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
            session_ttl_minutes=int(d.get("session_ttl_minutes", 10)),
            geo_enabled=bool(d.get("geo_enabled", False)),
            country=str(d.get("country")) if d.get("country") else None,
            version=int(d.get("version", 1)),
        )
        
    def build_username_with_session(self, session_token: str) -> str:
        """Create session-specific username with session time"""
        base = self.username.split("-sessid-")[0]
        # Use the session_ttl_minutes value from the secret
        ttl = self.session_ttl_minutes 
        return f"{base}-sessid-{session_token}-sesstime-{ttl}"
        
    def build_proxy_url(self, session_token: Optional[str] = None) -> str:
        """Build proxy URL with runtime password encoding"""
        user = self.username if session_token is None else self.build_username_with_session(session_token)
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
        # Explicitly initialize in_use to False. It will be set to True upon successful secret validation.
        self.in_use = False
        self.secret = None
        self.preflight_cache = PreflightCache()
        self.session_blacklist = BoundedBlacklist(max_size=1000, ttl=3600)
        self._preflight_lock = threading.Lock()
        self._preflight_count = 0
        self._preflight_window_start = time.time()
        self._healthy: Optional[bool] = None
        
        # Health metrics tracking - Requirement 16.1, 16.5
        self._preflight_hits = 0
        self._preflight_misses = 0
        self._preflight_total = 0
        self._last_preflight_time: Optional[float] = None
        self._preflight_durations = deque(maxlen=100)  # Keep last 100 durations for performance metrics
        
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
        
        # For IP Whitelisting, username/password can be empty.
        # Only validate that provider, host, and port are not empty.
        core_fields = ["provider", "host", "port"]
        empty_fields = [field for field in core_fields
                       if not secret_data.get(field) or (isinstance(secret_data.get(field), str) and not str(secret_data.get(field)).strip())]

        if empty_fields:
            self.logger.log_event("warning", f"Proxy secret has empty fields: {empty_fields}",
                                secret_name=self.secret_name, empty_fields=empty_fields)
            return False
            
        return True
        
    @property
    def healthy(self) -> Optional[bool]:
        """Get cached health status - Requirement 16.3"""
        if self._healthy is not None:
            return self._healthy
        cached = self.preflight_cache.get()
        return cached.healthy if cached else None
    
    def _get_masked_username_tail(self) -> str:
        """Get masked username tail for identification - Requirement 16.2"""
        if not self.secret or not self.secret.username:
            return "***"
        
        username = self.secret.username
        if len(username) <= 4:
            return "***"
        
        # Show last 4 characters for identification
        return f"...{username[-4:]}"
    
    def get_preflight_metrics(self) -> Dict[str, any]:
        """Get preflight performance metrics - Requirement 16.5"""
        hit_rate = (self._preflight_hits / self._preflight_total) if self._preflight_total > 0 else 0.0
        
        # Calculate average duration from recent preflights
        avg_duration_ms = 0.0
        if self._preflight_durations:
            avg_duration_ms = sum(self._preflight_durations) / len(self._preflight_durations) * 1000
        
        return {
            "preflight_hits": self._preflight_hits,
            "preflight_misses": self._preflight_misses,
            "preflight_total": self._preflight_total,
            "hit_rate": round(hit_rate, 3),
            "avg_duration_ms": round(avg_duration_ms, 2),
            "last_check_time": self._last_preflight_time,
            "proxy_username_tail": self._get_masked_username_tail(),
            "healthy": self.healthy
        }
        
    def preflight(self, timeout: float = 5.0) -> bool:
        """Perform cached preflight check with comprehensive metrics - Requirements 16.1, 16.4, 16.5"""
        start_time = time.time()
        
        if not self.in_use or self.secret is None:
            self.logger.log_event("info", "Proxy not in use, skipping preflight", 
                                proxy_available=False, username_tail="N/A")
            self._healthy = False
            return False
            
        if self.preflight_disabled:
            self.logger.log_event("info", "Proxy preflight disabled via OXY_PREFLIGHT_DISABLED",
                                proxy_available=True, username_tail=self._get_masked_username_tail())
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
            self.logger.log_event("info", "Preflight rate limited, using cached result",
                                cached_healthy=cached.healthy if cached else None,
                                username_tail=self._get_masked_username_tail())
            return cached.healthy if cached else False
            
        with self._preflight_lock:  # Single-flight
            cached = self.preflight_cache.get()
            if cached and not self.preflight_cache.is_expired():
                self._healthy = cached.healthy
                # Log cache hit - Requirement 16.1
                self._preflight_hits += 1
                self._preflight_total += 1
                self.logger.log_event("info", "Preflight cache hit",
                                    cached_healthy=cached.healthy,
                                    username_tail=self._get_masked_username_tail(),
                                    cache_age_seconds=int((datetime.utcnow() - cached.timestamp).total_seconds()))
                return cached.healthy
            
            # Cache miss - perform actual preflight - Requirement 16.1
            self._preflight_misses += 1
            self._preflight_total += 1
            self._preflight_count += 1
            self._last_preflight_time = now
            
            # Perform actual preflight with enhanced out-of-band validation
            proxies = self.proxies_for(None)
            
            # --- ADD THESE TWO LINES FOR DEBUGGING ---
            full_proxy_user = urlparse(proxies.get("https", "")).username
            logging.info(f"DIAGNOSTIC_LOG: Full proxy username being sent is: {full_proxy_user}")
            # -----------------------------------------
            
            session_token = extract_session_from_proxies(proxies)
            
            try:
                # Enhanced: Test with httpbin.org/ip first for pure proxy validation
                r = requests.get("http://httpbin.org/ip", proxies=proxies, timeout=timeout)
                if r.status_code == 200:
                    # Log proxy validation success with masked username - Requirement 16.2, 16.4
                    proxy_username = extract_session_from_proxies(proxies)
                    masked_username = f"...{proxy_username[-4:]}" if len(proxy_username) > 4 else "***"
                    self.logger.log_event("info", "Proxy out-of-band validation ok: httpbin returned 200",
                                        proxy_user_tail=masked_username,
                                        username_tail=self._get_masked_username_tail())
                    
                    # Continue with YouTube-specific validation
                    for url in ("https://www.youtube.com/generate_204", "https://httpbin.org/status/204"):
                        try:
                            r = requests.get(url, proxies=proxies, timeout=timeout)
                            if r.status_code == 204:
                                duration = time.time() - start_time
                                self._preflight_durations.append(duration)
                                
                                self.preflight_cache.set(True)
                                self._healthy = True
                                
                                # Structured logging with performance metrics - Requirement 16.4, 16.5
                                self.logger.log_event("info", "Proxy preflight successful",
                                                    status_code=204,
                                                    duration_ms=round(duration * 1000, 2),
                                                    username_tail=self._get_masked_username_tail(),
                                                    hit_rate=round(self._preflight_hits / self._preflight_total, 3),
                                                    total_checks=self._preflight_total)
                                return True
                            if r.status_code in (401, 407):
                                duration = time.time() - start_time
                                self._preflight_durations.append(duration)
                                
                                self.preflight_cache.set(False, f"auth_{r.status_code}")
                                self._healthy = False
                                
                                # Log auth failure with metrics - Requirement 16.4
                                self.logger.log_event("warning", "Proxy preflight auth failed",
                                                    status_code=r.status_code,
                                                    duration_ms=round(duration * 1000, 2),
                                                    username_tail=self._get_masked_username_tail(),
                                                    error_type="auth_failure")
                                raise ProxyAuthError(f"proxy_auth_failed_{r.status_code}")
                            r.raise_for_status()
                        except requests.RequestException as e:
                            continue  # Try next URL
                    
                    # All YouTube URLs failed but httpbin worked - likely YouTube blocking
                    duration = time.time() - start_time
                    self._preflight_durations.append(duration)
                    
                    self.preflight_cache.set(False, "youtube_blocked")
                    self._healthy = False
                    
                    self.logger.log_event("warning", "YouTube endpoints blocked but httpbin accessible",
                                        duration_ms=round(duration * 1000, 2),
                                        username_tail=self._get_masked_username_tail(),
                                        error_type="youtube_blocked")
                    raise ProxyConfigError("proxy_preflight_youtube_blocked")
                    
                elif r.status_code in (401, 407):
                    # Proxy auth failed at httpbin level - definitive failure
                    duration = time.time() - start_time
                    self._preflight_durations.append(duration)
                    
                    self.preflight_cache.set(False, f"httpbin_auth_{r.status_code}")
                    self._healthy = False
                    
                    self.logger.log_event("warning", "Proxy auth failed at httpbin level",
                                        status_code=r.status_code,
                                        duration_ms=round(duration * 1000, 2),
                                        username_tail=self._get_masked_username_tail(),
                                        error_type="httpbin_auth_failure")
                    raise ProxyAuthError(f"proxy_auth_failed_{r.status_code}")
                else:
                    # Unexpected httpbin response
                    self.logger.log_event("warning", "Unexpected httpbin response",
                                        status_code=r.status_code,
                                        username_tail=self._get_masked_username_tail())
                    
            except requests.RequestException as e:
                self.logger.log_event("warning", "Httpbin preflight failed, falling back to YouTube-only validation",
                                    error=str(e),
                                    username_tail=self._get_masked_username_tail())
                # Fall back to original YouTube-only validation
                pass
            
            # Fallback: Original validation if httpbin fails
            last_err = None
            for url in ("https://www.youtube.com/generate_204", "https://httpbin.org/status/204"):
                try:
                    r = requests.get(url, proxies=proxies, timeout=timeout)
                    if r.status_code == 204:
                        duration = time.time() - start_time
                        self._preflight_durations.append(duration)
                        
                        self.preflight_cache.set(True)
                        self._healthy = True
                        
                        self.logger.log_event("info", "Proxy preflight successful (fallback)",
                                            status_code=204,
                                            duration_ms=round(duration * 1000, 2),
                                            username_tail=self._get_masked_username_tail(),
                                            validation_method="fallback")
                        return True
                    if r.status_code in (401, 407):
                        duration = time.time() - start_time
                        self._preflight_durations.append(duration)
                        
                        self.preflight_cache.set(False, f"auth_{r.status_code}")
                        self._healthy = False
                        
                        self.logger.log_event("warning", "Proxy preflight auth failed (fallback)",
                                            status_code=r.status_code,
                                            duration_ms=round(duration * 1000, 2),
                                            username_tail=self._get_masked_username_tail(),
                                            error_type="auth_failure")
                        raise ProxyAuthError(f"proxy_auth_failed_{r.status_code}")
                    r.raise_for_status()
                except requests.RequestException as e:
                    last_err = e
                    continue
            
            # All URLs failed
            duration = time.time() - start_time
            self._preflight_durations.append(duration)
            
            self.preflight_cache.set(False, str(last_err) if last_err else "unknown")
            self._healthy = False
            
            # Comprehensive failure logging - Requirement 16.4, 16.5
            self.logger.log_event("error", "All proxy preflight endpoints failed",
                                duration_ms=round(duration * 1000, 2),
                                username_tail=self._get_masked_username_tail(),
                                last_error=str(last_err) if last_err else "unknown",
                                error_type="all_endpoints_failed",
                                hit_rate=round(self._preflight_hits / self._preflight_total, 3))
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
        
    def proxy_url(self, sticky: bool = True) -> Optional[str]:
        """
        Return a full URL with auth, e.g. http://user:pass@pr.oxylabs.io:10000
        Return None if proxies disabled/unavailable.
        """
        if not self.in_use or not self.secret:
            return None
        token = self._generate_session_token()
        return self.secret.build_proxy_url(token)

    def proxy_dict_for(self, client: str = "requests", sticky: bool = True):
        """
        Unified proxy configuration for different client types.
        
        Args:
            client: Client type - "requests" or "playwright"
            sticky: Whether to use sticky session (default: True)
            
        Returns:
            requests  -> {"http": url, "https": url}
            playwright-> {"server": "http://host:port", "username": "...", "password": "..."}
            None if proxy not available or client type unsupported
        """
        # Validate client type first
        supported_clients = ["requests", "playwright"]
        if client not in supported_clients:
            self.logger.log_event("error", f"Unsupported proxy client type: {client}", 
                                client_type=client, supported_clients=supported_clients)
            # Fallback to requests format for unknown clients
            self.logger.log_event("info", f"Falling back to requests format for unsupported client: {client}")
            client = "requests"
        
        # Get proxy URL
        try:
            url = self.proxy_url(sticky=sticky)
            if not url:
                self.logger.log_event("debug", f"No proxy URL available for client: {client}")
                return None

            if client == "requests":
                proxy_dict = {"http": url, "https": url}
                self.logger.log_event("debug", f"Generated requests proxy dict for client: {client}")
                return proxy_dict

            if client == "playwright":
                from urllib.parse import urlparse
                try:
                    u = urlparse(url)
                    server = f"{u.scheme}://{u.hostname}:{u.port}"
                    proxy_dict = {
                        "server": server,
                        "username": u.username or "",
                        "password": u.password or ""
                    }
                    self.logger.log_event("debug", f"Generated playwright proxy dict for client: {client}")
                    return proxy_dict
                except Exception as e:
                    self.logger.log_event("error", f"Failed to parse proxy URL for playwright: {e}", 
                                        client_type=client, error_type=type(e).__name__)
                    # Fallback to None for playwright parsing errors
                    return None
                    
        except Exception as e:
            self.logger.log_event("error", f"Failed to generate proxy dict for client {client}: {e}", 
                                client_type=client, error_type=type(e).__name__)
            # Return appropriate fallback based on client type
            if client == "requests":
                return {}  # Empty dict allows requests to work without proxy
            else:  # playwright
                return None  # None disables proxy for playwright
        
        # This should never be reached, but provide fallback
        self.logger.log_event("warning", f"Unexpected code path in proxy_dict_for for client: {client}")
        return None

    def playwright_proxy(self) -> dict | None:
        """
        Returns Playwright proxy dict: {"server": "...", "username": "...", "password": "..."}
        or None if proxies disabled.
        """
        proxy_url = self.proxy_url()
        if not proxy_url:
            return None
        # Parse URL to components for Playwright
        from urllib.parse import urlparse
        u = urlparse(proxy_url)
        auth = u.username, u.password
        return {
            "server": f"{u.scheme}://{u.hostname}:{u.port}",
            **({"username": auth[0], "password": auth[1]} if all(auth) else {})
        }

    def is_production_environment(self) -> bool:
        """Detect if running in production environment."""
        return os.getenv('ENVIRONMENT') == 'production' or os.getenv('AWS_REGION') is not None

    def rotate_session(self, failed_token: Optional[str] = None):
        """Enhanced session rotation with automatic token extraction"""
        if not self.in_use or self.secret is None:
            self.logger.log_event("debug", "Proxy not in use, skipping session rotation")
            return
        
        # If no token provided, generate a new one to force rotation
        if failed_token is None:
            # Clear preflight cache to force re-validation
            self.preflight_cache = PreflightCache()
            self._healthy = None
            self.logger.log_event("info", "Session rotation requested: clearing preflight cache")
            return
            
        # Only log last 4 chars to prevent token leakage
        self.logger.log_event("info", f"Blacklisting session: ...{failed_token[-4:]}")
        self.session_blacklist.add(failed_token)
        
        # Clear preflight cache when rotating due to failures
        self.preflight_cache = PreflightCache()
        self._healthy = None

    def _rotate(self):
        """Best-effort session rotation implementation (e.g., Oxylabs sessid bump)"""
        try:
            # This is a placeholder for provider-specific rotation logic
            # For Oxylabs, this could involve session ID manipulation
            # For now, we just clear caches and force new session generation
            self.preflight_cache = PreflightCache()
            self._healthy = None
            self.logger.log_event("info", "Internal session rotation completed")
        except Exception as e:
            self.logger.log_event("warning", f"Session rotation failed: {e}")

    def proxy_env_for_subprocess(self) -> Dict[str, str]:
        """Return environment variables for subprocess proxy configuration"""
        if not self.in_use or self.secret is None:
            self.logger.log_event("debug", "Proxy not available, returning empty environment")
            return {}
        
        try:
            # Generate a fresh session token for subprocess
            token = self._generate_session_token("subprocess")
            proxy_url = self.secret.build_proxy_url(token)
            
            # Return standard proxy environment variables
            env_vars = {
                "http_proxy": proxy_url,
                "https_proxy": proxy_url
            }
            
            self.logger.log_event("debug", "Generated proxy environment variables for subprocess")
            return env_vars
            
        except Exception as e:
            self.logger.log_event("error", f"Failed to generate proxy environment variables: {e}")
            return {}

    def for_job(self, job_id: str) -> str:
        """
        Get or create a sticky session ID for a specific job.
        
        This ensures one proxy identity per job across all stages:
        - Requests (Transcript API, timedtext)
        - Playwright (--proxy-server or context proxy)
        - ffmpeg (-http_proxy and env)
        
        Args:
            job_id: Unique job identifier
            
        Returns:
            Session ID that will be consistent for this job
        """
        if not self.in_use or self.secret is None:
            self.logger.log_event("debug", "Proxy not available for job", job_id=job_id)
            return ""
        
        with _job_sessions_lock:
            if job_id not in _job_sessions:
                # Generate deterministic session ID based on job_id
                session_hash = hashlib.sha256(job_id.encode()).hexdigest()[:12]
                _job_sessions[job_id] = session_hash
                
                self.logger.log_event("info", "Created sticky session for job", 
                                    job_id=job_id, 
                                    session_hash=session_hash[:8] + "***",  # Mask for security
                                    username_tail=self._get_masked_username_tail())
            
            return _job_sessions[job_id]
    
    def proxies_for_job(self, job_id: str) -> Dict[str, str]:
        """
        Get proxy configuration with job-scoped sticky session.
        
        Args:
            job_id: Unique job identifier
            
        Returns:
            Proxy dictionary for requests library
        """
        if not self.in_use or self.secret is None:
            self.logger.log_event("debug", "Proxy not available for job", job_id=job_id)
            return {}
        
        session_id = self.for_job(job_id)
        if not session_id:
            return {}
        
        # Ensure we don't reuse blacklisted tokens
        if session_id in self.session_blacklist:
            self.logger.log_event("warning", "Job session blacklisted, generating new session", 
                                job_id=job_id, session_hash=session_id[:8] + "***")
            # Remove from job sessions to force regeneration
            with _job_sessions_lock:
                _job_sessions.pop(job_id, None)
            # Recursively call to get new session
            return self.proxies_for_job(job_id)
        
        proxy_url = self.secret.build_proxy_url(session_id)
        return {"http": proxy_url, "https": proxy_url}
    
    def proxy_dict_for_job(self, job_id: str, client: str = "requests") -> Optional[Dict[str, str]]:
        """
        Get proxy configuration for specific client type with job-scoped sticky session.
        
        Args:
            job_id: Unique job identifier
            client: Client type - "requests" or "playwright"
            
        Returns:
            Client-specific proxy configuration
        """
        if not self.in_use or self.secret is None:
            return None if client == "playwright" else {}
        
        session_id = self.for_job(job_id)
        if not session_id:
            return None if client == "playwright" else {}
        
        # Check blacklist
        if session_id in self.session_blacklist:
            self.logger.log_event("warning", "Job session blacklisted for client", 
                                job_id=job_id, client=client, session_hash=session_id[:8] + "***")
            # Remove from job sessions to force regeneration
            with _job_sessions_lock:
                _job_sessions.pop(job_id, None)
            # Recursively call to get new session
            return self.proxy_dict_for_job(job_id, client)
        
        proxy_url = self.secret.build_proxy_url(session_id)
        
        if client == "requests":
            return {"http": proxy_url, "https": proxy_url}
        elif client == "playwright":
            try:
                from urllib.parse import urlparse
                u = urlparse(proxy_url)
                server = f"{u.scheme}://{u.hostname}:{u.port}"
                return {
                    "server": server,
                    "username": u.username or "",
                    "password": u.password or ""
                }
            except Exception as e:
                self.logger.log_event("error", f"Failed to parse proxy URL for playwright job", 
                                    job_id=job_id, error_type=type(e).__name__)
                return None
        else:
            self.logger.log_event("error", f"Unsupported client type for job", 
                                job_id=job_id, client=client)
            return None
    
    def proxy_env_for_job(self, job_id: str) -> Dict[str, str]:
        """
        Get proxy environment variables for subprocess with job-scoped sticky session.
        
        Args:
            job_id: Unique job identifier
            
        Returns:
            Environment variables for subprocess proxy configuration
        """
        if not self.in_use or self.secret is None:
            self.logger.log_event("debug", "Proxy not available for job subprocess", job_id=job_id)
            return {}
        
        session_id = self.for_job(job_id)
        if not session_id:
            return {}
        
        # Check blacklist
        if session_id in self.session_blacklist:
            self.logger.log_event("warning", "Job session blacklisted for subprocess", 
                                job_id=job_id, session_hash=session_id[:8] + "***")
            # Remove from job sessions to force regeneration
            with _job_sessions_lock:
                _job_sessions.pop(job_id, None)
            # Recursively call to get new session
            return self.proxy_env_for_job(job_id)
        
        try:
            proxy_url = self.secret.build_proxy_url(session_id)
            
            # Return standard proxy environment variables
            env_vars = {
                "http_proxy": proxy_url,
                "https_proxy": proxy_url,
                "all_proxy": proxy_url  # Some tools check this
            }
            
            self.logger.log_event("debug", "Generated job-scoped proxy environment variables", 
                                job_id=job_id, session_hash=session_id[:8] + "***")
            return env_vars
            
        except Exception as e:
            self.logger.log_event("error", f"Failed to generate job proxy environment variables", 
                                job_id=job_id, error_type=type(e).__name__)
            return {}
    
    def cleanup_job_session(self, job_id: str):
        """
        Clean up job-scoped session when job completes.
        
        Args:
            job_id: Job identifier to clean up
        """
        with _job_sessions_lock:
            if job_id in _job_sessions:
                session_hash = _job_sessions.pop(job_id)
                self.logger.log_event("info", "Cleaned up job session", 
                                    job_id=job_id, session_hash=session_hash[:8] + "***")

    def emit_health_status(self) -> None:
        """Emit structured health status logs without credential leakage - Requirement 16.4"""
        if not self.in_use or self.secret is None:
            self.logger.log_event("info", "Proxy health status: not configured",
                                proxy_available=False,
                                healthy=False,
                                username_tail="N/A")
            return
        
        metrics = self.get_preflight_metrics()
        
        # Emit comprehensive health status - Requirement 16.4, 16.5
        self.logger.log_event("info", "Proxy health status report",
                            healthy=metrics["healthy"],
                            username_tail=metrics["proxy_username_tail"],
                            hit_rate=metrics["hit_rate"],
                            total_checks=metrics["preflight_total"],
                            avg_duration_ms=metrics["avg_duration_ms"],
                            last_check_timestamp=metrics["last_check_time"],
                            provider=self.secret.provider if self.secret else "unknown")

    def youtube_preflight(self, timeout: float = 5.0) -> bool:
        """YouTube-specific preflight check with enhanced validation"""
        if not self.in_use or self.secret is None:
            self.logger.log_event("info", "Proxy not in use, skipping YouTube preflight (OK)")
            return True
            
        if self.preflight_disabled:
            self.logger.log_event("info", "YouTube preflight disabled via OXY_PREFLIGHT_DISABLED")
            return True
        
        # Use existing rate limiting and caching infrastructure
        with self._preflight_lock:
            # Check if we have a recent YouTube-specific result
            cached = self.preflight_cache.get()
            if cached and not self.preflight_cache.is_expired():
                return cached.healthy
            
            self._preflight_count += 1
            
            # Generate fresh session for YouTube testing
            proxies = self.proxies_for("youtube_preflight")
            
            # YouTube-specific endpoints in order of preference
            youtube_endpoints = [
                "https://www.youtube.com/generate_204",
                "https://m.youtube.com/generate_204", 
                "https://www.youtube.com/favicon.ico"  # Fallback
            ]
            
            last_error = None
            for endpoint in youtube_endpoints:
                try:
                    r = requests.get(endpoint, proxies=proxies, timeout=timeout, 
                                   headers={"User-Agent": "Mozilla/5.0 (compatible; TLDW/1.0)"})
                    
                    if r.status_code in (200, 204):
                        self.preflight_cache.set(True)
                        self._healthy = True
                        self.logger.log_event("info", f"YouTube preflight ok: {endpoint} returned {r.status_code}")
                        return True
                    elif r.status_code in (401, 407):
                        # Definitive auth failure
                        self.preflight_cache.set(False, f"youtube_auth_{r.status_code}")
                        self._healthy = False
                        self.logger.log_event("warning", f"YouTube preflight auth failed: {endpoint} returned {r.status_code}")
                        raise ProxyAuthError(f"youtube_proxy_auth_failed_{r.status_code}")
                    elif r.status_code == 429:
                        # Rate limited - might be temporary
                        self.logger.log_event("warning", f"YouTube preflight rate limited: {endpoint}")
                        last_error = f"rate_limited_{r.status_code}"
                        continue
                    else:
                        # Other error codes - try next endpoint
                        self.logger.log_event("debug", f"YouTube preflight unexpected status: {endpoint} returned {r.status_code}")
                        last_error = f"unexpected_status_{r.status_code}"
                        continue
                        
                except requests.RequestException as e:
                    self.logger.log_event("debug", f"YouTube preflight request failed: {endpoint} - {e}")
                    last_error = str(e)
                    continue
            
            # All endpoints failed
            self.preflight_cache.set(False, last_error or "all_endpoints_failed")
            self._healthy = False
            self.logger.log_event("warning", f"YouTube preflight failed: all endpoints unreachable - {last_error}")
            return False

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

def ensure_proxy_session(job_id: str, video_id: str):
    """Ensure consistent proxy session for a job"""
    # Import here to avoid circular imports
    from shared_managers import shared_managers
    
    # Get ENFORCE_PROXY_ALL from environment
    ENFORCE_PROXY_ALL = os.getenv("ENFORCE_PROXY_ALL", "false").lower() == "true"
    
    if not ENFORCE_PROXY_ALL:
        return None
        
    try:
        # Get or create sticky session for this job
        session_id = f"yt_{job_id}_{video_id}"
        proxy_config = shared_managers.get_proxy_manager().for_job(session_id)
        
        # Verify proxy is working
        if not _verify_proxy_connection(proxy_config):
            # Rotate proxy if current one is blocked
            shared_managers.get_proxy_manager().rotate_session(session_id)
            proxy_config = shared_managers.get_proxy_manager().for_job(session_id)
            
        return proxy_config
    except Exception as e:
        logging.error(f"Proxy session setup failed: {e}")
        return None

def _verify_proxy_connection(proxy_config):
    """Quick check if proxy can access YouTube"""
    # If no proxy config is provided, return False as we can't verify
    if not proxy_config or not any(proxy_config.values()):
        return False
        
    try:
        test_url = "https://www.youtube.com/generate_204"
        response = requests.get(
            test_url, 
            proxies=proxy_config,
            timeout=10
        )
        return response.status_code == 204
    except:
        return False

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
