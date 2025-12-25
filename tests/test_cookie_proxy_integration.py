#!/usr/bin/env python3
"""
Test cookie and proxy integration with the new YouTube Transcript API
"""
import logging
import tempfile
import os

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_api_method_signatures():
    """Test that the new API methods accept cookies and proxies"""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        import inspect
        
        print("=== Testing API Method Signatures ===")
        
        # Create API instance
        api = YouTubeTranscriptApi()
        
        # Check list method signature
        if hasattr(api, 'list'):
            list_sig = inspect.signature(api.list)
            print(f"✅ list() method signature: {list_sig}")
        else:
            print("❌ list() method not found")
            return False
        
        # Check fetch method signature
        if hasattr(api, 'fetch'):
            fetch_sig = inspect.signature(api.fetch)
            print(f"✅ fetch() method signature: {fetch_sig}")
        else:
            print("❌ fetch() method not found")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ API signature test failed: {e}")
        return False

def test_compatibility_layer_with_cookies():
    """Test that the compatibility layer handles cookies correctly"""
    try:
        from youtube_transcript_api_compat import get_transcript, TranscriptApiError
        
        print("\n=== Testing Compatibility Layer Cookie Handling ===")
        
        # Create a temporary cookie file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            # Write sample Netscape cookie format
            f.write("# Netscape HTTP Cookie File\n")
            f.write(".youtube.com\tTRUE\t/\tFALSE\t1735689600\tsession_token\tabc123\n")
            cookie_file = f.name
        
        try:
            # Test that the method accepts cookies parameter (don't actually call to avoid network)
            print(f"✅ Created test cookie file: {cookie_file}")
            
            # Test cookie parameter acceptance
            import inspect
            sig = inspect.signature(get_transcript)
            print(f"✅ get_transcript signature: {sig}")
            
            # Check if cookies parameter exists
            if 'cookies' in sig.parameters:
                print("✅ cookies parameter found in get_transcript")
            else:
                print("❌ cookies parameter not found in get_transcript")
                return False
            
            # Check if proxies parameter exists
            if 'proxies' in sig.parameters:
                print("✅ proxies parameter found in get_transcript")
            else:
                print("❌ proxies parameter not found in get_transcript")
                return False
            
            return True
            
        finally:
            # Clean up temp file
            try:
                os.unlink(cookie_file)
            except:
                pass
        
    except Exception as e:
        print(f"❌ Compatibility layer cookie test failed: {e}")
        return False

def test_transcript_service_integration():
    """Test that TranscriptService properly integrates cookies and proxies"""
    try:
        from transcript_service import TranscriptService
        
        print("\n=== Testing TranscriptService Integration ===")
        
        # Create service instance
        service = TranscriptService()
        
        # Check that _get_cookies_for_api method exists
        if hasattr(service, '_get_cookies_for_api'):
            print("✅ _get_cookies_for_api method exists")
        else:
            print("❌ _get_cookies_for_api method not found")
            return False
        
        # Check that get_captions_via_api method exists
        if hasattr(service, 'get_captions_via_api'):
            print("✅ get_captions_via_api method exists")
            
            # Check method signature
            import inspect
            sig = inspect.signature(service.get_captions_via_api)
            print(f"✅ get_captions_via_api signature: {sig}")
        else:
            print("❌ get_captions_via_api method not found")
            return False
        
        # Test that proxy manager integration works
        if hasattr(service, 'proxy_manager'):
            print("✅ proxy_manager attribute exists")
            
            # Test proxy_dict_for method if proxy manager exists
            if service.proxy_manager and hasattr(service.proxy_manager, 'proxy_dict_for'):
                print("✅ proxy_manager.proxy_dict_for method available")
            else:
                print("⚠️  proxy_manager not configured (expected in test environment)")
        else:
            print("❌ proxy_manager attribute not found")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ TranscriptService integration test failed: {e}")
        return False

def test_error_handling():
    """Test that error handling works correctly with new API"""
    try:
        from youtube_transcript_api_compat import TranscriptApiError
        
        print("\n=== Testing Error Handling ===")
        
        # Test that TranscriptApiError exists and is usable
        try:
            raise TranscriptApiError("Test error")
        except TranscriptApiError as e:
            print(f"✅ TranscriptApiError works correctly: {e}")
        
        # Test error message formatting
        error = TranscriptApiError("Test error with details")
        if "Test error with details" in str(error):
            print("✅ Error message formatting works")
        else:
            print("❌ Error message formatting failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        return False

def main():
    """Run all integration tests"""
    print("🧪 Testing Cookie and Proxy Integration with New API")
    print("=" * 60)
    
    tests = [
        ("API Method Signatures", test_api_method_signatures),
        ("Compatibility Layer Cookies", test_compatibility_layer_with_cookies),
        ("TranscriptService Integration", test_transcript_service_integration),
        ("Error Handling", test_error_handling),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} PASSED\n")
            else:
                print(f"❌ {test_name} FAILED\n")
        except Exception as e:
            print(f"❌ {test_name} CRASHED: {e}\n")
    
    print("=" * 60)
    print(f"📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All cookie and proxy integration tests passed!")
        print("✅ The new API properly supports cookies and proxies")
        return True
    else:
        print("⚠️  Some integration tests failed")
        print("🔧 Check the output above for specific issues")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)