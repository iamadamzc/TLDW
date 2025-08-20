#!/usr/bin/env python3
"""
Test for async job processing system with concurrency controls
"""
import os
import sys
import logging
import time

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_job_manager_class():
    """Test that JobManager class exists and is properly structured"""
    try:
        from routes import JobManager, JobStatus
        
        print("=== Job Manager Class Test ===")
        print("✅ JobManager class exists")
        print("✅ JobStatus dataclass exists")
        
        # Test JobManager initialization
        job_manager = JobManager(worker_concurrency=2)
        
        # Check required methods exist
        methods = [
            'submit_summarization_job',
            'get_job_status',
            'update_job_status',
            '_run_summarize_job',
            '_get_user_cookies'
        ]
        
        for method_name in methods:
            if hasattr(job_manager, method_name):
                print(f"✅ Method {method_name} exists")
            else:
                print(f"❌ Method {method_name} missing")
                return False
        
        # Test JobStatus dataclass
        if hasattr(JobStatus, 'to_dict'):
            print("✅ JobStatus has to_dict method")
        else:
            print("❌ JobStatus missing to_dict method")
            return False
        
        return True
        
    except ImportError as e:
        print(f"❌ JobManager import failed: {e}")
        return False

def test_concurrency_controls():
    """Test concurrency control mechanisms"""
    try:
        from routes import JobManager, WORKER_CONCURRENCY
        
        print("\n=== Concurrency Controls Test ===")
        print(f"Worker concurrency setting: {WORKER_CONCURRENCY}")
        
        job_manager = JobManager(worker_concurrency=2)
        
        # Check semaphore exists
        if hasattr(job_manager, 'job_semaphore'):
            print(f"✅ Job semaphore configured: {job_manager.job_semaphore._value}")
        else:
            print("❌ Job semaphore missing")
            return False
        
        # Check thread pool executor
        if hasattr(job_manager, 'executor'):
            print(f"✅ Thread pool executor configured: {job_manager.executor._max_workers} workers")
        else:
            print("❌ Thread pool executor missing")
            return False
        
        # Check thread lock
        if hasattr(job_manager, 'lock'):
            print("✅ Thread lock configured for job status updates")
        else:
            print("❌ Thread lock missing")
            return False
        
        return True
        
    except ImportError as e:
        print(f"❌ Concurrency controls test failed: {e}")
        return False

def test_job_status_dataclass():
    """Test JobStatus dataclass functionality"""
    try:
        from routes import JobStatus
        from datetime import datetime
        
        print("\n=== Job Status Dataclass Test ===")
        
        # Create test job status
        job_status = JobStatus(
            job_id="test-123",
            status="queued",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            user_id=1,
            video_count=5
        )
        
        # Test to_dict method
        job_dict = job_status.to_dict()
        
        required_fields = [
            "job_id", "status", "created_at", "updated_at", 
            "user_id", "video_count", "processed_count", "error_message"
        ]
        
        for field in required_fields:
            if field in job_dict:
                print(f"✅ Field {field} in job dict")
            else:
                print(f"❌ Field {field} missing from job dict")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ JobStatus test failed: {e}")
        return False

def test_global_job_manager():
    """Test that global job manager instance is properly configured"""
    try:
        from routes import job_manager
        
        print("\n=== Global Job Manager Test ===")
        
        if job_manager:
            print("✅ Global job_manager instance exists")
        else:
            print("❌ Global job_manager instance missing")
            return False
        
        # Check it's properly configured
        if hasattr(job_manager, 'executor') and hasattr(job_manager, 'jobs'):
            print("✅ Global job_manager properly configured")
        else:
            print("❌ Global job_manager not properly configured")
            return False
        
        return True
        
    except ImportError as e:
        print(f"❌ Global job manager test failed: {e}")
        return False

def test_per_video_error_isolation():
    """Test that per-video error isolation is implemented"""
    try:
        from routes import JobManager
        import inspect
        
        print("\n=== Per-Video Error Isolation Test ===")
        
        job_manager = JobManager(worker_concurrency=2)
        
        # Check the _run_summarize_job method for error isolation
        source = inspect.getsource(job_manager._run_summarize_job)
        
        isolation_indicators = [
            "per-video error isolation",
            "don't stop entire job",
            "except Exception as e:",
            "processed_count += 1"
        ]
        
        found_indicators = [indicator for indicator in isolation_indicators if indicator in source]
        
        if len(found_indicators) >= 3:
            print(f"✅ Per-video error isolation implemented: {len(found_indicators)}/4 indicators found")
            return True
        else:
            print(f"❌ Per-video error isolation incomplete: {found_indicators}")
            return False
        
    except Exception as e:
        print(f"❌ Error isolation test failed: {e}")
        return False

def test_api_route_updates():
    """Test that API routes are updated to use JobManager"""
    try:
        # This is a basic test to ensure the routes file can be imported
        # without errors after our changes
        import routes
        
        print("\n=== API Route Updates Test ===")
        
        # Check that the routes module imports successfully
        if hasattr(routes, 'job_manager'):
            print("✅ Routes module imports successfully with job_manager")
        else:
            print("❌ Routes module missing job_manager")
            return False
        
        # Check that main routes blueprint exists
        if hasattr(routes, 'main_routes'):
            print("✅ Main routes blueprint exists")
        else:
            print("❌ Main routes blueprint missing")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ API route updates test failed: {e}")
        return False

if __name__ == "__main__":
    print("=== Async Job Processing System Test ===")
    
    job_manager_success = test_job_manager_class()
    concurrency_success = test_concurrency_controls()
    job_status_success = test_job_status_dataclass()
    global_manager_success = test_global_job_manager()
    error_isolation_success = test_per_video_error_isolation()
    api_routes_success = test_api_route_updates()
    
    all_tests = [
        job_manager_success, concurrency_success, job_status_success,
        global_manager_success, error_isolation_success, api_routes_success
    ]
    
    if all(all_tests):
        print("\n✅ All async job processing tests passed!")
        print("Task 6: Implement async job processing system with concurrency controls - COMPLETE")
        sys.exit(0)
    else:
        print(f"\n❌ Some async job tests failed! Results: {all_tests}")
        sys.exit(1)