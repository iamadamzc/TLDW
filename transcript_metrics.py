import logging
import time
from collections import Counter, defaultdict, deque
from threading import Lock
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import statistics

_success = Counter()   # keys: 'yt_api', 'timedtext', 'youtubei', 'asr'
_fail = Counter()      # keys: 'timedtext', 'youtubei', 'asr', 'none'
_lock = Lock()

# Enhanced metrics storage
_stage_durations = defaultdict(list)  # stage -> list of duration_ms
_stage_metrics = deque(maxlen=1000)   # Recent stage metrics for detailed analysis
_circuit_breaker_events = deque(maxlen=100)  # Recent circuit breaker events
_successful_attempts = {}  # video_id -> successful stage name


@dataclass
class StageMetrics:
    """Structured metrics for individual stage attempts."""
    timestamp: str
    video_id: str
    stage: str
    proxy_used: bool
    profile: Optional[str]
    duration_ms: int
    success: bool
    error_type: Optional[str] = None
    circuit_breaker_state: Optional[str] = None


@dataclass
class CircuitBreakerEvent:
    """Structured event for circuit breaker state changes."""
    timestamp: str
    event_type: str  # state_change, skip_operation, success_reset, failure_recorded, activated
    previous_state: Optional[str] = None
    new_state: Optional[str] = None
    failure_count: Optional[int] = None
    video_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


def inc_success(source: str):
    with _lock:
        _success[source] += 1


def inc_fail(stage: str):
    with _lock:
        _fail[stage] += 1


def record_stage_metrics(
    video_id: str,
    stage: str,
    duration_ms: int,
    success: bool,
    proxy_used: bool = False,
    profile: Optional[str] = None,
    error_type: Optional[str] = None,
    circuit_breaker_state: Optional[str] = None
) -> None:
    """Record comprehensive stage metrics with structured logging."""
    
    with _lock:
        # Store duration for percentile calculations
        _stage_durations[stage].append(duration_ms)
        
        # Keep only recent durations (last 1000 per stage)
        if len(_stage_durations[stage]) > 1000:
            _stage_durations[stage] = _stage_durations[stage][-1000:]
        
        # Create structured metrics record
        metrics = StageMetrics(
            timestamp=datetime.utcnow().isoformat(),
            video_id=video_id,
            stage=stage,
            proxy_used=proxy_used,
            profile=profile,
            duration_ms=duration_ms,
            success=success,
            error_type=error_type,
            circuit_breaker_state=circuit_breaker_state
        )
        
        _stage_metrics.append(metrics)
        
        # Track successful attempts for "which method succeeded" logging
        if success:
            _successful_attempts[video_id] = stage
    
    # Emit structured log with all required labels
    log_data = {
        "video_id": video_id,
        "stage": stage,
        "duration_ms": duration_ms,
        "success": success,
        "proxy_used": proxy_used
    }
    
    if profile:
        log_data["profile"] = profile
    if error_type:
        log_data["error_type"] = error_type
    if circuit_breaker_state:
        log_data["breaker_state"] = circuit_breaker_state
    
    # Format structured log message
    log_fields = " ".join(f"{k}={v}" for k, v in log_data.items())
    
    if success:
        logging.info(f"stage_success {log_fields}")
    else:
        logging.warning(f"stage_failure {log_fields}")


def record_circuit_breaker_event(
    event_type: str,
    previous_state: Optional[str] = None,
    new_state: Optional[str] = None,
    failure_count: Optional[int] = None,
    video_id: Optional[str] = None,
    **details
) -> None:
    """Record circuit breaker events with structured logging."""
    
    with _lock:
        event = CircuitBreakerEvent(
            timestamp=datetime.utcnow().isoformat(),
            event_type=event_type,
            previous_state=previous_state,
            new_state=new_state,
            failure_count=failure_count,
            video_id=video_id,
            details=details if details else None
        )
        
        _circuit_breaker_events.append(event)
    
    # Emit structured log
    log_data = {"event_type": event_type}
    if previous_state:
        log_data["previous_state"] = previous_state
    if new_state:
        log_data["new_state"] = new_state
    if failure_count is not None:
        log_data["failure_count"] = failure_count
    if video_id:
        log_data["video_id"] = video_id
    
    # Add any additional details
    log_data.update(details)
    
    log_fields = " ".join(f"{k}={v}" for k, v in log_data.items())
    
    if event_type in ["activated", "failure_recorded"]:
        logging.warning(f"circuit_breaker_event {log_fields}")
    else:
        logging.info(f"circuit_breaker_event {log_fields}")


def log_successful_transcript_method(video_id: str) -> None:
    """Log which transcript extraction method succeeded for a video."""
    
    with _lock:
        successful_stage = _successful_attempts.get(video_id)
    
    if successful_stage:
        logging.info(
            f"transcript_success_method video_id={video_id} "
            f"successful_method={successful_stage}"
        )


def get_stage_percentiles(stage: str) -> Dict[str, float]:
    """Calculate p50 and p95 percentiles for stage duration."""
    
    with _lock:
        durations = _stage_durations.get(stage, [])
    
    if not durations:
        return {"p50": 0.0, "p95": 0.0, "count": 0}
    
    try:
        p50 = statistics.median(durations)
        p95 = statistics.quantiles(durations, n=20)[18] if len(durations) >= 20 else max(durations)
        
        return {
            "p50": round(p50, 2),
            "p95": round(p95, 2),
            "count": len(durations)
        }
    except Exception:
        # Fallback for edge cases
        return {
            "p50": sum(durations) / len(durations),
            "p95": max(durations),
            "count": len(durations)
        }


def get_comprehensive_metrics() -> Dict[str, Any]:
    """Get comprehensive metrics including percentiles and recent events."""
    
    with _lock:
        # Calculate percentiles for each stage
        stage_percentiles = {}
        for stage in _stage_durations.keys():
            stage_percentiles[stage] = get_stage_percentiles(stage)
        
        # Get recent stage metrics
        recent_metrics = [
            {
                "timestamp": m.timestamp,
                "video_id": m.video_id,
                "stage": m.stage,
                "proxy_used": m.proxy_used,
                "profile": m.profile,
                "duration_ms": m.duration_ms,
                "success": m.success,
                "error_type": m.error_type,
                "circuit_breaker_state": m.circuit_breaker_state
            }
            for m in list(_stage_metrics)[-50:]  # Last 50 events
        ]
        
        # Get recent circuit breaker events
        recent_cb_events = [
            {
                "timestamp": e.timestamp,
                "event_type": e.event_type,
                "previous_state": e.previous_state,
                "new_state": e.new_state,
                "failure_count": e.failure_count,
                "video_id": e.video_id,
                "details": e.details
            }
            for e in list(_circuit_breaker_events)[-20:]  # Last 20 events
        ]
        
        # Calculate success rates by stage
        stage_success_rates = {}
        for stage in ["yt_api", "timedtext", "youtubei", "asr"]:
            total_attempts = len([m for m in _stage_metrics if m.stage == stage])
            successful_attempts = len([m for m in _stage_metrics if m.stage == stage and m.success])
            
            if total_attempts > 0:
                stage_success_rates[stage] = (successful_attempts / total_attempts) * 100
            else:
                stage_success_rates[stage] = 0.0
        
        return {
            "legacy_metrics": {
                "success_by_source": dict(_success),
                "fail_by_stage": dict(_fail),
                "total_success": sum(_success.values()),
                "total_fail": sum(_fail.values()),
            },
            "stage_percentiles": stage_percentiles,
            "stage_success_rates": stage_success_rates,
            "recent_stage_metrics": recent_metrics,
            "recent_circuit_breaker_events": recent_cb_events,
            "successful_methods": dict(_successful_attempts),
            "metrics_summary": {
                "total_stage_attempts": len(_stage_metrics),
                "total_circuit_breaker_events": len(_circuit_breaker_events),
                "stages_tracked": list(_stage_durations.keys())
            }
        }


def snapshot() -> Dict[str, Dict[str, int]]:
    """Legacy function for backward compatibility."""
    with _lock:
        return {
            "success_by_source": dict(_success),
            "fail_by_stage": dict(_fail),
            "total_success": sum(_success.values()),
            "total_fail": sum(_fail.values()),
        }


def reset_metrics() -> None:
    """Reset all metrics (for testing purposes)."""
    with _lock:
        _success.clear()
        _fail.clear()
        _stage_durations.clear()
        _stage_metrics.clear()
        _circuit_breaker_events.clear()
        _successful_attempts.clear()
