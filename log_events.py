"""
Event helper functions for structured JSON logging.

This module provides consistent event emission and stage timing utilities
for the TL;DW application's logging system.
"""

import logging
import time
from typing import Any, Dict, Optional
from contextlib import contextmanager

# Get the main application logger
logger = logging.getLogger()

# Get the dedicated performance metrics logger
perf_logger = logging.getLogger('perf')


def evt(event: str, **fields) -> None:
    """
    Emit a structured event with consistent field naming.
    
    Args:
        event: The event type/name
        **fields: Additional fields to include in the event
        
    Example:
        evt("job_received", video_id="abc123", config="default")
        evt("stage_result", stage="youtubei", outcome="success", dur_ms=1250)
    """
    # Create the event data with the event field
    event_data = {"event": event}
    event_data.update(fields)
    
    # Log at INFO level with the structured data
    logger.info("", extra=event_data)


def perf_evt(**fields) -> None:
    """
    Emit a performance metric event on the dedicated performance channel.
    
    This function logs to the 'perf' logger to separate performance metrics
    from pipeline events, enabling independent querying and retention policies.
    
    Args:
        **fields: Performance metric fields to include
        
    Example:
        perf_evt(cpu=15.2, mem_mb=512, disk_usage_pct=45.0)
        perf_evt(stage_duration_ms=1250, stage="youtubei", success=True)
    """
    # Create the performance metric event data
    event_data = {"event": "performance_metric"}
    event_data.update(fields)
    
    # Log to the dedicated performance logger
    perf_logger.info("", extra=event_data)


class StageTimer:
    """
    Context manager for automatic stage timing with structured logging.
    
    Emits stage_start event on entry and stage_result event on exit,
    with automatic duration calculation and exception handling.
    
    Example:
        with StageTimer("youtubei", profile="mobile", use_proxy=True):
            # Stage processing code here
            process_stage()
    """
    
    def __init__(self, stage: str, **context_fields):
        """
        Initialize the stage timer.
        
        Args:
            stage: The name of the stage being timed
            **context_fields: Additional context fields (profile, use_proxy, etc.)
        """
        self.stage = stage
        self.context_fields = context_fields
        self.start_time: Optional[float] = None
        
    def __enter__(self):
        """Enter the stage timer context."""
        self.start_time = time.time()
        
        # Emit stage_start event
        evt("stage_start", stage=self.stage, **self.context_fields)
        
        return self
        
    def __exit__(self, exc_type, exc_value, traceback):
        """Exit the stage timer context with duration calculation."""
        if self.start_time is None:
            # This shouldn't happen, but handle gracefully
            duration_ms = 0
        else:
            # Calculate duration in milliseconds as integer
            duration_ms = int((time.time() - self.start_time) * 1000)
        
        # Determine outcome based on exception
        if exc_type is None:
            # No exception - success
            outcome = "success"
            detail = None
        else:
            # Exception occurred - error
            outcome = "error"
            # Include exception type and message in detail
            detail = f"{exc_type.__name__}: {str(exc_value)}"
        
        # Emit stage_result event
        event_fields = {
            "stage": self.stage,
            "outcome": outcome,
            "dur_ms": duration_ms,
            **self.context_fields
        }
        
        # Only include detail if there's an error
        if detail is not None:
            event_fields["detail"] = detail
            
        evt("stage_result", **event_fields)
        
        # Don't suppress the exception - let it propagate
        return False


# Convenience function for timing stages without context manager
def time_stage(stage: str, **context_fields):
    """
    Create a StageTimer context manager for the given stage.
    
    This is a convenience function that returns a StageTimer instance.
    
    Args:
        stage: The name of the stage being timed
        **context_fields: Additional context fields
        
    Returns:
        StageTimer: Context manager for timing the stage
        
    Example:
        with time_stage("youtubei", profile="mobile"):
            process_youtubei_stage()
    """
    return StageTimer(stage, **context_fields)


def log_cpu_memory_metrics(cpu_percent: Optional[float] = None, memory_mb: Optional[float] = None, **extra_fields) -> None:
    """
    Log CPU and memory performance metrics.
    
    Args:
        cpu_percent: CPU usage percentage (0-100)
        memory_mb: Memory usage in megabytes
        **extra_fields: Additional metric fields
        
    Example:
        log_cpu_memory_metrics(cpu_percent=15.2, memory_mb=512)
        log_cpu_memory_metrics(memory_mb=1024, disk_usage_pct=45.0)
    """
    metric_fields = {}
    
    if cpu_percent is not None:
        metric_fields["cpu_percent"] = cpu_percent
    
    if memory_mb is not None:
        metric_fields["memory_mb"] = memory_mb
    
    # Add any extra fields
    metric_fields.update(extra_fields)
    
    # Emit performance metric event
    perf_evt(metric_type="system_resources", **metric_fields)


# Job Lifecycle Event Helpers

def job_received(video_count: int, **config_fields) -> None:
    """
    Emit job_received event at the start of job processing.
    
    Args:
        video_count: Number of videos to process in this job
        **config_fields: Job configuration parameters (e.g., use_cookies, proxy_enabled)
        
    Example:
        job_received(video_count=5, use_cookies=True, proxy_enabled=False)
    """
    evt("job_received", video_count=video_count, **config_fields)


def job_finished(total_duration_ms: int, processed_count: int, video_count: int, outcome: str = "success", **result_fields) -> None:
    """
    Emit job_finished event at the end of job processing.
    
    Args:
        total_duration_ms: Total job duration in milliseconds
        processed_count: Number of videos successfully processed
        video_count: Total number of videos in the job
        outcome: Job outcome (success, partial_success, error)
        **result_fields: Additional result fields (e.g., email_sent, error_count)
        
    Example:
        job_finished(total_duration_ms=45000, processed_count=4, video_count=5, 
                    outcome="partial_success", email_sent=True, error_count=1)
    """
    evt("job_finished", 
        total_duration_ms=total_duration_ms,
        processed_count=processed_count, 
        video_count=video_count,
        outcome=outcome,
        **result_fields)


def job_failed(total_duration_ms: int, processed_count: int, video_count: int, error_type: str, error_detail: str, **error_fields) -> None:
    """
    Emit job failure event for critical job-level errors.
    
    Args:
        total_duration_ms: Duration before failure in milliseconds
        processed_count: Number of videos processed before failure
        video_count: Total number of videos in the job
        error_type: Classification of error (auth_error, service_error, config_error, etc.)
        error_detail: Detailed error message
        **error_fields: Additional error context
        
    Example:
        job_failed(total_duration_ms=5000, processed_count=0, video_count=5,
                  error_type="auth_error", error_detail="User not found")
    """
    evt("job_failed",
        total_duration_ms=total_duration_ms,
        processed_count=processed_count,
        video_count=video_count,
        error_type=error_type,
        detail=error_detail,
        **error_fields)


def video_processed(video_id: str, outcome: str, duration_ms: int, transcript_source: str = None, **processing_fields) -> None:
    """
    Emit video processing completion event.
    
    Args:
        video_id: YouTube video ID
        outcome: Processing outcome (success, transcript_failed, summary_failed, error)
        duration_ms: Video processing duration in milliseconds
        transcript_source: Source of transcript (yt_api, timedtext, youtubei, asr, cache, none)
        **processing_fields: Additional processing context
        
    Example:
        video_processed("abc123", outcome="success", duration_ms=8500, 
                       transcript_source="youtubei", summary_length=250)
    """
    event_fields = {
        "video_id": video_id,
        "outcome": outcome,
        "dur_ms": duration_ms
    }
    
    if transcript_source:
        event_fields["transcript_source"] = transcript_source
    
    event_fields.update(processing_fields)
    
    evt("video_processed", **event_fields)


def classify_error_type(exception: Exception) -> str:
    """
    Classify exception into error type for structured logging.
    
    Args:
        exception: The exception to classify
        
    Returns:
        Error type string for consistent categorization
    """
    exception_name = type(exception).__name__
    exception_str = str(exception).lower()
    
    # Authentication and authorization errors
    if "auth" in exception_str or "token" in exception_str or "permission" in exception_str:
        return "auth_error"
    
    # Network and connectivity errors
    if any(term in exception_str for term in ["connection", "timeout", "network", "dns", "ssl"]):
        return "network_error"
    
    # Service-specific errors
    if "youtube" in exception_str or "transcript" in exception_str:
        return "transcript_error"
    
    if "openai" in exception_str or "summariz" in exception_str:
        return "summarization_error"
    
    if "email" in exception_str or "resend" in exception_str:
        return "email_error"
    
    # Configuration errors
    if "config" in exception_str or "key" in exception_str or "missing" in exception_str:
        return "config_error"
    
    # Resource errors
    if any(term in exception_str for term in ["memory", "disk", "quota", "limit"]):
        return "resource_error"
    
    # Default classification
    return "service_error"