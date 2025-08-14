import unittest
from unittest.mock import Mock, patch, MagicMock
from googleapiclient.errors import HttpError

# Mock the imports to avoid Flask app context issues
with patch.dict('sys.modules', {'token_manager': Mock()}):
    from youtube_service import YouTubeService, AuthenticationError

class TestYouTubeService(unittest.TestCase):
    """Test cases for YouTubeService class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_user = Mock()
        self.mock_user.id = 123
        self.mock_user.access_token = "test_access_token"
        self.mock_user.refresh_token = "test_refresh_token"
        
        # Mock TokenManager
        self.token_manager_patcher = patch('youtube_service.TokenManager')
        self.mock_token_manager_class = self.token_manager_patcher.start()
        self.mock_token_manager = Mock()
        self.mock_token_manager_class.return_value = self.mock_token_manager
        
        # Mock build function
        self.build_patcher = patch('youtube_service.build')
        self.mock_build = self.build_patcher.start()
        self.mock_youtube = Mock()
        self.mock_build.return_value = self.mock_youtube
        
        # Mock credentials
        self.credentials_patcher = patch('youtube_service.Credentials')
        self.mock_credentials_class = self.credentials_patcher.start()
        self.mock_credentials = Mock()
        self.mock_credentials_class.return_value = self.mock_credentials
        
        self.mock_token_manager.get_valid_credentials.return_value = self.mock_credentials
    
    def tearDown(self):
        """Clean up test fixtures"""
        self.token_manager_patcher.stop()
        self.build_patcher.stop()
        self.credentials_patcher.stop()
    
    def test_init_success(self):
        """Test successful YouTubeService initialization"""
        service = YouTubeService(self.mock_user)
        
        self.assertEqual(service.user, self.mock_user)
        self.mock_token_manager_class.assert_called_once_with(self.mock_user)
        self.mock_token_manager.get_valid_credentials.assert_called_once()
        self.mock_build.assert_called_once_with('youtube', 'v3', credentials=self.mock_credentials)
    
    def test_init_authentication_error(self):
        """Test YouTubeService initialization with authentication error"""
        self.mock_token_manager.get_valid_credentials.side_effect = ValueError("No access token")
        
        with self.assertRaises(AuthenticationError) as context:
            YouTubeService(self.mock_user)
        
        self.assertIn("Authentication failed", str(context.exception))
    
    def test_handle_auth_error_decorator_success(self):
        """Test auth error decorator with successful API call"""
        service = YouTubeService(self.mock_user)
        
        # Mock a successful API method
        @service._handle_auth_error
        def mock_api_call():
            return "success"
        
        result = mock_api_call()
        self.assertEqual(result, "success")
    
    def test_handle_auth_error_decorator_401_retry_success(self):
        """Test auth error decorator with 401 error and successful retry"""
        service = YouTubeService(self.mock_user)
        
        # Mock HttpError with 401 status
        mock_response = Mock()
        mock_response.status = 401
        http_error = HttpError(mock_response, b'Unauthorized')
        
        call_count = 0
        
        @service._handle_auth_error
        def mock_api_call():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise http_error
            return "success_after_retry"
        
        # Mock successful token refresh
        self.mock_token_manager.force_refresh.return_value = True
        
        result = mock_api_call()
        
        self.assertEqual(result, "success_after_retry")
        self.assertEqual(call_count, 2)  # Called twice: initial + retry
        self.mock_token_manager.force_refresh.assert_called_once()
    
    def test_handle_auth_error_decorator_401_refresh_failure(self):
        """Test auth error decorator with 401 error and failed token refresh"""
        service = YouTubeService(self.mock_user)
        
        # Mock HttpError with 401 status
        mock_response = Mock()
        mock_response.status = 401
        http_error = HttpError(mock_response, b'Unauthorized')
        
        @service._handle_auth_error
        def mock_api_call():
            raise http_error
        
        # Mock failed token refresh
        self.mock_token_manager.force_refresh.return_value = False
        
        with self.assertRaises(AuthenticationError) as context:
            mock_api_call()
        
        self.assertIn("Token refresh failed", str(context.exception))
    
    def test_handle_auth_error_decorator_non_401_error(self):
        """Test auth error decorator with non-401 HTTP error"""
        service = YouTubeService(self.mock_user)
        
        # Mock HttpError with 403 status
        mock_response = Mock()
        mock_response.status = 403
        http_error = HttpError(mock_response, b'Forbidden')
        
        @service._handle_auth_error
        def mock_api_call():
            raise http_error
        
        # Should re-raise non-401 errors
        with self.assertRaises(HttpError):
            mock_api_call()
        
        # Should not attempt token refresh for non-401 errors
        self.mock_token_manager.force_refresh.assert_not_called()
    
    def test_get_user_playlists_success(self):
        """Test successful playlist retrieval"""
        service = YouTubeService(self.mock_user)
        
        # Mock Watch Later count
        with patch.object(service, '_get_watch_later_count') as mock_watch_later:
            mock_watch_later.return_value = {
                'count': 5,
                'has_error': False,
                'error_message': ''
            }
            
            # Mock playlists API response
            mock_request = Mock()
            mock_response = {
                'items': [
                    {
                        'id': 'playlist1',
                        'snippet': {
                            'title': 'Test Playlist',
                            'description': 'Test Description',
                            'thumbnails': {'default': {'url': 'test_url'}}
                        },
                        'contentDetails': {'itemCount': 10}
                    }
                ]
            }
            mock_request.execute.return_value = mock_response
            service.youtube.playlists.return_value.list.return_value = mock_request
            
            playlists = service.get_user_playlists()
            
            # Should have Watch Later + regular playlist
            self.assertEqual(len(playlists), 2)
            
            # Check Watch Later playlist
            watch_later = next(p for p in playlists if p['id'] == 'WL')
            self.assertEqual(watch_later['title'], 'Watch Later')
            self.assertEqual(watch_later['video_count'], 5)
            
            # Check regular playlist
            regular = next(p for p in playlists if p['id'] == 'playlist1')
            self.assertEqual(regular['title'], 'Test Playlist')
    
    def test_get_playlist_videos_success(self):
        """Test successful playlist video retrieval"""
        service = YouTubeService(self.mock_user)
        
        # Mock API response
        mock_request = Mock()
        mock_response = {
            'items': [
                {
                    'snippet': {
                        'title': 'Test Video',
                        'description': 'Test Description',
                        'thumbnails': {'medium': {'url': 'test_url'}},
                        'channelTitle': 'Test Channel',
                        'publishedAt': '2023-01-01T00:00:00Z'
                    },
                    'contentDetails': {
                        'videoId': 'test_video_id'
                    }
                }
            ]
        }
        mock_request.execute.return_value = mock_response
        service.youtube.playlistItems.return_value.list.return_value = mock_request
        
        videos = service.get_playlist_videos('test_playlist')
        
        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0]['id'], 'test_video_id')
        self.assertEqual(videos[0]['title'], 'Test Video')
    
    def test_get_video_details_success(self):
        """Test successful video details retrieval"""
        service = YouTubeService(self.mock_user)
        
        # Mock API response
        mock_request = Mock()
        mock_response = {
            'items': [
                {
                    'snippet': {
                        'title': 'Test Video',
                        'description': 'Test Description',
                        'thumbnails': {'medium': {'url': 'test_url'}},
                        'channelTitle': 'Test Channel',
                        'publishedAt': '2023-01-01T00:00:00Z'
                    },
                    'contentDetails': {
                        'duration': 'PT5M30S',
                        'caption': 'true'
                    }
                }
            ]
        }
        mock_request.execute.return_value = mock_response
        service.youtube.videos.return_value.list.return_value = mock_request
        
        details = service.get_video_details('test_video_id')
        
        self.assertEqual(details['id'], 'test_video_id')
        self.assertEqual(details['title'], 'Test Video')
        self.assertTrue(details['has_captions'])

if __name__ == '__main__':
    unittest.main()