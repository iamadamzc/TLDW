#!/usr/bin/env python3
"""
Demo script showing performance metrics channel separation in action.

This script demonstrates how pipeline events and performance metrics
are logged to separate channels for independent querying and retention.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logging_setup import configure_logging, get_perf_logger
from log_events import evt, perf_evt, log_cpu_memory_metrics, StageTimer

def main():
    """Demonstrate performance channel separation."""
    print("=== Performance Metrics Channel Separation Demo ===\n")
    
    # Configure logging
    configure_logging(log_level="INFO", use_json=True)
    
    print("1. Pipeline Events (main channel):")
    print("   These go to the main logger for job correlation and pipeline tracking")
    
    # Pipeline events
    evt("job_received", video_id="demo123", config="default", timeout=30)
    
    with StageTimer("youtubei", profile="mobile", use_proxy=True):
        # Simulate some work
        import time
        time.sleep(0.1)
    
    evt("job_finished", outcome="success", total_dur_ms=2500)
    
    print("\n2. Performance Metrics (dedicated 'perf' channel):")
    print("   These go to the dedicated performance logger for metrics and monitoring")
    
    # Performance metrics
    perf_evt(metric_type="stage_duration", stage="youtubei", duration_ms=1500, success=True)
    perf_evt(metric_type="circuit_breaker", state="closed", failure_count=0)
    log_cpu_memory_metrics(cpu_percent=15.2, memory_mb=512, disk_usage_pct=45.0)
    
    print("\n3. Channel Separation Benefits:")
    print("   - Pipeline events: filter with `event != \"performance_metric\"`")
    print("   - Performance metrics: filter with `event == \"performance_metric\"`")
    print("   - Independent retention policies possible")
    print("   - Separate log analysis and alerting")
    
    print("\n4. CloudWatch Logs Insights Query Examples:")
    print("   Pipeline events only:")
    print("   fields @timestamp, event, stage, outcome, dur_ms")
    print("   | filter event != \"performance_metric\"")
    print("   | sort @timestamp desc")
    
    print("\n   Performance metrics only:")
    print("   fields @timestamp, metric_type, value, unit")
    print("   | filter event == \"performance_metric\"")
    print("   | stats avg(value) by metric_type")
    
    print("\nDemo completed successfully!")

if __name__ == '__main__':
    main()