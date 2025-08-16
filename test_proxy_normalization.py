#!/usr/bin/env python3
"""
Test script to verify proxy credential normalization functionality.
This tests the _normalize_credential function with various encoding scenarios.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from urllib.parse import quote
from proxy_manager import _normalize_credential

def test_normalize_credential():
    """Test the _normalize_credential function with various scenarios"""
    
    print("=== Testing Proxy Credential Normalization ===\n")
    
    # Test cases based on the actual credentials provided
    test_cases = [
        # Case 1: Raw credentials (should remain unchanged)
        ("new_user_LDKZF", "new_user_LDKZF", "Raw username with underscore"),
        ("319z8jZt4KkHgR+", "319z8jZt4KkHgR+", "Raw password with plus sign"),
        
        # Case 2: URL-encoded credentials (should be decoded)
        ("new_user_LDKZF", "new_user_LDKZF", "Username with underscore (no encoding needed)"),
        ("new%5Fuser%5FLDKZF", "new_user_LDKZF", "URL-encoded username with %5F (underscore)"),
        ("319z8jZt4KkHgR%2B", "319z8jZt4KkHgR+", "URL-encoded password with %2B (plus sign)"),
        
        # Case 3: Common URL-encoded characters
        ("user%40domain", "user@domain", "Username with %40 (at symbol)"),
        ("pass%3Aword", "pass:word", "Password with %3A (colon)"),
        ("test%21pass", "test!pass", "Password with %21 (exclamation)"),
        
        # Case 4: No encoding needed
        ("plainuser", "plainuser", "Plain username"),
        ("plainpass123", "plainpass123", "Plain password"),
        
        # Case 5: Edge cases
        ("", "", "Empty string"),
        ("no%percent", "no%percent", "String with % but no valid encoding"),
    ]
    
    all_passed = True
    
    for i, (input_val, expected, description) in enumerate(test_cases, 1):
        result = _normalize_credential(input_val)
        passed = result == expected
        all_passed = all_passed and passed
        
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"Test {i}: {status}")
        print(f"  Description: {description}")
        print(f"  Input:       '{input_val}'")
        print(f"  Expected:    '{expected}'")
        print(f"  Got:         '{result}'")
        if not passed:
            print(f"  ERROR: Expected '{expected}' but got '{result}'")
        print()
    
    return all_passed

def test_proxy_url_construction():
    """Test that normalized credentials produce correct proxy URLs"""
    
    print("=== Testing Proxy URL Construction ===\n")
    
    # Simulate the exact scenario from the logs
    raw_username = "new_user_LDKZF"
    raw_password = "319z8jZt4KkHgR+"
    
    # Test if password was stored URL-encoded
    encoded_password = "319z8jZt4KkHgR%2B"  # + becomes %2B
    
    print(f"Raw username: '{raw_username}'")
    print(f"Raw password: '{raw_password}'")
    print(f"URL-encoded password: '{encoded_password}'")
    print()
    
    # Test normalization
    normalized_user = _normalize_credential(raw_username)
    normalized_pass_raw = _normalize_credential(raw_password)
    normalized_pass_encoded = _normalize_credential(encoded_password)
    
    print(f"Normalized username (raw): '{normalized_user}'")
    print(f"Normalized password (raw): '{normalized_pass_raw}'")
    print(f"Normalized password (encoded): '{normalized_pass_encoded}'")
    print()
    
    # Test final URL encoding (what _build_proxy_url does)
    final_user = quote(f"customer-{normalized_user}-cc-us-sessid-test123", safe="")
    final_pass_raw = quote(normalized_pass_raw, safe="")
    final_pass_encoded = quote(normalized_pass_encoded, safe="")
    
    print(f"Final URL-encoded username: '{final_user}'")
    print(f"Final URL-encoded password (from raw): '{final_pass_raw}'")
    print(f"Final URL-encoded password (from encoded): '{final_pass_encoded}'")
    print()
    
    # Check if they match (they should after normalization)
    passwords_match = final_pass_raw == final_pass_encoded
    print(f"Passwords match after normalization: {'✅ YES' if passwords_match else '❌ NO'}")
    
    if passwords_match:
        print("✅ SUCCESS: Normalization fixes the double-encoding issue!")
    else:
        print("❌ FAILURE: Normalization did not fix the issue")
    
    return passwords_match

def main():
    """Run all tests"""
    print("Proxy Credential Normalization Test Suite")
    print("=" * 50)
    print()
    
    # Test 1: Basic normalization
    test1_passed = test_normalize_credential()
    
    # Test 2: Proxy URL construction
    test2_passed = test_proxy_url_construction()
    
    print("\n" + "=" * 50)
    print("SUMMARY:")
    print(f"Normalization tests: {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"URL construction test: {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 ALL TESTS PASSED! The fix should resolve the 407 errors.")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED! Review the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
