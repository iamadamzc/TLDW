import time
import random
import logging
import requests
from typing import Dict, Any, Optional, Tuple
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException, Timeout, ConnectionError
from urllib3.util.retry import Retry

class YouTubeBlockingError(Exception):
    """Raised when YouTube blocks the request (403/429 or bot detection)"""
    pass

class ProxyHTTPClient:
    """HTTP client with proxy support and YouTube blocking detection"""
    
    def __init__(self, proxy_manager):
        self.proxy_manager = proxy_manager
        self.session = requests.Session()
        
        # Configure retry strategy for non-proxy errors
        retry_strategy = Retry(
            total=2,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set user agent to look more like a regular browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def get_with_proxy(self, url: str, video_id: str, **kwargs) -> requests.Response:
        """Make GET request with proxy support and YouTube blocking detection"""
        return self._request_with_proxy('GET', url, video_id, **kwargs)
    
    def post_with_proxy(self, url: str, video_id: str, **kwargs) -> requests.Response:
        """Make POST request with proxy support and YouTube blocking detection"""
        return self._request_with_proxy('POST', url, video_id, **kwargs)
    
    def _request_with_proxy(self, method: str, url: str, video_id: str, **kwargs) -> requests.Response:
        """Internal method to handle proxy requests with retry logic"""
        
        # If proxies are disabled, make direct request
        if not self.proxy_manager.enabled:
            return self._make_direct_request(method, url, **kwargs)
        
        # Get proxy session for this video
        session = self.proxy_manager.get_session_for_video(video_id)
        if not session:
            return self._make_direct_request(method, url, **kwargs)
        
        # First attempt with current session
        try:
            response = self._make_proxy_request(method, url, session, **kwargs)
            self._log_request_success(video_id, session, url, response.status_code)
            return response
            
        except YouTubeBlockingError as e:
            logging.warning(f"YouTube blocking detected for video {video_id}, session {session.session_id}: {e}")
            self.proxy_manager.mark_session_blocked(video_id)
            
            # Try one rotation (MVP: single retry)
            rotated_session = self.proxy_manager.rotate_session(video_id)
            if rotated_session:
                try:
                    response = self._make_proxy_request(method, url, rotated_session, **kwargs)
                    self._log_request_success(video_id, rotated_session, url, response.status_code)
                    return response
                    
                except YouTubeBlockingError as e2:
                    logging.error(f"YouTube blocking persists after rotation for video {video_id}: {e2}")
                    self.proxy_manager.mark_session_blocked(video_id)
                    # Re-raise to trigger fallback to ASR
                    raise YouTubeBlockingError(f"Persistent YouTube blocking after rotation: {e2}")
            
            # If rotation failed, re-raise original error
            raise e
            
        except Exception as e:
            logging.error(f"Proxy request failed for video {video_id}: {e}")
            self.proxy_manager.mark_session_failed(video_id)
            raise
    
    def _make_proxy_request(self, method: str, url: str, session, **kwargs) -> requests.Response:
        """Make a single proxy request with rate limiting and error detection"""
        
        # Apply rate limiting with jitter
        self._apply_rate_limiting(session)
        
        # Get proxy configuration
        proxies = self.proxy_manager.get_proxy_dict(session)
        timeout = session.proxy_config.get('timeout', 30)
        
        # Add proxy to kwargs
        kwargs['proxies'] = proxies
        kwargs['timeout'] = timeout
        
        start_time = time.time()
        
        try:
            # Make the request
            response = self.session.request(method, url, **kwargs)
            
            # Check for YouTube blocking
            self._check_youtube_blocking(response, url)
            
            # Log successful request
            latency_ms = int((time.time() - start_time) * 1000)
            logging.info(f"Proxy request successful: video_id={getattr(session, 'video_id', 'unknown')}, "
                        f"status={response.status_code}, latency_ms={latency_ms}")
            
            return response
            
        except (Timeout, ConnectionError) as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logging.error(f"Proxy request timeout/connection error: video_id={getattr(session, 'video_id', 'unknown')}, "
                         f"error={str(e)}, latency_ms={latency_ms}")
            raise
        
        except RequestException as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logging.error(f"Proxy request failed: video_id={getattr(session, 'video_id', 'unknown')}, "
                         f"error={str(e)}, latency_ms={latency_ms}")
            raise
    
    def _make_direct_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Make direct request without proxy"""
        logging.debug(f"Making direct request to {url}")
        return self.session.request(method, url, **kwargs)
    
    def _apply_rate_limiting(self, session) -> None:
        """Apply rate limiting with jitter as per MVP requirements"""
        if not hasattr(session, 'last_request_time'):
            session.last_request_time = 0
        
        # Get rate limiting config
        max_rps = session.proxy_config.get('max_requests_per_second', 2)
        jitter_ms = session.proxy_config.get('jitter_ms', 250)
        
        # Calculate minimum time between requests
        min_interval = 1.0 / max_rps
        
        # Add jitter (±250ms by default)
        jitter = random.uniform(-jitter_ms/1000, jitter_ms/1000)
        interval_with_jitter = min_interval + jitter
        
        # Calculate time to wait
        time_since_last = time.time() - session.last_request_time
        if time_since_last < interval_with_jitter:
            sleep_time = interval_with_jitter - time_since_last
            logging.debug(f"Rate limiting: sleeping {sleep_time:.3f}s")
            time.sleep(sleep_time)
        
        session.last_request_time = time.time()
    
    def _check_youtube_blocking(self, response: requests.Response, url: str) -> None:
        """Check if YouTube is blocking the request"""
        
        # Check HTTP status codes that indicate blocking (including 407 proxy auth errors)
        if response.status_code in [403, 407, 429]:
            raise YouTubeBlockingError(f"HTTP {response.status_code} - YouTube/Proxy blocking detected")
        
        # Check for specific YouTube blocking patterns in response text
        if response.status_code == 200:
            response_text = response.text.lower()
            
            # Common YouTube blocking indicators
            blocking_indicators = [
                "not a robot",
                "unusual traffic",
                "automated requests",
                "captcha",
                "verify you're human",
                "blocked",
                "access denied",
                "sign in to confirm"
            ]
            
            for indicator in blocking_indicators:
                if indicator in response_text:
                    raise YouTubeBlockingError(f"YouTube bot detection: '{indicator}' found in response")
        
        # Check for empty or suspicious responses
        if response.status_code == 200 and len(response.text) < 100:
            # Very short responses might indicate blocking
            logging.warning(f"Suspiciously short response ({len(response.text)} chars) from {url}")
    
    def _log_request_success(self, video_id: str, session, url: str, status_code: int) -> None:
        """Log successful request with structured logging"""
        logging.info(f"Request success: video_id={video_id}, session_id={session.session_id}, "
                    f"url={url}, status={status_code}, requests_in_session={session.request_count}")
    
    def close(self):
        """Close the HTTP session"""
        self.session.close()

# Convenience functions for backward compatibility
def get_with_proxy(proxy_manager, url: str, video_id: str, **kwargs) -> requests.Response:
    """Convenience function for GET requests with proxy"""
    client = ProxyHTTPClient(proxy_manager)
    try:
        return client.get_with_proxy(url, video_id, **kwargs)
    finally:
        client.close()

def post_with_proxy(proxy_manager, url: str, video_id: str, **kwargs) -> requests.Response:
    """Convenience function for POST requests with proxy"""
    client = ProxyHTTPClient(proxy_manager)
    try:
        return client.post_with_proxy(url, video_id, **kwargs)
    finally:
        client.close()
