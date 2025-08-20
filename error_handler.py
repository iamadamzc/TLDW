#!/usr/bin/env python3
"""
Comprehensive error handling and logging system for the no-yt-dl summarization stack
"""
import os
import logging
import traceback
import time
from typing import Dict, Any, Optional
from functools import wraps
from datetime import datetime


class StructuredLogger:
    """Structured logging with consistent format and context"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.context = {}
    
    def set_context(self, **kwargs):
        """Set context that will be included in all log messages"""
        self.context.update(kwargs)
    
    def clear_context(self):
        """Clear all context"""
        self.context = {}
    
    def _format_message(self, message: str, **kwargs) -> str:
        """Format message with context and additional fields"""
        fields = {**self.context, **kwargs}
        if fields:
            field_str = " ".join(f"{k}={v}" for k, v in fields.items())
            return f"{message} {field_str}"
        return message
    
    def info(self, message: str, **kwargs):
        """Log info message with context"""
        self.logger.info(self._format_message(message, **kwargs))
    
    def warning(self, message: str, **kwargs):
        """Log warning message with context"""
        self.logger.warning(self._format_message(message, **kwargs))
    
    def error(self, message: str, **kwargs):
        """Log error message with context"""
        self.logger.error(self._format_message(message, **kwargs))
    
    def debug(self, message: str, **kwargs):
        """Log debug message with context"""
        self.logger.debug(self._format_message(message, **kwargs))


class ErrorHandler:
    """Centralized error handling with categorization and recovery strategies"""
    
    def __init__(self):
        self.logger = StructuredLogger(__name__)
        self.error_counts = {}
        self.last_errors = {}
    
    def handle_transcript_error(self, video_id: str, method: str, error: Exception, 
                              duration_ms: int = None) -> str:
        """Handle transcript acquisition errors with context"""
        error_key = f"transcript_{method}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        self.last_errors[error_key] = {
            "error": str(error),
            "timestamp": datetime.utcnow().isoformat(),
            "video_id": video_id
        }
        
        # Log with structured format
        self.logger.error(
            f"transcript_error method={method} video_id={video_id}",
            error=str(error),
            error_type=type(error).__name__,
            duration_ms=duration_ms,
            error_count=self.error_counts[error_key]
        )
        
        # Return appropriate fallback message
        error_msg = str(error).lower()
        if "timeout" in error_msg or "timed out" in error_msg:
            return "Transcript unavailable: Request timed out"
        elif "auth" in error_msg or "permission" in error_msg:
            return "Transcript unavailable: Access denied"
        elif "not found" in error_msg:
            return "Transcript unavailable: Video not found"
        else:
            return "Transcript unavailable: Processing error"
    
    def handle_summarization_error(self, video_id: str, error: Exception, 
                                 transcript_length: int = None) -> str:
        """Handle summarization errors with context"""
        error_key = "summarization"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        self.last_errors[error_key] = {
            "error": str(error),
            "timestamp": datetime.utcnow().isoformat(),
            "video_id": video_id
        }
        
        # Log with structured format
        self.logger.error(
            f"summarization_error video_id={video_id}",
            error=str(error),
            error_type=type(error).__name__,
            transcript_length=transcript_length,
            error_count=self.error_counts[error_key]
        )
        
        # Return appropriate fallback message based on error type
        if "rate limit" in str(error).lower():
            return "Summary unavailable: API rate limit exceeded"
        elif "auth" in str(error).lower():
            return "Summary unavailable: API authentication failed"
        elif "timeout" in str(error).lower():
            return "Summary unavailable: Request timed out"
        else:
            return "Summary unavailable: Processing error"
    
    def handle_email_error(self, user_email: str, error: Exception, 
                          items_count: int = None) -> bool:
        """Handle email delivery errors with context"""
        error_key = "email_delivery"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        self.last_errors[error_key] = {
            "error": str(error),
            "timestamp": datetime.utcnow().isoformat(),
            "user_email": user_email
        }
        
        # Log with structured format
        self.logger.error(
            f"email_error recipient={user_email}",
            error=str(error),
            error_type=type(error).__name__,
            items_count=items_count,
            error_count=self.error_counts[error_key]
        )
        
        # Email errors are not recoverable - return False
        return False
    
    def handle_job_error(self, job_id: str, error: Exception, 
                        video_count: int = None, processed_count: int = None) -> None:
        """Handle job-level errors with context"""
        error_key = "job_processing"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        self.last_errors[error_key] = {
            "error": str(error),
            "timestamp": datetime.utcnow().isoformat(),
            "job_id": job_id
        }
        
        # Log with structured format and full traceback for job errors
        self.logger.error(
            f"job_error job_id={job_id}",
            error=str(error),
            error_type=type(error).__name__,
            video_count=video_count,
            processed_count=processed_count,
            error_count=self.error_counts[error_key],
            traceback=traceback.format_exc()
        )
    
    def handle_api_error(self, endpoint: str, error: Exception, 
                        user_id: int = None, request_data: Dict = None) -> tuple[Dict[str, Any], int]:
        """Handle API endpoint errors with appropriate HTTP responses"""
        error_key = f"api_{endpoint}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        self.last_errors[error_key] = {
            "error": str(error),
            "timestamp": datetime.utcnow().isoformat(),
            "endpoint": endpoint
        }
        
        # Log with structured format
        self.logger.error(
            f"api_error endpoint={endpoint}",
            error=str(error),
            error_type=type(error).__name__,
            user_id=user_id,
            error_count=self.error_counts[error_key]
        )
        
        # Return appropriate HTTP response based on error type
        if "auth" in str(error).lower() or "permission" in str(error).lower():
            return {"error": "Authentication required"}, 401
        elif "not found" in str(error).lower():
            return {"error": "Resource not found"}, 404
        elif "rate limit" in str(error).lower():
            return {"error": "Rate limit exceeded"}, 429
        elif "timeout" in str(error).lower():
            return {"error": "Request timeout"}, 408
        else:
            return {"error": "Internal server error"}, 500
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics for monitoring"""
        return {
            "error_counts": self.error_counts.copy(),
            "last_errors": {k: v.copy() for k, v in self.last_errors.items()},
            "total_errors": sum(self.error_counts.values())
        }
    
    def reset_error_stats(self):
        """Reset error statistics (for testing or periodic cleanup)"""
        self.error_counts.clear()
        self.last_errors.clear()


def with_error_handling(error_handler: ErrorHandler, operation_type: str):
    """Decorator for consistent error handling across operations"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration_ms = int((time.time() - start_time) * 1000)
                
                # Log successful operation
                logger = StructuredLogger(func.__module__)
                logger.info(
                    f"{operation_type}_success",
                    function=func.__name__,
                    duration_ms=duration_ms
                )
                
                return result
                
            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                
                # Log error with context
                logger = StructuredLogger(func.__module__)
                logger.error(
                    f"{operation_type}_error",
                    function=func.__name__,
                    error=str(e),
                    error_type=type(e).__name__,
                    duration_ms=duration_ms
                )
                
                # Re-raise the exception for handling by specific error handlers
                raise
        
        return wrapper
    return decorator


def setup_logging(log_level: str = None, log_format: str = None):
    """Setup centralized logging configuration"""
    # Default log level from environment or INFO
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Default structured log format
    if log_format is None:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Set specific log levels for noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)
    
    # Create application logger
    app_logger = StructuredLogger("tldw")
    app_logger.info("logging_initialized", log_level=log_level)
    
    return app_logger


def log_performance_metrics(operation: str, duration_ms: int, **metrics):
    """Log performance metrics in structured format"""
    logger = StructuredLogger("performance")
    logger.info(
        f"performance_metric operation={operation}",
        duration_ms=duration_ms,
        **metrics
    )


def log_resource_cleanup(resource_type: str, resource_id: str, success: bool, **context):
    """Log resource cleanup operations"""
    logger = StructuredLogger("cleanup")
    status = "success" if success else "failed"
    logger.info(
        f"resource_cleanup_{status}",
        resource_type=resource_type,
        resource_id=resource_id,
        **context
    )


# Global error handler instance
global_error_handler = ErrorHandler()


# Convenience functions for common error handling patterns
def handle_transcript_error(video_id: str, method: str, error: Exception, duration_ms: int = None) -> str:
    """Global function for handling transcript errors"""
    return global_error_handler.handle_transcript_error(video_id, method, error, duration_ms)


def handle_summarization_error(video_id: str, error: Exception, transcript_length: int = None) -> str:
    """Global function for handling summarization errors"""
    return global_error_handler.handle_summarization_error(video_id, error, transcript_length)


def handle_email_error(user_email: str, error: Exception, items_count: int = None) -> bool:
    """Global function for handling email errors"""
    return global_error_handler.handle_email_error(user_email, error, items_count)


def handle_job_error(job_id: str, error: Exception, video_count: int = None, processed_count: int = None) -> None:
    """Global function for handling job errors"""
    return global_error_handler.handle_job_error(job_id, error, video_count, processed_count)


def handle_api_error(endpoint: str, error: Exception, user_id: int = None, request_data: Dict = None) -> tuple[Dict[str, Any], int]:
    """Global function for handling API errors"""
    return global_error_handler.handle_api_error(endpoint, error, user_id, request_data)


def get_error_stats() -> Dict[str, Any]:
    """Get global error statistics"""
    return global_error_handler.get_error_stats()