#!/usr/bin/env python3
"""
Dashboard integration for transcript service performance monitoring.
Provides metrics endpoints and real-time monitoring data for external dashboards.
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict
from flask import Blueprint, jsonify, request
import threading

from performance_monitor import get_performance_monitor, get_dashboard_metrics
from transcript_metrics import get_comprehensive_metrics
from monitoring import TranscriptMetrics, JobMetrics, HealthChecker
from logging_setup import get_logger, set_job_ctx, get_job_ctx


# Create blueprint for dashboard endpoints
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')
logger = get_logger(__name__)


class MetricsAggregator:
    """Aggregates metrics from various sources for dashboard consumption."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self._cache = {}
        self._cache_ttl = 30  # 30 seconds cache TTL
        self._lock = threading.Lock()
    
    def get_aggregated_metrics(self, hours: int = 1) -> Dict[str, Any]:
        """Get aggregated metrics with caching."""
        cache_key = f"metrics_{hours}h"
        
        with self._lock:
            # Check cache
            if cache_key in self._cache:
                cached_data, timestamp = self._cache[cache_key]
                if time.time() - timestamp < self._cache_ttl:
                    return cached_data
            
            # Generate fresh metrics
            metrics = self._generate_metrics(hours)
            self._cache[cache_key] = (metrics, time.time())
            
            return metrics
    
    def _generate_metrics(self, hours: int) -> Dict[str, Any]:
        """Generate comprehensive metrics for dashboard."""
        try:
            # Get performance metrics
            performance_data = get_dashboard_metrics(hours)
            
            # Get transcript metrics
            transcript_metrics = get_comprehensive_metrics()
            
            # Get circuit breaker status (lazy import to avoid circular import issues)
            try:
                from transcript_service import get_circuit_breaker_status
                circuit_breaker_status = get_circuit_breaker_status()
            except ImportError as e:
                self.logger.warning(f"Could not import get_circuit_breaker_status: {e}")
                circuit_breaker_status = {"state": "unknown", "failure_count": 0}
            
            # Get system health
            health_checker = HealthChecker()
            health_status = health_checker.run_health_checks()
            
            # Aggregate everything
            aggregated = {
                "timestamp": datetime.utcnow().isoformat(),
                "collection_period_hours": hours,
                "performance": performance_data,
                "transcript_pipeline": {
                    "stage_success_rates": transcript_metrics.get("stage_success_rates", {}),
                    "stage_percentiles": transcript_metrics.get("stage_percentiles", {}),
                    "recent_events": transcript_metrics.get("recent_stage_metrics", [])[-20:],
                    "successful_methods": transcript_metrics.get("successful_methods", {})
                },
                "circuit_breaker": {
                    "status": circuit_breaker_status,
                    "recent_events": transcript_metrics.get("recent_circuit_breaker_events", [])[-10:]
                },
                "system_health": {
                    "overall_status": health_status.get("overall_status"),
                    "checks_summary": {
                        "healthy": health_status.get("checks_healthy", 0),
                        "degraded": health_status.get("checks_degraded", 0),
                        "unhealthy": health_status.get("checks_unhealthy", 0)
                    },
                    "critical_issues": [
                        name for name, check in health_status.get("dependencies", {}).items()
                        if check.get("status") == "unhealthy"
                    ]
                },
                "browser_contexts": performance_data.get("browser_context_stats", {}),
                "proxy_health": self._get_proxy_health_summary()
            }
            
            return aggregated
            
        except Exception as e:
            self.logger.error(f"Error generating dashboard metrics: {e}")
            return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}
    
    def _get_proxy_health_summary(self) -> Dict[str, Any]:
        """Get proxy health summary."""
        try:
            from proxy_manager import ProxyManager
            from shared_managers import shared_managers
            
            proxy_manager = shared_managers.get_proxy_manager()
            if proxy_manager and hasattr(proxy_manager, 'get_preflight_metrics'):
                return proxy_manager.get_preflight_metrics()
            else:
                return {"status": "not_available"}
        except Exception as e:
            return {"status": "error", "error": str(e)}


# Global metrics aggregator
_metrics_aggregator = MetricsAggregator()


@dashboard_bp.route('/metrics')
def get_metrics():
    """Get comprehensive metrics for dashboard."""
    # Set correlation ID for this request
    correlation_id = request.headers.get('X-Correlation-ID')
    if correlation_id:
        set_job_ctx(job_id=correlation_id)
    
    try:
        hours = request.args.get('hours', 1, type=int)
        hours = max(1, min(hours, 24))  # Limit to 1-24 hours
        
        metrics = _metrics_aggregator.get_aggregated_metrics(hours)
        
        logger.info(f"Dashboard metrics requested", 
                   hours=hours, 
                   metrics_count=len(metrics))
        
        return jsonify(metrics)
        
    except Exception as e:
        logger.error(f"Error serving dashboard metrics: {e}")
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route('/metrics/performance')
def get_performance_metrics():
    """Get performance-specific metrics."""
    # Set correlation ID for this request
    correlation_id = request.headers.get('X-Correlation-ID')
    if correlation_id:
        set_job_ctx(job_id=correlation_id)
    
    try:
        hours = request.args.get('hours', 1, type=int)
        stage = request.args.get('stage')  # Optional stage filter
        
        performance_data = get_dashboard_metrics(hours)
        
        # Filter by stage if requested
        if stage:
            filtered_data = {}
            for metric_type, metrics in performance_data.get("metrics_by_type", {}).items():
                if metric_type == "stage_duration":
                    filtered_metrics = [
                        m for m in metrics 
                        if m.get("labels", {}).get("stage") == stage
                    ]
                    if filtered_metrics:
                        filtered_data[metric_type] = filtered_metrics
            
            performance_data["metrics_by_type"] = filtered_data
        
        logger.info(f"Performance metrics requested", 
                   hours=hours, 
                   stage_filter=stage)
        
        return jsonify(performance_data)
        
    except Exception as e:
        logger.error(f"Error serving performance metrics: {e}")
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route('/metrics/circuit-breaker')
def get_circuit_breaker_metrics():
    """Get circuit breaker specific metrics."""
    # Set correlation ID for this request
    correlation_id = request.headers.get('X-Correlation-ID')
    if correlation_id:
        set_job_ctx(job_id=correlation_id)
    
    try:
        # Lazy import to avoid circular import issues
        try:
            from transcript_service import get_circuit_breaker_status
            status = get_circuit_breaker_status()
        except ImportError as e:
            logger.warning(f"Could not import get_circuit_breaker_status: {e}")
            status = {"state": "unknown", "failure_count": 0}
        
        comprehensive_metrics = get_comprehensive_metrics()
        
        circuit_breaker_data = {
            "current_status": status,
            "recent_events": comprehensive_metrics.get("recent_circuit_breaker_events", []),
            "monitoring_summary": get_performance_monitor().circuit_breaker_monitor.get_monitoring_summary()
        }
        
        logger.info("Circuit breaker metrics requested")
        
        return jsonify(circuit_breaker_data)
        
    except Exception as e:
        logger.error(f"Error serving circuit breaker metrics: {e}")
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route('/metrics/browser-contexts')
def get_browser_context_metrics():
    """Get browser context specific metrics."""
    # Set correlation ID for this request
    correlation_id = request.headers.get('X-Correlation-ID')
    if correlation_id:
        set_job_ctx(job_id=correlation_id)
    
    try:
        performance_monitor = get_performance_monitor()
        context_stats = performance_monitor.browser_manager.get_context_stats()
        
        logger.info("Browser context metrics requested")
        
        return jsonify(context_stats)
        
    except Exception as e:
        logger.error(f"Error serving browser context metrics: {e}")
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route('/metrics/health')
def get_health_metrics():
    """Get system health metrics."""
    # Set correlation ID for this request
    correlation_id = request.headers.get('X-Correlation-ID')
    if correlation_id:
        set_job_ctx(job_id=correlation_id)
    
    try:
        health_checker = HealthChecker()
        health_status = health_checker.run_health_checks()
        
        logger.info("Health metrics requested")
        
        return jsonify(health_status)
        
    except Exception as e:
        logger.error(f"Error serving health metrics: {e}")
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route('/metrics/proxy')
def get_proxy_metrics():
    """Get proxy health and performance metrics."""
    # Set correlation ID for this request
    correlation_id = request.headers.get('X-Correlation-ID')
    if correlation_id:
        set_job_ctx(job_id=correlation_id)
    
    try:
        proxy_summary = _metrics_aggregator._get_proxy_health_summary()
        
        logger.info("Proxy metrics requested")
        
        return jsonify(proxy_summary)
        
    except Exception as e:
        logger.error(f"Error serving proxy metrics: {e}")
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route('/metrics/alerts')
def get_alerts():
    """Get recent alerts and critical events."""
    # Set correlation ID for this request
    correlation_id = request.headers.get('X-Correlation-ID')
    if correlation_id:
        set_job_ctx(job_id=correlation_id)
    
    try:
        hours = request.args.get('hours', 24, type=int)
        
        # This would typically query an alerts database or log aggregation system
        # For now, we'll return a placeholder structure
        alerts_data = {
            "collection_period_hours": hours,
            "active_alerts": [],
            "recent_alerts": [],
            "alert_summary": {
                "critical": 0,
                "warning": 0,
                "info": 0
            }
        }
        
        logger.info(f"Alerts requested", hours=hours)
        
        return jsonify(alerts_data)
        
    except Exception as e:
        logger.error(f"Error serving alerts: {e}")
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route('/metrics/export')
def export_metrics():
    """Export metrics in Prometheus format."""
    # Set correlation ID for this request
    correlation_id = request.headers.get('X-Correlation-ID')
    if correlation_id:
        set_job_ctx(job_id=correlation_id)
    
    try:
        # Get comprehensive metrics
        metrics = _metrics_aggregator.get_aggregated_metrics(1)
        
        # Convert to Prometheus format
        prometheus_metrics = _convert_to_prometheus_format(metrics)
        
        logger.info("Metrics export requested", format="prometheus")
        
        return prometheus_metrics, 200, {'Content-Type': 'text/plain; charset=utf-8'}
        
    except Exception as e:
        logger.error(f"Error exporting metrics: {e}")
        return f"# Error exporting metrics: {e}\n", 500


def _convert_to_prometheus_format(metrics: Dict[str, Any]) -> str:
    """Convert metrics to Prometheus exposition format."""
    lines = []
    timestamp = int(time.time() * 1000)
    
    # Add metadata
    lines.append("# HELP tldw_transcript_stage_duration_ms Stage duration in milliseconds")
    lines.append("# TYPE tldw_transcript_stage_duration_ms histogram")
    
    # Convert stage percentiles
    stage_percentiles = metrics.get("transcript_pipeline", {}).get("stage_percentiles", {})
    for stage, percentiles in stage_percentiles.items():
        if percentiles.get("count", 0) > 0:
            lines.append(f'tldw_transcript_stage_duration_ms{{stage="{stage}",quantile="0.5"}} {percentiles["p50"]} {timestamp}')
            lines.append(f'tldw_transcript_stage_duration_ms{{stage="{stage}",quantile="0.95"}} {percentiles["p95"]} {timestamp}')
            lines.append(f'tldw_transcript_stage_duration_ms_count{{stage="{stage}"}} {percentiles["count"]} {timestamp}')
    
    # Add circuit breaker metrics
    lines.append("# HELP tldw_circuit_breaker_state Circuit breaker state (0=closed, 1=half-open, 2=open)")
    lines.append("# TYPE tldw_circuit_breaker_state gauge")
    
    cb_status = metrics.get("circuit_breaker", {}).get("status", {})
    state_values = {"closed": 0, "half-open": 1, "open": 2}
    state_value = state_values.get(cb_status.get("state", "closed"), 0)
    lines.append(f'tldw_circuit_breaker_state {state_value} {timestamp}')
    
    lines.append("# HELP tldw_circuit_breaker_failures Circuit breaker failure count")
    lines.append("# TYPE tldw_circuit_breaker_failures counter")
    lines.append(f'tldw_circuit_breaker_failures {cb_status.get("failure_count", 0)} {timestamp}')
    
    # Add browser context metrics
    lines.append("# HELP tldw_browser_contexts_active Active browser contexts")
    lines.append("# TYPE tldw_browser_contexts_active gauge")
    
    browser_stats = metrics.get("browser_contexts", {})
    lines.append(f'tldw_browser_contexts_active {browser_stats.get("active_contexts", 0)} {timestamp}')
    
    lines.append("# HELP tldw_browser_memory_usage_mb Browser memory usage in MB")
    lines.append("# TYPE tldw_browser_memory_usage_mb gauge")
    lines.append(f'tldw_browser_memory_usage_mb {browser_stats.get("memory_usage_mb", 0)} {timestamp}')
    
    # Add system health metrics
    lines.append("# HELP tldw_system_health_status System health status (1=healthy, 0=unhealthy)")
    lines.append("# TYPE tldw_system_health_status gauge")
    
    health_status = metrics.get("system_health", {}).get("overall_status", "unknown")
    health_value = 1 if health_status == "healthy" else 0
    lines.append(f'tldw_system_health_status {{status="{health_status}"}} {health_value} {timestamp}')
    
    return "\n".join(lines) + "\n"


def register_dashboard_routes(app):
    """Register dashboard routes with Flask app."""
    app.register_blueprint(dashboard_bp)
    
    # Add CORS headers for dashboard access
    @dashboard_bp.after_request
    def after_request(response):
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-Correlation-ID')
        response.headers.add('Access-Control-Allow-Methods', 'GET,OPTIONS')
        return response
    
    logging.info("Dashboard routes registered", 
                blueprint="dashboard", 
                prefix="/api/dashboard")


# Health check endpoint for dashboard monitoring
@dashboard_bp.route('/health')
def dashboard_health():
    """Health check endpoint for dashboard service."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "dashboard",
        "version": os.getenv("APP_VERSION", "unknown")
    })
