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
        """Get user's YouTube playlists, including Watch Later and filtering out YouTube Music"""
        try:
            playlists = []
            
            # First, add the special "Watch Later" playlist
            logging.info("Attempting to access Watch Later playlist...")
            try:
                # Try different approaches to get Watch Later count
                watch_later_count = 0
                
                # Method 1: Try getting a sample to see if we have access
                test_request = self.youtube.playlistItems().list(
                    part="snippet",
                    playlistId="WL",
                    maxResults=1
                )
                test_response = test_request.execute()
                logging.info(f"Watch Later test response: {len(test_response.get('items', []))} items")
                
                if test_response.get('items'):
                    # We have access, now count properly
                    next_page_token = None
                    total_results = test_response.get('pageInfo', {}).get('totalResults', 0)
                    logging.info(f"Watch Later total results from pageInfo: {total_results}")
                    
                    # If totalResults is available and reasonable, use it
                    if total_results and total_results < 1000:
                        watch_later_count = total_results
                    else:
                        # Count manually by paginating
                        while True:
                            count_request = self.youtube.playlistItems().list(
                                part="id",
                                playlistId="WL",
                                maxResults=50,
                                pageToken=next_page_token
                            )
                            count_response = count_request.execute()
                            current_batch = len(count_response.get('items', []))
                            watch_later_count += current_batch
                            logging.info(f"Watch Later batch: {current_batch} items, total so far: {watch_later_count}")
                            
                            next_page_token = count_response.get('nextPageToken')
                            if not next_page_token or current_batch == 0:
                                break
                            
                            # Safety limit to prevent infinite loops
                            if watch_later_count > 2000:
                                logging.warning("Watch Later count exceeded 2000, stopping pagination")
                                break
                
                # Always add Watch Later
                playlists.append({
                    'id': 'WL',
                    'title': 'Watch Later',
                    'description': 'Your Watch Later playlist',
                    'thumbnail': '',
                    'video_count': watch_later_count,
                    'is_special': True
                })
                logging.info(f"Successfully added Watch Later playlist with {watch_later_count} videos")
                
            except HttpError as e:
                logging.error(f"HttpError accessing Watch Later playlist: {e}")
                logging.error(f"Error details: {e.resp.status}, {e.content}")
                # Still add it, but mark as having permission issues
                playlists.append({
                    'id': 'WL',
                    'title': 'Watch Later',
                    'description': 'Your Watch Later playlist (permission limited)',
                    'thumbnail': '',
                    'video_count': 0,
                    'is_special': True
                })
            except Exception as e:
                logging.error(f"Unexpected error accessing Watch Later: {e}")
                playlists.append({
                    'id': 'WL',
                    'title': 'Watch Later',
                    'description': 'Your Watch Later playlist (error accessing)',
                    'thumbnail': '',
                    'video_count': 0,
                    'is_special': True
                })
            
            # Get regular user playlists
            request = self.youtube.playlists().list(
                part="snippet,contentDetails",
                mine=True,
                maxResults=50
            )
            response = request.execute()
            
            for item in response.get('items', []):
                title = item['snippet']['title']
                description = item['snippet'].get('description', '')
                
                # Filter out YouTube Music playlists
                # YouTube Music playlists often have these characteristics:
                channel_title = item['snippet'].get('channelTitle', '')
                
                is_music_playlist = (
                    # Common YouTube Music playlist indicators
                    'Your Likes' in title or
                    'Liked Music' in title or
                    'My Mix' in title or
                    'Discover Mix' in title or
                    'New Release Mix' in title or
                    'Your Episode Mix' in title or
                    title.endswith(' Mix') or
                    title.endswith(' Radio') or
                    title.endswith(' Station') or
                    'Auto-generated by YouTube' in description or
                    'YouTube Music' in channel_title or
                    # Check playlist description for music indicators
                    'auto-generated' in description.lower() or
                    'youtube music' in description.lower() or
                    # Check if playlist has music-related tags
                    any(tag in title.lower() for tag in [
                        'mix', 'radio', 'station', 'auto-generated', 
                        'liked music', 'music videos', 'album', 'artist radio'
                    ]) or
                    # Check for specific playlist IDs that are typically music
                    (item['contentDetails']['itemCount'] > 0 and 
                     any(music_word in title.lower() for music_word in [
                         'music', 'songs', 'tracks', 'albums', 'artists'
                     ]) and
                     len(title.split()) <= 4)  # Short titles are often auto-generated
                )
                
                logging.debug(f"Playlist '{title}' - Music: {is_music_playlist}, Channel: {channel_title}")
                
                # Only add non-music playlists
                if not is_music_playlist:
                    playlists.append({
                        'id': item['id'],
                        'title': title,
                        'description': description,
                        'thumbnail': item['snippet']['thumbnails'].get('default', {}).get('url', ''),
                        'video_count': item['contentDetails']['itemCount'],
                        'is_special': False
                    })
            
            # Sort playlists: Watch Later first, then alphabetically
            playlists.sort(key=lambda x: (0 if x.get('is_special', False) else 1, x['title'].lower()))
            
            logging.info(f"Found {len(playlists)} playlists after filtering")
            for playlist in playlists[:5]:  # Log first 5 for debugging
                logging.info(f"Playlist: {playlist['title']} (special: {playlist.get('is_special', False)})")
            
            return playlists
            
        except HttpError as e:
            logging.error(f"YouTube API error getting playlists: {e}")
            return []

    def get_playlist_videos(self, playlist_id):
        """Get videos from a specific playlist, including Watch Later"""
        try:
            # Handle Watch Later playlist specially
            if playlist_id == 'WL':
                # For Watch Later, we need to get more items since it's commonly used
                request = self.youtube.playlistItems().list(
                    part="snippet,contentDetails",
                    playlistId=playlist_id,
                    maxResults=50
                )
            else:
                request = self.youtube.playlistItems().list(
                    part="snippet,contentDetails",
                    playlistId=playlist_id,
                    maxResults=50
                )
            
            response = request.execute()
            
            videos = []
            for item in response.get('items', []):
                # Skip private or deleted videos
                if item['snippet']['title'] == 'Private video' or item['snippet']['title'] == 'Deleted video':
                    continue
                    
                video_id = item['contentDetails']['videoId']
                videos.append({
                    'id': video_id,
                    'title': item['snippet']['title'],
                    'description': item['snippet'].get('description', ''),
                    'thumbnail': item['snippet']['thumbnails'].get('medium', {}).get('url', ''),
                    'channel_title': item['snippet']['channelTitle'],
                    'published_at': item['snippet']['publishedAt']
                })
            
            logging.info(f"Retrieved {len(videos)} videos from playlist {playlist_id}")
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
