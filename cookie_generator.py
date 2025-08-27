#!/usr/bin/env python3
"""
High-Quality Cookie Generation for YouTube Transcript API
=========================================================

This script performs a one-time "warm-up" session to generate natural-looking cookies
that bypass YouTube's anti-bot fingerprinting. The primary goal is to create a 
"warmed-up" session state that includes the critical CONSENT cookie.

Usage:
    python cookie_generator.py                           # Generate new session
    python cookie_generator.py --from-netscape cookies.txt  # Convert Netscape cookies

Output:
    youtube_session.json - Complete browser session state with cookies
"""

import logging
import os
import time
import json
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- CONFIGURE THESE ---
# This must be a STICKY session proxy URL for consistent IP
PROXY_URL = os.getenv("STICKY_PROXY_URL", "http://customer-new_user_LDKZF-sessid-0322886770-sesstime-10:Change_Password1@pr.oxylabs.io:7777")

# Use COOKIE_DIR environment variable for storage state location
import os
from pathlib import Path
COOKIE_DIR = Path(os.getenv("COOKIE_DIR", "/app/cookies"))
SESSION_FILE_PATH = str(COOKIE_DIR / "youtube_session.json")
# ---

def generate_youtube_session():
    """
    Generate a high-quality YouTube session with natural cookies.
    
    This function:
    1. Launches Playwright with a sticky residential proxy
    2. Navigates to YouTube and accepts cookie consent
    3. Performs additional browsing to warm up the session
    4. Saves the complete session state including all cookies
    """
    
    logging.info("🚀 Starting YouTube session generation...")
    logging.info(f"📁 Session will be saved to: {SESSION_FILE_PATH}")
    
    if PROXY_URL.startswith("http://user-session123"):
        logging.warning("⚠️  Using default proxy URL - please configure STICKY_PROXY_URL environment variable")
        logging.warning("⚠️  For production, use a real sticky residential proxy")
    
    with sync_playwright() as p:
        browser = None
        try:
            logging.info("🌐 Launching browser with sticky proxy...")
            browser = p.chromium.launch(
                headless=True,  # Set to False for debugging to watch the process
                proxy={
                    "server": PROXY_URL
                },
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-web-security",
                    "--disable-features=VizDisplayCompositor"
                ]
            )
            
            # Create context with realistic user agent and viewport
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="America/New_York",
                # Add realistic browser features
                extra_http_headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1"
                }
            )
            
            page = context.new_page()
            
            # Step 3: Navigate and Accept Cookie Consent
            logging.info("📺 Navigating to YouTube...")
            try:
                page.goto("https://www.youtube.com", timeout=60000, wait_until="domcontentloaded")
                logging.info("✅ Successfully loaded YouTube homepage")
                
                # Wait a moment for any dynamic content to load
                page.wait_for_timeout(3000)
                
                logging.info("🍪 Looking for cookie consent dialog...")
                
                # Try multiple selectors for the consent button
                consent_selectors = [
                    'button:has-text("Accept all")',
                    'button:has-text("I agree")',
                    'button:has-text("Agree to all")',
                    '[aria-label*="Accept"] button',
                    'button[jsname="b3VHJd"]',  # YouTube's consent button
                    'form[action*="consent"] button:first-child'
                ]
                
                consent_clicked = False
                for selector in consent_selectors:
                    try:
                        consent_button = page.locator(selector).first
                        if consent_button.is_visible(timeout=5000):
                            logging.info(f"🎯 Found consent button with selector: {selector}")
                            consent_button.click()
                            page.wait_for_timeout(3000)  # Wait for consent processing
                            logging.info("✅ Cookie consent accepted successfully")
                            consent_clicked = True
                            break
                    except Exception as e:
                        logging.debug(f"Selector '{selector}' not found: {e}")
                        continue
                
                if not consent_clicked:
                    logging.warning("⚠️  Could not find consent button - it may not have appeared")
                    logging.info("ℹ️  This is normal for some regions or if consent was already given")
                
            except Exception as e:
                logging.error(f"❌ Failed to navigate to YouTube: {e}")
                raise
            
            # Step 4: "Warm-up" the Session with Additional Browsing
            logging.info("🔥 Warming up session with additional browsing...")
            
            warm_up_pages = [
                ("https://www.youtube.com/feed/trending", "Trending page"),
                ("https://www.youtube.com/feed/subscriptions", "Subscriptions page"),
                ("https://www.youtube.com/results?search_query=test", "Search results")
            ]
            
            for url, description in warm_up_pages:
                try:
                    logging.info(f"🌐 Navigating to {description}...")
                    page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    
                    # Simulate realistic user behavior
                    page.wait_for_timeout(2000)  # Wait for page to load
                    
                    # Scroll down a bit to simulate reading
                    page.mouse.wheel(0, 500)
                    page.wait_for_timeout(1000)
                    
                    logging.info(f"✅ Successfully visited {description}")
                    
                except Exception as e:
                    logging.warning(f"⚠️  Failed to visit {description}: {e}")
                    # Continue with other pages even if one fails
                    continue
            
            logging.info("🔥 Session warm-up complete")
            
            # Step 5: Save the Complete Session State
            logging.info(f"💾 Saving browser session state to {SESSION_FILE_PATH}...")
            
            # Ensure the cookies directory exists
            COOKIE_DIR.mkdir(parents=True, exist_ok=True)
            
            try:
                context.storage_state(path=SESSION_FILE_PATH)
                print(f"[cookie_generator] wrote storage_state at {SESSION_FILE_PATH}")
                logging.info("✅ Session state saved successfully")
                
                # Inject SOCS/CONSENT cookies if missing after warm-up session
                inject_consent_cookies_after_generation(SESSION_FILE_PATH)
                
                # Verify the file was created and has content
                if os.path.exists(SESSION_FILE_PATH):
                    file_size = os.path.getsize(SESSION_FILE_PATH)
                    logging.info(f"📊 Session file size: {file_size} bytes")
                    
                    # Load and analyze the session
                    import json
                    with open(SESSION_FILE_PATH, 'r') as f:
                        session_data = json.load(f)
                        
                    cookies = session_data.get('cookies', [])
                    logging.info(f"🍪 Total cookies saved: {len(cookies)}")
                    
                    # Log important cookies (without values for security)
                    important_cookies = ['CONSENT', 'VISITOR_INFO1_LIVE', 'YSC', 'PREF']
                    found_important = []
                    
                    for cookie in cookies:
                        if cookie.get('name') in important_cookies:
                            found_important.append(cookie.get('name'))
                    
                    if found_important:
                        logging.info(f"🎯 Important cookies found: {', '.join(found_important)}")
                    else:
                        logging.warning("⚠️  No critical YouTube cookies found - session may not be optimal")
                    
                    # Check for CONSENT cookie specifically
                    consent_cookies = [c for c in cookies if c.get('name') == 'CONSENT']
                    if consent_cookies:
                        logging.info("✅ CONSENT cookie successfully generated - this is critical for bypassing blocks")
                    else:
                        logging.warning("⚠️  CONSENT cookie not found - consent dialog may not have been processed")
                
                else:
                    logging.error("❌ Session file was not created")
                    
            except Exception as e:
                logging.error(f"❌ Failed to save session state: {e}")
                raise
            
        except Exception as e:
            logging.error(f"❌ Session generation failed: {e}")
            raise
            
        finally:
            if browser:
                try:
                    browser.close()
                    logging.info("🔒 Browser closed")
                except Exception as e:
                    logging.warning(f"⚠️  Error closing browser: {e}")
    
    logging.info("🎉 YouTube session generation completed successfully!")
    logging.info(f"📁 Session file ready at: {os.path.abspath(SESSION_FILE_PATH)}")
    logging.info("💡 Next step: Update your TranscriptService to use this session file")

def convert_netscape_to_storage_state(netscape_path: str) -> bool:
    """
    Convert Netscape cookies.txt to Playwright storage_state.json format.
    Returns True if conversion successful, False otherwise.
    """
    logging.info(f"🔄 Converting Netscape cookies from {netscape_path}...")
    
    try:
        # Validate input file exists
        if not os.path.exists(netscape_path):
            logging.error(f"❌ Netscape cookies file not found: {netscape_path}")
            return False
        
        # Read and validate Netscape cookies
        with open(netscape_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        if not validate_netscape_format(content):
            logging.error(f"❌ Invalid Netscape cookie format in {netscape_path}")
            return False
        
        # Parse Netscape cookies
        cookies = []
        for line_num, line in enumerate(content.strip().split('\n'), 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            parts = line.split('\t')
            if len(parts) < 7:
                logging.warning(f"⚠️  Skipping malformed line {line_num}: insufficient fields")
                continue
            
            domain, flag, path, secure, expiry, name, value = parts[:7]
            
            # Skip empty names or values
            if not name or not value:
                logging.warning(f"⚠️  Skipping line {line_num}: empty name or value")
                continue
            
            # Convert to Playwright cookie format
            cookie = {
                "name": name,
                "value": value,
                "domain": domain if not domain.startswith('.') else domain[1:],
                "path": path,
                "secure": secure.lower() == 'true',
                "httpOnly": False,  # Default for Netscape format
            }
            
            # Handle expiry (convert to seconds since epoch)
            try:
                if expiry and expiry != '0':
                    cookie["expires"] = int(expiry)
            except (ValueError, TypeError):
                logging.debug(f"⚠️  Invalid expiry for cookie {name}: {expiry}")
            
            # Sanitize __Host- cookies for Playwright compatibility
            if name.startswith('__Host-'):
                cookie = sanitize_host_cookie(cookie)
            
            cookies.append(cookie)
        
        if not cookies:
            logging.error("❌ No valid cookies found in Netscape file")
            return False
        
        # Create storage state structure
        storage_state = {
            "cookies": cookies,
            "origins": create_minimal_origins_structure(cookies),
            "localStorage": []
        }
        
        # Inject SOCS/CONSENT cookies if missing
        storage_state = inject_consent_cookies_if_missing(storage_state)
        
        # Ensure cookie directory exists
        COOKIE_DIR.mkdir(parents=True, exist_ok=True)
        
        # Write storage state file
        with open(SESSION_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(storage_state, f, indent=2)
        
        logging.info(f"✅ Successfully converted {len(cookies)} cookies to storage state")
        logging.info(f"📁 Storage state saved to: {SESSION_FILE_PATH}")
        return True
        
    except Exception as e:
        logging.error(f"❌ Failed to convert Netscape cookies: {e}")
        return False


def validate_netscape_format(content: str) -> bool:
    """Validate Netscape format before parsing."""
    if not content.strip():
        return False
    
    lines = content.strip().split('\n')
    # Check for Netscape format indicators
    has_comment = any(line.startswith('#') for line in lines[:5])
    has_tabs = any('\t' in line for line in lines if not line.startswith('#'))
    
    return has_comment and has_tabs


def sanitize_host_cookie(cookie: dict) -> dict:
    """
    Sanitize __Host- cookies for Playwright compatibility.
    
    __Host- cookies have strict requirements:
    - Must have secure=True
    - Must have path="/"
    - Must NOT have domain field (use url field instead)
    
    This prevents Playwright __Host- cookie validation errors.
    """
    # Requirement 12.1: Normalize with secure=True
    cookie["secure"] = True
    
    # Requirement 12.2: Normalize with path="/"
    cookie["path"] = "/"
    
    # Requirement 12.3: Remove domain field and use url field instead
    if "domain" in cookie:
        domain = cookie["domain"]
        # Remove leading dot if present (common in cookie files)
        if domain.startswith('.'):
            domain = domain[1:]
        # Store original domain as url for Playwright
        cookie["url"] = f"https://{domain}/"
        del cookie["domain"]
    
    return cookie


def create_minimal_origins_structure(cookies: list) -> list:
    """Create minimal origins structure for Playwright compatibility."""
    origins = set()
    
    # Extract unique domains from cookies
    for cookie in cookies:
        domain = cookie.get("domain", "")
        if domain:
            # Add both www and non-www variants for YouTube
            if "youtube" in domain.lower():
                origins.add("https://www.youtube.com")
                origins.add("https://youtube.com")
                origins.add("https://m.youtube.com")
            else:
                origins.add(f"https://{domain}")
    
    # Ensure YouTube origins are always present
    origins.update([
        "https://www.youtube.com",
        "https://youtube.com",
        "https://m.youtube.com"
    ])
    
    return [{"origin": origin, "localStorage": []} for origin in sorted(origins)]


def inject_consent_cookies_if_missing(storage_state: dict) -> dict:
    """Inject SOCS/CONSENT cookies if missing to prevent consent dialogs."""
    cookies = storage_state.get("cookies", [])
    
    # Check if SOCS or CONSENT cookies already exist
    has_consent = any(
        cookie.get("name") in ["SOCS", "CONSENT"] 
        for cookie in cookies
    )
    
    if not has_consent:
        logging.info("🍪 Injecting CONSENT cookie to prevent consent dialogs")
        
        # Requirement 13.2: Synthesize safe "accepted" values when missing
        # Requirement 13.3: Scope synthesized cookies to .youtube.com with long expiry
        consent_cookie = {
            "name": "CONSENT",
            "value": "YES+cb.20210328-17-p0.en+FX+1",  # Safe accepted value
            "domain": ".youtube.com",  # Scoped to .youtube.com
            "path": "/",
            "secure": True,
            "httpOnly": False,
            "expires": int(time.time()) + (365 * 24 * 60 * 60)  # Long expiry (1 year)
        }
        
        cookies.append(consent_cookie)
        storage_state["cookies"] = cookies
        
        logging.info("✅ CONSENT cookie injected successfully")
    else:
        logging.info("ℹ️  CONSENT/SOCS cookie already present")
    
    return storage_state


def inject_consent_cookies_after_generation(session_file_path: str) -> bool:
    """
    Inject SOCS/CONSENT cookies after session generation if missing.
    
    This function implements Requirements 13.1-13.6:
    - 13.1: Check for SOCS/CONSENT cookie presence after generation
    - 13.2: Synthesize safe "accepted" values when missing
    - 13.3: Scope synthesized cookies to .youtube.com with long expiry
    - 13.4: Ensure storage_state always includes consent cookies
    - 13.5: Implement synthesis after generation/conversion only
    - 13.6: Not at runtime
    
    Returns True if injection was successful or not needed, False on error.
    """
    try:
        # Load existing storage state
        with open(session_file_path, 'r', encoding='utf-8') as f:
            storage_state = json.load(f)
        
        cookies = storage_state.get("cookies", [])
        
        # Requirement 13.1: Check for SOCS/CONSENT cookie presence
        has_socs = any(cookie.get("name") == "SOCS" for cookie in cookies)
        has_consent = any(cookie.get("name") == "CONSENT" for cookie in cookies)
        
        if has_socs or has_consent:
            logging.info("ℹ️  SOCS/CONSENT cookie already present - no injection needed")
            return True
        
        logging.info("🍪 No SOCS/CONSENT cookies found - injecting safe consent cookie")
        
        # Requirement 13.2: Synthesize safe "accepted" values when missing
        # Requirement 13.3: Scope synthesized cookies to .youtube.com with long expiry
        consent_cookie = {
            "name": "CONSENT",
            "value": "YES+cb.20210328-17-p0.en+FX+1",  # Safe accepted value
            "domain": ".youtube.com",  # Scoped to .youtube.com
            "path": "/",
            "secure": True,
            "httpOnly": False,
            "expires": int(time.time()) + (365 * 24 * 60 * 60)  # Long expiry (1 year)
        }
        
        # Add the consent cookie to the storage state
        cookies.append(consent_cookie)
        storage_state["cookies"] = cookies
        
        # Requirement 13.4: Ensure storage_state always includes consent cookies
        # Write the updated storage state back to file
        with open(session_file_path, 'w', encoding='utf-8') as f:
            json.dump(storage_state, f, indent=2)
        
        logging.info("✅ CONSENT cookie injected successfully after session generation")
        return True
        
    except Exception as e:
        logging.error(f"❌ Failed to inject consent cookies after generation: {e}")
        return False


def verify_session_file():
    """Verify the generated session file is valid and contains expected data."""
    
    if not os.path.exists(SESSION_FILE_PATH):
        logging.error(f"❌ Session file not found: {SESSION_FILE_PATH}")
        return False
    
    try:
        with open(SESSION_FILE_PATH, 'r') as f:
            session_data = json.load(f)
        
        required_keys = ['cookies', 'origins']
        for key in required_keys:
            if key not in session_data:
                logging.error(f"❌ Session file missing required key: {key}")
                return False
        
        cookies = session_data['cookies']
        if not cookies:
            logging.error("❌ Session file contains no cookies")
            return False
        
        logging.info(f"✅ Session file verification passed - {len(cookies)} cookies found")
        return True
        
    except Exception as e:
        logging.error(f"❌ Session file verification failed: {e}")
        return False

def main():
    """Main function with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Generate or convert YouTube session cookies for Playwright",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cookie_generator.py                           # Generate new session
  python cookie_generator.py --from-netscape cookies.txt  # Convert Netscape cookies
        """
    )
    
    parser.add_argument(
        "--from-netscape",
        metavar="COOKIES_FILE",
        help="Convert Netscape cookies.txt file to storage_state.json"
    )
    
    args = parser.parse_args()
    
    try:
        if args.from_netscape:
            # Convert Netscape cookies
            logging.info("🔄 Converting Netscape cookies to storage state...")
            success = convert_netscape_to_storage_state(args.from_netscape)
            
            if success and verify_session_file():
                logging.info("🎉 Netscape conversion completed successfully!")
                print("\n" + "="*60)
                print("✅ SUCCESS: Netscape cookies converted to storage state!")
                print(f"📁 Input file: {os.path.abspath(args.from_netscape)}")
                print(f"📁 Output file: {os.path.abspath(SESSION_FILE_PATH)}")
                print("💡 Storage state ready for Playwright use")
                print("="*60)
            else:
                logging.error("❌ Netscape conversion failed")
                exit(1)
        else:
            # Generate new session
            logging.info("🚀 Generating new YouTube session...")
            generate_youtube_session()
            
            # Verify the generated session
            if verify_session_file():
                logging.info("🎉 Session generation and verification completed successfully!")
                print("\n" + "="*60)
                print("✅ SUCCESS: High-quality YouTube session generated!")
                print(f"📁 Session file: {os.path.abspath(SESSION_FILE_PATH)}")
                print("💡 Next: Update TranscriptService to use this session file")
                print("="*60)
            else:
                logging.error("❌ Session verification failed")
                exit(1)
                
    except KeyboardInterrupt:
        logging.info("⏹️  Operation interrupted by user")
        exit(1)
    except Exception as e:
        logging.error(f"❌ Operation failed: {e}")
        exit(1)


if __name__ == "__main__":
    main()
