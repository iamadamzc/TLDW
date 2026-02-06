"""
Test urllib3 compatibility fix for method_whitelist -> allowed_methods
"""
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_http_session():
    """Test that make_http_session() works with the fix"""
    try:
        # Import after fix is applied
        from transcript_service import make_http_session
        
        print("\n" + "="*60)
        print("Testing urllib3 compatibility fix")
        print("="*60 + "\n")
        
        # Try to create session (this is where the error would occur)
        session = make_http_session()
        
        print("✅ SUCCESS: make_http_session() created successfully")
        print(f"   Session type: {type(session)}")
        print(f"   Has adapters: {len(session.adapters)} adapter(s)")
        
        # Verify retry strategy is configured
        adapter = session.get_adapter('https://www.youtube.com')
        if hasattr(adapter, 'max_retries'):
            print(f"✅ Retry strategy configured: {adapter.max_retries}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_http_session()
    sys.exit(0 if success else 1)
