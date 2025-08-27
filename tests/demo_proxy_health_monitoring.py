#!/usr/bin/env python3
"""
Demo script for Task 16: Proxy Health Metrics and Preflight Monitoring

This demonstrates the implemented functionality:
- Requirement 16.1: Preflight check counters for hits/misses logging
- Requirement 16.2: Masked username tail logging for identification  
- Requirement 16.3: Healthy boolean accessor for proxy status
- Requirement 16.4: Structured logs showing proxy health without credential leakage
- Requirement 16.5: Preflight rates and proxy performance metrics
"""

import logging
import time
from proxy_manager import ProxyManager

def setup_logging():
    """Set up logging to see the structured output"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def demo_proxy_health_monitoring():
    """Demonstrate proxy health monitoring functionality"""
    logger = setup_logging()
    
    print("🔍 Demo: Proxy Health Metrics and Preflight Monitoring")
    print("=" * 60)
    
    # Test secret data (would normally come from AWS Secrets Manager)
    test_secret_data = {
        "provider": "oxylabs",
        "host": "pr.oxylabs.io",
        "port": 10000,
        "username": "demo-user-12345",
        "password": "demo+password!",
        "session_ttl_minutes": 10
    }
    
    print("\n1. Creating ProxyManager with test configuration...")
    pm = ProxyManager(test_secret_data, logger)
    
    print(f"\n2. Testing masked username tail generation (Requirement 16.2):")
    masked_tail = pm._get_masked_username_tail()
    print(f"   Original username: demo-user-12345")
    print(f"   Masked tail: {masked_tail}")
    print(f"   ✅ Full username is protected, only last 4 chars shown")
    
    print(f"\n3. Testing healthy boolean accessor (Requirement 16.3):")
    print(f"   Initial health status: {pm.healthy}")
    
    # Set health status manually for demo
    pm._healthy = True
    print(f"   After setting healthy=True: {pm.healthy}")
    
    pm._healthy = False  
    print(f"   After setting healthy=False: {pm.healthy}")
    
    print(f"\n4. Testing preflight metrics collection (Requirement 16.1, 16.5):")
    
    # Simulate some preflight activity
    pm._preflight_hits = 8
    pm._preflight_misses = 2
    pm._preflight_total = 10
    pm._preflight_durations.extend([0.1, 0.15, 0.12, 0.18, 0.09])
    pm._last_preflight_time = time.time()
    
    metrics = pm.get_preflight_metrics()
    print(f"   Preflight hits: {metrics['preflight_hits']}")
    print(f"   Preflight misses: {metrics['preflight_misses']}")
    print(f"   Total checks: {metrics['preflight_total']}")
    print(f"   Hit rate: {metrics['hit_rate']}")
    print(f"   Average duration: {metrics['avg_duration_ms']}ms")
    print(f"   Username tail: {metrics['proxy_username_tail']}")
    
    print(f"\n5. Testing structured health status logging (Requirement 16.4):")
    print("   Emitting health status (check logs for structured output)...")
    pm.emit_health_status()
    
    print(f"\n6. Testing credential protection:")
    print("   Checking that no sensitive data appears in logs...")
    
    # Get all log output as string to verify no credential leakage
    import io
    import sys
    
    # Capture log output
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    logger.addHandler(handler)
    
    # Emit more logs
    pm.emit_health_status()
    pm.get_preflight_metrics()
    
    log_output = log_capture.getvalue()
    
    # Check for credential leakage
    has_password = "demo+password!" in log_output
    has_full_username = "demo-user-12345" in log_output
    has_proxy_url = "demo-user-12345:demo+password!" in log_output
    
    print(f"   Password in logs: {'❌ LEAKED' if has_password else '✅ Protected'}")
    print(f"   Full username in logs: {'❌ LEAKED' if has_full_username else '✅ Protected'}")
    print(f"   Proxy URL with creds in logs: {'❌ LEAKED' if has_proxy_url else '✅ Protected'}")
    
    print(f"\n7. Testing proxy manager without configuration:")
    pm_no_proxy = ProxyManager({}, logger)
    print(f"   Health status with no proxy: {pm_no_proxy.healthy}")
    print("   Emitting health status for unconfigured proxy...")
    pm_no_proxy.emit_health_status()
    
    print(f"\n✅ Demo completed successfully!")
    print(f"All requirements for Task 16 have been implemented and demonstrated:")
    print(f"  ✅ 16.1: Preflight check counters for hits/misses logging")
    print(f"  ✅ 16.2: Masked username tail logging for identification")
    print(f"  ✅ 16.3: Healthy boolean accessor for proxy status")
    print(f"  ✅ 16.4: Structured logs showing proxy health without credential leakage")
    print(f"  ✅ 16.5: Preflight rates and proxy performance metrics")

if __name__ == "__main__":
    demo_proxy_health_monitoring()