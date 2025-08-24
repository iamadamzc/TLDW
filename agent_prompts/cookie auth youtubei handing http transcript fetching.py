# Add this method to TranscriptService class

def set_current_user_id(self, user_id: int):
    """Set the current user ID for cookie loading."""
    self.current_user_id = user_id

def get_captions_via_api(self, video_id: str, languages=("en", "en-US", "es")) -> str:
    """
    Enhanced YouTube Transcript API with proper cookie support.
    Uses direct HTTP method when library fails due to cookie limitations.
    """
    try:
        # Strategy 1: Try direct HTTP with user cookies first
        if self.current_user_id:
            logging.info(f"Attempting direct HTTP transcript fetch with user {self.current_user_id} cookies")
            transcript_text = get_transcript_with_cookies_fixed(
                video_id, 
                list(languages), 
                user_id=self.current_user_id,
                proxies=self.proxy_manager.proxy_dict_for("requests") if self.proxy_manager else None
            )
            if transcript_text:
                logging.info(f"Direct HTTP transcript success for {video_id}")
                return transcript_text

        # Strategy 2: Try original library approach (may work for some videos)
        logging.info(f"Attempting library-based transcript fetch for {video_id}")
        
        # Log API version for debugging
        import youtube_transcript_api as yta_mod
        logging.info(f"yt-transcript-api version={getattr(yta_mod, '__version__', 'unknown')}")

        try:
            # Try list_transcripts approach
            transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Find the best available transcript
            transcript_obj = None
            source_info = ""
            
            # Prefer manual transcripts in preferred languages
            for lang in languages:
                try:
                    transcript_obj = transcripts.find_transcript([lang])
                    if not transcript_obj.is_generated:
                        source_info = f"yt_api:{lang}:manual"
                        logging.info(f"Found manual transcript for {video_id}: {source_info}")
                        break
                except NoTranscriptFound:
                    continue
            
            # If no manual transcript found, try auto-generated
            if not transcript_obj:
                for lang in languages:
                    try:
                        transcript_obj = transcripts.find_generated_transcript([lang])
                        source_info = f"yt_api:{lang}:auto"
                        logging.info(f"Found auto transcript for {video_id}: {source_info}")
                        break
                    except NoTranscriptFound:
                        continue
            
            # If still no transcript, take any available
            if not transcript_obj:
                available = list(transcripts)
                if available:
                    transcript_obj = available[0]
                    source_info = f"yt_api:{transcript_obj.language_code}:{'auto' if transcript_obj.is_generated else 'manual'}"
                    logging.info(f"Found fallback transcript for {video_id}: {source_info}")
            
            if transcript_obj:
                # Fetch transcript segments (this should work without cookies for public videos)
                segments = transcript_obj.fetch()
                
                if segments:
                    # Convert to text
                    lines = []
                    for seg in segments:
                        text = seg.get("text", "").strip()
                        if text and text not in ["[Music]", "[Applause]", "[Laughter]"]:
                            lines.append(text)
                    
                    transcript_text = "\n".join(lines).strip()
                    if transcript_text:
                        logging.info(f"Library transcript success for {video_id}: {len(transcript_text)} chars")
                        return transcript_text
                        
        except Exception as library_error:
            logging.info(f"Library approach failed for {video_id}: {library_error}")
            
            # Strategy 3: Try direct get_transcript as final fallback
            try:
                segments = YouTubeTranscriptApi.get_transcript(video_id, languages=list(languages))
                if segments:
                    lines = [seg.get("text", "").strip() for seg in segments if seg.get("text", "").strip()]
                    transcript_text = "\n".join(lines).strip()
                    if transcript_text:
                        logging.info(f"Direct get_transcript success for {video_id}")
                        return transcript_text
            except Exception as direct_error:
                logging.warning(f"Direct get_transcript also failed for {video_id}: {direct_error}")

        return ""

    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        
        if "no element found" in error_msg or "ParseError" in error_type:
            logging.warning(f"YouTube Transcript API XML parsing error for {video_id}: {error_msg}")
            logging.info("This usually indicates YouTube is blocking requests or the video has no transcript")
        else:
            logging.warning(f"YouTube Transcript API error for {video_id}: {error_type}: {error_msg}")
        
        return ""

# Also update the main get_transcript method to set the user ID:

def get_transcript(self, video_id: str, language: str = "en", user_cookies=None, playwright_cookies=None, user_id: Optional[int] = None) -> str:
    """
    Enhanced transcript acquisition with proper user context.
    """
    # Set current user ID for cookie loading
    if user_id:
        self.set_current_user_id(user_id)
    
    # Rest of the existing method remains the same...
    correlation_id = generate_correlation_id()
    start_time = time.time()
    
    # ... existing implementation ...