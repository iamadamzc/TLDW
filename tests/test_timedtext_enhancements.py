#!/usr/bin/env python3
"""
Test script to verify the enhanced timedtext blocking detection.
This script tests the new _is_blocking_response method.
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from timedtext_service import _is_blocking_response

def test_blocking_detection():
    """Test the blocking response detection functionality"""
    print("Testing timedtext blocking response detection...")
    
    # Test cases for blocking responses
    blocking_cases = [
        # Captcha pages
        "<html><body>Please complete the captcha to continue</body></html>",
        "CAPTCHA verification required",
        
        # Consent walls
        "Before you continue to YouTube",
        "We need your consent to continue",
        
        # Rate limiting
        "Rate limit exceeded. Please try again later.",
        "Too many requests",
        
        # Security checks
        "Security check required",
        "Verify you are human",
        
        # Cloudflare blocking
        "Cloudflare security check",
        "Checking your browser before accessing",
        
        # Access denied
        "Access denied",
        "You don't have permission to access",
        
        # Robot detection
        "Automated access detected",
        "Unusual traffic from your computer network",
        
        # Very short responses (suspicious)
        "{}",
        "[]",
        "",
        " ",
        "error",
    ]
    
    # Test cases for valid responses (should not be blocked)
    valid_cases = [
        # JSON transcript responses
        '{"events": [{"segs": [{"utf8": "Hello world"}]}]}',
        '{"events": [{"segs": [{"utf8": "This is a transcript"}]}]}',
        
        # XML transcript responses
        '<transcript><text start="1.0" dur="5.0">Hello world</text></transcript>',
        '<transcript><text start="1.0" dur="5.0">This is a longer transcript that should pass validation</text></transcript>',
        
        # Longer valid content
        "This is a valid transcript content that should not be blocked because it contains actual text and is long enough to be legitimate",
    ]
    
    
    
    print("Testing blocking cases:")
    for i, case in enumerate(blocking_cases):
        result = _is_blocking_response(case)
        status = "✓" if result else "✗"
        print(f"  {status} Case {i+1}: {result} - '{case[:50]}...'")
        if not result:
            print(f"    ERROR: Expected blocking response but got non-blocking for: '{case}'")
            return False
    
    print("\nTesting valid cases:")
    for i, case in enumerate(valid_cases):
        result = _is_blocking_response(case)
        status = "✓" if not result else "✗"
        print(f"  {status} Case {i+1}: {not result} - '{case[:50]}...'")
        if result:
            print(f"    ERROR: Expected non-blocking response but got blocking for: '{case}'")
            return False
    
    print("\n✓ All blocking detection tests passed!")
    print("The enhanced blocking detection includes checks for:")
    print("- Captcha and consent pages")
    print("- Rate limiting and security checks") 
    print("- Cloudflare and access denial")
    print("- Robot detection and automated access")
    print("- Very short/suspicious responses")
    
    return True

if __name__ == "__main__":
    success = test_blocking_detection()
    sys.exit(0 if success else 1)
