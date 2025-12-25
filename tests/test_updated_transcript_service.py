#!/usr/bin/env python3
"""
Test the updated transcript service with new API
"""
import logging
import os

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_transcript_service_import():
    """Test that the updated transcript service imports correctly"""
    try:
        from transcript_service import TranscriptService
        print("✅ TranscriptService imports successfully")
        
        # Test initialization
        service = TranscriptService()
        print("✅ TranscriptService initializes successfully")
        
        # Test API compatibility detection
        from youtube_transcript_api_compat import check_api_migration_status
        status = check_api_migration_status()
        print(f"✅ API Status: {status['api_version']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Import/initialization failed: {e}")
        return False

def test_get_captions_method():
    """Test that the get_captions_via_api method exists and is callable"""
    try:
        from transcript_service import TranscriptService
        
        service = TranscriptService()
        
        # Check that the method exists
        if hasattr(service, 'get_captions_via_api'):
            print("✅ get_captions_via_api method exists")
            
            # Check method signature (don't actually call it to avoid network requests)
            import inspect
            sig = inspect.signature(service.get_captions_via_api)
            print(f"✅ Method signature: {sig}")
            
            return True
        else:
            print("❌ get_captions_via_api method not found")
            return False
            
    except Exception as e:
        print(f"❌ Method test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=== Testing Updated Transcript Service ===")
    
    tests = [
        ("Import and Initialization", test_transcript_service_import),
        ("Method Availability", test_get_captions_method),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            print(f"❌ {test_name} CRASHED: {e}")
    
    print(f"\n=== Results: {passed}/{total} tests passed ===")
    
    if passed == total:
        print("🎉 All tests passed! The transcript service has been successfully updated.")
        return True
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)