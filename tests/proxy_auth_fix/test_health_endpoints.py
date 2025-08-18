#!/usr/bin/env python3
"""
Test script for health endpoints
"""

import sys
import os
import json
import requests
import time
from unittest.mock import patch, MagicMock

# Set up test environment
os.environ["OXYLABS_PROXY_CONFIG"] = json.dumps({
    "provider": "oxylabs",
    "host": "pr.oxylabs.io", 
    "port": 7777,
    "username": "customer-test123",
    "password": "myRawPassword123!",
    "geo_enabled": False,
    "country": "us",
    "version": 1
})

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_health_endpoints():
    """Test health endpoints"""
    
    print("Testing health endpoints...")
    
    # Import app after setting environment
    from app import app
    
    with app.test_client() as client:
        # Test 1: /health/live endpoint
        print("\n1. Testing /health/live endpoint...")
        response = client.get('/health/live')
        
        if response.status_code == 200:
            data = response.get_json()
            if data.get("status") == "ok" and "timestamp" in data:
                print("✅ /health/live endpoint working correctly")
                print(f"   Response: {data}")
            else:
                print(f"❌ /health/live response format incorrect: {data}")
                return False
        else:
            print(f"❌ /health/live returned status {response.status_code}")
            return False
        
        # Test 2: /health/ready endpoint with mocked success
        print("\n2. Testing /health/ready endpoint with mocked success...")
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 204
            mock_get.return_value = mock_response
            
            response = client.get('/health/ready')
            
            if response.status_code == 200:
                data = response.get_json()
                if data.get("status") == "ready" and data.get("proxy_healthy") is True:
                    print("✅ /health/ready success test passed")
                    print(f"   Response: {data}")
                else:
                    print(f"❌ /health/ready success response incorrect: {data}")
                    return False
            else:
                print(f"❌ /health/ready success returned status {response.status_code}")
                return False
        
        # Test 3: /health/ready endpoint with mocked auth failure
        print("\n3. Testing /health/ready endpoint with mocked auth failure...")
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 407
            mock_get.return_value = mock_response
            
            response = client.get('/health/ready')
            
            if response.status_code == 503:
                data = response.get_json()
                if (data.get("status") == "not_ready" and 
                    data.get("proxy_healthy") is False and
                    "Retry-After" in response.headers):
                    print("✅ /health/ready auth failure test passed")
                    print(f"   Response: {data}")
                    print(f"   Retry-After header: {response.headers.get('Retry-After')}")
                else:
                    print(f"❌ /health/ready auth failure response incorrect: {data}")
                    return False
            else:
                print(f"❌ /health/ready auth failure returned status {response.status_code}")
                return False
        
        # Test 4: /health/ready endpoint with network error
        print("\n4. Testing /health/ready endpoint with network error...")
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.ConnectionError("Network error")
            
            response = client.get('/health/ready')
            
            if response.status_code == 503:
                data = response.get_json()
                if (data.get("status") == "not_ready" and 
                    data.get("proxy_healthy") is False and
                    "reason" in data):
                    print("✅ /health/ready network error test passed")
                    print(f"   Response: {data}")
                else:
                    print(f"❌ /health/ready network error response incorrect: {data}")
                    return False
            else:
                print(f"❌ /health/ready network error returned status {response.status_code}")
                return False
        
        # Test 5: Original /health endpoint still works
        print("\n5. Testing original /health endpoint...")
        response = client.get('/health')
        
        if response.status_code in [200, 503]:  # May fail due to missing dependencies
            data = response.get_json()
            if "status" in data and "message" in data:
                print(f"✅ Original /health endpoint working (status: {response.status_code})")
                print(f"   Status: {data.get('status')}")
                print(f"   Message: {data.get('message')}")
            else:
                print(f"❌ Original /health response format incorrect: {data}")
                return False
        else:
            print(f"❌ Original /health returned unexpected status {response.status_code}")
            return False
    
    print("\n🎉 All health endpoint tests passed!")
    return True

if __name__ == "__main__":
    success = test_health_endpoints()
    sys.exit(0 if success else 1)