#!/usr/bin/env python3
"""
Test script for Playwright transcript pipeline integration.
"""

import os
import sys
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_playwright_configuration():
    """Test Playwright configuration and dependencies."""
    print("🧪 Testing Playwright configuration...")
    
    try:
        from playwright.sync_api import sync_playwright
        print("✅ Playwright import successful")
    except ImportError as e:
        print(f"❌ Playwright import failed: {e}")
        return False
    
    # Test browser availability
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        print("✅ Chromium browser launch successful")
    except Exception as e:
        print(f"❌ Chromium browser launch failed: {e}")
        return False
    
    return True

def test_storage_state_path():
    """Test storage state path resolution."""
    print("🧪 Testing storage state path...")
    
    cookie_dir = Path(os.getenv("COOKIE_DIR", "/app/cookies"))
    storage_state_path = cookie_dir / "youtube_session.json"
    
    print(f"📁 COOKIE_DIR: {cookie_dir}")
    print(f"📄 Storage state path: {storage_state_path}")
    
    if storage_state_path.exists():
        print("✅ Storage state file exists")
        
        # Validate JSON format
        try:
            import json
            with open(storage_state_path, 'r') as f:
                session_data = json.load(f)
            
            if 'cookies' in session_data:
                cookies = session_data['cookies']
                print(f"🍪 Found {len(cookies)} cookies in session file")
                
                # Check for YouTube cookies
                youtube_cookies = [c for c in cookies if 'youtube.com' in c.get('domain', '')]
                print(f"📺 Found {len(youtube_cookies)} YouTube cookies")
                
                return True
            else:
                print("⚠️  Session file missing 'cookies' key")
                return False
                
        except Exception as e:
            print(f"❌ Failed to parse session file: {e}")
            return False
    else:
        print("⚠️  Storage state file not found")
        print("💡 Run: python cookie_generator.py")
        return False

def test_proxy_configuration():
    """Test proxy configuration for Playwright."""
    print("🧪 Testing proxy configuration...")
    
    try:
        from proxy_manager import ProxyManager
        
        proxy_manager = ProxyManager()
        
        # Test production environment detection
        is_prod = proxy_manager.is_production_environment()
        print(f"🏭 Production environment: {is_prod}")
        
        # Test Playwright proxy configuration
        playwright_proxy = proxy_manager.playwright_proxy()
        if playwright_proxy:
            # Mask credentials for logging
            masked_proxy = {
                "server": playwright_proxy["server"],
                "username": playwright_proxy.get("username", "")[:4] + "***" if playwright_proxy.get("username") else None,
                "password": "***" if playwright_proxy.get("password") else None
            }
            print(f"🌐 Playwright proxy config: {masked_proxy}")
            return True
        else:
            if is_prod:
                print("❌ No proxy configuration in production environment")
                return False
            else:
                print("⚠️  No proxy configuration (OK for development)")
                return True
                
    except Exception as e:
        print(f"❌ Proxy configuration test failed: {e}")
        return False

def test_transcript_service_integration():
    """Test TranscriptService Playwright integration."""
    print("🧪 Testing TranscriptService integration...")
    
    try:
        from transcript_service import TranscriptService
        
        service = TranscriptService()
        
        # Test that Playwright method exists
        if hasattr(service, '_get_transcript_via_playwright_sync'):
            print("✅ Playwright sync method available")
        else:
            print("❌ Playwright sync method missing")
            return False
        
        # Test that production validation exists
        if hasattr(service, '_validate_production_requirements'):
            print("✅ Production validation method available")
        else:
            print("❌ Production validation method missing")
            return False
        
        # Test circuit breaker integration
        from transcript_service import _playwright_circuit_breaker
        
        is_open = _playwright_circuit_breaker.is_open()
        print(f"🔌 Circuit breaker status: {'open' if is_open else 'closed'}")
        
        return True
        
    except Exception as e:
        print(f"❌ TranscriptService integration test failed: {e}")
        return False

def test_feature_flags():
    """Test feature flag configuration."""
    print("🧪 Testing feature flags...")
    
    playwright_enabled = os.getenv("ENABLE_PLAYWRIGHT_PRIMARY", "true").lower() == "true"
    print(f"🎭 ENABLE_PLAYWRIGHT_PRIMARY: {playwright_enabled}")
    
    if not playwright_enabled:
        print("⚠️  Playwright is disabled via feature flag")
    
    return True

def main():
    """Run all tests."""
    print("🚀 Starting Playwright transcript pipeline tests...\n")
    
    tests = [
        ("Playwright Configuration", test_playwright_configuration),
        ("Storage State Path", test_storage_state_path),
        ("Proxy Configuration", test_proxy_configuration),
        ("TranscriptService Integration", test_transcript_service_integration),
        ("Feature Flags", test_feature_flags),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Running: {test_name}")
        print('='*50)
        
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print(f"\n{'='*50}")
    print("TEST SUMMARY")
    print('='*50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Playwright transcript pipeline is ready.")
        return 0
    else:
        print("⚠️  Some tests failed. Check configuration before deployment.")
        return 1

if __name__ == "__main__":
    sys.exit(main())