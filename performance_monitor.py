#!/usr/bin/env python3
"""
Performance monitoring and optimization for transcript service enhancements.
Implements comprehensive metrics collection, dashboard integration, and browser context optimization.
"""

import os
import time
import logging
import threading
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
import json
import gc
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
from contextlib import contextmanager

# Import existing monitoring components
from monitoring import TranscriptMetrics, JobMetrics, HealthChecker, AlertManager
from transcript_metrics import (
    record_stage_metrics, 
    record_circuit_breaker_event,
    get_comprehensive_metrics,
    get_stage_percentiles
)


@dataclass
class PerformanceMetrics:
    """Enhanced performance metrics for dashboard integration."""
    timestamp: str
    metric_type: str  # "stage_duration", "circuit_breaker", "browser_context", "memory"
    labels: Dict[str, str]  # {stage, proxy_used, profile, etc.}
    value: float
    unit: str  # "ms", "bytes", "count", "percent"
    p50: Optional[float] = None
    p95: Optional[float] = None


class BrowserContextManager:
    """Optimized browser context management with memory monitoring."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._contexts = {}  # profile -> context
        self._browsers = {}  # profile -> browser
        self._context_usage = defaultdict(int)  # profile -> usage_count
        self._context_created_at = {}  # profile -> timestamp
        self._memory_usage = deque(maxlen=100)
        self._lock = threading.Lock()
        
        # Configuration
        self.max_context_age_minutes = int(os.getenv("BROWSER_CONTEXT_MAX_AGE_MINUTES", "30"))
        self.max_context_uses = int(os.getenv("BROWSER_CONTEXT_MAX_USES", "50"))
        self.memory_threshold_mb = int(os.getenv("BROWSER_MEMORY_THRESHOLD_MB", "512"))
        
    def get_context_stats(self) -> Dict[str, Any]:
        """Get browser context statistics for monitoring."""
        with self._lock:
            return {
                "active_contexts": len(self._contexts),
                "active_browsers": len(self._browsers),
                "context_usage": dict(self._context_usage),
                "memory_usage_mb": self._get_current_memory_usage(),
                "contexts_by_profile": list(self._contexts.keys()),
                "oldest_context_age_minutes": self._get_oldest_context_age()
            }
    
    def _get_current_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            if PSUTIL_AVAILABLE:
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                self._memory_usage.append(memory_mb)
                return memory_mb
            else:
                # Fallback: estimate memory usage
                import sys
                memory_mb = sys.getsizeof(self._contexts) / 1024 / 1024
                self._memory_usage.append(memory_mb)
                return memory_mb
        except Exception:
            return 0.0
    
    def _get_oldest_context_age(self) -> Optional[float]:
        """Get age of oldest context in minutes."""
        if not self._context_created_at:
            return None
        
        oldest_time = min(self._context_created_at.values())
        return (time.time() - oldest_time) / 60
    
    def should_cleanup_context(self, profile: str) -> bool:
        """Determine if context should be cleaned up."""
        if profile not in self._contexts:
            return False
        
        # Check age
        created_at = self._context_created_at.get(profile, time.time())
        age_minutes = (time.time() - created_at) / 60
        if age_minutes > self.max_context_age_minutes:
            return True
        
        # Check usage count
        if self._context_usage[profile] > self.max_context_uses:
            return True
        
        # Check memory pressure
        current_memory = self._get_current_memory_usage()
        if current_memory > self.memory_threshold_mb:
            return True
        
        return False
    
    @contextmanager
    def get_optimized_context(self, profile: str, proxy_config: Optional[Dict] = None):
        """Get optimized browser context with automatic cleanup."""
        start_time = time.time()
        context = None
        browser = None
        
        try:
            with self._lock:
                # Check if we should cleanup existing context
                if self.should_cleanup_context(profile):
                    self._cleanup_context(profile)
                
                # Get or create context
                if profile in self._contexts:
                    context = self._contexts[profile]
                    browser = self._browsers[profile]
                    self._context_usage[profile] += 1
                    
                    self.logger.info(
                        f"browser_context_reused profile={profile} "
                        f"usage_count={self._context_usage[profile]} "
                        f"age_minutes={self._get_oldest_context_age():.1f}"
                    )
                else:
                    # Create new context
                    context, browser = self._create_new_context(profile, proxy_config)
                    self._contexts[profile] = context
                    self._browsers[profile] = browser
                    self._context_usage[profile] = 1
                    self._context_created_at[profile] = time.time()
                    
                    self.logger.info(
                        f"browser_context_created profile={profile} "
                        f"total_contexts={len(self._contexts)}"
                    )
            
            # Record performance metrics
            creation_time_ms = (time.time() - start_time) * 1000
            record_stage_metrics(
                video_id="context_management",
                stage="browser_context",
                duration_ms=creation_time_ms,
                success=True,
                proxy_used=proxy_config is not None,
                profile=profile
            )
            
            yield context
            
        except Exception as e:
            # Record failure metrics
            creation_time_ms = (time.time() - start_time) * 1000
            record_stage_metrics(
                video_id="context_management",
                stage="browser_context",
                duration_ms=creation_time_ms,
                success=False,
                proxy_used=proxy_config is not None,
                profile=profile,
                error_type=type(e).__name__
            )
            raise
        
        finally:
            # Update memory metrics
            self._get_current_memory_usage()
    
    def _create_new_context(self, profile: str, proxy_config: Optional[Dict] = None):
        """Create new browser context with optimized settings."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise ImportError("Playwright not available - browser context optimization disabled")
        
        try:
            from transcript_service import PROFILES
        except ImportError:
            # Fallback profile definitions
            PROFILES = {
                "desktop": type('ClientProfile', (), {
                    'name': 'desktop',
                    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'viewport': {'width': 1920, 'height': 1080}
                })(),
                "mobile": type('ClientProfile', (), {
                    'name': 'mobile',
                    'user_agent': 'Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                    'viewport': {'width': 390, 'height': 844}
                })()
            }
        
        playwright = sync_playwright().start()
        
        # Launch browser with optimized settings
        browser = playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--memory-pressure-off",  # Reduce memory pressure handling
                "--max_old_space_size=256",  # Limit V8 heap size
            ]
        )
        
        # Get profile configuration
        profile_config = PROFILES.get(profile, PROFILES["desktop"])
        
        # Create context with optimized settings
        context_options = {
            "user_agent": profile_config.user_agent,
            "viewport": profile_config.viewport,
            "locale": "en-US",
            "timezone_id": "America/New_York",
            "ignore_https_errors": True,
            "java_script_enabled": True,
            "bypass_csp": True,
        }
        
        # Add proxy configuration if provided
        if proxy_config:
            context_options["proxy"] = proxy_config
        
        # Load storage state if available
        cookie_dir = os.getenv("COOKIE_DIR", "/app/cookies")
        storage_state_path = os.path.join(cookie_dir, "youtube_session.json")
        if os.path.exists(storage_state_path):
            context_options["storage_state"] = storage_state_path
        
        context = browser.new_context(**context_options)
        
        return context, browser
    
    def _cleanup_context(self, profile: str):
        """Clean up browser context and browser."""
        try:
            if profile in self._contexts:
                context = self._contexts[profile]
                context.close()
                del self._contexts[profile]
                
                self.logger.info(f"browser_context_cleaned profile={profile}")
        except Exception as e:
            self.logger.warning(f"Error cleaning context for {profile}: {e}")
        
        try:
            if profile in self._browsers:
                browser = self._browsers[profile]
                browser.close()
                del self._browsers[profile]
                
                self.logger.info(f"browser_closed profile={profile}")
        except Exception as e:
            self.logger.warning(f"Error closing browser for {profile}: {e}")
        
        # Clean up tracking data
        self._context_usage.pop(profile, None)
        self._context_created_at.pop(profile, None)
        
        # Force garbage collection
        gc.collect()
    
    def cleanup_all_contexts(self):
        """Clean up all browser contexts."""
        with self._lock:
            profiles_to_cleanup = list(self._contexts.keys())
            for profile in profiles_to_cleanup:
                self._cleanup_context(profile)
        
        self.logger.info("All browser contexts cleaned up")


class CircuitBreakerMonitor:
    """Enhanced circuit breaker monitoring with alerting."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._state_history = deque(maxlen=1000)
        self._alert_thresholds = {
            "failure_rate": 0.5,  # Alert if >50% failures
            "open_duration_minutes": 5,  # Alert if open for >5 minutes
            "frequent_state_changes": 10,  # Alert if >10 state changes in 10 minutes
        }
        self._last_alert_time = {}
        self._alert_cooldown_minutes = 15
    
    def record_state_change(self, previous_state: str, new_state: str, failure_count: int):
        """Record circuit breaker state change with alerting."""
        timestamp = datetime.utcnow()
        
        state_change = {
            "timestamp": timestamp.isoformat(),
            "previous_state": previous_state,
            "new_state": new_state,
            "failure_count": failure_count
        }
        
        self._state_history.append(state_change)
        
        # Check for alert conditions
        self._check_alert_conditions(state_change)
        
        # Emit structured log
        self.logger.info(
            f"circuit_breaker_state_change previous={previous_state} "
            f"new={new_state} failure_count={failure_count}"
        )
    
    def _check_alert_conditions(self, state_change: Dict):
        """Check if alert conditions are met."""
        now = datetime.utcnow()
        
        # Check for frequent state changes
        recent_changes = [
            change for change in self._state_history
            if datetime.fromisoformat(change["timestamp"]) > now - timedelta(minutes=10)
        ]
        
        if len(recent_changes) > self._alert_thresholds["frequent_state_changes"]:
            self._emit_alert("frequent_state_changes", {
                "changes_count": len(recent_changes),
                "threshold": self._alert_thresholds["frequent_state_changes"]
            })
        
        # Check for prolonged open state
        if state_change["new_state"] == "open":
            # Look for how long it's been open
            open_duration = self._calculate_open_duration()
            if open_duration and open_duration > self._alert_thresholds["open_duration_minutes"]:
                self._emit_alert("prolonged_open_state", {
                    "duration_minutes": open_duration,
                    "threshold_minutes": self._alert_thresholds["open_duration_minutes"]
                })
    
    def _calculate_open_duration(self) -> Optional[float]:
        """Calculate how long circuit breaker has been open."""
        if not self._state_history:
            return None
        
        # Find the most recent transition to open state
        for change in reversed(self._state_history):
            if change["new_state"] == "open":
                open_time = datetime.fromisoformat(change["timestamp"])
                duration_minutes = (datetime.utcnow() - open_time).total_seconds() / 60
                return duration_minutes
        
        return None
    
    def _emit_alert(self, alert_type: str, details: Dict):
        """Emit alert if not in cooldown period."""
        now = datetime.utcnow()
        last_alert = self._last_alert_time.get(alert_type)
        
        if last_alert:
            minutes_since_last = (now - last_alert).total_seconds() / 60
            if minutes_since_last < self._alert_cooldown_minutes:
                return  # Still in cooldown
        
        self._last_alert_time[alert_type] = now
        
        self.logger.warning(
            f"circuit_breaker_alert type={alert_type} "
            f"details={json.dumps(details)}"
        )
    
    def get_monitoring_summary(self) -> Dict[str, Any]:
        """Get circuit breaker monitoring summary."""
        if not self._state_history:
            return {"no_data": True}
        
        recent_hour = datetime.utcnow() - timedelta(hours=1)
        recent_changes = [
            change for change in self._state_history
            if datetime.fromisoformat(change["timestamp"]) > recent_hour
        ]
        
        state_counts = defaultdict(int)
        for change in recent_changes:
            state_counts[change["new_state"]] += 1
        
        return {
            "total_state_changes": len(self._state_history),
            "recent_hour_changes": len(recent_changes),
            "recent_state_distribution": dict(state_counts),
            "current_open_duration_minutes": self._calculate_open_duration(),
            "alert_thresholds": self._alert_thresholds
        }


class DashboardMetricsCollector:
    """Collects and formats metrics for dashboard integration."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._metrics_buffer = deque(maxlen=10000)
        self._lock = threading.Lock()
        
        # Initialize component monitors
        self.browser_manager = BrowserContextManager()
        self.circuit_breaker_monitor = CircuitBreakerMonitor()
        
        # Start background collection thread
        self._collection_thread = threading.Thread(target=self._collect_metrics_loop, daemon=True)
        self._collection_thread.start()
    
    def emit_performance_metric(self, metric_type: str, value: float, labels: Dict[str, str], 
                               unit: str = "ms", p50: Optional[float] = None, p95: Optional[float] = None):
        """Emit performance metric for dashboard integration."""
        metric = PerformanceMetrics(
            timestamp=datetime.utcnow().isoformat(),
            metric_type=metric_type,
            labels=labels,
            value=value,
            unit=unit,
            p50=p50,
            p95=p95
        )
        
        with self._lock:
            self._metrics_buffer.append(metric)
        
        # Emit structured log for external collection using dedicated performance channel
        from log_events import perf_evt
        
        perf_evt(
            metric_type=metric_type,
            value=value,
            unit=unit,
            p50=p50,
            p95=p95,
            **labels
        )
    
    def _collect_metrics_loop(self):
        """Background thread to collect metrics periodically."""
        while True:
            try:
                self._collect_stage_duration_metrics()
                self._collect_browser_context_metrics()
                self._collect_circuit_breaker_metrics()
                time.sleep(30)  # Collect every 30 seconds
            except Exception as e:
                self.logger.error(f"Error in metrics collection loop: {e}")
                time.sleep(60)  # Wait longer on error
    
    def _collect_stage_duration_metrics(self):
        """Collect stage duration metrics with percentiles."""
        try:
            comprehensive_metrics = get_comprehensive_metrics()
            stage_percentiles = comprehensive_metrics.get("stage_percentiles", {})
            
            for stage, percentiles in stage_percentiles.items():
                if percentiles["count"] > 0:
                    # Emit p50 and p95 metrics
                    self.emit_performance_metric(
                        metric_type="stage_duration",
                        value=percentiles["p50"],
                        labels={"stage": stage, "percentile": "p50"},
                        unit="ms",
                        p50=percentiles["p50"],
                        p95=percentiles["p95"]
                    )
                    
                    self.emit_performance_metric(
                        metric_type="stage_duration",
                        value=percentiles["p95"],
                        labels={"stage": stage, "percentile": "p95"},
                        unit="ms",
                        p50=percentiles["p50"],
                        p95=percentiles["p95"]
                    )
        except Exception as e:
            self.logger.error(f"Error collecting stage duration metrics: {e}")
    
    def _collect_browser_context_metrics(self):
        """Collect browser context performance metrics."""
        try:
            stats = self.browser_manager.get_context_stats()
            
            # Emit context count metrics
            self.emit_performance_metric(
                metric_type="browser_contexts",
                value=stats["active_contexts"],
                labels={"metric": "active_count"},
                unit="count"
            )
            
            # Emit memory usage metrics
            self.emit_performance_metric(
                metric_type="browser_memory",
                value=stats["memory_usage_mb"],
                labels={"metric": "usage_mb"},
                unit="mb"
            )
            
            # Emit context age metrics
            if stats["oldest_context_age_minutes"]:
                self.emit_performance_metric(
                    metric_type="browser_context_age",
                    value=stats["oldest_context_age_minutes"],
                    labels={"metric": "oldest_age_minutes"},
                    unit="minutes"
                )
        except Exception as e:
            self.logger.error(f"Error collecting browser context metrics: {e}")
    
    def _collect_circuit_breaker_metrics(self):
        """Collect circuit breaker monitoring metrics."""
        try:
            # Lazy import to avoid circular import issues during startup
            from transcript_service import get_circuit_breaker_status
            
            status = get_circuit_breaker_status()
            
            # Emit circuit breaker state as numeric value
            state_values = {"closed": 0, "half-open": 1, "open": 2}
            state_value = state_values.get(status["state"], -1)
            
            self.emit_performance_metric(
                metric_type="circuit_breaker_state",
                value=state_value,
                labels={"state": status["state"]},
                unit="state"
            )
            
            # Emit failure count
            self.emit_performance_metric(
                metric_type="circuit_breaker_failures",
                value=status["failure_count"],
                labels={"metric": "failure_count"},
                unit="count"
            )
            
            # Emit recovery time remaining
            if status["recovery_time_remaining"]:
                self.emit_performance_metric(
                    metric_type="circuit_breaker_recovery",
                    value=status["recovery_time_remaining"],
                    labels={"metric": "time_remaining_seconds"},
                    unit="seconds"
                )
        except Exception as e:
            self.logger.error(f"Error collecting circuit breaker metrics: {e}")
    
    def get_dashboard_data(self, hours: int = 1) -> Dict[str, Any]:
        """Get formatted data for dashboard integration."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        with self._lock:
            recent_metrics = [
                metric for metric in self._metrics_buffer
                if datetime.fromisoformat(metric.timestamp) > cutoff_time
            ]
        
        # Group metrics by type
        metrics_by_type = defaultdict(list)
        for metric in recent_metrics:
            metrics_by_type[metric.metric_type].append(asdict(metric))
        
        # Calculate summary statistics
        summary = {}
        for metric_type, metrics in metrics_by_type.items():
            values = [m["value"] for m in metrics]
            if values:
                summary[metric_type] = {
                    "count": len(values),
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                    "recent_metrics": metrics[-10:]  # Last 10 metrics
                }
        
        return {
            "collection_period_hours": hours,
            "total_metrics": len(recent_metrics),
            "metrics_by_type": dict(metrics_by_type),
            "summary": summary,
            "browser_context_stats": self.browser_manager.get_context_stats(),
            "circuit_breaker_monitoring": self.circuit_breaker_monitor.get_monitoring_summary()
        }


# Global performance monitor instance
_performance_monitor = DashboardMetricsCollector()


def get_performance_monitor() -> DashboardMetricsCollector:
    """Get global performance monitor instance."""
    return _performance_monitor


def get_optimized_browser_context(profile: str, proxy_config: Optional[Dict] = None):
    """Get optimized browser context with automatic cleanup."""
    return _performance_monitor.browser_manager.get_optimized_context(profile, proxy_config)


def emit_performance_metric(metric_type: str, value: float, labels: Dict[str, str], 
                           unit: str = "ms", p50: Optional[float] = None, p95: Optional[float] = None):
    """Emit performance metric for dashboard integration."""
    _performance_monitor.emit_performance_metric(metric_type, value, labels, unit, p50, p95)


def cleanup_all_browser_contexts():
    """Clean up all browser contexts for shutdown."""
    _performance_monitor.browser_manager.cleanup_all_contexts()


def get_dashboard_metrics(hours: int = 1) -> Dict[str, Any]:
    """Get dashboard metrics for the specified time period."""
    return _performance_monitor.get_dashboard_data(hours)
