import os
import logging
import time
from functools import wraps
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from token_manager import TokenManager

class AuthenticationError(Exception):
    """Custom exception for authentication failures"""
    pass

class YouTubeService:
    def __init__(self, user):
        """
        Initialize YouTubeService with user object for token management
        
        Args:
            user: User model instance with access_token and refresh_token
        """
        self.user = user
        self.token_manager = TokenManager(user)
        self.youtube = self._build_service()
    
    def _build_service(self):
        """Build YouTube service with valid credentials"""
        try:
            credentials = self.token_manager.get_valid_credentials()
            return build('youtube', 'v3', credentials=credentials)
        except ValueError as e:
            logging.error(f"Failed to build YouTube service for user {self.user.id}: {str(e)}")
            raise AuthenticationError(f"Authentication failed: {str(e)}")
    
    def _handle_auth_error(self, func):
        """
        Decorator to handle authentication errors with retry logic
        
        Args:
            func: Function to wrap with auth error handling
            
        Returns:
            Wrapped function with retry logic
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # First attempt
                return func(*args, **kwargs)
            except HttpError as e:
                if e.resp.status == 401:
                    logging.warning(f"Authentication error (401) for user {self.user.id}, attempting token refresh")
                    
                    # Try to refresh token and rebuild service
                    if self.token_manager.force_refresh():
                        try:
                            self.youtube = self._build_service()
                            logging.info(f"Successfully refreshed token and rebuilt service for user {self.user.id}")
                            
                            # Retry the original function
                            return func(*args, **kwargs)
                        except Exception as retry_error:
                            logging.error(f"Retry failed after token refresh for user {self.user.id}: {str(retry_error)}")
                            raise AuthenticationError("Authentication failed after token refresh")
                    else:
                        logging.error(f"Token refresh failed for user {self.user.id}")
                        raise AuthenticationError("Token refresh failed, re-authentication required")
                else:
                    # Re-raise non-auth errors
                    raise
            except Exception as e:
                # Log unexpected errors
                logging.error(f"Unexpected error in YouTube API call for user {self.user.id}: {str(e)}")
                raise
        
        return wrapper

    @_handle_auth_error
    def _get_watch_later_count(self):
        """
        Efficiently count videos in Watch Later playlist using pagination.
        
        Returns:
            dict: {
                'count': int,        # Number of accessible videos
                'has_error': bool,   # Whether API errors occurred
                'error_message': str # Error details for logging
            }
        """
        start_time = time.time()
        video_count = 0
        next_page_token = None
        
        try:
            logging.debug("Starting Watch Later playlist counting")
            
            while True:
                # Request only essential parts for efficient counting
                request = self.youtube.playlistItems().list(
                    part="snippet",  # Need snippet to filter private/deleted videos
                    playlistId="WL",
                    maxResults=50,
                    pageToken=next_page_token
                )
                
                response = request.execute()
                items = response.get('items', [])
                
                # Filter out private/deleted videos during counting
                valid_videos = 0
                for item in items:
                    title = item.get('snippet', {}).get('title', '')
                    if title not in ['Private video', 'Deleted video']:
                        valid_videos += 1
                
                video_count += valid_videos
                logging.debug(f"Watch Later page processed: {valid_videos} valid videos, {len(items)} total items")
                
                # Check for next page
                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break
                    
                # Safety check to prevent infinite loops with very large playlists
                if video_count > 5000:  # Reasonable upper limit
                    logging.warning(f"Watch Later playlist very large ({video_count}+ videos), stopping count")
                    break
            
            processing_time = time.time() - start_time
            logging.info(f"Successfully counted {video_count} videos in Watch Later playlist (took {processing_time:.2f}s)")
            
            return {
                'count': video_count,
                'has_error': False,
                'error_message': ''
            }
            
        except HttpError as e:
            processing_time = time.time() - start_time
            error_code = e.resp.status if hasattr(e, 'resp') else 'unknown'
            
            # Enhanced error handling with specific messages for different scenarios
            if error_code == 403:
                error_message = "Access denied to Watch Later playlist - check OAuth scopes"
                logging.error(f"Watch Later access denied after {processing_time:.2f}s: {str(e)}")
            elif error_code == 404:
                error_message = "Watch Later playlist not found"
                logging.error(f"Watch Later playlist not found after {processing_time:.2f}s: {str(e)}")
            elif error_code == 429:
                error_message = "Rate limit exceeded for Watch Later playlist"
                logging.error(f"Rate limit exceeded for Watch Later after {processing_time:.2f}s: {str(e)}")
            elif error_code in [500, 502, 503, 504]:
                error_message = "YouTube API server error - temporary issue"
                logging.error(f"YouTube API server error for Watch Later after {processing_time:.2f}s: {str(e)}")
            else:
                error_message = f"YouTube API error {error_code}"
                logging.error(f"YouTube API error {error_code} for Watch Later after {processing_time:.2f}s: {str(e)}")
            
            return {
                'count': 0,
                'has_error': True,
                'error_message': error_message
            }
            
        except ConnectionError as e:
            processing_time = time.time() - start_time
            error_message = "Network connection error accessing Watch Later playlist"
            logging.error(f"Network error for Watch Later after {processing_time:.2f}s: {str(e)}")
            
            return {
                'count': 0,
                'has_error': True,
                'error_message': error_message
            }
            
        except TimeoutError as e:
            processing_time = time.time() - start_time
            error_message = "Timeout error accessing Watch Later playlist"
            logging.error(f"Timeout error for Watch Later after {processing_time:.2f}s: {str(e)}")
            
            return {
                'count': 0,
                'has_error': True,
                'error_message': error_message
            }
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_message = f"Unexpected error counting Watch Later videos: {str(e)}"
            logging.error(f"Unexpected error for Watch Later after {processing_time:.2f}s: {error_message}")
            
            return {
                'count': 0,
                'has_error': True,
                'error_message': error_message
            }

    @_handle_auth_error
    def get_user_playlists(self):
        """Get user's YouTube playlists, including Watch Later and filtering out YouTube Music"""
        try:
            playlists = []
            
            # Add Watch Later playlist with dynamic video counting
            watch_later_result = self._get_watch_later_count()
            
            if watch_later_result['has_error']:
                # Add Watch Later with error indicator if counting failed
                playlists.append({
                    'id': 'WL',
                    'title': 'Watch Later (Error)',
                    'description': f'Error accessing Watch Later playlist: {watch_later_result["error_message"]}',
                    'thumbnail': '',
                    'video_count': 0,
                    'is_special': True
                })
                logging.warning(f"Added Watch Later playlist with error: {watch_later_result['error_message']}")
            else:
                # Add Watch Later with actual video count
                playlists.append({
                    'id': 'WL',
                    'title': 'Watch Later',
                    'description': 'Your Watch Later playlist',
                    'thumbnail': '',
                    'video_count': watch_later_result['count'],
                    'is_special': True
                })
                logging.info(f"Added Watch Later playlist with {watch_later_result['count']} videos")
            
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
                
                # More focused YouTube Music filtering - only filter obvious auto-generated playlists
                is_music_playlist = (
                    # Auto-generated YouTube Music playlists
                    'Your Likes' in title or
                    'Liked Music' in title or
                    'My Mix' in title or
                    'Discover Mix' in title or  
                    'New Release Mix' in title or
                    'Your Episode Mix' in title or
                    title.endswith(' Mix') and len(title.split()) <= 3 or  # Only short auto-generated mixes
                    title.endswith(' Radio') or
                    title.endswith(' Station') or
                    'Auto-generated by YouTube' in description or
                    'YouTube Music' in channel_title or
                    'auto-generated' in description.lower() or
                    'youtube music' in description.lower()
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

    @_handle_auth_error
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

    @_handle_auth_error
    def get_video_details(self, video_id):
        """Get detailed information about a specific video including caption availability"""
        try:
            request = self.youtube.videos().list(
                part="snippet,contentDetails",
                id=video_id
            )
            response = request.execute()
            
            if response.get('items'):
                item = response['items'][0]
                
                # Check if captions are available
                has_captions = item['contentDetails'].get('caption', 'false') == 'true'
                
                return {
                    'id': video_id,
                    'title': item['snippet']['title'],
                    'description': item['snippet'].get('description', ''),
                    'thumbnail': item['snippet']['thumbnails'].get('medium', {}).get('url', ''),
                    'channel_title': item['snippet']['channelTitle'],
                    'published_at': item['snippet']['publishedAt'],
                    'duration': item['contentDetails']['duration'],
                    'has_captions': has_captions
                }
            return None
        except HttpError as e:
            logging.error(f"YouTube API error getting video details: {e}")
            return None
