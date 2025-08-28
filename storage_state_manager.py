"""
Enhanced storage state and consent management for Playwright.

This module provides:
- Netscape cookies.txt → Playwright storage_state.json conversion
- __Host- cookie sanitization (path /, Secure, no Domain)
- SameSite=None handling where appropriate
- Synthetic SOCS/CONSENT injection when missing
- Guaranteed storage state availability (no fallback paths without it)
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse

from logging_setup import get_logger
from log_events import evt

logger = get_logger(__name__)

# Default cookie directory
DEFAULT_COOKIE_DIR = Path("/app/cookies")

# Synthetic consent cookies for GDPR compliance
SYNTHETIC_CONSENT_COOKIES = [
    {
        "name": "SOCS",
        "value": "CAESEwgDEgk0ODE3Nzk3MjQaAmVuIAEaBgiA_LyaBg",
        "domain": ".youtube.com",
        "path": "/",
        "secure": True,
        "httpOnly": False,
        "sameSite": "None"
    },
    {
        "name": "CONSENT",
        "value": "YES+cb.20210328-17-p0.en+FX+1",
        "domain": ".youtube.com", 
        "path": "/",
        "secure": True,
        "httpOnly": False,
        "sameSite": "None"
    }
]


class StorageStateManager:
    """
    Enhanced storage state manager with guaranteed availability and consent handling.
    """
    
    def __init__(self, cookie_dir: Optional[str] = None):
        """
        Initialize storage state manager.
        
        Args:
            cookie_dir: Directory containing cookie files (defaults to /app/cookies)
        """
        self.cookie_dir = Path(cookie_dir or os.getenv("COOKIE_DIR", DEFAULT_COOKIE_DIR))
        self.storage_state_path = self.cookie_dir / "youtube_session.json"
        self.netscape_cookies_path = self.cookie_dir / "cookies.txt"
        
        # Ensure cookie directory exists
        self.cookie_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"StorageStateManager initialized: cookie_dir={self.cookie_dir}")
    
    def ensure_storage_state_available(self) -> bool:
        """
        Ensure storage state is available, converting from Netscape if needed.
        
        This method guarantees that a storage state file exists and is valid.
        It will create synthetic storage state if no cookies are available.
        
        Returns:
            True if storage state is available, False if creation failed
        """
        # Check if storage state already exists and is valid
        if self._validate_existing_storage_state():
            evt("storage_state_check", outcome="found_valid", path=str(self.storage_state_path))
            return True
        
        # Try to convert from Netscape cookies
        if self.netscape_cookies_path.exists():
            evt("storage_state_conversion", action="attempting", source=str(self.netscape_cookies_path))
            try:
                if self._convert_netscape_to_storage_state():
                    evt("storage_state_conversion", outcome="success", target=str(self.storage_state_path))
                    return True
                else:
                    evt("storage_state_conversion", outcome="failed")
            except Exception as e:
                evt("storage_state_conversion", outcome="error", detail=str(e))
                logger.warning(f"Failed to convert Netscape cookies: {e}")
        
        # Create synthetic storage state as last resort
        evt("storage_state_creation", action="synthetic")
        try:
            if self._create_synthetic_storage_state():
                evt("storage_state_creation", outcome="success", type="synthetic")
                return True
            else:
                evt("storage_state_creation", outcome="failed", type="synthetic")
                return False
        except Exception as e:
            evt("storage_state_creation", outcome="error", detail=str(e))
            logger.error(f"Failed to create synthetic storage state: {e}")
            return False
    
    def _validate_existing_storage_state(self) -> bool:
        """
        Validate existing storage state file.
        
        Returns:
            True if storage state exists and is valid
        """
        if not self.storage_state_path.exists():
            return False
        
        try:
            with open(self.storage_state_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check required structure
            if not isinstance(data, dict):
                return False
            
            if "cookies" not in data or not isinstance(data["cookies"], list):
                return False
            
            # Check if we have at least some cookies or consent cookies
            cookies = data["cookies"]
            if not cookies:
                return False
            
            # Validate cookie structure
            for cookie in cookies[:5]:  # Check first 5 cookies
                if not isinstance(cookie, dict) or "name" not in cookie or "value" not in cookie:
                    return False
            
            logger.debug(f"Storage state validation passed: {len(cookies)} cookies")
            return True
            
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Storage state validation failed: {e}")
            return False
    
    def _convert_netscape_to_storage_state(self) -> bool:
        """
        Convert Netscape cookies.txt to Playwright storage_state.json format.
        
        Returns:
            True if conversion successful
        """
        try:
            # Read and validate Netscape cookies
            with open(self.netscape_cookies_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            if not self._validate_netscape_format(content):
                logger.error(f"Invalid Netscape cookie format in {self.netscape_cookies_path}")
                return False
            
            # Parse Netscape cookies
            cookies = self._parse_netscape_cookies(content)
            if not cookies:
                logger.error("No valid cookies found in Netscape file")
                return False
            
            # Create storage state structure
            storage_state = {
                "cookies": cookies,
                "origins": self._create_origins_structure(cookies),
                "localStorage": []
            }
            
            # Inject SOCS/CONSENT cookies if missing
            storage_state = self._inject_consent_cookies_if_missing(storage_state)
            
            # Write storage state file
            with open(self.storage_state_path, 'w', encoding='utf-8') as f:
                json.dump(storage_state, f, indent=2)
            
            logger.info(f"Converted {len(cookies)} cookies to storage state format")
            return True
            
        except Exception as e:
            logger.error(f"Failed to convert Netscape cookies: {e}")
            return False
    
    def _create_synthetic_storage_state(self) -> bool:
        """
        Create synthetic storage state with minimal consent cookies.
        
        Returns:
            True if creation successful
        """
        try:
            # Create minimal storage state with consent cookies only
            storage_state = {
                "cookies": SYNTHETIC_CONSENT_COOKIES.copy(),
                "origins": [
                    {
                        "origin": "https://www.youtube.com",
                        "localStorage": []
                    },
                    {
                        "origin": "https://youtube.com", 
                        "localStorage": []
                    },
                    {
                        "origin": "https://m.youtube.com",
                        "localStorage": []
                    }
                ],
                "localStorage": []
            }
            
            # Write storage state file
            with open(self.storage_state_path, 'w', encoding='utf-8') as f:
                json.dump(storage_state, f, indent=2)
            
            logger.info("Created synthetic storage state with consent cookies")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create synthetic storage state: {e}")
            return False
    
    def _validate_netscape_format(self, content: str) -> bool:
        """
        Validate Netscape format before parsing.
        
        Args:
            content: Raw cookie file content
            
        Returns:
            True if format appears valid
        """
        if not content.strip():
            return False
        
        lines = content.strip().split('\n')
        
        # Check for Netscape format indicators
        has_comment = any(line.startswith('#') for line in lines[:5])
        has_tabs = any('\t' in line for line in lines if not line.startswith('#'))
        
        return has_comment and has_tabs
    
    def _parse_netscape_cookies(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse Netscape cookies.txt format.
        
        Args:
            content: Raw cookie file content
            
        Returns:
            List of cookie dictionaries in Playwright format
        """
        cookies = []
        
        for line in content.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            parts = line.split('\t')
            if len(parts) < 7:
                continue
            
            domain, flag, path, secure, expiry, name, value = parts[:7]
            
            # Skip empty names or values
            if not name or not value:
                continue
            
            # Create cookie dictionary
            cookie = {
                "name": name,
                "value": value,
                "path": path or "/",
                "secure": secure.lower() == 'true',
                "httpOnly": False,  # Default for Netscape format
            }
            
            # Handle domain - remove leading dot for Playwright
            if domain.startswith('.'):
                cookie["domain"] = domain[1:]
            else:
                cookie["domain"] = domain
            
            # Handle expiry (convert to seconds since epoch)
            try:
                if expiry and expiry != '0':
                    cookie["expires"] = int(expiry)
            except (ValueError, TypeError):
                pass  # Skip invalid expiry dates
            
            # Set SameSite for cross-origin cookies
            if cookie["secure"]:
                cookie["sameSite"] = "None"
            else:
                cookie["sameSite"] = "Lax"
            
            # Sanitize __Host- cookies for Playwright compatibility
            if name.startswith('__Host-'):
                cookie = self._sanitize_host_cookie(cookie)
            
            cookies.append(cookie)
        
        return cookies
    
    def _sanitize_host_cookie(self, cookie: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize __Host- cookies for Playwright compatibility.
        
        __Host- cookies have strict requirements:
        - Must have secure=True
        - Must have path="/"
        - Must NOT have domain field (use url field instead)
        
        Args:
            cookie: Cookie dictionary to sanitize
            
        Returns:
            Sanitized cookie dictionary
        """
        # Requirement: Normalize with secure=True
        cookie["secure"] = True
        
        # Requirement: Normalize with path="/"
        cookie["path"] = "/"
        
        # Requirement: Remove domain field and use url field instead
        if "domain" in cookie:
            domain = cookie["domain"]
            # Remove leading dot if present
            if domain.startswith('.'):
                domain = domain[1:]
            # Store original domain as url for Playwright
            cookie["url"] = f"https://{domain}/"
            del cookie["domain"]
        
        # __Host- cookies should use SameSite=None for cross-origin
        cookie["sameSite"] = "None"
        
        return cookie
    
    def _create_origins_structure(self, cookies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Create origins structure for Playwright compatibility.
        
        Args:
            cookies: List of cookie dictionaries
            
        Returns:
            List of origin dictionaries
        """
        origins = set()
        
        # Extract unique domains from cookies
        for cookie in cookies:
            domain = cookie.get("domain", "")
            if domain:
                # Add both www and non-www variants for YouTube
                if "youtube" in domain.lower():
                    origins.add("https://www.youtube.com")
                    origins.add("https://youtube.com")
                    origins.add("https://m.youtube.com")
                else:
                    origins.add(f"https://{domain}")
        
        # Ensure YouTube origins are always present
        origins.update([
            "https://www.youtube.com",
            "https://youtube.com",
            "https://m.youtube.com"
        ])
        
        return [{"origin": origin, "localStorage": []} for origin in sorted(origins)]
    
    def _inject_consent_cookies_if_missing(self, storage_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inject SOCS/CONSENT cookies if missing to prevent consent dialogs.
        
        Args:
            storage_state: Storage state dictionary
            
        Returns:
            Storage state with consent cookies injected if needed
        """
        cookies = storage_state.get("cookies", [])
        
        # Check if SOCS or CONSENT cookies already exist
        existing_consent_cookies = set()
        for cookie in cookies:
            name = cookie.get("name", "").upper()
            if name in ["SOCS", "CONSENT"]:
                existing_consent_cookies.add(name)
        
        # Inject missing consent cookies
        injected_count = 0
        for consent_cookie in SYNTHETIC_CONSENT_COOKIES:
            if consent_cookie["name"].upper() not in existing_consent_cookies:
                # Create a copy with current timestamp
                new_cookie = consent_cookie.copy()
                new_cookie["expires"] = int(time.time()) + (365 * 24 * 60 * 60)  # 1 year
                cookies.append(new_cookie)
                injected_count += 1
        
        if injected_count > 0:
            storage_state["cookies"] = cookies
            logger.info(f"Injected {injected_count} consent cookies to prevent consent dialogs")
            evt("consent_injection", count=injected_count, existing=list(existing_consent_cookies))
        
        return storage_state
    
    def get_storage_state_path(self) -> str:
        """
        Get the path to the storage state file.
        
        Returns:
            Path to storage state file as string
        """
        return str(self.storage_state_path)
    
    def create_playwright_context_args(self, proxy_dict: Optional[Dict[str, str]] = None, profile: str = "desktop") -> Dict[str, Any]:
        """
        Create Playwright context arguments with guaranteed storage state.
        
        Args:
            proxy_dict: Proxy configuration for Playwright
            profile: Client profile ("desktop" or "mobile")
            
        Returns:
            Dictionary of context arguments for browser.new_context()
        """
        # Ensure storage state is available
        if not self.ensure_storage_state_available():
            raise RuntimeError("Failed to ensure storage state availability")
        
        # Profile configurations
        profiles = {
            "desktop": {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "viewport": {"width": 1920, "height": 1080}
            },
            "mobile": {
                "user_agent": "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
                "viewport": {"width": 390, "height": 844}
            }
        }
        
        # Get profile configuration
        profile_config = profiles.get(profile, profiles["desktop"])
        
        # Build context arguments
        context_args = {
            "user_agent": profile_config["user_agent"],
            "viewport": profile_config["viewport"],
            "locale": "en-US",
            "ignore_https_errors": True,
            "storage_state": str(self.storage_state_path)
        }
        
        # Add proxy if provided
        if proxy_dict:
            context_args["proxy"] = proxy_dict
        
        # Log context creation
        evt("playwright_context_args",
            profile=profile,
            has_proxy=bool(proxy_dict),
            storage_state_path=str(self.storage_state_path))
        
        return context_args
    
    def get_storage_state_info(self) -> Dict[str, Any]:
        """
        Get information about the current storage state.
        
        Returns:
            Dictionary with storage state information
        """
        info = {
            "storage_state_exists": self.storage_state_path.exists(),
            "netscape_cookies_exists": self.netscape_cookies_path.exists(),
            "storage_state_path": str(self.storage_state_path),
            "netscape_cookies_path": str(self.netscape_cookies_path),
            "cookie_count": 0,
            "has_consent_cookies": False,
            "consent_cookies": []
        }
        
        if self.storage_state_path.exists():
            try:
                with open(self.storage_state_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                cookies = data.get("cookies", [])
                info["cookie_count"] = len(cookies)
                
                # Check for consent cookies
                consent_cookies = []
                for cookie in cookies:
                    name = cookie.get("name", "")
                    if name.upper() in ["SOCS", "CONSENT"]:
                        consent_cookies.append(name)
                
                info["has_consent_cookies"] = len(consent_cookies) > 0
                info["consent_cookies"] = consent_cookies
                
            except Exception as e:
                info["error"] = str(e)
        
        return info


# Global instance for easy access
_storage_state_manager: Optional[StorageStateManager] = None


def get_storage_state_manager(cookie_dir: Optional[str] = None) -> StorageStateManager:
    """
    Get global storage state manager instance.
    
    Args:
        cookie_dir: Cookie directory (only used for first initialization)
        
    Returns:
        StorageStateManager instance
    """
    global _storage_state_manager
    
    if _storage_state_manager is None:
        _storage_state_manager = StorageStateManager(cookie_dir)
    
    return _storage_state_manager
