#!/usr/bin/env python3
"""
Test for enhanced EmailService with fault tolerance and flat item structure
"""
import os
import sys
import logging

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_email_service_initialization():
    """Test EmailService initialization and configuration"""
    print("=== EmailService Initialization Test ===")
    
    # Test without required environment variables
    original_resend_key = os.environ.get("RESEND_API_KEY")
    original_sender_email = os.environ.get("SENDER_EMAIL")
    
    # Remove required env vars
    if "RESEND_API_KEY" in os.environ:
        del os.environ["RESEND_API_KEY"]
    if "SENDER_EMAIL" in os.environ:
        del os.environ["SENDER_EMAIL"]
    
    try:
        from email_service import EmailService
        service = EmailService()
        print("❌ Should have failed without RESEND_API_KEY")
        return False
    except ValueError as e:
        if "RESEND_API_KEY" in str(e):
            print("✅ Properly validates RESEND_API_KEY requirement")
        else:
            print(f"❌ Wrong error message: {e}")
            return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    finally:
        # Restore original values
        if original_resend_key:
            os.environ["RESEND_API_KEY"] = original_resend_key
        if original_sender_email:
            os.environ["SENDER_EMAIL"] = original_sender_email
    
    return True

def test_flat_item_structure():
    """Test that EmailService handles flat item structure correctly"""
    print("\n=== Flat Item Structure Test ===")
    
    # Set required env vars for testing
    os.environ["RESEND_API_KEY"] = "test-key-for-validation"
    os.environ["SENDER_EMAIL"] = "test@example.com"
    
    try:
        from email_service import EmailService
        
        service = EmailService()
        
        # Test flat item structure
        test_items = [
            {
                "title": "Test Video 1",
                "thumbnail_url": "https://example.com/thumb1.jpg",
                "video_url": "https://www.youtube.com/watch?v=test1",
                "summary": "This is a test summary for video 1."
            },
            {
                "title": "Test Video 2", 
                "thumbnail_url": "",
                "video_url": "https://www.youtube.com/watch?v=test2",
                "summary": "This is a test summary for video 2."
            }
        ]
        
        # Test HTML generation (won't actually send email)
        html_content = service._generate_email_html(test_items)
        
        # Check that HTML contains expected elements
        if "Test Video 1" in html_content and "Test Video 2" in html_content:
            print("✅ Flat item structure processed correctly")
        else:
            print("❌ Flat item structure not processed correctly")
            return False
        
        # Check that missing thumbnail is handled
        if "No Image" in html_content:
            print("✅ Missing thumbnail handled correctly")
        else:
            print("❌ Missing thumbnail not handled correctly")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Flat item structure test failed: {e}")
        return False

def test_fault_tolerance():
    """Test fault tolerance with malformed data"""
    print("\n=== Fault Tolerance Test ===")
    
    os.environ["RESEND_API_KEY"] = "test-key-for-validation"
    os.environ["SENDER_EMAIL"] = "test@example.com"
    
    try:
        from email_service import EmailService
        
        service = EmailService()
        
        # Test with malformed items
        malformed_items = [
            None,  # None item
            {},    # Empty dict
            {"title": None, "summary": None},  # None values
            {"title": 123, "summary": 456},    # Non-string values
            {"wrong_key": "value"},            # Missing required keys
            {
                "title": "Good Video",
                "thumbnail_url": "https://example.com/thumb.jpg", 
                "video_url": "https://www.youtube.com/watch?v=good",
                "summary": "This should work fine."
            }
        ]
        
        # Should not crash on malformed data
        try:
            html_content = service._generate_email_html(malformed_items)
            print("✅ Malformed data handled without crashing")
            
            # Should still contain the good video
            if "Good Video" in html_content:
                print("✅ Valid items still processed correctly")
            else:
                print("❌ Valid items not processed correctly")
                return False
                
        except Exception as e:
            print(f"❌ Crashed on malformed data: {e}")
            return False
        
        # Test empty items list
        try:
            empty_html = service._generate_email_html([])
            if "No summaries were generated" in empty_html:
                print("✅ Empty items list handled correctly")
            else:
                print("❌ Empty items list not handled correctly")
                return False
        except Exception as e:
            print(f"❌ Crashed on empty items: {e}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Fault tolerance test failed: {e}")
        return False

def test_safe_helper_methods():
    """Test safe helper methods"""
    print("\n=== Safe Helper Methods Test ===")
    
    os.environ["RESEND_API_KEY"] = "test-key-for-validation"
    os.environ["SENDER_EMAIL"] = "test@example.com"
    
    try:
        from email_service import EmailService
        
        service = EmailService()
        
        # Test _safe_get method
        test_cases = [
            ({"key": "value"}, "key", "default", "value"),
            ({"key": None}, "key", "default", "default"),
            ({}, "missing", "default", "default"),
            (None, "key", "default", "default"),
            ({"key": 123}, "key", "default", "123"),
        ]
        
        for item, key, default, expected in test_cases:
            result = service._safe_get(item, key, default)
            if result == expected:
                print(f"✅ _safe_get({item}, '{key}', '{default}') -> '{result}'")
            else:
                print(f"❌ _safe_get({item}, '{key}', '{default}') -> '{result}' (expected '{expected}')")
                return False
        
        # Test _escape_html method
        html_test_cases = [
            ("Normal text", "Normal text"),
            ("<script>alert('xss')</script>", "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"),
            ("", ""),
            (None, ""),
            (123, "123"),
        ]
        
        for input_text, expected in html_test_cases:
            result = service._escape_html(input_text)
            if result == expected:
                print(f"✅ _escape_html('{input_text}') -> '{result}'")
            else:
                print(f"❌ _escape_html('{input_text}') -> '{result}' (expected '{expected}')")
                return False
        
        # Test _build_thumbnail_html method
        thumbnail_html = service._build_thumbnail_html("https://example.com/thumb.jpg")
        if "img src=" in thumbnail_html:
            print("✅ _build_thumbnail_html with URL works")
        else:
            print("❌ _build_thumbnail_html with URL failed")
            return False
        
        placeholder_html = service._build_thumbnail_html("")
        if "No Image" in placeholder_html:
            print("✅ _build_thumbnail_html with empty URL works")
        else:
            print("❌ _build_thumbnail_html with empty URL failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Safe helper methods test failed: {e}")
        return False

def test_single_attempt_delivery():
    """Test single attempt email delivery behavior"""
    print("\n=== Single Attempt Delivery Test ===")
    
    os.environ["RESEND_API_KEY"] = "test-key-for-validation"
    os.environ["SENDER_EMAIL"] = "test@example.com"
    
    try:
        from email_service import EmailService
        import inspect
        
        service = EmailService()
        
        # Check method signature
        sig = inspect.signature(service.send_digest_email)
        
        # Should return bool
        if sig.return_annotation != bool:
            print("❌ send_digest_email should return bool")
            return False
        
        print("✅ send_digest_email returns bool for single attempt")
        
        # Test input validation
        result = service.send_digest_email("", [])
        if result == False:
            print("✅ Invalid email address handled correctly")
        else:
            print("❌ Invalid email address not handled correctly")
            return False
        
        result = service.send_digest_email("test@example.com", "not a list")
        if result == False:
            print("✅ Invalid items type handled correctly")
        else:
            print("❌ Invalid items type not handled correctly")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Single attempt delivery test failed: {e}")
        return False

if __name__ == "__main__":
    print("=== Enhanced EmailService Test ===")
    
    init_success = test_email_service_initialization()
    flat_success = test_flat_item_structure()
    fault_success = test_fault_tolerance()
    helper_success = test_safe_helper_methods()
    delivery_success = test_single_attempt_delivery()
    
    all_tests = [init_success, flat_success, fault_success, helper_success, delivery_success]
    
    if all(all_tests):
        print("\n✅ All EmailService enhancement tests passed!")
        print("Task 8: Update EmailService for consolidated digest delivery with fault tolerance - COMPLETE")
        sys.exit(0)
    else:
        print(f"\n❌ Some EmailService tests failed! Results: {all_tests}")
        sys.exit(1)