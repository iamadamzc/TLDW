#!/usr/bin/env python3
"""
Test script to verify proxy configuration is properly loaded from environment
This can be run in App Runner to test proxy secret injection
"""

import os
import json

# Try to import boto3, but handle gracefully if not available
try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    print("⚠️  boto3 not available locally - this test should be run in App Runner environment")

def test_proxy_environment():
    """Test that proxy environment variables are properly configured"""
    print("=== Testing Proxy Configuration ===")
    
    # Check USE_PROXIES environment variable
    use_proxies = os.getenv('USE_PROXIES', 'false')
    print(f"USE_PROXIES: {use_proxies}")
    
    # Check if OXYLABS_PROXY_CONFIG is set (this should be the secret ARN)
    proxy_config_env = os.getenv('OXYLABS_PROXY_CONFIG')
    print(f"OXYLABS_PROXY_CONFIG env var: {proxy_config_env}")
    
    if not proxy_config_env:
        print("❌ OXYLABS_PROXY_CONFIG environment variable not set")
        return False
    
    # Test AWS Secrets Manager access
    if not BOTO3_AVAILABLE:
        print("⚠️  Skipping AWS Secrets Manager test - boto3 not available")
        return True
    
    try:
        print("\n=== Testing AWS Secrets Manager Access ===")
        session = boto3.Session()
        client = session.client('secretsmanager', region_name='us-west-2')
        
        # Try to get the secret value
        response = client.get_secret_value(SecretId='tldw-oxylabs-proxy-config')
        secret_string = response['SecretString']
        
        # Parse the JSON configuration
        proxy_config = json.loads(secret_string)
        
        print("✅ Successfully loaded proxy configuration from AWS Secrets Manager")
        print(f"Proxy host: {proxy_config.get('host', 'N/A')}")
        print(f"Proxy port: {proxy_config.get('port', 'N/A')}")
        print(f"Username configured: {'Yes' if proxy_config.get('username') else 'No'}")
        print(f"Password configured: {'Yes' if proxy_config.get('password') else 'No'}")
        
        return True
        
    except ClientError as e:
        print(f"❌ Failed to access AWS Secrets Manager: {e}")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse proxy configuration JSON: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_proxy_manager_initialization():
    """Test that ProxyManager can be initialized properly"""
    print("\n=== Testing ProxyManager Initialization ===")
    
    if not BOTO3_AVAILABLE:
        print("⚠️  Skipping ProxyManager test - boto3 not available")
        return True
    
    try:
        from proxy_manager import ProxyManager
        
        # Initialize proxy manager
        proxy_manager = ProxyManager()
        
        if proxy_manager.enabled:
            print("✅ ProxyManager initialized successfully")
            print(f"Proxy enabled: {proxy_manager.enabled}")
            
            # Get stats
            stats = proxy_manager.get_session_stats()
            print(f"Proxy stats: {stats}")
            
            return True
        else:
            print("❌ ProxyManager initialized but proxies are disabled")
            return False
            
    except Exception as e:
        print(f"❌ Failed to initialize ProxyManager: {e}")
        return False

def test_proxy_connectivity():
    """Test actual proxy connectivity using a simple request"""
    print("\n=== Testing Proxy Connectivity ===")
    
    if not BOTO3_AVAILABLE:
        print("⚠️  Skipping proxy connectivity test - boto3 not available")
        return True
    
    try:
        from proxy_manager import ProxyManager
        import requests
        
        proxy_manager = ProxyManager()
        
        if not proxy_manager.enabled or not proxy_manager.proxy_config:
            print("❌ Proxy not enabled or configured")
            return False
        
        # Create a test session
        session = proxy_manager.get_session_for_video("test_video_123")
        if not session:
            print("❌ Failed to create proxy session")
            return False
        
        # Get proxy configuration
        proxy_dict = proxy_manager.get_proxy_dict(session)
        
        # Test with a simple request to check IP
        test_url = "https://httpbin.org/ip"
        
        print(f"Testing proxy connectivity to {test_url}")
        response = requests.get(test_url, proxies=proxy_dict, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Proxy connectivity test successful")
            print(f"External IP via proxy: {result.get('origin', 'N/A')}")
            return True
        else:
            print(f"❌ Proxy connectivity test failed: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Proxy connectivity test failed: {e}")
        return False

if __name__ == "__main__":
    print("TL;DW Proxy Configuration Test")
    print("=" * 40)
    
    success = True
    
    # Run all tests
    success &= test_proxy_environment()
    success &= test_proxy_manager_initialization()
    success &= test_proxy_connectivity()
    
    print("\n" + "=" * 40)
    if success:
        print("✅ All proxy configuration tests passed!")
    else:
        print("❌ Some proxy configuration tests failed!")
    
    print("=" * 40)