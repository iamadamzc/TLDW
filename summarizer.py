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

    def summarize_video(self, transcript_text, video_id):
        """
        Generate AI summary using OpenAI GPT-4o with specific formatting
        """
        if not transcript_text or not transcript_text.strip():
            logging.error("Empty or invalid transcript provided")
            raise ValueError("Transcript text is required for summarization")

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
            logging.error(f"OpenAI authentication failed - check API key: {e}")
            raise AuthenticationError("OpenAI API authentication failed. Please check your API key.")
        except RateLimitError as e:
            logging.error(f"OpenAI rate limit exceeded: {e}")
            raise RateLimitError("OpenAI API rate limit exceeded. Please try again later.")
        except APIError as e:
            logging.error(f"OpenAI API error: {e}")
            raise APIError(f"OpenAI API error: {str(e)}")
        except Exception as e:
            logging.error(f"Unexpected error during summarization: {e}")
            raise Exception(f"Unexpected error during video summarization: {str(e)}")

    def _add_timestamp_links(self, summary_text, video_id):
        """
        Convert timestamps like (12:34) or (1:05:22) to clickable YouTube links
        """
        def replace_timestamp(match):
            timestamp = match.group(1)
            total_seconds = self._timestamp_to_seconds(timestamp)
            return f'<a href="https://www.youtube.com/watch?v={video_id}&t={total_seconds}s">({timestamp})</a>'
        
        # Regex to find timestamps in format (MM:SS) or (HH:MM:SS)
        timestamp_pattern = r'\((\d{1,2}:\d{2}(?::\d{2})?)\)'
        
        return re.sub(timestamp_pattern, replace_timestamp, summary_text)

    def _timestamp_to_seconds(self, timestamp):
        """Convert timestamp string to total seconds"""
        parts = timestamp.split(':')
        if len(parts) == 2:  # MM:SS
            minutes, seconds = map(int, parts)
            return minutes * 60 + seconds
        elif len(parts) == 3:  # HH:MM:SS
            hours, minutes, seconds = map(int, parts)
            return hours * 3600 + minutes * 60 + seconds
        return 0
