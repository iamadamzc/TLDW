#!/usr/bin/env python3
"""
Security enhancements for cookie and credential handling in the no-yt-dl summarization stack
"""
import os
import logging
import json
import time
import hashlib
import secrets
from typing import Dict, Any, Optional, Union
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64


class SecureCookieManager:
    """Secure cookie storage with encryption at rest and TTL enforcement"""
    
    def __init__(self, encryption_key: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self.cookie_ttl_hours = int(os.getenv("COOKIE_TTL_HOURS", "24"))
        self.max_cookie_size = int(os.getenv("MAX_COOKIE_SIZE_KB", "100")) * 1024  # 100KB default
        
        # Initialize encryption
        if encryption_key:
            self.fernet = Fernet(encryption_key.encode())
        else:
            # Generate key from environment or create new one
            self.fernet = self._initialize_encryption()
    
    def _initialize_encryption(self) -> Fernet:
        """Initialize encryption with key derivation from environment"""
        # Use SESSION_SECRET as base for key derivation
        session_secret = os.getenv("SESSION_SECRET", "default-dev-secret-change-in-production")
        
        # Derive encryption key using PBKDF2
        salt = b"tldw-cookie-salt"  # Static salt for consistency
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(session_secret.encode()))
        return Fernet(key)
    
    def store_cookies(self, user_id: int, cookies: Union[str, Dict, list], source: str = "upload") -> bool:
        """
        Store user cookies with encryption and metadata
        
        Args:
            user_id: User ID for cookie ownership
            cookies: Cookie data (string, dict, or list format)
            source: Source of cookies (upload, browser, etc.)
            
        Returns:
            bool: True if stored successfully, False otherwise
        """
        try:
            # Validate input
            if not isinstance(user_id, int) or user_id <= 0:
                self.logger.error(f"Invalid user_id for cookie storage: {user_id}")
                return False
            
            # Convert cookies to standardized format
            cookie_data = self._normalize_cookie_data(cookies)
            if not cookie_data:
                self.logger.error("Failed to normalize cookie data")
                return False
            
            # Check size limits
            cookie_json = json.dumps(cookie_data)
            if len(cookie_json.encode()) > self.max_cookie_size:
                self.logger.error(f"Cookie data too large: {len(cookie_json.encode())} bytes > {self.max_cookie_size}")
                return False
            
            # Create metadata
            metadata = {
                "user_id": user_id,
                "source": source,
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(hours=self.cookie_ttl_hours)).isoformat(),
                "size_bytes": len(cookie_json.encode())
            }
            
            # Encrypt cookie data
            encrypted_cookies = self.fernet.encrypt(cookie_json.encode())
            
            # Store encrypted data with metadata
            storage_data = {
                "metadata": metadata,
                "encrypted_cookies": base64.b64encode(encrypted_cookies).decode()
            }
            
            # Write to secure storage
            storage_path = self._get_cookie_storage_path(user_id)
            os.makedirs(os.path.dirname(storage_path), exist_ok=True)
            
            with open(storage_path, 'w') as f:
                json.dump(storage_data, f, indent=2)
            
            # Set restrictive permissions (Unix-like systems)
            try:
                os.chmod(storage_path, 0o600)  # Owner read/write only
            except (OSError, AttributeError):
                pass  # Windows or permission error
            
            self.logger.info(f"Stored encrypted cookies for user {user_id} from {source}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to store cookies for user {user_id}: {e}")
            return False
    
    def retrieve_cookies(self, user_id: int) -> Optional[Dict]:
        """
        Retrieve and decrypt user cookies with TTL validation
        
        Args:
            user_id: User ID for cookie ownership
            
        Returns:
            Dict: Decrypted cookie data or None if not found/expired
        """
        try:
            storage_path = self._get_cookie_storage_path(user_id)
            
            if not os.path.exists(storage_path):
                return None
            
            # Read storage data
            with open(storage_path, 'r') as f:
                storage_data = json.load(f)
            
            metadata = storage_data.get("metadata", {})
            
            # Validate ownership
            if metadata.get("user_id") != user_id:
                self.logger.warning(f"Cookie ownership mismatch for user {user_id}")
                return None
            
            # Check TTL
            expires_at = datetime.fromisoformat(metadata.get("expires_at", "1970-01-01T00:00:00"))
            if datetime.utcnow() > expires_at:
                self.logger.info(f"Cookies expired for user {user_id}, cleaning up")
                self.delete_cookies(user_id)
                return None
            
            # Decrypt cookie data
            encrypted_cookies = base64.b64decode(storage_data["encrypted_cookies"])
            decrypted_json = self.fernet.decrypt(encrypted_cookies).decode()
            cookie_data = json.loads(decrypted_json)
            
            self.logger.info(f"Retrieved cookies for user {user_id} (expires: {expires_at.strftime('%Y-%m-%d %H:%M')})")
            return cookie_data
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve cookies for user {user_id}: {e}")
            return None
    
    def delete_cookies(self, user_id: int) -> bool:
        """
        Delete user cookies and cleanup storage
        
        Args:
            user_id: User ID for cookie ownership
            
        Returns:
            bool: True if deleted successfully, False otherwise
        """
        try:
            storage_path = self._get_cookie_storage_path(user_id)
            
            if os.path.exists(storage_path):
                os.remove(storage_path)
                self.logger.info(f"Deleted cookies for user {user_id}")
                return True
            else:
                self.logger.debug(f"No cookies to delete for user {user_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to delete cookies for user {user_id}: {e}")
            return False
    
    def cleanup_expired_cookies(self) -> int:
        """
        Cleanup expired cookies across all users
        
        Returns:
            int: Number of expired cookie files cleaned up
        """
        cleaned_count = 0
        try:
            cookies_dir = os.path.dirname(self._get_cookie_storage_path(0))
            
            if not os.path.exists(cookies_dir):
                return 0
            
            for filename in os.listdir(cookies_dir):
                if not filename.endswith('.json'):
                    continue
                
                filepath = os.path.join(cookies_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        storage_data = json.load(f)
                    
                    metadata = storage_data.get("metadata", {})
                    expires_at = datetime.fromisoformat(metadata.get("expires_at", "1970-01-01T00:00:00"))
                    
                    if datetime.utcnow() > expires_at:
                        os.remove(filepath)
                        cleaned_count += 1
                        self.logger.debug(f"Cleaned up expired cookies: {filename}")
                        
                except Exception as e:
                    self.logger.warning(f"Failed to process cookie file {filename}: {e}")
                    continue
            
            if cleaned_count > 0:
                self.logger.info(f"Cleaned up {cleaned_count} expired cookie files")
            
            return cleaned_count
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup expired cookies: {e}")
            return 0
    
    def get_cookie_status(self, user_id: int) -> Dict[str, Any]:
        """
        Get cookie status and metadata for a user
        
        Args:
            user_id: User ID for cookie ownership
            
        Returns:
            Dict: Cookie status information
        """
        try:
            storage_path = self._get_cookie_storage_path(user_id)
            
            if not os.path.exists(storage_path):
                return {
                    "has_cookies": False,
                    "status": "not_configured"
                }
            
            with open(storage_path, 'r') as f:
                storage_data = json.load(f)
            
            metadata = storage_data.get("metadata", {})
            expires_at = datetime.fromisoformat(metadata.get("expires_at", "1970-01-01T00:00:00"))
            is_expired = datetime.utcnow() > expires_at
            
            return {
                "has_cookies": True,
                "status": "expired" if is_expired else "active",
                "created_at": metadata.get("created_at"),
                "expires_at": metadata.get("expires_at"),
                "source": metadata.get("source"),
                "size_bytes": metadata.get("size_bytes"),
                "ttl_hours": self.cookie_ttl_hours
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get cookie status for user {user_id}: {e}")
            return {
                "has_cookies": False,
                "status": "error",
                "error": str(e)
            }
    
    def _normalize_cookie_data(self, cookies: Union[str, Dict, list]) -> Optional[Dict]:
        """Normalize cookie data to standard format"""
        try:
            if isinstance(cookies, str):
                # Try to parse as JSON first
                try:
                    return json.loads(cookies)
                except json.JSONDecodeError:
                    # Treat as cookie string format
                    return {"cookie_string": cookies}
            elif isinstance(cookies, (dict, list)):
                return {"cookies": cookies}
            else:
                return None
        except Exception:
            return None
    
    def _get_cookie_storage_path(self, user_id: int) -> str:
        """Get secure storage path for user cookies"""
        cookies_dir = os.getenv("SECURE_COOKIES_DIR", "/app/secure_cookies")
        return os.path.join(cookies_dir, f"user_{user_id}_cookies.json")


class CredentialProtector:
    """Protect sensitive credentials and API keys from exposure"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.sensitive_patterns = [
            r'sk-[a-zA-Z0-9]{48}',  # OpenAI API keys
            r're_[a-zA-Z0-9]{24}',  # Resend API keys
            r'[a-zA-Z0-9]{32,}',    # Generic long keys
            r'Bearer\s+[a-zA-Z0-9]+',  # Bearer tokens
            r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+',  # Passwords
            r'secret["\']?\s*[:=]\s*["\']?[^"\'\s]+',    # Secrets
        ]
    
    def redact_sensitive_data(self, text: str) -> str:
        """
        Redact sensitive data from text for safe logging
        
        Args:
            text: Text that may contain sensitive data
            
        Returns:
            str: Text with sensitive data redacted
        """
        if not isinstance(text, str):
            return str(text)
        
        redacted_text = text
        
        for pattern in self.sensitive_patterns:
            import re
            redacted_text = re.sub(pattern, '[REDACTED]', redacted_text, flags=re.IGNORECASE)
        
        return redacted_text
    
    def validate_api_key_format(self, key_type: str, api_key: str) -> tuple[bool, str]:
        """
        Validate API key format for security
        
        Args:
            key_type: Type of API key (openai, resend, deepgram, etc.)
            api_key: The API key to validate
            
        Returns:
            tuple: (is_valid, message)
        """
        if not isinstance(api_key, str) or not api_key.strip():
            return False, "API key is empty or invalid type"
        
        key = api_key.strip()
        
        # Check for common security issues
        if len(key) < 16:
            return False, "API key too short (potential security risk)"
        
        if key.lower() in ['test', 'demo', 'example', 'placeholder']:
            return False, "API key appears to be a placeholder"
        
        # Type-specific validation
        if key_type.lower() == 'google':
            if not key.startswith('AIza'):
                return False, "Google API key should start with 'AIza'"
            if len(key) < 39:
                return False, "Google API key appears too short"
        
        elif key_type.lower() == 'resend':
            if not key.startswith('re_'):
                return False, "Resend API key should start with 're_'"
            if len(key) < 24:
                return False, "Resend API key appears too short"
        
        elif key_type.lower() == 'deepgram':
            if len(key) < 32:
                return False, "Deepgram API key appears too short"
        
        return True, "API key format is valid"
    
    def secure_environment_check(self) -> Dict[str, Any]:
        """
        Check environment for security best practices
        
        Returns:
            Dict: Security assessment results
        """
        issues = []
        warnings = []
        
        # Check for default/weak secrets
        session_secret = os.getenv("SESSION_SECRET", "")
        if not session_secret or session_secret == "dev-secret-key-change-in-production":
            issues.append("SESSION_SECRET is using default/weak value")
        elif len(session_secret) < 32:
            warnings.append("SESSION_SECRET should be at least 32 characters")
        
        # Check API key presence and format
        api_keys = {
            "GOOGLE_API_KEY": "google",
            "RESEND_API_KEY": "resend", 
            "DEEPGRAM_API_KEY": "deepgram"
        }
        
        for env_var, key_type in api_keys.items():
            key_value = os.getenv(env_var)
            if key_value:
                is_valid, message = self.validate_api_key_format(key_type, key_value)
                if not is_valid:
                    warnings.append(f"{env_var}: {message}")
        
        # Check file permissions on sensitive directories
        sensitive_dirs = [
            os.getenv("SECURE_COOKIES_DIR", "/app/secure_cookies"),
            os.getenv("COOKIE_LOCAL_DIR", "/app/cookies")
        ]
        
        for dir_path in sensitive_dirs:
            if os.path.exists(dir_path):
                try:
                    stat_info = os.stat(dir_path)
                    # Check if directory is world-readable (Unix-like systems)
                    if hasattr(stat_info, 'st_mode') and (stat_info.st_mode & 0o044):
                        warnings.append(f"Directory {dir_path} may be world-readable")
                except (OSError, AttributeError):
                    pass  # Windows or permission error
        
        return {
            "security_issues": issues,
            "security_warnings": warnings,
            "issues_count": len(issues),
            "warnings_count": len(warnings),
            "overall_status": "secure" if not issues else "issues_found"
        }


class LogRedactor:
    """Redact sensitive information from log messages"""
    
    def __init__(self):
        self.credential_protector = CredentialProtector()
    
    def redact_log_message(self, message: str) -> str:
        """
        Redact sensitive information from log messages
        
        Args:
            message: Log message that may contain sensitive data
            
        Returns:
            str: Log message with sensitive data redacted
        """
        return self.credential_protector.redact_sensitive_data(message)
    
    def create_safe_logging_filter(self):
        """Create a logging filter that redacts sensitive information"""
        class SensitiveDataFilter(logging.Filter):
            def __init__(self, redactor):
                super().__init__()
                self.redactor = redactor
            
            def filter(self, record):
                # Redact sensitive data from log message
                if hasattr(record, 'msg') and isinstance(record.msg, str):
                    record.msg = self.redactor.redact_log_message(record.msg)
                
                # Redact sensitive data from log arguments
                if hasattr(record, 'args') and record.args:
                    safe_args = []
                    for arg in record.args:
                        if isinstance(arg, str):
                            safe_args.append(self.redactor.redact_log_message(arg))
                        else:
                            safe_args.append(arg)
                    record.args = tuple(safe_args)
                
                return True
        
        return SensitiveDataFilter(self)


# Global instances
secure_cookie_manager = SecureCookieManager()
credential_protector = CredentialProtector()
log_redactor = LogRedactor()


def setup_secure_logging():
    """Setup logging with sensitive data redaction"""
    # Add redaction filter to root logger
    root_logger = logging.getLogger()
    redaction_filter = log_redactor.create_safe_logging_filter()
    root_logger.addFilter(redaction_filter)
    
    logging.info("Secure logging with data redaction enabled")


def get_security_status() -> Dict[str, Any]:
    """Get overall security status for health checks"""
    env_check = credential_protector.secure_environment_check()
    
    return {
        "cookie_encryption": "enabled",
        "log_redaction": "enabled", 
        "credential_validation": "enabled",
        "environment_security": env_check,
        "cookie_ttl_hours": secure_cookie_manager.cookie_ttl_hours
    }