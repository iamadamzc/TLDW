#!/usr/bin/env python3
"""
Download Attempt Tracking Module

This module provides comprehensive download attempt tracking and cookie freshness
logging for health endpoint exposure without exposing sensitive data.
"""

import os
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

@dataclass
class DownloadAttempt:
    """
    Comprehensive download attempt metadata for health endpoint exposure.
    
    This dataclass tracks download attempts without exposing sensitive data
    like file paths, cookie contents, or proxy credentials.
    """
    video_id: str
    success: bool
    error_message: Optional[str]
    cookies_used: bool
    client_used: str
    proxy_used: bool
    step1_error: Optional[str] = None
    step2_error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    duration_seconds: Optional[float] = None
    file_size_bytes: Optional[int] = None
    
    def get_combined_error(self) -> str:
        """Combine step errors for logging"""
        if self.step1_error and self.step2_error:
            return f"{self.step1_error} || {self.step2_error}"
        return self.step1_error or self.step2_error or self.error_message or "Unknown error"
    
    def to_health_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for health endpoint exposure (no sensitive data)"""
        return {
            "success": self.success,
            "cookies_used": self.cookies_used,
            "client_used": self.client_used,
            "proxy_used": self.proxy_used,
            "timestamp": self.timestamp.isoformat(),
            "duration_seconds": self.duration_seconds,
            "has_error": bool(self.error_message),
            # Note: Don't expose video_id, error_message, or file_size for privacy
        }

class CookieFreshnessLogger:
    """
    Cookie freshness logging utility that logs cookie metadata without exposing contents.
    """
    
    @staticmethod
    def log_cookie_freshness(cookiefile: Optional[str], user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Log cookie file freshness metadata without exposing contents.
        
        Args:
            cookiefile: Path to cookie file (can be None)
            user_id: User ID for logging context (optional)
            
        Returns:
            Dictionary with cookie metadata for logging
        """
        if not cookiefile:
            logging.info("🍪 Cookie usage: disabled (no cookiefile provided)")
            return {
                "cookies_enabled": False,
                "reason": "no_cookiefile"
            }
        
        if not os.path.exists(cookiefile):
            logging.warning(f"🍪 Cookie file not found: {Path(cookiefile).name}")
            return {
                "cookies_enabled": False,
                "reason": "file_not_found",
                "filename": Path(cookiefile).name  # Only filename, not full path
            }
        
        try:
            # Get file metadata without exposing contents
            stat = os.stat(cookiefile)
            file_size = stat.st_size
            mtime = stat.st_mtime
            age_hours = (time.time() - mtime) / 3600
            
            # Determine freshness
            is_fresh = age_hours <= 12  # 12 hour freshness threshold
            
            # Create safe logging context
            user_context = f" (user={user_id})" if user_id else ""
            filename = Path(cookiefile).name
            
            if is_fresh:
                logging.info(f"🍪 Cookie usage: enabled{user_context} - file={filename} age={age_hours:.1f}h size={file_size}b")
            else:
                logging.warning(f"🍪 Cookie usage: stale{user_context} - file={filename} age={age_hours:.1f}h (>12h) size={file_size}b")
            
            return {
                "cookies_enabled": True,
                "is_fresh": is_fresh,
                "age_hours": round(age_hours, 1),
                "file_size_bytes": file_size,
                "filename": filename,  # Only filename, not full path
                "user_id": user_id
            }
            
        except Exception as e:
            logging.error(f"🍪 Cookie freshness check failed: {e}")
            return {
                "cookies_enabled": False,
                "reason": "check_failed",
                "error": str(e)
            }

class DownloadAttemptTracker:
    """
    Download attempt tracking for health endpoint exposure.
    
    Tracks download attempts and maintains metadata for monitoring
    without exposing sensitive information.
    """
    
    def __init__(self):
        self.last_attempt: Optional[DownloadAttempt] = None
        self.attempt_count = 0
        self.success_count = 0
    
    def track_attempt(self, attempt: DownloadAttempt) -> None:
        """
        Track a download attempt for health monitoring.
        
        Args:
            attempt: DownloadAttempt instance with metadata
        """
        self.last_attempt = attempt
        self.attempt_count += 1
        
        if attempt.success:
            self.success_count += 1
        
        # Log attempt without sensitive data
        status = "success" if attempt.success else "failed"
        logging.info(
            f"📊 Download attempt tracked: {status} "
            f"cookies={attempt.cookies_used} client={attempt.client_used} "
            f"proxy={attempt.proxy_used}"
        )
    
    def get_health_metadata(self) -> Dict[str, Any]:
        """
        Get health metadata for endpoint exposure.
        
        Returns:
            Dictionary with safe metadata for health endpoints
        """
        if not self.last_attempt:
            return {
                "has_attempts": False,
                "total_attempts": self.attempt_count,
                "success_count": self.success_count
            }
        
        return {
            "has_attempts": True,
            "total_attempts": self.attempt_count,
            "success_count": self.success_count,
            "success_rate": self.success_count / self.attempt_count if self.attempt_count > 0 else 0,
            "last_attempt": self.last_attempt.to_health_dict()
        }
    
    def create_attempt(
        self,
        video_id: str,
        success: bool,
        cookies_used: bool,
        client_used: str,
        proxy_used: bool,
        error_message: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        file_size_bytes: Optional[int] = None
    ) -> DownloadAttempt:
        """
        Create and track a download attempt.
        
        Args:
            video_id: Video identifier (will be sanitized for logging)
            success: Whether the download succeeded
            cookies_used: Whether cookies were used
            client_used: Which client was used (android, web, etc.)
            proxy_used: Whether proxy was used
            error_message: Error message if failed (optional)
            duration_seconds: Download duration (optional)
            file_size_bytes: Downloaded file size (optional)
            
        Returns:
            DownloadAttempt instance
        """
        # Sanitize video_id for privacy (only keep first 8 chars)
        sanitized_video_id = video_id[:8] + "..." if len(video_id) > 8 else video_id
        
        attempt = DownloadAttempt(
            video_id=sanitized_video_id,
            success=success,
            error_message=error_message,
            cookies_used=cookies_used,
            client_used=client_used,
            proxy_used=proxy_used,
            duration_seconds=duration_seconds,
            file_size_bytes=file_size_bytes
        )
        
        self.track_attempt(attempt)
        return attempt

# Global tracker instance
_global_tracker = DownloadAttemptTracker()

def get_global_tracker() -> DownloadAttemptTracker:
    """Get the global download attempt tracker instance"""
    return _global_tracker

def log_cookie_freshness(cookiefile: Optional[str], user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Convenience function for cookie freshness logging.
    
    Args:
        cookiefile: Path to cookie file
        user_id: User ID for context
        
    Returns:
        Cookie metadata dictionary
    """
    return CookieFreshnessLogger.log_cookie_freshness(cookiefile, user_id)

def track_download_attempt(
    video_id: str,
    success: bool,
    cookies_used: bool,
    client_used: str,
    proxy_used: bool,
    error_message: Optional[str] = None,
    duration_seconds: Optional[float] = None,
    file_size_bytes: Optional[int] = None
) -> DownloadAttempt:
    """
    Convenience function for tracking download attempts.
    
    Args:
        video_id: Video identifier
        success: Whether download succeeded
        cookies_used: Whether cookies were used
        client_used: Client type used
        proxy_used: Whether proxy was used
        error_message: Error message if failed
        duration_seconds: Download duration
        file_size_bytes: File size
        
    Returns:
        DownloadAttempt instance
    """
    return _global_tracker.create_attempt(
        video_id=video_id,
        success=success,
        cookies_used=cookies_used,
        client_used=client_used,
        proxy_used=proxy_used,
        error_message=error_message,
        duration_seconds=duration_seconds,
        file_size_bytes=file_size_bytes
    )

def get_download_health_metadata() -> Dict[str, Any]:
    """
    Get download attempt metadata for health endpoints.
    
    Returns:
        Health metadata dictionary
    """
    return _global_tracker.get_health_metadata()