"""
UserAgentManager - Centralized management of User-Agent headers for YouTube requests

This module provides realistic User-Agent strings to bypass YouTube's anti-bot detection
while maintaining compatibility with existing proxy and authentication systems.
"""

import logging
from typing import Dict, Optional


class UserAgentManager:
    """
    Manages User-Agent strings for YouTube API interactions.
    
    Provides realistic, current User-Agent strings that mimic popular browsers
    to avoid detection by YouTube's anti-bot systems.
    """
    
    # Configuration for different User-Agent strings
    USER_AGENT_CONFIG = {
        "default": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "fallback": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "firefox": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
        "edge": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Edg/127.0.0.0"
    }
    
    def __init__(self):
        """Initialize UserAgentManager with default configuration."""
        self.default_user_agent = self._get_default_user_agent()
        logging.debug(f"UserAgentManager initialized with default User-Agent: {self.default_user_agent[:50]}...")
    
    def _get_default_user_agent(self) -> str:
        """
        Returns a realistic, current User-Agent string.
        
        Uses Chrome on Windows 10/11 as it's the most common browser/OS combination
        and less likely to trigger anti-bot detection.
        
        Returns:
            str: A realistic User-Agent string
        """
        try:
            return self.USER_AGENT_CONFIG["default"]
        except KeyError:
            # Fallback to hardcoded string if config is corrupted
            logging.warning("Default User-Agent not found in config, using hardcoded fallback")
            return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
    
    def get_user_agent(self, request_type: str = "default") -> str:
        """
        Get User-Agent string for specific request types with error handling.
        
        Args:
            request_type (str): Type of request ("default", "fallback", "firefox", "edge")
            
        Returns:
            str: User-Agent string for the specified request type
        """
        try:
            user_agent = self.USER_AGENT_CONFIG.get(request_type, self.default_user_agent)
            
            # Validate the User-Agent before returning
            if not self.validate_user_agent(user_agent):
                logging.warning(f"Invalid User-Agent for type '{request_type}', using default")
                user_agent = self.default_user_agent
            
            logging.debug(f"Retrieved User-Agent for type '{request_type}': {user_agent[:50]}...")
            return user_agent
            
        except Exception as e:
            logging.error(f"Error getting User-Agent for type '{request_type}': {e}")
            # Graceful degradation to default
            return self.default_user_agent
    
    def get_headers(self, additional_headers: Optional[Dict[str, str]] = None, 
                   request_type: str = "default") -> Dict[str, str]:
        """
        Get complete headers dictionary with User-Agent.
        
        Args:
            additional_headers (dict, optional): Additional headers to include
            request_type (str): Type of User-Agent to use
            
        Returns:
            dict: Complete headers dictionary with User-Agent and any additional headers
        """
        try:
            headers = {
                'User-Agent': self.get_user_agent(request_type)
            }
            
            # Add any additional headers, allowing them to override User-Agent if needed
            if additional_headers:
                headers.update(additional_headers)
            
            logging.debug(f"Generated headers with {len(headers)} entries")
            return headers
            
        except Exception as e:
            logging.error(f"Error generating headers: {e}")
            # Return minimal headers with default User-Agent
            return {'User-Agent': self.default_user_agent}
    
    def get_transcript_headers(self, request_type: str = "default") -> Dict[str, str]:
        """
        Get headers for transcript requests with User-Agent and Accept-Language.
        
        Args:
            request_type (str): Type of User-Agent to use
            
        Returns:
            dict: Headers dictionary with User-Agent and Accept-Language for transcript requests
        """
        try:
            user_agent = self.get_user_agent(request_type)  # Same UA string for both paths
            headers = {
                'User-Agent': user_agent,
                'Accept-Language': 'en-US,en;q=0.9'  # Only for transcript HTTP
            }
            
            logging.debug(f"Generated transcript headers with User-Agent: {user_agent[:50]}...")
            return headers
            
        except Exception as e:
            logging.error(f"Error generating transcript headers: {e}")
            # Return minimal headers with default User-Agent and Accept-Language
            return {
                'User-Agent': self.default_user_agent,
                'Accept-Language': 'en-US,en;q=0.9'
            }
    
    def get_yt_dlp_user_agent(self, request_type: str = "default") -> str:
        """
        Get identical User-Agent string for yt-dlp --user-agent parameter.
        Ensures UA parity between transcript and yt-dlp operations.
        
        Args:
            request_type (str): Type of User-Agent to use
            
        Returns:
            str: User-Agent string suitable for yt-dlp configuration (identical to transcript)
        """
        return self.get_user_agent(request_type)  # Ensures UA parity between transcript and yt-dlp
    
    def rotate_user_agent(self, current_type: str = "default") -> str:
        """
        Rotate to a different User-Agent if the current one is being blocked.
        
        Args:
            current_type (str): Currently used User-Agent type
            
        Returns:
            str: Different User-Agent string to try
        """
        # Define rotation order
        rotation_order = ["default", "fallback", "firefox", "edge"]
        
        try:
            current_index = rotation_order.index(current_type)
            next_index = (current_index + 1) % len(rotation_order)
            next_type = rotation_order[next_index]
            
            logging.info(f"Rotating User-Agent from '{current_type}' to '{next_type}'")
            return self.get_user_agent(next_type)
            
        except (ValueError, Exception) as e:
            logging.warning(f"Error rotating User-Agent from '{current_type}': {e}")
            return self.get_user_agent("fallback")
    
    def validate_user_agent(self, user_agent: str) -> bool:
        """
        Validate that a User-Agent string looks realistic.
        
        Args:
            user_agent (str): User-Agent string to validate
            
        Returns:
            bool: True if User-Agent appears realistic, False otherwise
        """
        if not user_agent or len(user_agent) < 50:
            return False
        
        # Check for common browser indicators
        browser_indicators = ["Mozilla", "AppleWebKit", "Chrome", "Safari", "Firefox", "Edge"]
        has_browser_indicator = any(indicator in user_agent for indicator in browser_indicators)
        
        # Check for OS indicators
        os_indicators = ["Windows", "Macintosh", "Linux", "X11"]
        has_os_indicator = any(indicator in user_agent for indicator in os_indicators)
        
        return has_browser_indicator and has_os_indicator
    
    def get_stats(self) -> Dict[str, any]:
        """
        Get statistics about User-Agent configuration.
        
        Returns:
            dict: Statistics about available User-Agent strings
        """
        return {
            "available_types": list(self.USER_AGENT_CONFIG.keys()),
            "default_type": "default",
            "total_user_agents": len(self.USER_AGENT_CONFIG),
            "default_valid": self.validate_user_agent(self.default_user_agent)
        }