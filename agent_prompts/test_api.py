import logging
from youtube_transcript_api import YouTubeTranscriptApi

# --- CONFIGURE THESE ---
# NOTE: In production, these credentials are stored in AWS Secrets Manager
# under the OXYLABS_PROXY_CONFIG environment variable as a JSON object.
# For testing, you need to get your actual Oxylabs username and password.
VIDEO_ID = 'rNxC16mlO60'  # A video that definitely has a transcript
COOKIE_FILE = '/path/to/your/cookies.txt' # The full path to your cookie file
# If you are using Oxylabs, format your proxy URL like this:
# Using correct credentials
PROXY_URL = 'http://customer-new_user_LDKZF319z8jZt4KkHgR:update@pr.oxylabs.io:7777' 
# --- END CONFIGURATION ---

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

proxies = {
   'http': PROXY_URL,
   'https': PROXY_URL,
}

try:
    logging.info(f"Attempting to fetch transcript for {VIDEO_ID} using proxy and cookies...")
    
    # The library accepts a `proxies` dictionary
    transcript = YouTubeTranscriptApi.get_transcript(
        VIDEO_ID, 
        cookies=COOKIE_FILE, 
        proxies=proxies
    )
    
    logging.info("SUCCESS! Transcript fetched.")
    # print(transcript) # Uncomment to see the output

except Exception as e:
    logging.error(f"FAILED to fetch transcript: {e}")