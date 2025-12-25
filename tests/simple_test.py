#!/usr/bin/env python3
"""
Simple test for youtube-transcript-api v1.2.2
"""
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Test configuration
VIDEO_ID = 'rNxC16mlO60'  # Original video
BACKUP_VIDEO_ID = 'dQw4w9WgXcQ'  # Rick Roll as backup
PROXY_URL = 'http://customer-new_user_LDKZF-sessid-0322886770-sesstime-10:Change_Password1@pr.oxylabs.io:7777'

def test_simple_transcript():
    """Simple test of the transcript API using compatibility layer"""
    
    try:
        # Import compatibility layer
        from youtube_transcript_api_compat import (
            get_transcript, 
            list_transcripts, 
            check_api_migration_status
        )
        logging.info("✅ Successfully imported compatibility layer")
        
        # Check API status
        api_status = check_api_migration_status()
        logging.info(f"API Version: {api_status['api_version']}")
        logging.info(f"Migration Complete: {api_status['migration_complete']}")
        
        # Test 1: Try compatibility layer get_transcript
        try:
            logging.info(f"Testing compatibility layer get_transcript with {VIDEO_ID}...")
            transcript = get_transcript(VIDEO_ID, languages=['en', 'en-US'])
            logging.info(f"✅ SUCCESS! Got {len(transcript)} segments")
            return transcript
        except Exception as e:
            logging.error(f"Compatibility layer get_transcript failed: {e}")
        
        # Test 2: Try list_transcripts first, then get_transcript
        try:
            logging.info(f"Testing list_transcripts approach with {VIDEO_ID}...")
            transcript_list = list_transcripts(VIDEO_ID)
            logging.info(f"Found {len(transcript_list)} available transcripts")
            
            if transcript_list:
                # Get the first available language
                first_lang = transcript_list[0].get('language_code', 'en')
                logging.info(f"Using language: {first_lang}")
                
                transcript = get_transcript(VIDEO_ID, languages=[first_lang])
                logging.info(f"✅ SUCCESS! Got {len(transcript)} segments")
                return transcript
            
        except Exception as e:
            logging.error(f"List transcripts approach failed: {e}")
        
        # Test 3: Try with backup video
        logging.info(f"Trying backup video: {BACKUP_VIDEO_ID}")
        try:
            transcript = get_transcript(BACKUP_VIDEO_ID, languages=['en'])
            logging.info(f"✅ SUCCESS with backup video! Got {len(transcript)} segments")
            logging.info("Original video may not have transcripts available")
            return transcript
        except Exception as e:
            logging.error(f"Backup video failed: {e}")
        
        logging.error("❌ All approaches failed")
        return None
        
    except ImportError as e:
        logging.error(f"❌ Import failed: {e}")
        logging.error("Make sure youtube_transcript_api_compat.py is available")
        return None

def main():
    print("=== Simple YouTube Transcript API Test ===")
    
    result = test_simple_transcript()
    
    if result:
        print(f"\n✅ SUCCESS: Got {len(result)} transcript segments")
        if result:
            first_segment = result[0]
            print(f"First segment: {first_segment}")
            if isinstance(first_segment, dict) and 'text' in first_segment:
                print(f"Sample text: {first_segment['text'][:100]}...")
    else:
        print("\n❌ FAILED: Could not get transcript")
        print("\nPossible issues:")
        print("1. The video doesn't have transcripts/captions")
        print("2. The video is private or restricted")
        print("3. YouTube is blocking the requests")
        print("4. API version compatibility issue")
        
        print("\nTry these solutions:")
        print("1. Test with a different video ID that definitely has captions")
        print("2. Update the library: pip install --upgrade youtube-transcript-api")
        print("3. Check if the video is publicly accessible")

if __name__ == "__main__":
    main()
