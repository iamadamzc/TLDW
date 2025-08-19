#!/usr/bin/env python3
"""
Test health endpoints with gated diagnostics
"""

import os
import sys
import json
from unittest.mock import patch, MagicMock

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_basic_health_without_diagnostics():
    """Test that basic health endpoint works without exposing diagnostics"""
    print("Testing basic health endpoint (diagnostics disabled)...")
    
    # Ensure diagnostics are disabled
    with patch.dict(os.environ, {'EXPOSE_HEALTH_DIAGNOSTICS': 'false'}):
        from app import app
        
        with app.test_client() as client:
            response = client.get('/healthz')
            
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            
            data = response.get_json()
            assert data['status'] == 'healthy', f"Expected healthy status, got {data.get('status')}"
            
            # Should NOT contain diagnostic information
            diagnostic_fields = ['yt_dlp_version', 'ffmpeg_available', 'proxy_in_use', 
                               'last_download_used_cookies', 'last_download_client', 'timestamp']
            
            for field in diagnostic_fields:
                assert field not in data, f"Field '{field}' should not be exposed when diagnostics disabled"
            
            print("✅ Basic health endpoint works without exposing diagnostics")
            return True

def test_health_with_diagnostics_enabled():
    """Test that health endpoint exposes diagnostics when enabled"""
    print("Testing health endpoint with diagnostics enabled...")
    
    # Enable diagnostics
    with patch.dict(os.environ, {'EXPOSE_HEALTH_DIAGNOSTICS': 'true'}):
        # Mock yt_dlp import
        mock_yt_dlp = MagicMock()
        mock_yt_dlp.version.__version__ = "2025.8.11"
        
        with patch.dict('sys.modules', {'yt_dlp': mock_yt_dlp}):
            with patch('os.path.exists', return_value=True):  # Mock ffmpeg exists
                from app import app
                
                with app.test_client() as client:
                    response = client.get('/healthz')
                    
                    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
                    
                    data = response.get_json()
                    assert data['status'] == 'healthy', f"Expected healthy status, got {data.get('status')}"
                    
                    # Should contain diagnostic information
                    expected_fields = ['yt_dlp_version', 'ffmpeg_available', 'proxy_in_use', 
                                     'last_download_used_cookies', 'last_download_client', 'timestamp']
                    
                    for field in expected_fields:
                        assert field in data, f"Field '{field}' should be present when diagnostics enabled"
                    
                    # Verify specific values
                    assert data['yt_dlp_version'] == "2025.8.11", f"Expected yt-dlp version 2025.8.11, got {data['yt_dlp_version']}"
                    assert data['ffmpeg_available'] == True, f"Expected ffmpeg_available=True, got {data['ffmpeg_available']}"
                    assert isinstance(data['proxy_in_use'], bool), f"proxy_in_use should be boolean, got {type(data['proxy_in_use'])}"
                    
                    print("✅ Health endpoint exposes diagnostics when enabled")
                    print(f"   - yt_dlp_version: {data['yt_dlp_version']}")
                    print(f"   - ffmpeg_available: {data['ffmpeg_available']}")
                    print(f"   - proxy_in_use: {data['proxy_in_use']}")
                    return True

def test_yt_dlp_specific_endpoint():
    """Test the /health/yt-dlp specific endpoint"""
    print("Testing /health/yt-dlp endpoint...")
    
    # Mock yt_dlp import
    mock_yt_dlp = MagicMock()
    mock_yt_dlp.version.__version__ = "2025.8.11"
    
    with patch.dict('sys.modules', {'yt_dlp': mock_yt_dlp}):
        from app import app
        
        with app.test_client() as client:
            response = client.get('/health/yt-dlp')
            
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            
            data = response.get_json()
            assert data['status'] == 'available', f"Expected available status, got {data.get('status')}"
            assert data['version'] == "2025.8.11", f"Expected version 2025.8.11, got {data['version']}"
            assert 'proxy_in_use' in data, "proxy_in_use field should be present"
            assert isinstance(data['proxy_in_use'], bool), f"proxy_in_use should be boolean, got {type(data['proxy_in_use'])}"
            
            print("✅ /health/yt-dlp endpoint works correctly")
            print(f"   - version: {data['version']}")
            print(f"   - status: {data['status']}")
            print(f"   - proxy_in_use: {data['proxy_in_use']}")
            return True

def test_yt_dlp_endpoint_error_handling():
    """Test /health/yt-dlp endpoint error handling"""
    print("Testing /health/yt-dlp error handling...")
    
    # Mock yt_dlp import failure
    with patch.dict('sys.modules', {'yt_dlp': None}):
        from app import app
        
        with app.test_client() as client:
            response = client.get('/health/yt-dlp')
            
            assert response.status_code == 500, f"Expected 500, got {response.status_code}"
            
            data = response.get_json()
            assert data['status'] == 'error', f"Expected error status, got {data.get('status')}"
            assert 'error' in data, "Error field should be present"
            
            print("✅ /health/yt-dlp error handling works correctly")
            print(f"   - status: {data['status']}")
            print(f"   - error: {data.get('error', 'N/A')}")
            return True

def test_no_sensitive_data_exposure():
    """Test that health endpoints never expose sensitive data"""
    print("Testing that no sensitive data is exposed...")
    
    # Enable diagnostics and set up mock proxy config
    proxy_config = {
        "provider": "oxylabs",
        "host": "proxy.example.com",
        "port": 8080,
        "username": "secret_user",
        "password": "secret_pass",
        "protocol": "http"
    }
    
    with patch.dict(os.environ, {
        'EXPOSE_HEALTH_DIAGNOSTICS': 'true',
        'OXYLABS_PROXY_CONFIG': json.dumps(proxy_config)
    }):
        mock_yt_dlp = MagicMock()
        mock_yt_dlp.version.__version__ = "2025.8.11"
        
        with patch.dict('sys.modules', {'yt_dlp': mock_yt_dlp}):
            with patch('os.path.exists', return_value=True):
                from app import app
                
                with app.test_client() as client:
                    # Test /healthz
                    response = client.get('/healthz')
                    data = response.get_json()
                    
                    # Convert to string to check for sensitive data
                    response_str = json.dumps(data)
                    
                    # Should not contain sensitive information
                    sensitive_data = ['secret_user', 'secret_pass', 'proxy.example.com', '/usr/bin']
                    
                    for sensitive in sensitive_data:
                        assert sensitive not in response_str, f"Sensitive data '{sensitive}' found in /healthz response"
                    
                    # Test /health/yt-dlp
                    response = client.get('/health/yt-dlp')
                    data = response.get_json()
                    response_str = json.dumps(data)
                    
                    for sensitive in sensitive_data:
                        assert sensitive not in response_str, f"Sensitive data '{sensitive}' found in /health/yt-dlp response"
                    
                    print("✅ No sensitive data exposed in health endpoints")
                    return True

def test_environment_variable_gating():
    """Test that EXPOSE_HEALTH_DIAGNOSTICS properly gates diagnostic information"""
    print("Testing environment variable gating...")
    
    mock_yt_dlp = MagicMock()
    mock_yt_dlp.version.__version__ = "2025.8.11"
    
    with patch.dict('sys.modules', {'yt_dlp': mock_yt_dlp}):
        with patch('os.path.exists', return_value=True):
            from app import app
            
            # Test with diagnostics disabled (default)
            with patch.dict(os.environ, {'EXPOSE_HEALTH_DIAGNOSTICS': 'false'}):
                with app.test_client() as client:
                    response = client.get('/healthz')
                    data = response.get_json()
                    
                    # Should only have basic fields
                    assert 'status' in data
                    assert 'yt_dlp_version' not in data
                    assert 'ffmpeg_available' not in data
            
            # Test with diagnostics enabled
            with patch.dict(os.environ, {'EXPOSE_HEALTH_DIAGNOSTICS': 'true'}):
                with app.test_client() as client:
                    response = client.get('/healthz')
                    data = response.get_json()
                    
                    # Should have diagnostic fields
                    assert 'status' in data
                    assert 'yt_dlp_version' in data
                    assert 'ffmpeg_available' in data
            
            print("✅ Environment variable gating works correctly")
            return True

if __name__ == "__main__":
    print("🧪 Testing health endpoints with gated diagnostics...")
    print()
    
    tests = [
        test_basic_health_without_diagnostics,
        test_health_with_diagnostics_enabled,
        test_yt_dlp_specific_endpoint,
        test_yt_dlp_endpoint_error_handling,
        test_no_sensitive_data_exposure,
        test_environment_variable_gating
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
        print()
    
    print(f"📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Health endpoints are properly configured.")
        print("📝 Key features verified:")
        print("   - Basic health check always available")
        print("   - Diagnostics gated behind EXPOSE_HEALTH_DIAGNOSTICS (default off)")
        print("   - No sensitive data exposure (paths, credentials)")
        print("   - Specific /health/yt-dlp endpoint works")
        print("   - Proper error handling")
        sys.exit(0)
    else:
        print("💥 Some tests failed. Health endpoints need fixes.")
        sys.exit(1)