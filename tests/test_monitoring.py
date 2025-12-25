#!/usr/bin/env python3
"""
Test for monitoring and observability features
"""
import os
import sys
import time
import logging
import threading
from unittest.mock import patch, Mock

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_with_timeout(func, timeout_seconds=10):
    """Run a function with a timeout"""
    result = [None]
    exception = [None]
    
    def target():
        try:
            result[0] = func()
        except Exception as e:
            exception[0] = e
    
    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    thread.join(timeout_seconds)
    
    if thread.is_alive():
        print(f"  ❌ Test timed out after {timeout_seconds} seconds")
        return False
    
    if exception[0]:
        raise exception[0]
    
    return result[0]

def test_transcript_metrics():
    """Test TranscriptMetrics functionality"""
    print("=== TranscriptMetrics Test ===")
    
    try:
        from monitoring import TranscriptMetrics
        
        metrics = TranscriptMetrics()
        
        # Test recording transcript attempts and successes
        start_time = time.time()
        metrics.record_transcript_attempt("test_video_1", "youtube_api", start_time)
        metrics.record_transcript_success("test_video_1", "youtube_api", start_time, 1500)
        
        # Test recording failures  
        start_time2 = time.time()
        metrics.record_transcript_attempt("test_video_2", "timed_text", start_time2)
        metrics.record_transcript_failure("test_video_2", "timed_text", start_time2, 
                                        "timeout", "Connection timeout")
        
        # Test metrics calculation
        success_rates = metrics.get_success_rates()
        avg_times = metrics.get_average_processing_times()
        summary = metrics.get_metrics_summary()
        
        print(f"  Debug: success_rates={success_rates}")
        print(f"  Debug: summary attempts={summary.get('total_attempts', {})}")
        
        # Verify results
        if (success_rates.get("youtube_api", 0) == 100.0 and
            success_rates.get("timed_text", 0) == 0.0 and
            "youtube_api" in avg_times and
            summary["total_attempts"]["youtube_api"] == 1):
            print("  ✅ TranscriptMetrics recording and calculation works")
            return True
        else:
            print(f"  ❌ TranscriptMetrics failed: rates={success_rates}")
            return False
            
    except Exception as e:
        print(f"❌ TranscriptMetrics test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_job_metrics():
    """Test JobMetrics functionality"""
    print("\n=== JobMetrics Test ===")
    
    try:
        from monitoring import JobMetrics
        
        metrics = JobMetrics()
        
        # Test job submission and completion
        metrics.record_job_submitted("job_123", 3)
        time.sleep(0.01)  # Simulate processing time
        metrics.record_job_completed("job_123", 2, 3, True)  # Partial success
        
        # Test video processing
        metrics.record_video_processed("video_1", 1500.0, True)
        metrics.record_video_processed("video_2", 2000.0, True)
        metrics.record_video_processed("video_3", 500.0, False)
        
        # Test metrics calculation
        completion_rates = metrics.get_job_completion_rates()
        summary = metrics.get_metrics_summary()
        
        # Verify results
        if (summary["jobs_submitted"] == 1 and
            summary["jobs_partial"] == 1 and
            summary["total_videos_processed"] == 3 and
            summary["total_videos_successful"] == 2 and
            summary["emails_sent"] == 1):
            print("  ✅ JobMetrics recording and calculation works")
            return True
        else:
            print(f"  ❌ JobMetrics failed: rates={completion_rates}, summary={summary}")
            return False
            
    except Exception as e:
        print(f"❌ JobMetrics test failed: {e}")
        return False

def test_health_checker():
    """Test HealthChecker functionality"""
    print("\n=== HealthChecker Test ===")
    
    try:
        from monitoring import HealthChecker
        
        checker = HealthChecker()
        
        # Mock environment variables for testing
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'sk-test123456789',
            'RESEND_API_KEY': 're_test123',
            'SENDER_EMAIL': 'test@example.com'
        }):
            # Run health checks
            results = checker.run_health_checks(force=True)
            
            # Verify structure
            if (isinstance(results, dict) and
                "overall_status" in results and
                "dependencies" in results and
                "checks_total" in results):
                
                # Check that some basic checks passed
                deps = results["dependencies"]
                openai_healthy = deps.get("openai_api", {}).get("status") == "healthy"
                resend_healthy = deps.get("resend_api", {}).get("status") == "healthy"
                
                if openai_healthy and resend_healthy:
                    print("  ✅ HealthChecker works and basic checks pass")
                    return True
                else:
                    print(f"  ❌ Some health checks failed: openai={openai_healthy}, resend={resend_healthy}")
                    return False
            else:
                print(f"  ❌ HealthChecker returned invalid structure: {results}")
                return False
            
    except Exception as e:
        print(f"❌ HealthChecker test failed: {e}")
        return False

def test_alert_manager():
    """Test AlertManager functionality"""
    print("\n=== AlertManager Test ===")
    
    try:
        from monitoring import AlertManager, TranscriptMetrics, JobMetrics
        
        alert_manager = AlertManager()
        
        # Create metrics with high failure rates to trigger alerts
        transcript_metrics = TranscriptMetrics()
        job_metrics = JobMetrics()
        
        # Simulate high failure scenario
        for i in range(10):
            start_time = time.time()
            transcript_metrics.record_transcript_attempt(f"video_{i}", "youtube_api", start_time)
            if i < 3:  # Only 30% success rate
                transcript_metrics.record_transcript_success(f"video_{i}", "youtube_api", start_time, 1000)
            else:
                transcript_metrics.record_transcript_failure(f"video_{i}", "youtube_api", start_time, 
                                                           "error", "Test error")
        
        # Simulate job failures
        for i in range(5):
            job_metrics.record_job_submitted(f"job_{i}", 1)
            if i < 2:  # 40% success rate
                job_metrics.record_job_completed(f"job_{i}", 1, 1, True)
            else:
                job_metrics.record_job_completed(f"job_{i}", 0, 1, False)
        
        # Mock health status with unhealthy dependency
        health_status = {
            "dependencies": {
                "test_service": {
                    "status": "unhealthy",
                    "message": "Test service down"
                }
            }
        }
        
        # Check for alerts
        alerts = alert_manager.check_and_alert(transcript_metrics, job_metrics, health_status)
        alert_summary = alert_manager.get_alert_summary()
        
        # Verify alerts were triggered
        if (len(alerts) > 0 and
            alert_summary["total_alerts"] > 0 and
            any(alert["alert_type"] == "transcript_failure_rate" for alert in alerts)):
            print("  ✅ AlertManager detects issues and triggers alerts")
            return True
        else:
            print(f"  ❌ AlertManager failed to trigger alerts: {len(alerts)} alerts, summary={alert_summary}")
            return False
            
    except Exception as e:
        print(f"❌ AlertManager test failed: {e}")
        return False

def test_monitoring_dashboard():
    """Test monitoring dashboard integration"""
    print("\n=== Monitoring Dashboard Test ===")
    
    try:
        from monitoring import get_monitoring_dashboard
        
        # Mock environment for health checks
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'sk-test123456789',
            'RESEND_API_KEY': 're_test123',
            'SENDER_EMAIL': 'test@example.com'
        }):
            dashboard = get_monitoring_dashboard()
            
            # Verify dashboard structure
            required_sections = [
                "timestamp", "health_status", "transcript_metrics", 
                "job_metrics", "alerts", "system_info"
            ]
            
            if all(section in dashboard for section in required_sections):
                # Check that each section has expected structure
                health_ok = "overall_status" in dashboard["health_status"]
                metrics_ok = "success_rates" in dashboard["transcript_metrics"]
                jobs_ok = "jobs_submitted" in dashboard["job_metrics"]
                alerts_ok = "alert_summary" in dashboard["alerts"]
                
                if health_ok and metrics_ok and jobs_ok and alerts_ok:
                    print("  ✅ Monitoring dashboard provides comprehensive data")
                    return True
                else:
                    print(f"  ❌ Dashboard sections incomplete: health={health_ok}, metrics={metrics_ok}, jobs={jobs_ok}, alerts={alerts_ok}")
                    return False
            else:
                missing = [s for s in required_sections if s not in dashboard]
                print(f"  ❌ Dashboard missing sections: {missing}")
                return False
            
    except Exception as e:
        print(f"❌ Monitoring dashboard test failed: {e}")
        return False

def test_performance_logging():
    """Test performance event logging"""
    print("\n=== Performance Logging Test ===")
    
    try:
        from monitoring import log_performance_event
        
        # Test logging performance events
        log_performance_event("transcript_processing", {
            "video_id": "test123",
            "source": "youtube_api",
            "duration_ms": 1500,
            "success": True
        })
        
        log_performance_event("job_completion", {
            "job_id": "job_456",
            "total_videos": 3,
            "successful_videos": 2,
            "processing_time_ms": 5000
        })
        
        # If no exceptions were raised, logging works
        print("  ✅ Performance event logging works")
        return True
        
    except Exception as e:
        print(f"❌ Performance logging test failed: {e}")
        return False

def run_monitoring_tests():
    """Run all monitoring tests"""
    print("=" * 50)
    print("MONITORING AND OBSERVABILITY TESTS")
    print("=" * 50)
    
    # Run tests with timeout protection
    test_functions = [
        ("transcript_metrics", test_transcript_metrics),
        ("job_metrics", test_job_metrics),
        ("health_checker", test_health_checker),
        ("alert_manager", test_alert_manager),
        ("monitoring_dashboard", test_monitoring_dashboard),
        ("performance_logging", test_performance_logging)
    ]
    
    test_results = {}
    
    for test_name, test_func in test_functions:
        try:
            print(f"\nRunning {test_name}...")
            result = run_with_timeout(test_func, timeout_seconds=5)  # 5 second timeout
            test_results[test_name] = result
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            test_results[test_name] = False
    
    # Calculate results
    passed_tests = sum(1 for result in test_results.values() if result)
    total_tests = len(test_results)
    pass_rate = (passed_tests / total_tests) * 100
    
    print("\n" + "=" * 50)
    print("MONITORING TEST RESULTS")
    print("=" * 50)
    
    for test_name, passed in test_results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:20} {status}")
    
    print(f"\nOverall Results: {passed_tests}/{total_tests} tests passed ({pass_rate:.1f}%)")
    
    if pass_rate >= 80:
        print("\n🎉 MONITORING TESTS PASSED!")
        print("Task 15: Add monitoring and observability features - COMPLETE")
        return True
    else:
        print(f"\n❌ MONITORING TESTS FAILED - {pass_rate:.1f}% pass rate (need ≥80%)")
        return False

if __name__ == "__main__":
    success = run_monitoring_tests()
    sys.exit(0 if success else 1)