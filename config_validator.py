#!/usr/bin/env python3
"""
Configuration management and validation for the no-yt-dl summarization stack
"""
import os
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ConfigValidationResult:
    """Result of configuration validation"""
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    config: Dict[str, Any]


class ConfigValidator:
    """Comprehensive configuration validator for all services"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def validate_all_config(self) -> ConfigValidationResult:
        """Validate all configuration settings"""
        errors = []
        warnings = []
        config = {}
        
        # Validate feature flags
        feature_config, feature_errors, feature_warnings = self._validate_feature_flags()
        config.update(feature_config)
        errors.extend(feature_errors)
        warnings.extend(feature_warnings)
        
        # Validate performance settings
        perf_config, perf_errors, perf_warnings = self._validate_performance_config()
        config.update(perf_config)
        errors.extend(perf_errors)
        warnings.extend(perf_warnings)
        
        # Validate service credentials
        cred_config, cred_errors, cred_warnings = self._validate_service_credentials()
        config.update(cred_config)
        errors.extend(cred_errors)
        warnings.extend(cred_warnings)
        
        # Validate email configuration
        email_config, email_errors, email_warnings = self._validate_email_config()
        config.update(email_config)
        errors.extend(email_errors)
        warnings.extend(email_warnings)
        
        # Validate ASR configuration
        asr_config, asr_errors, asr_warnings = self._validate_asr_config()
        config.update(asr_config)
        errors.extend(asr_errors)
        warnings.extend(asr_warnings)
        
        is_valid = len(errors) == 0
        
        return ConfigValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            config=config
        )
    
    def _validate_feature_flags(self) -> tuple[Dict[str, Any], list[str], list[str]]:
        """Validate feature flag configuration"""
        config = {}
        errors = []
        warnings = []
        
        # Feature flags with defaults
        flags = {
            "ENABLE_YT_API": ("1", "YouTube Transcript API"),
            "ENABLE_TIMEDTEXT": ("1", "Timed-text endpoints"),
            "ENABLE_YOUTUBEI": ("0", "YouTubei Playwright capture"),
            "ENABLE_ASR_FALLBACK": ("0", "ASR fallback system")
        }
        
        for flag, (default, description) in flags.items():
            value = os.getenv(flag, default)
            if value not in ["0", "1"]:
                errors.append(f"{flag} must be '0' or '1', got '{value}'")
                config[flag] = default == "1"
            else:
                config[flag] = value == "1"
                if value != default:
                    warnings.append(f"{flag} set to {value} (non-default for {description})")
        
        # Validate feature flag combinations
        if not config.get("ENABLE_YT_API") and not config.get("ENABLE_TIMEDTEXT"):
            errors.append("At least one of ENABLE_YT_API or ENABLE_TIMEDTEXT must be enabled")
        
        if config.get("ENABLE_ASR_FALLBACK") and not config.get("ENABLE_YOUTUBEI"):
            warnings.append("ASR fallback enabled without YouTubei - may have limited effectiveness")
        
        return config, errors, warnings
    
    def _validate_performance_config(self) -> tuple[Dict[str, Any], list[str], list[str]]:
        """Validate performance and timeout configuration"""
        config = {}
        errors = []
        warnings = []
        
        # Performance settings with validation
        settings = {
            "WORKER_CONCURRENCY": (2, 1, 10, "Background worker threads"),
            "PW_NAV_TIMEOUT_MS": (15000, 5000, 60000, "Playwright navigation timeout"),
            "ASR_MAX_VIDEO_MINUTES": (20, 1, 120, "ASR maximum video duration")
        }
        
        for setting, (default, min_val, max_val, description) in settings.items():
            try:
                value = int(os.getenv(setting, str(default)))
                if value < min_val or value > max_val:
                    errors.append(f"{setting} must be between {min_val} and {max_val}, got {value}")
                    config[setting] = default
                else:
                    config[setting] = value
                    if value != default:
                        warnings.append(f"{setting} set to {value} (default: {default}) for {description}")
            except ValueError:
                errors.append(f"{setting} must be a valid integer, got '{os.getenv(setting)}'")
                config[setting] = default
        
        # Validate proxy settings
        use_proxy_timedtext = os.getenv("USE_PROXY_FOR_TIMEDTEXT", "0")
        if use_proxy_timedtext not in ["0", "1"]:
            errors.append(f"USE_PROXY_FOR_TIMEDTEXT must be '0' or '1', got '{use_proxy_timedtext}'")
            config["USE_PROXY_FOR_TIMEDTEXT"] = False
        else:
            config["USE_PROXY_FOR_TIMEDTEXT"] = use_proxy_timedtext == "1"
            if use_proxy_timedtext == "1":
                warnings.append("USE_PROXY_FOR_TIMEDTEXT=1 may increase latency and error rates")
        
        return config, errors, warnings
    
    def _validate_service_credentials(self) -> tuple[Dict[str, Any], list[str], list[str]]:
        """Validate service credentials and API keys"""
        config = {}
        errors = []
        warnings = []
        
        # Required credentials
        required_creds = {
            "OPENAI_API_KEY": "OpenAI API for summarization",
            "GOOGLE_CLIENT_ID": "Google OAuth for YouTube access",
            "GOOGLE_CLIENT_SECRET": "Google OAuth secret",
            "SESSION_SECRET": "Flask session encryption"
        }
        
        for cred, description in required_creds.items():
            value = os.getenv(cred)
            if not value:
                errors.append(f"{cred} is required for {description}")
                config[f"{cred}_configured"] = False
            else:
                config[f"{cred}_configured"] = True
                # Basic validation for key format
                if cred == "OPENAI_API_KEY" and not value.startswith("sk-"):
                    warnings.append("OPENAI_API_KEY should start with 'sk-'")
                elif cred == "SESSION_SECRET" and len(value) < 32:
                    warnings.append("SESSION_SECRET should be at least 32 characters for security")
        
        return config, errors, warnings
    
    def _validate_email_config(self) -> tuple[Dict[str, Any], list[str], list[str]]:
        """Validate email service configuration"""
        config = {}
        errors = []
        warnings = []
        
        # Email service settings
        resend_key = os.getenv("RESEND_API_KEY")
        sender_email = os.getenv("SENDER_EMAIL")
        
        if not resend_key:
            errors.append("RESEND_API_KEY is required for email functionality")
            config["email_configured"] = False
        else:
            config["email_configured"] = True
            config["RESEND_API_KEY_configured"] = True
            # Basic validation for Resend API key format
            if not resend_key.startswith("re_"):
                warnings.append("RESEND_API_KEY should start with 're_'")
        
        if not sender_email:
            errors.append("SENDER_EMAIL is required for email functionality")
            config["SENDER_EMAIL_configured"] = False
        else:
            config["SENDER_EMAIL_configured"] = True
            # Basic email validation
            if "@" not in sender_email or "." not in sender_email:
                warnings.append("SENDER_EMAIL format may be invalid")
        
        return config, errors, warnings
    
    def _validate_asr_config(self) -> tuple[Dict[str, Any], list[str], list[str]]:
        """Validate ASR (Deepgram) configuration"""
        config = {}
        errors = []
        warnings = []
        
        enable_asr = os.getenv("ENABLE_ASR_FALLBACK", "0") == "1"
        deepgram_key = os.getenv("DEEPGRAM_API_KEY")
        
        config["asr_enabled"] = enable_asr
        
        if enable_asr:
            if not deepgram_key:
                errors.append("DEEPGRAM_API_KEY is required when ENABLE_ASR_FALLBACK=1")
                config["DEEPGRAM_API_KEY_configured"] = False
            else:
                config["DEEPGRAM_API_KEY_configured"] = True
                # Basic validation for Deepgram API key
                if len(deepgram_key) < 32:
                    warnings.append("DEEPGRAM_API_KEY seems too short")
        else:
            config["DEEPGRAM_API_KEY_configured"] = bool(deepgram_key)
            if deepgram_key:
                warnings.append("DEEPGRAM_API_KEY configured but ASR fallback disabled")
        
        return config, errors, warnings
    
    def validate_runtime_config(self) -> Dict[str, Any]:
        """Validate configuration at runtime and return safe defaults"""
        result = self.validate_all_config()
        
        if not result.is_valid:
            self.logger.error("Configuration validation failed:")
            for error in result.errors:
                self.logger.error(f"  - {error}")
        
        if result.warnings:
            self.logger.warning("Configuration warnings:")
            for warning in result.warnings:
                self.logger.warning(f"  - {warning}")
        
        return result.config
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of current configuration for health checks"""
        result = self.validate_all_config()
        
        return {
            "validation_status": "valid" if result.is_valid else "invalid",
            "error_count": len(result.errors),
            "warning_count": len(result.warnings),
            "feature_flags": {
                "yt_api": result.config.get("ENABLE_YT_API", False),
                "timedtext": result.config.get("ENABLE_TIMEDTEXT", False),
                "youtubei": result.config.get("ENABLE_YOUTUBEI", False),
                "asr_fallback": result.config.get("ENABLE_ASR_FALLBACK", False)
            },
            "services_configured": {
                "openai": result.config.get("OPENAI_API_KEY_configured", False),
                "email": result.config.get("email_configured", False),
                "deepgram": result.config.get("DEEPGRAM_API_KEY_configured", False),
                "google_oauth": result.config.get("GOOGLE_CLIENT_ID_configured", False)
            },
            "performance_settings": {
                "worker_concurrency": result.config.get("WORKER_CONCURRENCY", 2),
                "pw_timeout_ms": result.config.get("PW_NAV_TIMEOUT_MS", 15000),
                "asr_max_minutes": result.config.get("ASR_MAX_VIDEO_MINUTES", 20)
            }
        }


# Global configuration validator instance
config_validator = ConfigValidator()


def validate_startup_config() -> bool:
    """Validate configuration at application startup"""
    result = config_validator.validate_all_config()
    
    if result.errors:
        logging.error("=== Configuration Validation Errors ===")
        for error in result.errors:
            logging.error(f"❌ {error}")
    
    if result.warnings:
        logging.warning("=== Configuration Warnings ===")
        for warning in result.warnings:
            logging.warning(f"⚠️  {warning}")
    
    if result.is_valid:
        logging.info("✅ Configuration validation passed")
    else:
        logging.error("❌ Configuration validation failed - some features may not work")
    
    return result.is_valid


def get_validated_config() -> Dict[str, Any]:
    """Get validated configuration with safe defaults"""
    return config_validator.validate_runtime_config()