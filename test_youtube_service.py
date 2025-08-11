import unittest
from unittest.mock import Mock, patch, MagicMock
from googleapiclient.errors import HttpError
from youtube_service import YouTubeService


class TestYouTubeServiceWatchLater(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.access_token = "test_token"
        self.youtube_service = YouTubeService(self.access_token)
        
    @patch('youtube_service.build')
    def test_get_watch_later_count_empty_playlist(self, mock_build):
        """Test counting an empty Watch Later playlist."""
        # Mock YouTube API response for empty playlist
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        mock_response = {
            'items': [],
            'nextPageToken': None
        }
        mock_youtube.playlistItems().list().execute.return_value = mock_response
        
        # Create service instance and test
        service = YouTubeService(self.access_token)
        result = service._get_watch_later_count()
        
        # Assertions
        self.assertEqual(result['count'], 0)
        self.assertFalse(result['has_error'])
        self.assertEqual(result['error_message'], '')
        
    @patch('youtube_service.build')
    def test_get_watch_later_count_single_page(self, mock_build):
        """Test counting Watch Later playlist with single page of videos."""
        # Mock YouTube API response
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        mock_response = {
            'items': [
                {'snippet': {'title': 'Video 1'}},
                {'snippet': {'title': 'Video 2'}},
                {'snippet': {'title': 'Private video'}},  # Should be filtered out
                {'snippet': {'title': 'Video 3'}},
            ],
            'nextPageToken': None
        }
        mock_youtube.playlistItems().list().execute.return_value = mock_response
        
        # Create service instance and test
        service = YouTubeService(self.access_token)
        result = service._get_watch_later_count()
        
        # Assertions - should count 3 videos (excluding private video)
        self.assertEqual(result['count'], 3)
        self.assertFalse(result['has_error'])
        self.assertEqual(result['error_message'], '')
        
    @patch('youtube_service.build')
    def test_get_watch_later_count_multiple_pages(self, mock_build):
        """Test counting Watch Later playlist with pagination."""
        # Mock YouTube API response
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        # First page response
        first_page_response = {
            'items': [
                {'snippet': {'title': 'Video 1'}},
                {'snippet': {'title': 'Video 2'}},
            ],
            'nextPageToken': 'page2_token'
        }
        
        # Second page response
        second_page_response = {
            'items': [
                {'snippet': {'title': 'Video 3'}},
                {'snippet': {'title': 'Deleted video'}},  # Should be filtered out
                {'snippet': {'title': 'Video 4'}},
            ],
            'nextPageToken': None
        }
        
        # Configure mock to return different responses for different calls
        mock_youtube.playlistItems().list().execute.side_effect = [
            first_page_response,
            second_page_response
        ]
        
        # Create service instance and test
        service = YouTubeService(self.access_token)
        result = service._get_watch_later_count()
        
        # Assertions - should count 4 videos total (excluding deleted video)
        self.assertEqual(result['count'], 4)
        self.assertFalse(result['has_error'])
        self.assertEqual(result['error_message'], '')
        
    @patch('youtube_service.build')
    def test_get_watch_later_count_filters_private_deleted(self, mock_build):
        """Test that private and deleted videos are filtered out."""
        # Mock YouTube API response
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        mock_response = {
            'items': [
                {'snippet': {'title': 'Normal Video 1'}},
                {'snippet': {'title': 'Private video'}},
                {'snippet': {'title': 'Deleted video'}},
                {'snippet': {'title': 'Normal Video 2'}},
                {'snippet': {'title': 'Private video'}},
            ],
            'nextPageToken': None
        }
        mock_youtube.playlistItems().list().execute.return_value = mock_response
        
        # Create service instance and test
        service = YouTubeService(self.access_token)
        result = service._get_watch_later_count()
        
        # Assertions - should only count 2 normal videos
        self.assertEqual(result['count'], 2)
        self.assertFalse(result['has_error'])
        
    @patch('youtube_service.build')
    def test_get_watch_later_count_api_error_403(self, mock_build):
        """Test handling of 403 Forbidden API error."""
        # Mock YouTube API to raise HttpError
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        # Create mock HttpError with proper structure
        mock_resp = Mock()
        mock_resp.status = 403
        mock_resp.reason = 'Forbidden'
        http_error = HttpError(mock_resp, b'Forbidden')
        http_error.resp = mock_resp
        
        mock_youtube.playlistItems().list().execute.side_effect = http_error
        
        # Create service instance and test
        service = YouTubeService(self.access_token)
        result = service._get_watch_later_count()
        
        # Assertions
        self.assertEqual(result['count'], 0)
        self.assertTrue(result['has_error'])
        self.assertIn('Access denied', result['error_message'])
        
    @patch('youtube_service.build')
    def test_get_watch_later_count_api_error_429(self, mock_build):
        """Test handling of 429 Rate Limit API error."""
        # Mock YouTube API to raise HttpError
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        # Create mock HttpError with proper structure
        mock_resp = Mock()
        mock_resp.status = 429
        mock_resp.reason = 'Rate limit exceeded'
        http_error = HttpError(mock_resp, b'Rate limit exceeded')
        http_error.resp = mock_resp
        
        mock_youtube.playlistItems().list().execute.side_effect = http_error
        
        # Create service instance and test
        service = YouTubeService(self.access_token)
        result = service._get_watch_later_count()
        
        # Assertions
        self.assertEqual(result['count'], 0)
        self.assertTrue(result['has_error'])
        self.assertIn('Rate limit exceeded', result['error_message'])
        
    @patch('youtube_service.build')
    def test_get_watch_later_count_network_error(self, mock_build):
        """Test handling of network connection errors."""
        # Mock YouTube API to raise ConnectionError
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        mock_youtube.playlistItems().list().execute.side_effect = ConnectionError("Network error")
        
        # Create service instance and test
        service = YouTubeService(self.access_token)
        result = service._get_watch_later_count()
        
        # Assertions
        self.assertEqual(result['count'], 0)
        self.assertTrue(result['has_error'])
        self.assertIn('Network connection error', result['error_message'])
        
    @patch('youtube_service.build')
    def test_get_watch_later_count_unexpected_error(self, mock_build):
        """Test handling of unexpected errors."""
        # Mock YouTube API to raise unexpected error
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        mock_youtube.playlistItems().list().execute.side_effect = ValueError("Unexpected error")
        
        # Create service instance and test
        service = YouTubeService(self.access_token)
        result = service._get_watch_later_count()
        
        # Assertions
        self.assertEqual(result['count'], 0)
        self.assertTrue(result['has_error'])
        self.assertIn('Unexpected error', result['error_message'])


if __name__ == '__main__':
    unittest.main()


class TestYouTubeServicePlaylistIntegration(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.access_token = "test_token"
        
    @patch('youtube_service.build')
    def test_get_user_playlists_with_watch_later_success(self, mock_build):
        """Test get_user_playlists includes Watch Later with correct count."""
        # Mock YouTube API
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        # Mock Watch Later count response
        watch_later_response = {
            'items': [
                {'snippet': {'title': 'Video 1'}},
                {'snippet': {'title': 'Video 2'}},
            ],
            'nextPageToken': None
        }
        
        # Mock regular playlists response
        playlists_response = {
            'items': [
                {
                    'id': 'playlist1',
                    'snippet': {
                        'title': 'My Custom Playlist',
                        'description': 'User created playlist',
                        'channelTitle': 'User Channel',
                        'thumbnails': {'default': {'url': 'thumb.jpg'}}
                    },
                    'contentDetails': {'itemCount': 5}
                }
            ]
        }
        
        # Configure mock responses
        mock_youtube.playlistItems().list().execute.return_value = watch_later_response
        mock_youtube.playlists().list().execute.return_value = playlists_response
        
        # Create service and test
        service = YouTubeService(self.access_token)
        playlists = service.get_user_playlists()
        
        # Assertions
        self.assertEqual(len(playlists), 2)  # Watch Later + 1 regular playlist
        
        # Check Watch Later playlist
        watch_later = next((p for p in playlists if p['id'] == 'WL'), None)
        self.assertIsNotNone(watch_later)
        self.assertEqual(watch_later['title'], 'Watch Later')
        self.assertEqual(watch_later['video_count'], 2)
        self.assertTrue(watch_later['is_special'])
        
        # Check regular playlist
        regular = next((p for p in playlists if p['id'] == 'playlist1'), None)
        self.assertIsNotNone(regular)
        self.assertEqual(regular['title'], 'My Custom Playlist')
        self.assertEqual(regular['video_count'], 5)
        self.assertFalse(regular['is_special'])
        
    @patch('youtube_service.build')
    def test_get_user_playlists_with_watch_later_error(self, mock_build):
        """Test get_user_playlists handles Watch Later errors gracefully."""
        # Mock YouTube API
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        # Mock Watch Later to raise error
        mock_error = Mock()
        mock_error.resp.status = 403
        http_error = HttpError(mock_error, b'Forbidden')
        mock_youtube.playlistItems().list().execute.side_effect = http_error
        
        # Mock regular playlists response (should still work)
        playlists_response = {
            'items': [
                {
                    'id': 'playlist1',
                    'snippet': {
                        'title': 'My Custom Playlist',
                        'description': 'User created playlist',
                        'channelTitle': 'User Channel',
                        'thumbnails': {'default': {'url': 'thumb.jpg'}}
                    },
                    'contentDetails': {'itemCount': 3}
                }
            ]
        }
        mock_youtube.playlists().list().execute.return_value = playlists_response
        
        # Create service and test
        service = YouTubeService(self.access_token)
        playlists = service.get_user_playlists()
        
        # Assertions
        self.assertEqual(len(playlists), 2)  # Watch Later (with error) + 1 regular playlist
        
        # Check Watch Later playlist shows error
        watch_later = next((p for p in playlists if p['id'] == 'WL'), None)
        self.assertIsNotNone(watch_later)
        self.assertEqual(watch_later['title'], 'Watch Later (Error)')
        self.assertEqual(watch_later['video_count'], 0)
        self.assertTrue(watch_later['is_special'])
        self.assertIn('Error accessing', watch_later['description'])
        
        # Check regular playlist still works
        regular = next((p for p in playlists if p['id'] == 'playlist1'), None)
        self.assertIsNotNone(regular)
        self.assertEqual(regular['video_count'], 3)
        
    @patch('youtube_service.build')
    def test_get_user_playlists_sorting_watch_later_first(self, mock_build):
        """Test that Watch Later appears first in the playlist list."""
        # Mock YouTube API
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        # Mock Watch Later count response
        watch_later_response = {
            'items': [{'snippet': {'title': 'Video 1'}}],
            'nextPageToken': None
        }
        
        # Mock regular playlists response with multiple playlists
        playlists_response = {
            'items': [
                {
                    'id': 'playlist_z',
                    'snippet': {
                        'title': 'Z Playlist',  # Should be last alphabetically
                        'description': '',
                        'channelTitle': 'User Channel',
                        'thumbnails': {'default': {'url': ''}}
                    },
                    'contentDetails': {'itemCount': 1}
                },
                {
                    'id': 'playlist_a',
                    'snippet': {
                        'title': 'A Playlist',  # Should be first alphabetically
                        'description': '',
                        'channelTitle': 'User Channel',
                        'thumbnails': {'default': {'url': ''}}
                    },
                    'contentDetails': {'itemCount': 2}
                }
            ]
        }
        
        # Configure mock responses
        mock_youtube.playlistItems().list().execute.return_value = watch_later_response
        mock_youtube.playlists().list().execute.return_value = playlists_response
        
        # Create service and test
        service = YouTubeService(self.access_token)
        playlists = service.get_user_playlists()
        
        # Assertions
        self.assertEqual(len(playlists), 3)
        
        # Check sorting: Watch Later first, then alphabetical
        self.assertEqual(playlists[0]['id'], 'WL')  # Watch Later first
        self.assertEqual(playlists[1]['title'], 'A Playlist')  # Then alphabetical
        self.assertEqual(playlists[2]['title'], 'Z Playlist')
        
    @patch('youtube_service.build')
    def test_get_user_playlists_filters_music_playlists(self, mock_build):
        """Test that YouTube Music playlists are filtered out."""
        # Mock YouTube API
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        # Mock Watch Later count response
        watch_later_response = {
            'items': [],
            'nextPageToken': None
        }
        
        # Mock playlists response including music playlists
        playlists_response = {
            'items': [
                {
                    'id': 'playlist_normal',
                    'snippet': {
                        'title': 'My Videos',
                        'description': 'Normal playlist',
                        'channelTitle': 'User Channel',
                        'thumbnails': {'default': {'url': ''}}
                    },
                    'contentDetails': {'itemCount': 5}
                },
                {
                    'id': 'playlist_music',
                    'snippet': {
                        'title': 'Your Likes',  # Should be filtered out
                        'description': 'Auto-generated by YouTube',
                        'channelTitle': 'YouTube Music',
                        'thumbnails': {'default': {'url': ''}}
                    },
                    'contentDetails': {'itemCount': 10}
                },
                {
                    'id': 'playlist_mix',
                    'snippet': {
                        'title': 'My Mix',  # Should be filtered out
                        'description': '',
                        'channelTitle': 'User Channel',
                        'thumbnails': {'default': {'url': ''}}
                    },
                    'contentDetails': {'itemCount': 25}
                }
            ]
        }
        
        # Configure mock responses
        mock_youtube.playlistItems().list().execute.return_value = watch_later_response
        mock_youtube.playlists().list().execute.return_value = playlists_response
        
        # Create service and test
        service = YouTubeService(self.access_token)
        playlists = service.get_user_playlists()
        
        # Assertions - should only have Watch Later + 1 normal playlist
        self.assertEqual(len(playlists), 2)
        
        # Check that only normal playlist and Watch Later are included
        playlist_titles = [p['title'] for p in playlists]
        self.assertIn('Watch Later', playlist_titles)
        self.assertIn('My Videos', playlist_titles)
        self.assertNotIn('Your Likes', playlist_titles)
        self.assertNotIn('My Mix', playlist_titles)


class TestYouTubeServiceErrorScenarios(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.access_token = "test_token"
        
    @patch('youtube_service.build')
    @patch('youtube_service.logging')
    def test_watch_later_error_logging(self, mock_logging, mock_build):
        """Test that Watch Later errors are logged appropriately."""
        # Mock YouTube API
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        # Mock Watch Later to raise 403 error
        mock_error = Mock()
        mock_error.resp.status = 403
        http_error = HttpError(mock_error, b'Forbidden')
        mock_youtube.playlistItems().list().execute.side_effect = http_error
        
        # Mock regular playlists response
        playlists_response = {'items': []}
        mock_youtube.playlists().list().execute.return_value = playlists_response
        
        # Create service and test
        service = YouTubeService(self.access_token)
        playlists = service.get_user_playlists()
        
        # Verify error logging was called
        mock_logging.error.assert_called()
        mock_logging.warning.assert_called()
        
        # Check that error message contains expected content
        error_calls = [call[0][0] for call in mock_logging.error.call_args_list]
        warning_calls = [call[0][0] for call in mock_logging.warning.call_args_list]
        
        # Should log the API error
        self.assertTrue(any('Watch Later access denied' in call for call in error_calls))
        # Should log the warning about adding error playlist
        self.assertTrue(any('Added Watch Later playlist with error' in call for call in warning_calls))
        
    @patch('youtube_service.build')
    def test_multiple_error_types_handling(self, mock_build):
        """Test handling of different error types for Watch Later."""
        # Mock YouTube API
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        # Mock regular playlists response (should always work)
        playlists_response = {'items': []}
        mock_youtube.playlists().list().execute.return_value = playlists_response
        
        # Test different error scenarios
        error_scenarios = [
            (403, 'Access denied'),
            (404, 'not found'),
            (429, 'Rate limit exceeded'),
            (500, 'server error'),
            (502, 'server error'),
        ]
        
        for error_code, expected_message in error_scenarios:
            with self.subTest(error_code=error_code):
                # Reset mock
                mock_youtube.reset_mock()
                mock_youtube.playlists().list().execute.return_value = playlists_response
                
                # Mock Watch Later error
                mock_error = Mock()
                mock_error.resp.status = error_code
                http_error = HttpError(mock_error, f'Error {error_code}')
                mock_youtube.playlistItems().list().execute.side_effect = http_error
                
                # Create service and test
                service = YouTubeService(self.access_token)
                playlists = service.get_user_playlists()
                
                # Should still return playlists with Watch Later in error state
                self.assertGreaterEqual(len(playlists), 1)
                watch_later = next((p for p in playlists if p['id'] == 'WL'), None)
                self.assertIsNotNone(watch_later)
                self.assertEqual(watch_later['video_count'], 0)
                self.assertIn('Error', watch_later['title'])
                self.assertIn(expected_message.lower(), watch_later['description'].lower())
                
    @patch('youtube_service.build')
    def test_watch_later_error_doesnt_break_regular_playlists(self, mock_build):
        """Test that Watch Later errors don't prevent loading other playlists."""
        # Mock YouTube API
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        # Mock Watch Later to raise error
        mock_youtube.playlistItems().list().execute.side_effect = Exception("Watch Later failed")
        
        # Mock successful regular playlists response
        playlists_response = {
            'items': [
                {
                    'id': 'playlist1',
                    'snippet': {
                        'title': 'Working Playlist',
                        'description': 'This should work',
                        'channelTitle': 'User Channel',
                        'thumbnails': {'default': {'url': ''}}
                    },
                    'contentDetails': {'itemCount': 10}
                },
                {
                    'id': 'playlist2',
                    'snippet': {
                        'title': 'Another Playlist',
                        'description': 'This should also work',
                        'channelTitle': 'User Channel',
                        'thumbnails': {'default': {'url': ''}}
                    },
                    'contentDetails': {'itemCount': 5}
                }
            ]
        }
        mock_youtube.playlists().list().execute.return_value = playlists_response
        
        # Create service and test
        service = YouTubeService(self.access_token)
        playlists = service.get_user_playlists()
        
        # Should have Watch Later (with error) + 2 regular playlists
        self.assertEqual(len(playlists), 3)
        
        # Check Watch Later is in error state
        watch_later = next((p for p in playlists if p['id'] == 'WL'), None)
        self.assertIsNotNone(watch_later)
        self.assertEqual(watch_later['video_count'], 0)
        self.assertIn('Error', watch_later['title'])
        
        # Check regular playlists work normally
        regular_playlists = [p for p in playlists if p['id'] != 'WL']
        self.assertEqual(len(regular_playlists), 2)
        self.assertEqual(regular_playlists[0]['video_count'], 10)
        self.assertEqual(regular_playlists[1]['video_count'], 5)
        
    @patch('youtube_service.build')
    def test_error_message_formatting(self, mock_build):
        """Test that error messages are properly formatted for user display."""
        # Mock YouTube API
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        # Mock Watch Later to raise network error
        mock_youtube.playlistItems().list().execute.side_effect = ConnectionError("Network failed")
        
        # Mock regular playlists response
        playlists_response = {'items': []}
        mock_youtube.playlists().list().execute.return_value = playlists_response
        
        # Create service and test
        service = YouTubeService(self.access_token)
        playlists = service.get_user_playlists()
        
        # Check error message formatting
        watch_later = next((p for p in playlists if p['id'] == 'WL'), None)
        self.assertIsNotNone(watch_later)
        
        # Error should be indicated in title
        self.assertIn('Error', watch_later['title'])
        
        # Description should contain helpful error information
        self.assertIn('Error accessing Watch Later playlist:', watch_later['description'])
        self.assertIn('Network connection error', watch_later['description'])
        
    @patch('youtube_service.build')
    def test_large_playlist_safety_limit(self, mock_build):
        """Test that very large playlists are handled with safety limits."""
        # Mock YouTube API
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        # Create a mock response that simulates a very large playlist
        def create_large_response(page_num):
            items = [{'snippet': {'title': f'Video {i + page_num * 50}'}} for i in range(50)]
            # Simulate having many pages by always returning a next token for first 100+ pages
            next_token = f'page_{page_num + 1}' if page_num < 101 else None
            return {
                'items': items,
                'nextPageToken': next_token
            }
        
        # Mock to return large responses
        mock_youtube.playlistItems().list().execute.side_effect = [
            create_large_response(i) for i in range(102)  # 102 pages = 5100 videos
        ]
        
        # Mock regular playlists response
        playlists_response = {'items': []}
        mock_youtube.playlists().list().execute.return_value = playlists_response
        
        # Create service and test
        service = YouTubeService(self.access_token)
        playlists = service.get_user_playlists()
        
        # Should stop at safety limit and not count all videos
        watch_later = next((p for p in playlists if p['id'] == 'WL'), None)
        self.assertIsNotNone(watch_later)
        
        # Should stop at or before the safety limit (5000)
        self.assertLessEqual(watch_later['video_count'], 5000)
        # But should have counted a significant number
        self.assertGreater(watch_later['video_count'], 4000)


class TestYouTubeServicePerformance(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.access_token = "test_token"
        
    @patch('youtube_service.build')
    @patch('youtube_service.time')
    def test_performance_timing_logged(self, mock_time, mock_build):
        """Test that performance timing is measured and logged."""
        # Mock time.time() to return predictable values
        mock_time.time.side_effect = [1000.0, 1002.5]  # 2.5 second duration
        
        # Mock YouTube API
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        mock_response = {
            'items': [{'snippet': {'title': 'Video 1'}}],
            'nextPageToken': None
        }
        mock_youtube.playlistItems().list().execute.return_value = mock_response
        
        # Create service and test
        service = YouTubeService(self.access_token)
        
        with patch('youtube_service.logging') as mock_logging:
            result = service._get_watch_later_count()
            
            # Verify timing was logged
            mock_logging.info.assert_called()
            info_calls = [call[0][0] for call in mock_logging.info.call_args_list]
            
            # Should log the processing time
            timing_logged = any('took 2.50s' in call for call in info_calls)
            self.assertTrue(timing_logged, f"Expected timing log not found in: {info_calls}")
            
    @patch('youtube_service.build')
    def test_api_request_efficiency(self, mock_build):
        """Test that API requests use minimal required data parts."""
        # Mock YouTube API
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        mock_response = {
            'items': [{'snippet': {'title': 'Video 1'}}],
            'nextPageToken': None
        }
        mock_youtube.playlistItems().list().execute.return_value = mock_response
        
        # Create service and test
        service = YouTubeService(self.access_token)
        service._get_watch_later_count()
        
        # Verify API was called with minimal parts
        mock_youtube.playlistItems().list.assert_called_with(
            part="snippet",  # Only snippet, not contentDetails or other expensive parts
            playlistId="WL",
            maxResults=50,   # Reasonable batch size
            pageToken=None
        )
        
    @patch('youtube_service.build')
    def test_pagination_batch_size_optimization(self, mock_build):
        """Test that pagination uses optimal batch size."""
        # Mock YouTube API
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        # First page response
        first_page = {
            'items': [{'snippet': {'title': f'Video {i}'}} for i in range(50)],
            'nextPageToken': 'page2'
        }
        
        # Second page response
        second_page = {
            'items': [{'snippet': {'title': f'Video {i}'}} for i in range(50, 75)],
            'nextPageToken': None
        }
        
        mock_youtube.playlistItems().list().execute.side_effect = [first_page, second_page]
        
        # Create service and test
        service = YouTubeService(self.access_token)
        result = service._get_watch_later_count()
        
        # Verify optimal batch size was used
        calls = mock_youtube.playlistItems().list.call_args_list
        for call in calls:
            args, kwargs = call
            self.assertEqual(kwargs['maxResults'], 50)  # Optimal batch size
            
        # Verify correct total count
        self.assertEqual(result['count'], 75)


if __name__ == '__main__':
    # Run all tests
    unittest.main(verbosity=2)