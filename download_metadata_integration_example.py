#!/usr/bin/env python3
"""
Example of integrating download metadata tracking for health endpoints
"""

import os
import sys
from datetime import datetime

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def simulate_download_with_metadata_tracking():
    """Simulate a download with metadata tracking for health endpoints"""
    
    # This would normally be imported from your app
    from app import app, update_download_metadata
    
    print("🎬 Simulating video download with metadata tracking...")
    
    # Simulate different download scenarios
    scenarios = [
        {"video_id": "dQw4w9WgXcQ", "used_cookies": True, "client_used": "android"},
        {"video_id": "test_video_123", "used_cookies": False, "client_used": "web"},
        {"video_id": "another_video", "used_cookies": True, "client_used": "web_safari"}
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n📥 Download {i}: {scenario['video_id']}")
        
        # Simulate download process
        print(f"   Using cookies: {scenario['used_cookies']}")
        print(f"   Client: {scenario['client_used']}")
        
        # Update metadata (this would be called from yt_download_helper.py)
        update_download_metadata(
            used_cookies=scenario['used_cookies'],
            client_used=scenario['client_used']
        )
        
        # Show what health endpoint would return
        with app.app_context():
            metadata = getattr(app, 'last_download_meta', {})
            print(f"   Health metadata: {metadata}")
    
    return True

def demonstrate_health_endpoint_integration():
    """Show how health endpoints expose download metadata"""
    
    from app import app
    
    print("\n🏥 Testing health endpoint integration...")
    
    # Test with diagnostics disabled (default)
    with app.test_client() as client:
        print("\n1. Basic health check (diagnostics disabled):")
        response = client.get('/healthz')
        data = response.get_json()
        print(f"   Status: {data.get('status')}")
        print(f"   Fields: {list(data.keys())}")
        
        # Should not contain download metadata
        if 'last_download_used_cookies' not in data:
            print("   ✅ Download metadata properly hidden")
        else:
            print("   ❌ Download metadata unexpectedly exposed")
    
    # Test with diagnostics enabled
    os.environ['EXPOSE_HEALTH_DIAGNOSTICS'] = 'true'
    
    with app.test_client() as client:
        print("\n2. Enhanced health check (diagnostics enabled):")
        response = client.get('/healthz')
        data = response.get_json()
        print(f"   Status: {data.get('status')}")
        print(f"   Last download used cookies: {data.get('last_download_used_cookies')}")
        print(f"   Last download client: {data.get('last_download_client')}")
        print(f"   Timestamp: {data.get('timestamp')}")
        
        # Should contain download metadata
        if 'last_download_used_cookies' in data:
            print("   ✅ Download metadata properly exposed when enabled")
        else:
            print("   ❌ Download metadata missing when diagnostics enabled")
    
    # Clean up
    os.environ.pop('EXPOSE_HEALTH_DIAGNOSTICS', None)
    
    return True

def show_cookie_freshness_logging():
    """Demonstrate cookie freshness logging for health endpoints"""
    
    print("\n🍪 Cookie freshness logging example...")
    
    # This would be integrated into yt_download_helper.py
    def log_cookie_freshness(cookiefile, user_id=None):
        """Log cookie freshness without exposing contents"""
        if not cookiefile or not os.path.exists(cookiefile):
            print(f"   No cookie file for user {user_id or 'unknown'}")
            return False
        
        try:
            import time
            mtime = os.path.getmtime(cookiefile)
            age_hours = (time.time() - mtime) / 3600
            
            # Log without exposing file path or contents
            print(f"   Cookie age: {age_hours:.1f} hours for user {user_id or 'unknown'}")
            
            if age_hours > 12:
                print(f"   ⚠️ Cookies may be stale (>{age_hours:.1f}h old)")
                return False
            else:
                print(f"   ✅ Cookies fresh (<{age_hours:.1f}h old)")
                return True
                
        except Exception as e:
            print(f"   ❌ Cookie freshness check failed: {e}")
            return False
    
    # Simulate cookie freshness checks
    print("Simulating cookie freshness checks:")
    
    # Create a temporary cookie file for testing
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("# Netscape HTTP Cookie File\n")
        f.write(".youtube.com\tTRUE\t/\tFALSE\t1234567890\ttest_cookie\tvalue\n")
        temp_cookie_file = f.name
    
    try:
        # Test with fresh cookies
        log_cookie_freshness(temp_cookie_file, user_id=123)
        
        # Test with missing cookies
        log_cookie_freshness("/nonexistent/cookie.txt", user_id=456)
        
    finally:
        # Clean up
        try:
            os.unlink(temp_cookie_file)
        except:
            pass
    
    return True

def demonstrate_download_attempt_dataclass():
    """Show the DownloadAttempt dataclass for comprehensive tracking"""
    
    print("\n📊 Download attempt tracking example...")
    
    from dataclasses import dataclass
    from datetime import datetime
    from typing import Optional
    
    @dataclass
    class DownloadAttempt:
        video_id: str
        success: bool
        error_message: Optional[str]
        cookies_used: bool
        client_used: str
        proxy_used: bool
        step1_error: Optional[str] = None
        step2_error: Optional[str] = None
        timestamp: datetime = None
        
        def __post_init__(self):
            if self.timestamp is None:
                self.timestamp = datetime.utcnow()
        
        def get_combined_error(self) -> str:
            """Combine step errors for logging"""
            if self.step1_error and self.step2_error:
                return f"{self.step1_error} || {self.step2_error}"
            return self.step1_error or self.step2_error or "Unknown error"
        
        def to_health_metadata(self) -> dict:
            """Convert to health endpoint safe metadata"""
            return {
                "used_cookies": self.cookies_used,
                "client_used": self.client_used,
                "timestamp": self.timestamp.isoformat()
            }
    
    # Simulate different download attempts
    attempts = [
        DownloadAttempt(
            video_id="dQw4w9WgXcQ",
            success=True,
            error_message=None,
            cookies_used=True,
            client_used="android",
            proxy_used=True
        ),
        DownloadAttempt(
            video_id="failed_video",
            success=False,
            error_message="Failed to extract player response",
            cookies_used=False,
            client_used="web",
            proxy_used=False,
            step1_error="Unable to extract video data",
            step2_error="Re-encoding failed"
        )
    ]
    
    for i, attempt in enumerate(attempts, 1):
        print(f"\nAttempt {i}: {attempt.video_id}")
        print(f"   Success: {attempt.success}")
        print(f"   Cookies used: {attempt.cookies_used}")
        print(f"   Client: {attempt.client_used}")
        print(f"   Proxy used: {attempt.proxy_used}")
        
        if not attempt.success:
            print(f"   Combined error: {attempt.get_combined_error()}")
        
        # Show health metadata (safe for exposure)
        health_meta = attempt.to_health_metadata()
        print(f"   Health metadata: {health_meta}")
    
    return True

if __name__ == "__main__":
    print("🧪 Demonstrating download metadata integration for health endpoints...")
    print()
    
    examples = [
        simulate_download_with_metadata_tracking,
        demonstrate_health_endpoint_integration,
        show_cookie_freshness_logging,
        demonstrate_download_attempt_dataclass
    ]
    
    success_count = 0
    
    for example in examples:
        try:
            if example():
                success_count += 1
        except Exception as e:
            print(f"❌ Example failed: {e}")
        print()
    
    print(f"📊 Results: {success_count}/{len(examples)} examples completed successfully")
    
    if success_count == len(examples):
        print("🎉 All examples completed! Download metadata integration is ready.")
        print("📝 Key features demonstrated:")
        print("   - Download metadata tracking for health endpoints")
        print("   - Gated diagnostic information exposure")
        print("   - Cookie freshness logging without sensitive data")
        print("   - Comprehensive download attempt tracking")
        print("   - Health endpoint integration")
    else:
        print("💥 Some examples failed. Check the implementation.")