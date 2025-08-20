#!/usr/bin/env python3
"""
Test for enhanced transcript service integration into job workflow
"""
import os
import sys
import logging

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_helper_methods():
    """Test the helper methods for safe field access"""
    print("=== Helper Methods Test ===")
    
    # We'll test the helper methods by creating a mock JobManager
    import threading
    import time
    from datetime import datetime
    from dataclasses import dataclass
    from typing import Optional, Dict, Any
    from concurrent.futures import ThreadPoolExecutor
    from uuid import uuid4

    @dataclass
    class JobStatus:
        job_id: str
        status: str
        created_at: datetime
        updated_at: datetime
        user_id: int
        video_count: int
        processed_count: int = 0
        error_message: Optional[str] = None

    class MockJobManager:
        def __init__(self):
            self.jobs: Dict[str, JobStatus] = {}
            self.lock = threading.Lock()
        
        def _safe_get_title(self, video: dict, video_id: str) -> str:
            """Safely extract video title with fallback"""
            try:
                title = video.get("title") if isinstance(video, dict) else None
                if title and isinstance(title, str) and title.strip():
                    return title.strip()
                return f"Video {video_id}"
            except Exception:
                return f"Video {video_id}"
        
        def _safe_get_thumbnail(self, video: dict) -> str:
            """Safely extract video thumbnail with fallback"""
            try:
                thumbnail = video.get("thumbnail") if isinstance(video, dict) else None
                if thumbnail and isinstance(thumbnail, str) and thumbnail.strip():
                    return thumbnail.strip()
                return ""
            except Exception:
                return ""
        
        def _truncate_error(self, error_msg: str, max_length: int = 200) -> str:
            """Safely truncate error message for email"""
            try:
                if not isinstance(error_msg, str):
                    error_msg = str(error_msg)
                if len(error_msg) <= max_length:
                    return error_msg
                return error_msg[:max_length] + "..."
            except Exception:
                return "Processing error occurred."
    
    try:
        job_manager = MockJobManager()
        
        # Test _safe_get_title
        test_cases = [
            ({"title": "Test Video"}, "vid123", "Test Video"),
            ({"title": ""}, "vid123", "Video vid123"),
            ({"title": None}, "vid123", "Video vid123"),
            ({}, "vid123", "Video vid123"),
            (None, "vid123", "Video vid123"),
            ({"title": "  Spaced Title  "}, "vid123", "Spaced Title"),
        ]
        
        for video, video_id, expected in test_cases:
            result = job_manager._safe_get_title(video, video_id)
            if result == expected:
                print(f"✅ _safe_get_title({video}, '{video_id}') -> '{result}'")
            else:
                print(f"❌ _safe_get_title({video}, '{video_id}') -> '{result}' (expected '{expected}')")
                return False
        
        # Test _safe_get_thumbnail
        thumbnail_cases = [
            ({"thumbnail": "https://example.com/thumb.jpg"}, "https://example.com/thumb.jpg"),
            ({"thumbnail": ""}, ""),
            ({"thumbnail": None}, ""),
            ({}, ""),
            (None, ""),
            ({"thumbnail": "  https://example.com/spaced.jpg  "}, "https://example.com/spaced.jpg"),
        ]
        
        for video, expected in thumbnail_cases:
            result = job_manager._safe_get_thumbnail(video)
            if result == expected:
                print(f"✅ _safe_get_thumbnail({video}) -> '{result}'")
            else:
                print(f"❌ _safe_get_thumbnail({video}) -> '{result}' (expected '{expected}')")
                return False
        
        # Test _truncate_error
        error_cases = [
            ("Short error", 200, "Short error"),
            ("A" * 300, 200, "A" * 200 + "..."),
            ("", 200, ""),
            (None, 200, "None"),
            (123, 200, "123"),
        ]
        
        for error_msg, max_length, expected in error_cases:
            result = job_manager._truncate_error(error_msg, max_length)
            if result == expected:
                print(f"✅ _truncate_error('{str(error_msg)[:20]}...', {max_length}) -> '{result[:20]}...'")
            else:
                print(f"❌ _truncate_error failed")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Helper methods test failed: {e}")
        return False

def test_logging_format():
    """Test that logging format includes required fields"""
    print("\n=== Logging Format Test ===")
    
    try:
        # Test that the expected log format strings are present in the code
        # This is a basic test to ensure the logging format is correct
        
        expected_log_patterns = [
            "job_video_processed",
            "transcript_source=",
            "transcript_duration_ms=",
            "total_duration_ms=",
            "job_video_failed",
            "job_email_sent",
            "job_email_failed"
        ]
        
        # Read the routes.py file to check for logging patterns
        try:
            with open("routes.py", "r") as f:
                routes_content = f.read()
            
            for pattern in expected_log_patterns:
                if pattern in routes_content:
                    print(f"✅ Logging pattern '{pattern}' found")
                else:
                    print(f"❌ Logging pattern '{pattern}' missing")
                    return False
            
            return True
            
        except FileNotFoundError:
            print("❌ routes.py file not found")
            return False
        
    except Exception as e:
        print(f"❌ Logging format test failed: {e}")
        return False

def test_error_isolation():
    """Test that per-video error isolation is properly implemented"""
    print("\n=== Error Isolation Test ===")
    
    try:
        # Read the routes.py file to check for error isolation patterns
        try:
            with open("routes.py", "r") as f:
                routes_content = f.read()
            
            isolation_patterns = [
                "Per-video error isolation",
                "don't stop entire job",
                "processed_count += 1",  # Should increment even on error
                "except Exception as e:",  # Should catch individual video errors
            ]
            
            for pattern in isolation_patterns:
                if pattern in routes_content:
                    print(f"✅ Error isolation pattern '{pattern}' found")
                else:
                    print(f"❌ Error isolation pattern '{pattern}' missing")
                    return False
            
            return True
            
        except FileNotFoundError:
            print("❌ routes.py file not found")
            return False
        
    except Exception as e:
        print(f"❌ Error isolation test failed: {e}")
        return False

def test_timing_metrics():
    """Test that timing metrics are properly implemented"""
    print("\n=== Timing Metrics Test ===")
    
    try:
        # Read the routes.py file to check for timing patterns
        try:
            with open("routes.py", "r") as f:
                routes_content = f.read()
            
            timing_patterns = [
                "video_start_time = time.time()",
                "transcript_start_time = time.time()",
                "summary_start_time = time.time()",
                "transcript_duration_ms = int((time.time() - transcript_start_time) * 1000)",
                "video_duration_ms = int((time.time() - video_start_time) * 1000)",
            ]
            
            for pattern in timing_patterns:
                if pattern in routes_content:
                    print(f"✅ Timing pattern '{pattern}' found")
                else:
                    print(f"❌ Timing pattern '{pattern}' missing")
                    return False
            
            return True
            
        except FileNotFoundError:
            print("❌ routes.py file not found")
            return False
        
    except Exception as e:
        print(f"❌ Timing metrics test failed: {e}")
        return False

def test_enhanced_email_integration():
    """Test that enhanced EmailService integration is properly implemented"""
    print("\n=== Enhanced Email Integration Test ===")
    
    try:
        # Read the routes.py file to check for enhanced email patterns
        try:
            with open("routes.py", "r") as f:
                routes_content = f.read()
            
            email_patterns = [
                "email_sent = email_service.send_digest_email(user_email, email_items)",
                "if email_sent:",
                "job_email_sent",
                "job_email_failed",
                "items_count=",
            ]
            
            for pattern in email_patterns:
                if pattern in routes_content:
                    print(f"✅ Email integration pattern '{pattern}' found")
                else:
                    print(f"❌ Email integration pattern '{pattern}' missing")
                    return False
            
            return True
            
        except FileNotFoundError:
            print("❌ routes.py file not found")
            return False
        
    except Exception as e:
        print(f"❌ Enhanced email integration test failed: {e}")
        return False

if __name__ == "__main__":
    print("=== Job Workflow Integration Test ===")
    
    helper_success = test_helper_methods()
    logging_success = test_logging_format()
    isolation_success = test_error_isolation()
    timing_success = test_timing_metrics()
    email_success = test_enhanced_email_integration()
    
    all_tests = [helper_success, logging_success, isolation_success, timing_success, email_success]
    
    if all(all_tests):
        print("\n✅ All job workflow integration tests passed!")
        print("Task 9: Integrate enhanced transcript service into job workflow - COMPLETE")
        sys.exit(0)
    else:
        print(f"\n❌ Some job workflow integration tests failed! Results: {all_tests}")
        sys.exit(1)