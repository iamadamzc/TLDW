import os
import logging
import tempfile
import yt_dlp
import requests
from youtube_transcript_api import YouTubeTranscriptApi

class TranscriptService:
    def __init__(self):
        self.deepgram_api_key = os.environ.get("DEEPGRAM_API_KEY", "")

    def get_transcript(self, video_id):
        """
        Two-step transcript generation:
        1. Try youtube-transcript-api first (fast and free)
        2. Fallback to yt-dlp + Deepgram if needed
        """
        # Step 1: Try to get existing transcript
        transcript_text = self._get_existing_transcript(video_id)
        if transcript_text:
            logging.info(f"Got existing transcript for video {video_id}")
            return transcript_text
        
        # Step 2: Fallback to audio transcription
        logging.info(f"No existing transcript found for {video_id}, using Deepgram fallback")
        return self._transcribe_audio(video_id)

    def _get_existing_transcript(self, video_id):
        """Try to get existing transcript using youtube-transcript-api"""
        try:
            api = YouTubeTranscriptApi()
            transcript = api.fetch(video_id)
            transcript_text = ' '.join([snippet.text for snippet in transcript])
            return transcript_text
        except Exception as e:
            logging.warning(f"Could not get existing transcript for {video_id}: {e}")
            return None

    def _transcribe_audio(self, video_id):
        """Fallback: Download audio and transcribe with Deepgram"""
        if not self.deepgram_api_key:
            logging.error("Deepgram API key not provided")
            return None

        try:
            # Download audio using yt-dlp
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                temp_filename = temp_file.name

            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': temp_filename,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }

            video_url = f"https://www.youtube.com/watch?v={video_id}"
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])

            # Send to Deepgram for transcription
            transcript_text = self._send_to_deepgram(temp_filename)
            
            # Clean up temp file
            os.unlink(temp_filename)
            
            return transcript_text

        except Exception as e:
            logging.error(f"Error transcribing audio for {video_id}: {e}")
            return None

    def _send_to_deepgram(self, audio_file_path):
        """Send audio file to Deepgram for transcription"""
        try:
            headers = {
                'Authorization': f'Token {self.deepgram_api_key}',
                'Content-Type': 'audio/mp3'
            }
            
            with open(audio_file_path, 'rb') as audio_file:
                response = requests.post(
                    'https://api.deepgram.com/v1/listen',
                    headers=headers,
                    data=audio_file,
                    params={'punctuate': 'true', 'model': 'nova'}
                )
            
            if response.status_code == 200:
                result = response.json()
                transcript = result['results']['channels'][0]['alternatives'][0]['transcript']
                return transcript
            else:
                logging.error(f"Deepgram API error: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logging.error(f"Error sending to Deepgram: {e}")
            return None
