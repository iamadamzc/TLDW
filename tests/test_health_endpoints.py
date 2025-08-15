#!/usr/bin/env python3
"""
Test script for enhanced health check endpoints
"""

import os
import sys
import json
from unittest.mock import patch

def test_health_endpoint_structure():
    """Test that health endpoints return the expected structure"""
    print("🧪 Testing Health Endpoint Structure")
    
    try:
        from app import app
        app.config['TESTING'] = True
        
        with app.test_client() as client:
            # Test /health endpoint
            response = client.get('/health')
            print(f"Health endpoint status: {response.status_code}")
            
            if response.status_code not in [200, 503]:
                print(f"❌ Unexpected status code: {response.status_code}")
                return False
            
            data = response.get_json()
            if not data:
                print("❌ No JSON response")
                return False
            
            # Check required fields
            required_fields = [
                'status', 'message', 'dependencies', 
                'ffmpeg_location', 'yt_dlp_version', 'allow_missing_deps'
            ]
            
            missing_fields = []
            for field in required_fields:
                if field not in data:
                    missing_fields.append(field)
            
            if missing_fields:
                print(f"❌ Missing fields: {missing_fields}")
                return False
            
            print("✅ All required fields present")
            print(f"   Status: {data['status']}")
            print(f"   FFMPEG Location: {data['ffmpeg_location']}")
            print(f"   yt-dlp Version: {data['yt_dlp_version']}")
            print(f"   Allow Missing Deps: {data['allow_missing_deps']}")
            
            # Test /healthz endpoint
            healthz_response = client.get('/healthz')
            if healthz_response.status_code != response.status_code:
                print(f"❌ /healthz status ({healthz_response.status_code}) != /health status ({response.status_code})")
                return False
            
            print("✅ Both endpoints return consistent status")
            return True
            
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False

def test_health_with_missing_deps():
    """Test health endpoint behavior with missing dependencies"""
    print("\n🧪 Testing Health Endpoint with Missing Dependencies")
    
    try:
        # Test with ALLOW_MISSING_DEPS=false (should return 503)
        with patch.dict(os.environ, {'ALLOW_MISSING_DEPS': 'false'}):
            with patch('app._check_dependencies') as mock_deps:
                mock_deps.return_value = {
                    'ffmpeg': {'available': False, 'error': 'not found'},
                    'yt_dlp': {'available': True, 'version': '2024.8.6'}
                }
                
                from app import app
                app.config['TESTING'] = True
                
                with app.test_client() as client:
                    response = client.get('/health')
                    
                    if response.status_code != 503:
                        print(f"❌ Expected 503, got {response.status_code}")
                        return False
                    
                    data = response.get_json()
                    if data['status'] != 'unhealthy':
                        print(f"❌ Expected 'unhealthy', got '{data['status']}'")
                        return False
                    
                    print("✅ Correctly returns 503 with missing deps (strict mode)")
        
        # Test with ALLOW_MISSING_DEPS=true (should return 200 with degraded)
        with patch.dict(os.environ, {'ALLOW_MISSING_DEPS': 'true'}):
            with patch('app._check_dependencies') as mock_deps:
                mock_deps.return_value = {
                    'ffmpeg': {'available': False, 'error': 'not found'},
                    'yt_dlp': {'available': True, 'version': '2024.8.6'}
                }
                
                from app import app
                app.config['TESTING'] = True
                
                with app.test_client() as client:
                    response = client.get('/health')
                    
                    if response.status_code != 200:
                        print(f"❌ Expected 200, got {response.status_code}")
                        return False
                    
                    data = response.get_json()
                    if data['status'] != 'degraded':
                        print(f"❌ Expected 'degraded', got '{data['status']}'")
                        return False
                    
                    if not data.get('degraded'):
                        print("❌ Missing 'degraded' flag")
                        return False
                    
                    print("✅ Correctly returns 200 with degraded status (permissive mode)")
        
        return True
        
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False

def main():
    """Run all health endpoint tests"""
    print("🏥 Health Endpoint Enhancement Tests")
    print("=" * 50)
    
    tests = [
        test_health_endpoint_structure,
        test_health_with_missing_deps
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test_func.__name__} crashed: {e}")
    
    print("\n" + "=" * 50)
    print(f"🏁 Health Tests Summary: {passed}/{total} passed")
    
    if passed == total:
        print("✅ All health endpoint tests passed!")
        return True
    else:
        print("❌ Some health endpoint tests failed!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)