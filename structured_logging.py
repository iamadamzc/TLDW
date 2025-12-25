#!/usr/bin/env python3
"""
Enhanced structured logging for production monitoring.
Implements comprehensive logging with JSON formatting, correlation IDs, and performance tracking.

BACKWARD COMPATIBILITY LAYER:
This module now provides backward compatibility for the transition to minimal JSON logging.
When USE_MINIMAL_LOGGING=true, it delegates to the new logging_setup.py system.
When USE_MINIMAL_LOGGING=false or unset, it uses the legacy structured logging system.
"""

import os
import sys
import json
import time
import logging
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List
from contextlib import contextmanager
from dataclasses import dataclass, asdict
import uuid
import traceback

# Feature flag for gradual migration to minimal logging
USE_MINIMAL_LOGGING = os.getenv("USE_MINIMAL_LOGGING", "false").lower() == "true"

# Import minimal logging components if enabled
if USE_MINIMAL_LOGGING:
    try:
        from logging_setup import configure_logging as _configure_minimal_logging
        from logging_setup import set_job_ctx as _set_minimal_job_ctx
        from logging_setup import clear_job_ctx as _clear_minimal_job_ctx
        from logging_setup import get_perf_logger as _get_minimal_perf_logger
        from log_events import evt as _minimal_evt, StageTimer as _MinimalStageTimer
        _MINIMAL_LOGGING_AVAILABLE = True
    except ImportError as e:
        logging.warning(f"Minimal logging not available, falling back to legacy: {e}")
        _MINIMAL_LOGGING_AVAILABLE = False
        USE_MINIMAL_LOGGING = False
else:
    _MINIMAL_LOGGING_AVAILABLE = False


@dataclass
class LogContext:
    """Structured log context for correlation and tracing."""
    correlation_id: str
    video_id: Optional[str] = None
    user_id: Optional[str] = None
    job_id: Optional[str] = None
    stage: Optional[str] = None
    profile: Optional[str] = None
    proxy_used: Optional[bool] = None
    start_time: Optional[float] = None


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def __init__(self):
        super().__init__()
        self.hostname = os.getenv("HOSTNAME", "unknown")
        self.service_name = os.getenv("SERVICE_NAME", "tldw-transcript-service")
        self.environment = os.getenv("ENVIRONMENT", "production")
        self.version = os.getenv("APP_VERSION", "unknown")
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        # Base log structure
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service_name,
            "environment": self.environment,
            "version": self.version,
            "hostname": self.hostname,
            "thread": threading.current_thread().name,
            "process_id": os.getpid()
        }
        
        # Add context information if available
        context = getattr(record, 'context', None)
        if context:
            log_entry.update({
                "correlation_id": context.correlation_id,
                "video_id": context.video_id,
                "user_id": context.user_id,
                "job_id": context.job_id,
                "stage": context.stage,
                "profile": context.profile,
                "proxy_used": context.proxy_used
            })
            
            # Add duration if start_time is available
            if context.start_time:
                log_entry["duration_ms"] = round((time.time() - context.start_time) * 1000, 2)
        
        # Add extra fields from record
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 
                          'msecs', 'relativeCreated', 'thread', 'threadName', 
                          'processName', 'process', 'getMessage', 'context']:
                extra_fields[key] = value
        
        if extra_fields:
            log_entry["extra"] = extra_fields
        
        # Add exception information if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Add source location for errors and warnings
        if record.levelno >= logging.WARNING:
            log_entry["source"] = {
                "file": record.filename,
                "line": record.lineno,
                "function": record.funcName
            }
        
        return json.dumps(log_entry, default=str, separators=(',', ':'))


class ContextualLogger:
    """Logger with automatic context injection."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self._local = threading.local()
    
    def set_context(self, context: LogContext):
        """Set logging context for current thread."""
        self._local.context = context
    
    def get_context(self) -> Optional[LogContext]:
        """Get current logging context."""
        return getattr(self._local, 'context', None)
    
    def clear_context(self):
        """Clear current logging context."""
        if hasattr(self._local, 'context'):
            delattr(self._local, 'context')
    
    def _log_with_context(self, level: int, message: str, **kwargs):
        """Log message with current context."""
        context = self.get_context()
        
        # Create log record
        record = self.logger.makeRecord(
            name=self.logger.name,
            level=level,
            fn="",
            lno=0,
            msg=message,
            args=(),
            exc_info=None
        )
        
        # Add context to record
        if context:
            record.context = context
        
        # Add extra fields
        for key, value in kwargs.items():
            setattr(record, key, value)
        
        # Handle the record
        self.logger.handle(record)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with context."""
        self._log_with_context(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message with context."""
        self._log_with_context(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with context."""
        self._log_with_context(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with context."""
        self._log_with_context(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message with context."""
        self._log_with_context(logging.CRITICAL, message, **kwargs)


class PerformanceLogger:
    """Specialized logger for performance metrics using dedicated performance channel."""
    
    def __init__(self):
        self.logger = ContextualLogger("perf")
    
    def log_stage_performance(self, stage: str, duration_ms: float, success: bool, 
                            video_id: str, **kwargs):
        """Log stage performance metrics using dedicated performance channel."""
        from log_events import perf_evt
        
        perf_evt(
            metric_type="stage_performance",
            stage=stage,
            duration_ms=duration_ms,
            success=success,
            video_id=video_id,
            **kwargs
        )
    
    def log_circuit_breaker_event(self, event_type: str, state: str, **kwargs):
        """Log circuit breaker events using dedicated performance channel."""
        from log_events import perf_evt
        
        perf_evt(
            metric_type="circuit_breaker",
            event_type=event_type,
            circuit_breaker_state=state,
            **kwargs
        )
    
    def log_browser_context_metrics(self, action: str, profile: str, **kwargs):
        """Log browser context metrics using dedicated performance channel."""
        from log_events import perf_evt
        
        perf_evt(
            metric_type="browser_context",
            action=action,
            profile=profile,
            **kwargs
        )
    
    def log_proxy_health_metrics(self, healthy: bool, **kwargs):
        """Log proxy health metrics using dedicated performance channel."""
        from log_events import perf_evt
        
        perf_evt(
            metric_type="proxy_health",
            healthy=healthy,
            **kwargs
        )


class AlertLogger:
    """Specialized logger for alerts and critical events."""
    
    def __init__(self):
        self.logger = ContextualLogger("alerts")
    
    def log_circuit_breaker_alert(self, alert_type: str, details: Dict[str, Any]):
        """Log circuit breaker alerts."""
        self.logger.warning(
            f"Circuit breaker alert: {alert_type}",
            alert_type=alert_type,
            alert_category="circuit_breaker",
            **details
        )
    
    def log_performance_alert(self, metric: str, threshold: float, current_value: float):
        """Log performance threshold alerts."""
        self.logger.warning(
            f"Performance alert: {metric} exceeded threshold",
            metric=metric,
            threshold=threshold,
            current_value=current_value,
            alert_category="performance"
        )
    
    def log_resource_alert(self, resource: str, usage_percent: float, threshold_percent: float):
        """Log resource usage alerts."""
        self.logger.warning(
            f"Resource alert: {resource} usage high",
            resource=resource,
            usage_percent=usage_percent,
            threshold_percent=threshold_percent,
            alert_category="resource"
        )


def setup_structured_logging():
    """Configure structured logging for production."""
    # Get log level from environment
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Create structured formatter
    formatter = StructuredFormatter()
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add console handler with structured formatting
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Configure specific loggers
    loggers_config = {
        "transcript_service": log_level,
        "proxy_manager": log_level,
        "performance": log_level,
        "alerts": "WARNING",
        "monitoring": log_level,
        "playwright": "WARNING",  # Reduce playwright noise
        "urllib3": "WARNING",     # Reduce HTTP noise
        "requests": "WARNING",    # Reduce requests noise
    }
    
    for logger_name, level in loggers_config.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(getattr(logging, level))
    
    logging.info(f"Structured logging configured: level={log_level}, formatter=json, environment={os.getenv('ENVIRONMENT', 'production')}")


@contextmanager
def log_context(correlation_id: Optional[str] = None, **context_kwargs):
    """Context manager for structured logging context."""
    logger = ContextualLogger("context")
    
    # Generate correlation ID if not provided
    if not correlation_id:
        correlation_id = str(uuid.uuid4())
    
    # Create context
    context = LogContext(
        correlation_id=correlation_id,
        start_time=time.time(),
        **context_kwargs
    )
    
    # Set context
    logger.set_context(context)
    
    try:
        yield context
    finally:
        # Clear context
        logger.clear_context()


@contextmanager
def log_performance(operation: str, **context_kwargs):
    """Context manager for performance logging."""
    perf_logger = PerformanceLogger()
    start_time = time.time()
    
    with log_context(**context_kwargs) as context:
        try:
            yield context
            
            # Log successful operation
            duration_ms = (time.time() - start_time) * 1000
            perf_logger.log_stage_performance(
                stage=operation,
                duration_ms=duration_ms,
                success=True,
                video_id=context.video_id or "unknown"
            )
            
        except Exception as e:
            # Log failed operation
            duration_ms = (time.time() - start_time) * 1000
            perf_logger.log_stage_performance(
                stage=operation,
                duration_ms=duration_ms,
                success=False,
                video_id=context.video_id or "unknown",
                error_type=type(e).__name__,
                error_message=str(e)
            )
            raise


# Global logger instances
performance_logger = PerformanceLogger()
alert_logger = AlertLogger()


def get_contextual_logger(name: str) -> ContextualLogger:
    """Get contextual logger instance."""
    return ContextualLogger(name)


def mask_sensitive_data(data: str, patterns: List[str] = None) -> str:
    """Mask sensitive data in log messages."""
    if not patterns:
        patterns = [
            r'(password["\s]*[:=]["\s]*)([^"\s,}]+)',
            r'(cookie["\s]*[:=]["\s]*)([^"\s,}]+)',
            r'(token["\s]*[:=]["\s]*)([^"\s,}]+)',
            r'(key["\s]*[:=]["\s]*)([^"\s,}]+)',
            r'(secret["\s]*[:=]["\s]*)([^"\s,}]+)',
        ]
    
    import re
    masked_data = data
    
    for pattern in patterns:
        masked_data = re.sub(pattern, r'\1***MASKED***', masked_data, flags=re.IGNORECASE)
    
    return masked_data


# Backward compatibility wrapper functions
def setup_structured_logging():
    """
    Configure structured logging for production.
    
    BACKWARD COMPATIBILITY: Routes to minimal logging if USE_MINIMAL_LOGGING=true,
    otherwise uses legacy structured logging system.
    """
    if USE_MINIMAL_LOGGING and _MINIMAL_LOGGING_AVAILABLE:
        try:
            # Use minimal logging system
            log_level = os.getenv("LOG_LEVEL", "INFO")
            _configure_minimal_logging(log_level=log_level, use_json=True)
            logging.info("Minimal JSON logging configured via backward compatibility layer")
            return
        except Exception as e:
            logging.error(f"Failed to configure minimal logging, falling back to legacy: {e}")
    
    # Use legacy structured logging system
    _setup_legacy_structured_logging()


def _setup_legacy_structured_logging():
    """Original structured logging setup function."""
    # Get log level from environment
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Create structured formatter
    formatter = StructuredFormatter()
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add console handler with structured formatting
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Configure specific loggers
    loggers_config = {
        "transcript_service": log_level,
        "proxy_manager": log_level,
        "performance": log_level,
        "alerts": "WARNING",
        "monitoring": log_level,
        "playwright": "WARNING",  # Reduce playwright noise
        "urllib3": "WARNING",     # Reduce HTTP noise
        "requests": "WARNING",    # Reduce requests noise
    }
    
    for logger_name, level in loggers_config.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(getattr(logging, level))
    
    logging.info(f"Legacy structured logging configured: level={log_level}, formatter=json, environment={os.getenv('ENVIRONMENT', 'production')}")


# Backward compatibility context managers
@contextmanager
def log_context(correlation_id: Optional[str] = None, **context_kwargs):
    """
    Context manager for structured logging context.
    
    BACKWARD COMPATIBILITY: Routes to minimal logging if USE_MINIMAL_LOGGING=true,
    otherwise uses legacy context management.
    """
    if USE_MINIMAL_LOGGING and _MINIMAL_LOGGING_AVAILABLE:
        # Use minimal logging context
        job_id = context_kwargs.get('job_id')
        video_id = context_kwargs.get('video_id')
        
        # Set context
        if job_id or video_id:
            _set_minimal_job_ctx(job_id=job_id, video_id=video_id)
        
        try:
            # Create a simple context object for compatibility
            class MinimalContext:
                def __init__(self, **kwargs):
                    self.correlation_id = correlation_id or str(uuid.uuid4())
                    for k, v in kwargs.items():
                        setattr(self, k, v)
            
            yield MinimalContext(**context_kwargs)
        finally:
            if job_id or video_id:
                _clear_minimal_job_ctx()
    else:
        # Use legacy context management
        logger = ContextualLogger("context")
        
        # Generate correlation ID if not provided
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        
        # Create context
        context = LogContext(
            correlation_id=correlation_id,
            start_time=time.time(),
            **context_kwargs
        )
        
        # Set context
        logger.set_context(context)
        
        try:
            yield context
        finally:
            # Clear context
            logger.clear_context()


@contextmanager
def log_performance(operation: str, **context_kwargs):
    """
    Context manager for performance logging.
    
    BACKWARD COMPATIBILITY: Routes to minimal logging if USE_MINIMAL_LOGGING=true,
    otherwise uses legacy performance logging.
    """
    if USE_MINIMAL_LOGGING and _MINIMAL_LOGGING_AVAILABLE:
        # Use minimal logging with StageTimer
        stage_fields = {}
        if 'video_id' in context_kwargs:
            stage_fields['video_id'] = context_kwargs['video_id']
        if 'profile' in context_kwargs:
            stage_fields['profile'] = context_kwargs['profile']
        if 'use_proxy' in context_kwargs:
            stage_fields['use_proxy'] = context_kwargs['use_proxy']
        
        with _MinimalStageTimer(operation, **stage_fields) as timer:
            # Create a simple context object for compatibility
            class MinimalContext:
                def __init__(self, **kwargs):
                    for k, v in kwargs.items():
                        setattr(self, k, v)
            
            yield MinimalContext(**context_kwargs)
    else:
        # Use legacy performance logging
        perf_logger = PerformanceLogger()
        start_time = time.time()
        
        with log_context(**context_kwargs) as context:
            try:
                yield context
                
                # Log successful operation
                duration_ms = (time.time() - start_time) * 1000
                perf_logger.log_stage_performance(
                    stage=operation,
                    duration_ms=duration_ms,
                    success=True,
                    video_id=context.video_id or "unknown"
                )
                
            except Exception as e:
                # Log failed operation
                duration_ms = (time.time() - start_time) * 1000
                perf_logger.log_stage_performance(
                    stage=operation,
                    duration_ms=duration_ms,
                    success=False,
                    video_id=context.video_id or "unknown",
                    error_type=type(e).__name__,
                    error_message=str(e)
                )
                raise


# Backward compatibility wrapper classes
class BackwardCompatiblePerformanceLogger:
    """
    Backward compatible performance logger that routes to minimal logging when enabled.
    """
    
    def __init__(self):
        if USE_MINIMAL_LOGGING and _MINIMAL_LOGGING_AVAILABLE:
            self._perf_logger = _get_minimal_perf_logger()
        else:
            self._legacy_logger = PerformanceLogger()
    
    def log_stage_performance(self, stage: str, duration_ms: float, success: bool, 
                            video_id: str, **kwargs):
        """Log stage performance metrics."""
        if USE_MINIMAL_LOGGING and _MINIMAL_LOGGING_AVAILABLE:
            # Use minimal logging event system
            outcome = "success" if success else "error"
            detail = kwargs.get('error_message', '') if not success else ''
            
            _minimal_evt(
                event="stage_result",
                stage=stage,
                outcome=outcome,
                dur_ms=int(duration_ms),
                detail=detail,
                video_id=video_id,
                **{k: v for k, v in kwargs.items() if k not in ['error_message', 'error_type']}
            )
        else:
            # Use legacy performance logger
            self._legacy_logger.log_stage_performance(
                stage=stage,
                duration_ms=duration_ms,
                success=success,
                video_id=video_id,
                **kwargs
            )
        return True  # Return something for compatibility
    
    def log_circuit_breaker_event(self, event_type: str, state: str, **kwargs):
        """Log circuit breaker events."""
        if USE_MINIMAL_LOGGING and _MINIMAL_LOGGING_AVAILABLE:
            _minimal_evt(
                event="circuit_breaker",
                detail=f"{event_type}:{state}",
                **kwargs
            )
        else:
            self._legacy_logger.log_circuit_breaker_event(event_type, state, **kwargs)
        return True  # Return something for compatibility
    
    def log_browser_context_metrics(self, action: str, profile: str, **kwargs):
        """Log browser context metrics."""
        if USE_MINIMAL_LOGGING and _MINIMAL_LOGGING_AVAILABLE:
            _minimal_evt(
                event="browser_context",
                detail=action,
                profile=profile,
                **kwargs
            )
        else:
            self._legacy_logger.log_browser_context_metrics(action, profile, **kwargs)
        return True  # Return something for compatibility
    
    def log_proxy_health_metrics(self, healthy: bool, **kwargs):
        """Log proxy health metrics."""
        if USE_MINIMAL_LOGGING and _MINIMAL_LOGGING_AVAILABLE:
            _minimal_evt(
                event="proxy_health",
                outcome="success" if healthy else "error",
                **kwargs
            )
        else:
            self._legacy_logger.log_proxy_health_metrics(healthy, **kwargs)
        return True  # Return something for compatibility


class BackwardCompatibleContextualLogger:
    """
    Backward compatible contextual logger that routes to minimal logging when enabled.
    """
    
    def __init__(self, name: str):
        self.name = name
        if USE_MINIMAL_LOGGING and _MINIMAL_LOGGING_AVAILABLE:
            self._logger = logging.getLogger(name)
        else:
            self._legacy_logger = ContextualLogger(name)
    
    def set_context(self, context):
        """Set logging context for current thread."""
        if USE_MINIMAL_LOGGING and _MINIMAL_LOGGING_AVAILABLE:
            # Extract job_id and video_id from context
            job_id = getattr(context, 'job_id', None)
            video_id = getattr(context, 'video_id', None)
            if job_id or video_id:
                _set_minimal_job_ctx(job_id=job_id, video_id=video_id)
        else:
            self._legacy_logger.set_context(context)
    
    def get_context(self):
        """Get current logging context."""
        if USE_MINIMAL_LOGGING and _MINIMAL_LOGGING_AVAILABLE:
            return None  # Minimal logging doesn't expose context objects
        else:
            return self._legacy_logger.get_context()
    
    def clear_context(self):
        """Clear current logging context."""
        if USE_MINIMAL_LOGGING and _MINIMAL_LOGGING_AVAILABLE:
            _clear_minimal_job_ctx()
        else:
            self._legacy_logger.clear_context()
    
    def debug(self, message: str, **kwargs):
        """Log debug message with context."""
        if USE_MINIMAL_LOGGING and _MINIMAL_LOGGING_AVAILABLE:
            self._logger.debug(message, extra=kwargs)
        else:
            self._legacy_logger.debug(message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message with context."""
        if USE_MINIMAL_LOGGING and _MINIMAL_LOGGING_AVAILABLE:
            self._logger.info(message, extra=kwargs)
        else:
            self._legacy_logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with context."""
        if USE_MINIMAL_LOGGING and _MINIMAL_LOGGING_AVAILABLE:
            self._logger.warning(message, extra=kwargs)
        else:
            self._legacy_logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with context."""
        if USE_MINIMAL_LOGGING and _MINIMAL_LOGGING_AVAILABLE:
            self._logger.error(message, extra=kwargs)
        else:
            self._legacy_logger.error(message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message with context."""
        if USE_MINIMAL_LOGGING and _MINIMAL_LOGGING_AVAILABLE:
            self._logger.critical(message, extra=kwargs)
        else:
            self._legacy_logger.critical(message, **kwargs)


# Update global instances to use backward compatible versions
performance_logger = BackwardCompatiblePerformanceLogger()
alert_logger = AlertLogger()  # Keep legacy for now, minimal logging doesn't have alerts


def get_contextual_logger(name: str) -> BackwardCompatibleContextualLogger:
    """Get contextual logger instance with backward compatibility."""
    return BackwardCompatibleContextualLogger(name)


# Initialize structured logging on import (only if not in test mode)
if os.getenv("ENABLE_STRUCTURED_LOGGING", "1") == "1" and "test" not in sys.argv[0].lower():
    try:
        setup_structured_logging()
    except Exception as e:
        # Fallback to basic logging on any initialization error
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        logging.error(f"Failed to initialize structured logging, using basic logging: {e}")