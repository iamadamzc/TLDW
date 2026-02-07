import os
import re
import logging
import google.generativeai as genai

class VideoSummarizer:
    def __init__(self):
        self.google_api_key = os.environ.get("GOOGLE_API_KEY", "")
        if not self.google_api_key:
            logging.error("GOOGLE_API_KEY environment variable is required but not set")
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        
        try:
            genai.configure(api_key=self.google_api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash')
            logging.info("Gemini Flash client initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize Gemini client: {e}")
            raise

    def summarize_video(self, *, transcript_text: str, video_id: str) -> str:
        """
        Generate AI summary using Google Gemini 2.0 Flash with specific formatting.
        
        Args:
            transcript_text: The video transcript text (keyword-only)
            video_id: The video ID for timestamp links (keyword-only)
            
        Returns:
            Summary text or "No transcript available for this video." for empty input
        """
        # Strict input validation to prevent pipeline crashes
        if not isinstance(transcript_text, str):
            logging.warning(f"Invalid transcript_text type: {type(transcript_text)}")
            return "No transcript available for this video."
        
        if not isinstance(video_id, str):
            logging.warning(f"Invalid video_id type: {type(video_id)}")
            video_id = str(video_id) if video_id else "unknown"
        
        # Check for empty or whitespace-only transcript
        if not transcript_text.strip():
            logging.info(f"Empty transcript for video {video_id} - skipping LLM call")
            return "No transcript available for this video."

        # Additional validation for transcript length
        if len(transcript_text.strip()) < 10:
            logging.info(f"Transcript too short for video {video_id} ({len(transcript_text)} chars) - skipping LLM call")
            return "No transcript available for this video."

        try:
            logging.info(f"Starting summarization for video {video_id}")
            logging.debug(f"Transcript length: {len(transcript_text)} characters")
            
            # The prompt for the AI
            prompt_text = f"""Summarize the following YouTube video transcript. Your goal is to create an engaging and easily digestible summary for a busy professional. Adopt a tone that is clear, insightful, and slightly informal.

Your response must follow this exact format:

**IQ SUMMARY:**

**High-level statement:** A 3-5 sentence paragraph giving the overall essence and conclusion of the video.

**Main points:** A bulleted list of the most important points or arguments. The number of points should be appropriate for the video's length (e.g., 3 points for a short video, up to 7 for a long one). Each main point must be in bold and must end with a timestamp in the format (MM:SS) or (HH:MM:SS) if the video is over an hour.

**Subpoints:** Under each main point, include 2-3 indented, non-bolded subpoints that provide supporting details for that main point.

Transcript to summarize:
{transcript_text}
"""

            response = self.model.generate_content(
                prompt_text,
                generation_config={
                    'temperature': 0.7,
                    'max_output_tokens': 1500,
                }
            )
            
            if not response or not response.text:
                logging.error("Gemini API returned empty response")
                return "Summary unavailable: API returned empty response."
            
            summary = response.text
            logging.info(f"Successfully generated summary for video {video_id}")
            
            # Add timestamp links
            summary_with_links = self._add_timestamp_links(summary, video_id)
            
            return summary_with_links

        except Exception as e:
            logging.error(f"Gemini API error for video {video_id}: {e}")
            return f"Summary unavailable: {str(e)}"

    def _add_timestamp_links(self, summary_text, video_id):
        """
        Convert timestamps like (12:34) or (1:05:22) to clickable YouTube links
        """
        try:
            if not isinstance(summary_text, str) or not isinstance(video_id, str):
                return summary_text
            
            def replace_timestamp(match):
                try:
                    timestamp = match.group(1)
                    total_seconds = self._timestamp_to_seconds(timestamp)
                    return f'<a href="https://www.youtube.com/watch?v={video_id}&t={total_seconds}s">({timestamp})</a>'
                except Exception:
                    # If timestamp conversion fails, return original
                    return match.group(0)
            
            # Regex to find timestamps in format (MM:SS) or (HH:MM:SS)
            timestamp_pattern = r'\((\d{1,2}:\d{2}(?::\d{2})?)\)'
            
            return re.sub(timestamp_pattern, replace_timestamp, summary_text)
        except Exception as e:
            logging.warning(f"Failed to add timestamp links: {e}")
            return summary_text

    def _timestamp_to_seconds(self, timestamp):
        """Convert timestamp string to total seconds"""
        try:
            if not isinstance(timestamp, str):
                return 0
            
            parts = timestamp.split(':')
            if len(parts) == 2:  # MM:SS
                minutes, seconds = map(int, parts)
                return max(0, minutes * 60 + seconds)
            elif len(parts) == 3:  # HH:MM:SS
                hours, minutes, seconds = map(int, parts)
                return max(0, hours * 3600 + minutes * 60 + seconds)
            return 0
        except (ValueError, TypeError) as e:
            logging.warning(f"Failed to convert timestamp '{timestamp}': {e}")
            return 0
