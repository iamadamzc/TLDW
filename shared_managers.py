"""
Shared manager factory to eliminate duplicate initializations
"""

import os
import logging
from typing import Optional, Dict, Any
from proxy_manager import ProxyManager
from proxy_http import ProxyHTTPClient
from user_agent_manager import UserAgentManager
from transcript_cache import TranscriptCache

class SharedManagers:
    """Factory for shared manager instances to avoid duplication"""
    
    _instance = None
    _managers = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_proxy_manager(self) -> Optional[ProxyManager]:
        """Get or create ProxyManager instance"""
        if 'proxy_manager' not in self._managers:
            try:
                self._managers['proxy_manager'] = self._create_proxy_manager()
                logging.info("Shared ProxyManager initialized successfully")
            except Exception as e:
                logging.error(f"Failed to initialize shared ProxyManager: {e}")
                self._managers['proxy_manager'] = None
        
        return self._managers['proxy_manager']
    
    def get_proxy_http_client(self) -> Optional[ProxyHTTPClient]:
        """Get or create ProxyHTTPClient instance"""
        if 'proxy_http_client' not in self._managers:
            proxy_manager = self.get_proxy_manager()
            if proxy_manager:
                try:
                    self._managers['proxy_http_client'] = ProxyHTTPClient(proxy_manager)
                    logging.info("Shared ProxyHTTPClient initialized successfully")
                except Exception as e:
                    logging.error(f"Failed to initialize shared ProxyHTTPClient: {e}")
                    self._managers['proxy_http_client'] = None
            else:
                self._managers['proxy_http_client'] = None
        
        return self._managers['proxy_http_client']
    
    def get_user_agent_manager(self) -> Optional[UserAgentManager]:
        """Get or create UserAgentManager instance"""
        if 'user_agent_manager' not in self._managers:
            try:
                self._managers['user_agent_manager'] = UserAgentManager()
                logging.info("Shared UserAgentManager initialized successfully")
            except Exception as e:
                logging.error(f"Failed to initialize shared UserAgentManager: {e}")
                self._managers['user_agent_manager'] = None
        
        return self._managers['user_agent_manager']
    
    def get_transcript_cache(self) -> Optional[TranscriptCache]:
        """Get or create TranscriptCache instance"""
        if 'transcript_cache' not in self._managers:
            try:
                cache_dir = os.getenv('TRANSCRIPT_CACHE_DIR', 'transcript_cache')
                ttl_days = int(os.getenv('TRANSCRIPT_CACHE_TTL_DAYS', '7'))
                self._managers['transcript_cache'] = TranscriptCache(cache_dir, ttl_days)
                logging.info("Shared TranscriptCache initialized successfully")
            except Exception as e:
                logging.error(f"Failed to initialize shared TranscriptCache: {e}")
                self._managers['transcript_cache'] = None
        
        return self._managers['transcript_cache']
    
    def get_all_managers(self) -> Dict[str, Any]:
        """Get all manager instances as a dictionary"""
        return {
            'proxy_manager': self.get_proxy_manager(),
            'proxy_http_client': self.get_proxy_http_client(),
            'user_agent_manager': self.get_user_agent_manager(),
            'transcript_cache': self.get_transcript_cache()
        }
    
    def _create_proxy_manager(self) -> ProxyManager:
        """Create ProxyManager with proper configuration"""
        # Use standardized environment variable names
        proxy_config = os.getenv('OXYLABS_PROXY_CONFIG', '').strip()
        
        if not proxy_config:
            # Try legacy environment variable for backwards compatibility
            legacy_config = os.getenv('PROXY_CONFIG', '').strip()
            if legacy_config:
                logging.warning("Using legacy PROXY_CONFIG environment variable. Consider migrating to OXYLABS_PROXY_CONFIG")
                proxy_config = legacy_config
        
        if proxy_config:
            import json
            try:
                secret_data = json.loads(proxy_config)
                return ProxyManager(secret_data, logging.getLogger(__name__))
            except json.JSONDecodeError as e:
                logging.error(f"Invalid JSON in proxy configuration: {e}")
                raise
        else:
            # Return ProxyManager with None to trigger graceful degradation
            return ProxyManager(None, logging.getLogger(__name__))
    
    def reset(self):
        """Reset all managers (useful for testing)"""
        self._managers.clear()

# Global instance
shared_managers = SharedManagers()