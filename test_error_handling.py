#!/usr/bin/env python3
"""
Test for comprehensive error handling and logging system
"""
import os
import sys
import logging
import time

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_structured_logger():
    """Test StructuredLogger functionality"""
    print("=== StructuredLogger Test ===")
    
    try:
        from error_handler import StructuredLogger
        
        # Create logger
        logger = StructuredLogger("test")
        
        # Test context setting
        logger.set_context(job_id="test-123", user_id=1)
        
        # Test logging with context (we can't easily test the output, but we can test it doesn't crash)
        logger.info("Test message", extra_field="value")
        logger.warning("Test warning", error_count=5)
        logger.error("Test error", error_type="TestError")
        
        # Test context clearing
        logger.clear_context()
        logger.info("Message without context")
        
        print("✅ StructuredLogger works correctly")
        return True
        
    except Exception as e:
        print(f"❌ StructuredLogger test failed: {e}")
        return False

def test_error_handler():
    """Test ErrorHandler functionality"""
    print("\n=== ErrorHandler Test ===")
    
    try:
        from error_handler import ErrorHandler
        
        handler = ErrorHandler()
        
        # Test transcript error handling
        test_error = Exception("Test transcript error")
        result = handler.handle_transcript_error("vid123", "yt_api", test_error, 1500)
        
        if isinstance(result, str) and "unavailable" in result.lower():
            print("✅ Transcript error handling works")
        else:
            print(f"❌ Transcript error handling failed: {result}")
            return False
        
        # Test summarization error handling
        result = handler.handle_summarization_error("vid123", test_error, 1000)
        
        if isinstance(result, str) and "unavailable" in result.lower():
            print("✅ Summarization error handling works")
        else:
            print(f"❌ Summarization error handling failed: {result}")
            return False
        
        # Test email error handling
        result = handler.handle_email_error("test@example.com", test_error, 5)
        
        if result == False:
            print("✅ Email error handling works")
        else:
            print(f"❌ Email error handling failed: {result}")
            return False
        
        # Test job error handling (should not crash)
        handler.handle_job_error("job123", test_error, 10, 5)
        print("✅ Job error handling works")
        
        # Test API error handling
        response, status_code = handler.handle_api_error("test_endpoint", test_error, 1)
        
        if isinstance(response, dict) and isinstance(status_code, int):
            print("✅ API error handling works")
        else:
            print(f"❌ API error handling failed: {response}, {status_code}")
            return False
        
        # Test error statistics
        stats = handler.get_error_stats()
        
        if isinstance(stats, dict) and "error_counts" in stats:
            print("✅ Error statistics work")
        else:
            print(f"❌ Error statistics failed: {stats}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ ErrorHandler test failed: {e}")
        return False

def test_error_categorization():
    """Test error categorization and appropriate responses"""
    print("\n=== Error Categorization Test ===")
    
    try:
        from error_handler import ErrorHandler
        
        handler = ErrorHandler()
        
        # Test timeout error categorization
        timeout_error = Exception("Request timed out after 30 seconds")
        result = handler.handle_transcript_error("vid123", "timedtext", timeout_error)
        
        if "timed out" in result.lower():
            print("✅ Timeout error categorized correctly")
        else:
            print(f"❌ Timeout error not categorized: {result}")
            return False
        
        # Test auth error categorization
        auth_error = Exception("Authentication failed")
        result = handler.handle_transcript_error("vid123", "yt_api", auth_error)
        
        if "access denied" in result.lower():
            print("✅ Auth error categorized correctly")
        else:
            print(f"❌ Auth error not categorized: {result}")
            return False
        
        # Test not found error categorization
        not_found_error = Exception("Video not found")
        result = handler.handle_transcript_error("vid123", "youtubei", not_found_error)
        
        if "not found" in result.lower():
            print("✅ Not found error categorized correctly")
        else:
            print(f"❌ Not found error not categorized: {result}")
            return False
        
        # Test API error HTTP status codes
        rate_limit_error = Exception("Rate limit exceeded")
        response, status_code = handler.handle_api_error("test", rate_limit_error)
        
        if status_code == 429:
            print("✅ Rate limit error returns correct HTTP status")
        else:
            print(f"❌ Rate limit error wrong status: {status_code}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error categorization test failed: {e}")
        return False

def test_performance_logging():
    """Test performance logging functionality"""
    print("\n=== Performance Logging Test ===")
    
    try:
        from error_handler import log_performance_metrics, log_resource_cleanup
        
        # Test performance metrics logging (should not crash)
        log_performance_metrics(
            operation="test_operation",
            duration_ms=1500,
            video_id="vid123",
            success=True
        )
        print("✅ Performance metrics logging works")
        
        # Test resource cleanup logging (should not crash)
        log_resource_cleanup(
            resource_type="browser",
            resource_id="browser-123",
            success=True,
            cleanup_duration_ms=500
        )
        print("✅ Resource cleanup logging works")
        
        return True
        
    except Exception as e:
        print(f"❌ Performance logging test failed: {e}")
        return False

def test_global_error_functions():
    """Test global error handling functions"""
    print("\n=== Global Error Functions Test ===")
    
    try:
        from error_handler import (
            handle_transcript_error, handle_summarization_error, 
            handle_email_error, handle_job_error, handle_api_error, get_error_stats
        )
        
        test_error = Exception("Global test error")
        
        # Test global transcript error function
        result = handle_transcript_error("vid123", "test_method", test_error, 1000)
        if isinstance(result, str):
            print("✅ Global transcript error function works")
        else:
            print(f"❌ Global transcript error function failed: {result}")
            return False
        
        # Test global summarization error function
        result = handle_summarization_error("vid123", test_error, 500)
        if isinstance(result, str):
            print("✅ Global summarization error function works")
        else:
            print(f"❌ Global summarization error function failed: {result}")
            return False
        
        # Test global email error function
        result = handle_email_error("test@example.com", test_error, 3)
        if isinstance(result, bool):
            print("✅ Global email error function works")
        else:
            print(f"❌ Global email error function failed: {result}")
            return False
        
        # Test global job error function (should not crash)
        handle_job_error("job123", test_error, 5, 3)
        print("✅ Global job error function works")
        
        # Test global API error function
        response, status_code = handle_api_error("test", test_error, 1)
        if isinstance(response, dict) and isinstance(status_code, int):
            print("✅ Global API error function works")
        else:
            print(f"❌ Global API error function failed: {response}, {status_code}")
            return False
        
        # Test global error stats function
        stats = get_error_stats()
        if isinstance(stats, dict):
            print("✅ Global error stats function works")
        else:
            print(f"❌ Global error stats function failed: {stats}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Global error functions test failed: {e}")
        return False

def test_logging_setup():
    """Test logging setup functionality"""
    print("\n=== Logging Setup Test ===")
    
    try:
        from error_handler import setup_logging
        
        # Test logging setup (should not crash)
        logger = setup_logging("INFO")
        
        if logger:
            print("✅ Logging setup works")
        else:
            print("❌ Logging setup failed")
            return False
        
        # Test with custom format
        logger = setup_logging("DEBUG", "%(levelname)s - %(message)s")
        
        if logger:
            print("✅ Custom logging setup works")
        else:
            print("❌ Custom logging setup failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Logging setup test failed: {e}")
        return False

def test_error_decorator():
    """Test error handling decorator"""
    print("\n=== Error Decorator Test ===")
    
    try:
        from error_handler import with_error_handling, ErrorHandler
        
        handler = ErrorHandler()
        
        # Test decorator on successful function
        @with_error_handling(handler, "test_operation")
        def successful_function():
            return "success"
        
        result = successful_function()
        if result == "success":
            print("✅ Error decorator works with successful function")
        else:
            print(f"❌ Error decorator failed with successful function: {result}")
            return False
        
        # Test decorator on failing function
        @with_error_handling(handler, "test_operation")
        def failing_function():
            raise Exception("Test error")
        
        try:
            failing_function()
            print("❌ Error decorator should have raised exception")
            return False
        except Exception:
            print("✅ Error decorator works with failing function")
        
        return True
        
    except Exception as e:
        print(f"❌ Error decorator test failed: {e}")
        return False

if __name__ == "__main__":
    print("=== Comprehensive Error Handling Test ===")
    
    logger_success = test_structured_logger()
    handler_success = test_error_handler()
    categorization_success = test_error_categorization()
    performance_success = test_performance_logging()
    global_success = test_global_error_functions()
    logging_success = test_logging_setup()
    decorator_success = test_error_decorator()
    
    all_tests = [
        logger_success, handler_success, categorization_success, 
        performance_success, global_success, logging_success, decorator_success
    ]
    
    if all(all_tests):
        print("\n✅ All error handling tests passed!")
        print("Task 12: Implement comprehensive error handling and logging - COMPLETE")
        sys.exit(0)
    else:
        print(f"\n❌ Some error handling tests failed! Results: {all_tests}")
        sys.exit(1)