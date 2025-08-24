import logging
import sys
import os

# Import the compatibility layer for API 1.2.2
try:
    from youtube_transcript_api_compat import (
        get_transcript, 
        list_transcripts, 
        check_api_migration_status,
        get_compat_instance
    )
    
    # Check API migration status
    api_status = check_api_migration_status()
    print(f"API Status: {api_status['api_version']}")
    print(f"Migration Complete: {api_status['migration_complete']}")
    
    # Also import the original API for comparison
    from youtube_transcript_api import YouTubeTranscriptApi
    import youtube_transcript_api
    print(f"youtube-transcript-api version: {getattr(youtube_transcript_api, '__version__', 'unknown')}")
        
except ImportError as e:
    print(f"ERROR: youtube-transcript-api or compatibility layer not available: {e}")
    print("Please install it with: pip install youtube-transcript-api")
    sys.exit(1)

# --- CONFIGURE THESE ---
# NOTE: In production, these credentials are stored in AWS Secrets Manager
# under the OXYLABS_PROXY_CONFIG environment variable as a JSON object.
# For testing, you need to get your actual Oxylabs username and password.
VIDEO_ID = 'rNxC16mlO60'  # A video that definitely has a transcript
COOKIE_FILE = '/path/to/your/cookies.txt' # The full path to your cookie file
# If you are using Oxylabs, format your proxy URL like this:
# Using correct credentials
PROXY_URL = 'http://customer-new_user_LDKZF-sessid-0322886770-sesstime-10:Change_Password1@pr.oxylabs.io:7777'
# --- END CONFIGURATION ---

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

proxies = {
   'http': PROXY_URL,
   'https': PROXY_URL,
}

def test_transcript_api():
    """Test the YouTube Transcript API using the compatibility layer for v1.2.2"""
    
    # Check if cookie file exists
    if COOKIE_FILE != '/path/to/your/cookies.txt' and not os.path.exists(COOKIE_FILE):
        logging.warning(f"Cookie file not found: {COOKIE_FILE}")
        logging.info("Continuing without cookies...")
        cookie_file = None
    else:
        cookie_file = COOKIE_FILE if COOKIE_FILE != '/path/to/your/cookies.txt' else None
    
    # Method 1: Test compatibility layer get_transcript function
    try:
        logging.info(f"Method 1: Using compatibility layer get_transcript for {VIDEO_ID}...")
        
        # Test with minimal parameters first
        transcript = get_transcript(VIDEO_ID)
        
        if transcript:
            logging.info(f"SUCCESS! Got {len(transcript)} transcript segments.")
            logging.info(f"First segment: {transcript[0]}")
            return transcript
            
    except Exception as e:
        logging.error(f"Method 1 (compatibility layer) failed: {e}")
        import traceback
        logging.debug(f"Full traceback: {traceback.format_exc()}")
    
    # Method 2: Test compatibility layer with language preferences
    try:
        logging.info(f"Method 2: Using compatibility layer with language preferences for {VIDEO_ID}...")
        
        transcript = get_transcript(
            VIDEO_ID, 
            languages=['en', 'en-US', 'en-GB'],
            cookies=cookie_file,
            proxies=proxies if 'customer-' in PROXY_URL else None
        )
        
        if transcript:
            logging.info(f"SUCCESS! Got {len(transcript)} transcript segments.")
            logging.info(f"First segment: {transcript[0]}")
            return transcript
            
    except Exception as e:
        logging.error(f"Method 2 (compatibility layer with options) failed: {e}")
        import traceback
        logging.debug(f"Full traceback: {traceback.format_exc()}")
    
    # Method 3: Test list_transcripts compatibility function
    try:
        logging.info(f"Method 3: Using compatibility layer list_transcripts for {VIDEO_ID}...")
        
        transcript_list = list_transcripts(VIDEO_ID)
        logging.info(f"Found {len(transcript_list)} available transcripts")
        
        if transcript_list:
            for i, transcript_info in enumerate(transcript_list):
                logging.info(f"Transcript {i}: {transcript_info}")
            
            # Now try to get the transcript using the first available language
            first_lang = transcript_list[0].get('language_code', 'en')
            transcript = get_transcript(VIDEO_ID, languages=[first_lang])
            
            if transcript:
                logging.info(f"SUCCESS! Got {len(transcript)} transcript segments.")
                logging.info(f"First segment: {transcript[0]}")
                return transcript
            
    except Exception as e:
        logging.error(f"Method 3 (list_transcripts) failed: {e}")
        import traceback
        logging.debug(f"Full traceback: {traceback.format_exc()}")
    
    # Method 4: Test with a different video that definitely has transcripts
    try:
        logging.info("Method 4: Trying with a known video that has transcripts...")
        test_video = "dQw4w9WgXcQ"  # Rick Roll - very likely to have captions
        
        transcript = get_transcript(test_video, languages=['en'])
        if transcript:
            logging.info(f"SUCCESS with test video! Got {len(transcript)} transcript segments.")
            logging.info("This confirms the compatibility layer works - the original video may not have transcripts")
            return transcript
                
    except Exception as e:
        logging.error(f"Method 4 (test video) failed: {e}")
    
    # Method 5: Test direct API instance (for debugging)
    try:
        logging.info("Method 5: Testing direct API instance for debugging...")
        
        compat_instance = get_compat_instance()
        logging.info(f"Compatibility instance API version: {compat_instance._api_version}")
        
        # Try to get transcript using the instance directly
        transcript = compat_instance.get_transcript(VIDEO_ID, languages=['en'])
        if transcript:
            logging.info(f"SUCCESS with direct instance! Got {len(transcript)} transcript segments.")
            return transcript
            
    except Exception as e:
        logging.error(f"Method 5 (direct instance) failed: {e}")
        import traceback
        logging.debug(f"Full traceback: {traceback.format_exc()}")
    
    # All methods failed
    logging.error("All methods failed!")
    logging.info("This might indicate:")
    logging.info("1. The video doesn't have transcripts available")
    logging.info("2. The video is private or restricted")
    logging.info("3. Network connectivity issues")
    logging.info("4. YouTube is blocking requests")
    
    return None

if __name__ == "__main__":
    print("=== YouTube Transcript API Test ===")
    result = test_transcript_api()
    
    if result:
        print(f"\n✅ SUCCESS: Retrieved {len(result)} transcript segments")
        if len(result) > 0:
            print(f"Sample text: {result[0].get('text', 'No text field')}")
    else:
        print("\n❌ FAILED: Could not retrieve transcript")
        print("\nTroubleshooting steps:")
        print("1. Check if youtube-transcript-api is installed: pip install youtube-transcript-api")
        print("2. Try a different video ID that definitely has captions")
        print("3. Check if the video is public and has transcripts available")
        print("4. Verify your proxy credentials are correct")
