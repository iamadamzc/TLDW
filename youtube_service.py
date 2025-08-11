import os
import logging
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials

class YouTubeService:
    def __init__(self, access_token):
        self.access_token = access_token
        # Create OAuth2 credentials object
        credentials = Credentials(token=access_token)
        self.youtube = build('youtube', 'v3', credentials=credentials)

    def get_user_playlists(self):
        """Get user's YouTube playlists"""
        try:
            request = self.youtube.playlists().list(
                part="snippet,contentDetails",
                mine=True,
                maxResults=50
            )
            response = request.execute()
            
            playlists = []
            for item in response.get('items', []):
                playlists.append({
                    'id': item['id'],
                    'title': item['snippet']['title'],
                    'description': item['snippet'].get('description', ''),
                    'thumbnail': item['snippet']['thumbnails'].get('default', {}).get('url', ''),
                    'video_count': item['contentDetails']['itemCount']
                })
            
            return playlists
        except HttpError as e:
            logging.error(f"YouTube API error getting playlists: {e}")
            return []

    def get_playlist_videos(self, playlist_id):
        """Get videos from a specific playlist"""
        try:
            request = self.youtube.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=playlist_id,
                maxResults=50
            )
            response = request.execute()
            
            videos = []
            for item in response.get('items', []):
                video_id = item['contentDetails']['videoId']
                videos.append({
                    'id': video_id,
                    'title': item['snippet']['title'],
                    'description': item['snippet'].get('description', ''),
                    'thumbnail': item['snippet']['thumbnails'].get('medium', {}).get('url', ''),
                    'channel_title': item['snippet']['channelTitle'],
                    'published_at': item['snippet']['publishedAt']
                })
            
            return videos
        except HttpError as e:
            logging.error(f"YouTube API error getting playlist videos: {e}")
            return []

    def get_video_details(self, video_id):
        """Get detailed information about a specific video"""
        try:
            request = self.youtube.videos().list(
                part="snippet,contentDetails",
                id=video_id
            )
            response = request.execute()
            
            if response.get('items'):
                item = response['items'][0]
                return {
                    'id': video_id,
                    'title': item['snippet']['title'],
                    'description': item['snippet'].get('description', ''),
                    'thumbnail': item['snippet']['thumbnails'].get('medium', {}).get('url', ''),
                    'channel_title': item['snippet']['channelTitle'],
                    'published_at': item['snippet']['publishedAt'],
                    'duration': item['contentDetails']['duration']
                }
            return None
        except HttpError as e:
            logging.error(f"YouTube API error getting video details: {e}")
            return None
