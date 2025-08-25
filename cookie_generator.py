#!/usr/bin/env python3
"""
High-Quality Cookie Generation for YouTube Transcript API
=========================================================

This script performs a one-time "warm-up" session to generate natural-looking cookies
that bypass YouTube's anti-bot fingerprinting. The primary goal is to create a 
"warmed-up" session state that includes the critical CONSENT cookie.

Usage:
    python cookie_generator.py

Output:
    youtube_session.json - Complete browser session state with cookies
"""

import logging
import os
import time
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

def verify_session_file():
    """Verify the generated session file is valid and contains expected data."""
    
    if not os.path.exists(SESSION_FILE_PATH):
        logging.error(f"❌ Session file not found: {SESSION_FILE_PATH}")
        return False
    
    try:
        import json
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

if __name__ == "__main__":
    try:
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
        logging.info("⏹️  Session generation interrupted by user")
        exit(1)
    except Exception as e:
        logging.error(f"❌ Session generation failed: {e}")
        exit(1)
