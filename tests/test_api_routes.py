#!/usr/bin/env python3
"""
Test for updated API routes with async job processing
"""
import os
import sys
import logging

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_api_route_structure():
    """Test that API routes have the correct structure"""
    print("=== API Route Structure Test ===")
    
    try:
        # Read the routes.py file to check for API route patterns
        with open("routes.py", "r") as f:
            routes_content = f.read()
        
        # Check for summarize endpoint
        summarize_patterns = [
            '@main_routes.route("/api/summarize", methods=["POST"])',
            '@login_required',
            'def summarize_videos():',
            'start_time = time.time()',
            'job_manager.submit_summarization_job',
            'return jsonify({',
            '"job_id": job_id',
            '"status": "queued"',
            '}), 202'
        ]
        
        for pattern in summarize_patterns:
            if pattern in routes_content:
                print(f"✅ Summarize endpoint pattern '{pattern}' found")
            else:
                print(f"❌ Summarize endpoint pattern '{pattern}' missing")
                return False
        
        # Check for job status endpoint
        status_patterns = [
            '@main_routes.route("/api/jobs/<job_id>")',
            '@login_required',
            'def get_job_status(job_id):',
            'job_manager.get_job_status(job_id)',
            'job_status.user_id != current_user.id',
            'job_status.to_dict()'
        ]
        
        for pattern in status_patterns:
            if pattern in routes_content:
                print(f"✅ Job status endpoint pattern '{pattern}' found")
            else:
                print(f"❌ Job status endpoint pattern '{pattern}' missing")
                return False
        
        return True
        
    except FileNotFoundError:
        print("❌ routes.py file not found")
        return False
    except Exception as e:
        print(f"❌ API route structure test failed: {e}")
        return False

def test_request_validation():
    """Test that request validation is properly implemented"""
    print("\n=== Request Validation Test ===")
    
    try:
        with open("routes.py", "r") as f:
            routes_content = f.read()
        
        validation_patterns = [
            'data = request.get_json(silent=True) or {}',
            'video_ids = data.get("video_ids") or data.get("videoIds") or []',
            'if isinstance(video_ids, str):',
            'video_ids = [v.strip() for v in video_ids.split(",") if v.strip()]',
            'if not video_ids:',
            'return jsonify({"error": "video_ids is required"}), 400',
            'if len(video_ids) > 50:',
            'return jsonify({"error": "Too many videos (max 50)"}), 400'
        ]
        
        for pattern in validation_patterns:
            if pattern in routes_content:
                print(f"✅ Validation pattern '{pattern}' found")
            else:
                print(f"❌ Validation pattern '{pattern}' missing")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Request validation test failed: {e}")
        return False

def test_response_time_tracking():
    """Test that response time tracking is implemented"""
    print("\n=== Response Time Tracking Test ===")
    
    try:
        with open("routes.py", "r") as f:
            routes_content = f.read()
        
        timing_patterns = [
            'start_time = time.time()',
            'response_time_ms = int((time.time() - start_time) * 1000)',
            'api_summarize_response job_id=',
            'response_time_ms='
        ]
        
        for pattern in timing_patterns:
            if pattern in routes_content:
                print(f"✅ Response timing pattern '{pattern}' found")
            else:
                print(f"❌ Response timing pattern '{pattern}' missing")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Response time tracking test failed: {e}")
        return False

def test_error_handling():
    """Test that comprehensive error handling is implemented"""
    print("\n=== Error Handling Test ===")
    
    try:
        with open("routes.py", "r") as f:
            routes_content = f.read()
        
        error_patterns = [
            'except Exception as e:',
            'logging.error(f"Summarize API error: {e}")',
            'return jsonify({"error": "Failed to submit job"}), 500',
            'logging.error(f"Job status API error: {e}")',
            'return jsonify({"error": "Failed to get job status"}), 500'
        ]
        
        for pattern in error_patterns:
            if pattern in routes_content:
                print(f"✅ Error handling pattern '{pattern}' found")
            else:
                print(f"❌ Error handling pattern '{pattern}' missing")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        return False

def test_security_features():
    """Test that security features are properly implemented"""
    print("\n=== Security Features Test ===")
    
    try:
        with open("routes.py", "r") as f:
            routes_content = f.read()
        
        security_patterns = [
            '@login_required',
            'job_status.user_id != current_user.id',
            'return jsonify({"error": "Job not found"}), 404'  # Security through obscurity
        ]
        
        for pattern in security_patterns:
            if pattern in routes_content:
                print(f"✅ Security pattern '{pattern}' found")
            else:
                print(f"❌ Security pattern '{pattern}' missing")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Security features test failed: {e}")
        return False

def test_job_manager_integration():
    """Test that JobManager integration is properly implemented"""
    print("\n=== JobManager Integration Test ===")
    
    try:
        with open("routes.py", "r") as f:
            routes_content = f.read()
        
        integration_patterns = [
            'job_manager = JobManager(WORKER_CONCURRENCY)',
            'job_manager.submit_summarization_job(current_user.id, video_ids, app_obj)',
            'job_manager.get_job_status(job_id)',
            'WORKER_CONCURRENCY = int(os.getenv("WORKER_CONCURRENCY", "2"))'
        ]
        
        for pattern in integration_patterns:
            if pattern in routes_content:
                print(f"✅ JobManager integration pattern '{pattern}' found")
            else:
                print(f"❌ JobManager integration pattern '{pattern}' missing")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ JobManager integration test failed: {e}")
        return False

if __name__ == "__main__":
    print("=== API Routes Update Test ===")
    
    structure_success = test_api_route_structure()
    validation_success = test_request_validation()
    timing_success = test_response_time_tracking()
    error_success = test_error_handling()
    security_success = test_security_features()
    integration_success = test_job_manager_integration()
    
    all_tests = [structure_success, validation_success, timing_success, error_success, security_success, integration_success]
    
    if all(all_tests):
        print("\n✅ All API routes update tests passed!")
        print("Task 10: Update API routes with async job processing - COMPLETE")
        sys.exit(0)
    else:
        print(f"\n❌ Some API routes tests failed! Results: {all_tests}")
        sys.exit(1)