#!/usr/bin/env python3
"""
Reliability Configuration Management for Transcript Services

This module provides centralized configuration management for reliability fixes
across YouTubei, FFmpeg, and Transcript services. It loads settings from
environment variables with sensible defaults and provides validation.
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any

from logging_setup import get_logger

logger = get_logger(__name__)


@dataclass
class ReliabilityConfig:
    """Configuration for reliability fixes across transcript services."""
    
    # Timeout settings
    ffmpeg_timeout: int = 60
    youtubei_hard_timeout: int = 45
    playwright_navigation_timeout: int = 60
    
    # Proxy enforcement
    enforce_proxy_all: bool = False
    use_proxy_for_timedtext: bool = True
    
    # Feature flags for reliability fixes
    enable_caption_tracks_shortcut: bool = True
    enable_deterministic_selectors: bool = True
    enable_content_validation: bool = True
    enable_fast_fail_youtubei: bool = True
    enable_asr_playback_trigger: bool = True
    
    # Retry and circuit breaker settings
    ffmpeg_max_retries: int = 2
    timedtext_retries: int = 1
    youtubei_retries: int = 0  # Fast-fail to next method
    circuit_breaker_recovery: int = 600  # 10 minutes
    
    # ASR settings
    asr_max_video_minutes: int = 20
    
    @classmethod
    def from_env(cls) -> 'ReliabilityConfig':
        """Load configuration from environment variables with validation."""
        try:
            config = cls(
                # Timeout settings
                ffmpeg_timeout=cls._parse_int_env("FFMPEG_TIMEOUT", 60, min_val=30, max_val=300),
                youtubei_hard_timeout=cls._parse_int_env("YOUTUBEI_HARD_TIMEOUT", 45, min_val=20, max_val=120),
                playwright_navigation_timeout=cls._parse_int_env("PLAYWRIGHT_NAVIGATION_TIMEOUT", 60, min_val=30, max_val=180),
                
                # Proxy settings
                enforce_proxy_all=cls._parse_bool_env("ENFORCE_PROXY_ALL", False),
                use_proxy_for_timedtext=cls._parse_bool_env("USE_PROXY_FOR_TIMEDTEXT", True),
                
                # Feature flags
                enable_caption_tracks_shortcut=cls._parse_bool_env("ENABLE_CAPTION_TRACKS_SHORTCUT", True),
                enable_deterministic_selectors=cls._parse_bool_env("ENABLE_DETERMINISTIC_SELECTORS", True),
                enable_content_validation=cls._parse_bool_env("ENABLE_CONTENT_VALIDATION", True),
                enable_fast_fail_youtubei=cls._parse_bool_env("ENABLE_FAST_FAIL_YOUTUBEI", True),
                enable_asr_playback_trigger=cls._parse_bool_env("ENABLE_ASR_PLAYBACK_TRIGGER", True),
                
                # Retry settings
                ffmpeg_max_retries=cls._parse_int_env("FFMPEG_MAX_RETRIES", 2, min_val=0, max_val=5),
                timedtext_retries=cls._parse_int_env("TIMEDTEXT_RETRIES", 1, min_val=0, max_val=3),
                youtubei_retries=cls._parse_int_env("YOUTUBEI_RETRIES", 0, min_val=0, max_val=2),
                circuit_breaker_recovery=cls._parse_int_env("CIRCUIT_BREAKER_RECOVERY", 600, min_val=60, max_val=3600),
                
                # ASR settings
                asr_max_video_minutes=cls._parse_int_env("ASR_MAX_VIDEO_MINUTES", 20, min_val=1, max_val=120)
            )
            
            # Validate configuration consistency
            config._validate_config()
            
            # Log configuration for debugging
            config._log_config()
            
            return config
            
        except Exception as e:
            logger.error(f"Failed to load reliability configuration: {e}")
            logger.warning("Using default reliability configuration")
            return cls()
    
    @staticmethod
    def _parse_bool_env(env_var: str, default: bool) -> bool:
        """Parse boolean environment variable with validation."""
        value = os.getenv(env_var, str(default).lower())
        if isinstance(value, bool):
            return value
        return value.lower() in ("1", "true", "yes", "on")
    
    @staticmethod
    def _parse_int_env(env_var: str, default: int, min_val: Optional[int] = None, max_val: Optional[int] = None) -> int:
        """Parse integer environment variable with validation."""
        try:
            value = int(os.getenv(env_var, str(default)))
            
            if min_val is not None and value < min_val:
                logger.warning(f"{env_var}={value} is below minimum {min_val}, using {min_val}")
                return min_val
                
            if max_val is not None and value > max_val:
                logger.warning(f"{env_var}={value} is above maximum {max_val}, using {max_val}")
                return max_val
                
            return value
            
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid value for {env_var}: {os.getenv(env_var)}, using default {default}")
            return default
    
    def _validate_config(self) -> None:
        """Validate configuration consistency and log warnings for problematic combinations."""
        warnings = []
        
        # Validate timeout relationships
        if self.youtubei_hard_timeout >= self.ffmpeg_timeout:
            warnings.append(f"YouTubei timeout ({self.youtubei_hard_timeout}s) should be less than FFmpeg timeout ({self.ffmpeg_timeout}s)")
        
        # Validate proxy enforcement consistency
        if self.enforce_proxy_all and not self.use_proxy_for_timedtext:
            warnings.append("ENFORCE_PROXY_ALL=True but USE_PROXY_FOR_TIMEDTEXT=False - this may cause inconsistent behavior")
        
        # Validate feature flag combinations
        if not self.enable_caption_tracks_shortcut and not self.enable_deterministic_selectors:
            warnings.append("Both caption tracks shortcut and deterministic selectors disabled - this may reduce success rates")
        
        # Validate retry settings
        if self.youtubei_retries > 0 and self.enable_fast_fail_youtubei:
            warnings.append("YouTubei retries > 0 with fast-fail enabled - fast-fail may not work as expected")
        
        # Log warnings
        for warning in warnings:
            logger.warning(f"Configuration warning: {warning}")
    
    def _log_config(self) -> None:
        """Log current configuration for debugging deployment issues."""
        logger.info("Reliability configuration loaded:")
        logger.info(f"  Timeouts: FFmpeg={self.ffmpeg_timeout}s, YouTubei={self.youtubei_hard_timeout}s, Playwright={self.playwright_navigation_timeout}s")
        logger.info(f"  Proxy: enforce_all={self.enforce_proxy_all}, timedtext={self.use_proxy_for_timedtext}")
        logger.info(f"  Features: caption_shortcut={self.enable_caption_tracks_shortcut}, deterministic_selectors={self.enable_deterministic_selectors}")
        logger.info(f"  Features: content_validation={self.enable_content_validation}, fast_fail={self.enable_fast_fail_youtubei}")
        logger.info(f"  Retries: FFmpeg={self.ffmpeg_max_retries}, Timedtext={self.timedtext_retries}, YouTubei={self.youtubei_retries}")
        logger.info(f"  ASR: max_minutes={self.asr_max_video_minutes}, playback_trigger={self.enable_asr_playback_trigger}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for serialization."""
        return {
            "timeouts": {
                "ffmpeg_timeout": self.ffmpeg_timeout,
                "youtubei_hard_timeout": self.youtubei_hard_timeout,
                "playwright_navigation_timeout": self.playwright_navigation_timeout
            },
            "proxy": {
                "enforce_proxy_all": self.enforce_proxy_all,
                "use_proxy_for_timedtext": self.use_proxy_for_timedtext
            },
            "features": {
                "enable_caption_tracks_shortcut": self.enable_caption_tracks_shortcut,
                "enable_deterministic_selectors": self.enable_deterministic_selectors,
                "enable_content_validation": self.enable_content_validation,
                "enable_fast_fail_youtubei": self.enable_fast_fail_youtubei,
                "enable_asr_playback_trigger": self.enable_asr_playback_trigger
            },
            "retries": {
                "ffmpeg_max_retries": self.ffmpeg_max_retries,
                "timedtext_retries": self.timedtext_retries,
                "youtubei_retries": self.youtubei_retries,
                "circuit_breaker_recovery": self.circuit_breaker_recovery
            },
            "asr": {
                "asr_max_video_minutes": self.asr_max_video_minutes
            }
        }
    
    def get_health_check_info(self) -> Dict[str, Any]:
        """Get configuration info for health checks."""
        return {
            "reliability_config_loaded": True,
            "proxy_enforcement": self.enforce_proxy_all,
            "feature_flags_enabled": sum([
                self.enable_caption_tracks_shortcut,
                self.enable_deterministic_selectors,
                self.enable_content_validation,
                self.enable_fast_fail_youtubei,
                self.enable_asr_playback_trigger
            ]),
            "timeout_config": {
                "ffmpeg": self.ffmpeg_timeout,
                "youtubei": self.youtubei_hard_timeout
            }
        }


# Global configuration instance
_reliability_config: Optional[ReliabilityConfig] = None


def get_reliability_config() -> ReliabilityConfig:
    """Get the global reliability configuration instance."""
    global _reliability_config
    if _reliability_config is None:
        _reliability_config = ReliabilityConfig.from_env()
    return _reliability_config


def reload_reliability_config() -> ReliabilityConfig:
    """Reload configuration from environment variables."""
    global _reliability_config
    _reliability_config = ReliabilityConfig.from_env()
    return _reliability_config


def validate_reliability_config() -> Dict[str, Any]:
    """Validate reliability configuration and return status."""
    try:
        config = get_reliability_config()
        return {
            "status": "valid",
            "config": config.to_dict(),
            "health_info": config.get_health_check_info()
        }
    except Exception as e:
        logger.error(f"Reliability configuration validation failed: {e}")
        return {
            "status": "invalid",
            "error": str(e),
            "config": None
        }