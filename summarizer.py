import os
import re
import logging
from openai import OpenAI
from openai import AuthenticationError, RateLimitError, APIError

class VideoSummarizer:
    def __init__(self):
        self.openai_api_key = os.environ.get("OPENAI_API_KEY", "")
        if not self.openai_api_key:
            logging.error("OPENAI_API_KEY environment variable is required but not set")
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        try:
            self.client = OpenAI(api_key=self.openai_api_key)
            logging.info("OpenAI client initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize OpenAI client: {e}")
            raise

    def summarize_video(self, *, transcript_text: str, video_id: str) -> str:
        """
        Generate AI summary using OpenAI GPT-4o with specific formatting.
        
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
            prompt_text = f"""
Summarize the following YouTube video transcript. Your goal is to create an engaging and easily digestible summary for a busy professional. Adopt a tone that is clear, insightful, and slightly informal.

Your response must follow this exact format:

**IQ SUMMARY:**

**High-level statement:** A 3-5 sentence paragraph giving the overall essence and conclusion of the video.

**Main points:** A bulleted list of the most important points or arguments. The number of points should be appropriate for the video's length (e.g., 3 points for a short video, up to 7 for a long one). Each main point must be in bold and must end with a timestamp in the format (MM:SS) or (HH:MM:SS) if the video is over an hour.

**Subpoints:** Under each main point, include 2-3 indented, non-bolded subpoints that provide supporting details for that main point.

Transcript to summarize:
{transcript_text}
"""

            response = self.client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
                messages=[{"role": "user", "content": prompt_text}],
                max_tokens=1500,
                temperature=0.7
            )
            
            if not response.choices or not response.choices[0].message.content:
                logging.error("OpenAI API returned empty response")
                raise APIError("OpenAI API returned empty response")
            
            summary = response.choices[0].message.content
            logging.info(f"Successfully generated summary for video {video_id}")
            
            # Add timestamp links
            summary_with_links = self._add_timestamp_links(summary, video_id)
            
            return summary_with_links

        except AuthenticationError as e:
            logging.error(f"OpenAI authentication failed for video {video_id}: {e}")
            return "Summary unavailable: OpenAI authentication failed."
        except RateLimitError as e:
            logging.error(f"OpenAI rate limit exceeded for video {video_id}: {e}")
            return "Summary unavailable: API rate limit exceeded."
        except APIError as e:
            logging.error(f"OpenAI API error for video {video_id}: {e}")
            return "Summary unavailable: API error occurred."
        except Exception as e:
            logging.error(f"Unexpected error during summarization for video {video_id}: {e}")
            return "Summary unavailable: Processing error occurred."

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
