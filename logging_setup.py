"""
Core logging infrastructure for TL;DW application.

Provides minimal JSON logging with thread-safe context management,
rate limiting, and third-party library noise suppression.
"""

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Set
from collections import defaultdict


# Thread-local storage for job context
_local = threading.local()


def set_job_ctx(job_id: str = None, video_id: str = None):
    """
    Set thread-local context for job correlation.
    
    Args:
        job_id: Unique job identifier
        video_id: YouTube video ID being processed
    """
    if not hasattr(_local, 'context'):
        _local.context = {}
    
    if job_id is not None:
        _local.context['job_id'] = job_id
    if video_id is not None:
        _local.context['video_id'] = video_id


def clear_job_ctx():
    """Clear thread-local context."""
    if hasattr(_local, 'context'):
        _local.context.clear()


def get_job_ctx() -> Dict[str, str]:
    """Get current thread-local context."""
    if not hasattr(_local, 'context'):
        return {}
    return _local.context.copy()


class JsonFormatter(logging.Formatter):
    """
    JSON formatter with standardized field order and context injection.
    
    Produces single-line JSON with stable schema:
    ts, lvl, job_id, video_id, stage, event, outcome, dur_ms, detail
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as single-line JSON."""
        try:
            # Start with timestamp and level (always present)
            # Truncate microseconds to milliseconds for consistent format
            dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
            # Format with milliseconds (3 digits)
            timestamp = dt.strftime('%Y-%m-%dT%H:%M:%S') + f'.{int(dt.microsecond / 1000):03d}Z'
            
            log_data = {
                'ts': timestamp,
                'lvl': record.levelname
            }
            
            # Add thread-local context
            context = get_job_ctx()
            if 'job_id' in context:
                log_data['job_id'] = context['job_id']
            if 'video_id' in context:
                log_data['video_id'] = context['video_id']
            
            # Add record attributes in stable order
            for field in ['stage', 'event', 'outcome', 'dur_ms', 'detail']:
                if hasattr(record, field) and getattr(record, field) is not None:
                    log_data[field] = getattr(record, field)
            
            # Add optional context fields
            for field in ['attempt', 'use_proxy', 'profile', 'cookie_source']:
                if hasattr(record, field) and getattr(record, field) is not None:
                    log_data[field] = getattr(record, field)
            
            # Add any other extra fields that were passed via logger.info(extra=...)
            # Skip standard LogRecord attributes and fields we've already processed
            standard_fields = {
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
                'module', 'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                'thread', 'threadName', 'processName', 'process', 'getMessage', 'exc_info',
                'exc_text', 'stack_info', 'ts', 'lvl', 'job_id', 'video_id', 'stage',
                'event', 'outcome', 'dur_ms', 'detail', 'attempt', 'use_proxy', 'profile',
                'cookie_source'
            }
            
            for attr_name in dir(record):
                if (not attr_name.startswith('_') and 
                    attr_name not in standard_fields and
                    not callable(getattr(record, attr_name))):
                    attr_value = getattr(record, attr_name)
                    if attr_value is not None:
                        log_data[attr_name] = attr_value
            
            # Add message if not already in detail
            if 'detail' not in log_data and record.getMessage():
                log_data['detail'] = record.getMessage()
            
            # Return single-line JSON
            return json.dumps(log_data, separators=(',', ':'), ensure_ascii=False)
            
        except Exception:
            # Fallback to basic formatting on any error
            return f'{{"ts":"{datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}","lvl":"{record.levelname}","detail":"{record.getMessage()}"}}'


class RateLimitFilter(logging.Filter):
    """
    Rate limiting filter to prevent log spam.
    
    Limits messages to 5 per key per 60-second sliding window.
    Emits suppression markers when limits are exceeded.
    """
    
    def __init__(self, per_key: int = 5, window_sec: int = 60):
        super().__init__()
        self.per_key = per_key
        self.window_sec = window_sec
        self.counts: Dict[str, list] = defaultdict(list)
        self.suppressed: Set[str] = set()
        self._lock = threading.Lock()
    
    def _get_message_key(self, record: logging.LogRecord) -> str:
        """Generate key for rate limiting based on level and message template."""
        # Use level and first 100 chars of message as key
        message = record.getMessage()[:100]
        return f"{record.levelname}:{message}"
    
    def _cleanup_old_entries(self, key: str, now: float):
        """Remove entries outside the current window."""
        cutoff = now - self.window_sec
        self.counts[key] = [ts for ts in self.counts[key] if ts > cutoff]
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter log record based on rate limits.
        
        Returns:
            True if record should be logged, False otherwise
        """
        try:
            key = self._get_message_key(record)
            now = time.time()
            
            with self._lock:
                # Clean up old entries
                self._cleanup_old_entries(key, now)
                
                # Check if we're within limits
                if len(self.counts[key]) < self.per_key:
                    self.counts[key].append(now)
                    # Remove from suppressed set if we were suppressing
                    self.suppressed.discard(key)
                    return True
                
                # We're over the limit
                if key not in self.suppressed:
                    # First time hitting limit in this window - emit suppression marker
                    self.suppressed.add(key)
                    # Modify the record to indicate suppression
                    original_msg = record.getMessage()
                    record.msg = f"{original_msg} [suppressed]"
                    record.args = ()
                    return True
                
                # Already suppressing this key
                return False
                
        except Exception:
            # On any error, allow the message through
            return True


def configure_logging(log_level: str = "INFO", use_json: bool = True) -> logging.Logger:
    """
    Configure application logging with JSON formatting and noise suppression.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        use_json: Whether to use JSON formatting (True) or basic formatting (False)
    
    Returns:
        Configured root logger
    """
    try:
        # Get root logger
        root_logger = logging.getLogger()
        
        # Clear any existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Set log level
        root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        
        # Create console handler
        handler = logging.StreamHandler()
        
        if use_json:
            # Use JSON formatter with rate limiting
            formatter = JsonFormatter()
            rate_filter = RateLimitFilter()
            handler.addFilter(rate_filter)
        else:
            # Basic formatter for fallback
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
        
        # Suppress third-party library noise
        _suppress_library_noise()
        
        return root_logger
        
    except Exception as e:
        # Fallback to basic logging configuration
        logging.basicConfig(
            level=getattr(logging, log_level.upper(), logging.INFO),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        logging.error(f"Failed to configure structured logging: {e}")
        return logging.getLogger()


def _suppress_library_noise():
    """Suppress verbose logging from third-party libraries."""
    library_levels = {
        'playwright': logging.WARNING,
        'urllib3': logging.WARNING,
        'botocore': logging.WARNING,
        'boto3': logging.WARNING,
        'asyncio': logging.WARNING,
        'httpx': logging.WARNING,
        'httpcore': logging.WARNING,
    }
    
    for library, level in library_levels.items():
        logging.getLogger(library).setLevel(level)


def get_logger(name: str = None) -> logging.Logger:
    """
    Get a logger instance.
    
    Args:
        name: Logger name (defaults to calling module)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def get_perf_logger() -> logging.Logger:
    """
    Get dedicated performance metrics logger.
    
    This logger is specifically for performance metrics and resource monitoring,
    separate from pipeline events to enable independent querying and retention.
    
    Returns:
        Logger instance for performance metrics with 'perf' name
    """
    return logging.getLogger('perf')