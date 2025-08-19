#!/usr/bin/env python3
"""
Example of how to integrate resilient ProxyManager in the application
"""

import logging
import os
from proxy_manager import ProxyManager

def create_resilient_proxy_manager():
    """Create ProxyManager that gracefully handles AWS Secrets Manager issues"""
    
    # Set up logging
    logger = logging.getLogger(__name__)
    
    # In real application, this would fetch from AWS Secrets Manager
    # For demo, simulate the missing provider field issue from production logs
    try:
        # Simulate fetching secret from AWS Secrets Manager
        secret_name = os.getenv('PROXY_SECRET_NAME', 'oxylabs-proxy-secret')
        
        # This would normally be:
        # secret_data = boto3.client('secretsmanager').get_secret_value(SecretId=secret_name)
        # secret_dict = json.loads(secret_data['SecretString'])
        
        # Simulate the production issue - missing provider field
        secret_dict = {
            "host": "pr.oxylabs.io",
            "port": 60000,
            "username": "customer-username",
            "password": "customer-password", 
            "protocol": "http"
            # Missing "provider" field - this was causing crashes
        }
        
        # Create ProxyManager - this will now gracefully handle the missing field
        proxy_manager = ProxyManager(secret_dict, logger)
        
        # Check if proxy is available
        if proxy_manager.in_use:
            logger.info("✅ Proxy configured successfully")
            return proxy_manager
        else:
            logger.warning("⚠️ Proxy not available, continuing without proxy support")
            return proxy_manager  # Still return it, just not in use
            
    except Exception as e:
        logger.error(f"❌ Failed to initialize proxy: {e}")
        # Return a ProxyManager in degraded state
        return ProxyManager(None, logger)

def use_proxy_for_request(proxy_manager: ProxyManager, video_id: str):
    """Example of using ProxyManager for a request"""
    
    # Get proxy configuration (returns empty dict if not available)
    proxies = proxy_manager.proxies_for(video_id)
    
    if proxies:
        print(f"🌐 Using proxy for video {video_id}")
        # In real code: requests.get(url, proxies=proxies)
        return "request_with_proxy"
    else:
        print(f"🔄 No proxy available, making direct request for video {video_id}")
        # In real code: requests.get(url)
        return "direct_request"

def health_check_integration(proxy_manager: ProxyManager):
    """Example of exposing proxy status in health endpoint"""
    
    health_data = {
        "status": "healthy",
        "proxy_in_use": proxy_manager.in_use,
        "proxy_healthy": proxy_manager.healthy
    }
    
    return health_data

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    print("🚀 Demonstrating resilient ProxyManager integration...")
    print()
    
    # Create ProxyManager (handles missing provider gracefully)
    proxy_manager = create_resilient_proxy_manager()
    
    # Use it for requests (works whether proxy is available or not)
    result1 = use_proxy_for_request(proxy_manager, "dQw4w9WgXcQ")
    result2 = use_proxy_for_request(proxy_manager, "test_video_123")
    
    # Health check integration
    health = health_check_integration(proxy_manager)
    print(f"🏥 Health check: {health}")
    
    print()
    print("✅ Application continues running even with proxy configuration issues!")
    print("📝 Key benefits:")
    print("   - Service doesn't crash on startup with malformed secrets")
    print("   - Graceful degradation to direct requests")
    print("   - Health endpoints show proxy status")
    print("   - Detailed logging for debugging without sensitive data")