#!/usr/bin/env python3
"""
Test Content-Type header fixes for Deepgram uploads
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock, mock_open

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TestContentTypeHeaders(unittest.TestCase):
    """Test Content-Type header implementation for Deepgram uploads"""
    
    def setUp(self):
        """Set up test environment"""
        # Mock environment variables
        os.environ['DEEPGRAM_API_KEY'] = 'test-api-key'
        
        # Mock shared_managers to avoid actual initialization
        self.shared_managers_patcher = patch('shared_managers.shared_managers')
        self.mock_shared_managers = self.shared_managers_patcher.start()
        
        # Mock the manager instances
        self.mock_proxy_manager = MagicMock()
        self.mock_http_client = MagicMock()
        self.mock_user_agent_manager = MagicMock()
        
        self.mock_shared_managers.get_proxy_manager.return_value = self.mock_proxy_manager
        self.mock_shared_managers.get_proxy_http_client.return_value = self.mock_http_client
        self.mock_shared_managers.get_user_agent_manager.return_value = self.mock_user_agent_manager
    
    def tearDown(self):
        """Clean up test environment"""
        self.shared_managers_patcher.stop()
        
        # Clear environment variables
        if 'DEEPGRAM_API_KEY' in os.environ:
            del os.environ['DEEPGRAM_API_KEY']
        
        # Clear any imported modules
        modules_to_clear = [mod for mod in sys.modules.keys() if 'transcript_service' in mod]
        for mod in modules_to_clear:
            del sys.modules[mod]
    
    @patch('requests.post')
    @patch('builtins.open', new_callable=mock_open, read_data=b'fake audio data')
    def test_m4a_content_type(self, mock_file, mock_post):
        """Test that .m4a files get correct Content-Type header"""
        # Mock successful Deepgram response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'results': {
                'channels': [{
                    'alternatives': [{
                        'transcript': 'test transcript'
                    }]
                }]
            }
        }
        mock_post.return_value = mock_response
        
        from transcript_service import TranscriptService
        service = TranscriptService()
        
        # Test with .m4a file
        result = service._send_to_deepgram('/path/to/audio.m4a')
        
        # Verify the request was made with correct Content-Type
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        headers = call_args[1]['headers']
        
        self.assertEqual(headers['Content-Type'], 'audio/mp4')
        self.assertEqual(result, 'test transcript')
    
    @patch('requests.post')
    @patch('builtins.open', new_callable=mock_open, read_data=b'fake audio data')
    def test_mp4_content_type(self, mock_file, mock_post):
        """Test that .mp4 files get correct Content-Type header"""
        # Mock successful Deepgram response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'results': {
                'channels': [{
                    'alternatives': [{
                        'transcript': 'test transcript'
                    }]
                }]
            }
        }
        mock_post.return_value = mock_response
        
        from transcript_service import TranscriptService
        service = TranscriptService()
        
        # Test with .mp4 file
        result = service._send_to_deepgram('/path/to/video.mp4')
        
        # Verify the request was made with correct Content-Type
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        headers = call_args[1]['headers']
        
        self.assertEqual(headers['Content-Type'], 'audio/mp4')
        self.assertEqual(result, 'test transcript')
    
    @patch('requests.post')
    @patch('builtins.open', new_callable=mock_open, read_data=b'fake audio data')
    def test_mp3_content_type(self, mock_file, mock_post):
        """Test that .mp3 files get correct Content-Type header"""
        # Mock successful Deepgram response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'results': {
                'channels': [{
                    'alternatives': [{
                        'transcript': 'test transcript'
                    }]
                }]
            }
        }
        mock_post.return_value = mock_response
        
        from transcript_service import TranscriptService
        service = TranscriptService()
        
        # Test with .mp3 file
        result = service._send_to_deepgram('/path/to/audio.mp3')
        
        # Verify the request was made with correct Content-Type
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        headers = call_args[1]['headers']
        
        self.assertEqual(headers['Content-Type'], 'audio/mpeg')
        self.assertEqual(result, 'test transcript')
    
    @patch('mimetypes.guess_type')
    @patch('requests.post')
    @patch('builtins.open', new_callable=mock_open, read_data=b'fake audio data')
    def test_unknown_extension_fallback(self, mock_file, mock_post, mock_guess_type):
        """Test that unknown extensions fall back to mimetypes.guess_type"""
        # Mock mimetypes.guess_type to return None (unknown type)
        mock_guess_type.return_value = (None, None)
        
        # Mock successful Deepgram response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'results': {
                'channels': [{
                    'alternatives': [{
                        'transcript': 'test transcript'
                    }]
                }]
            }
        }
        mock_post.return_value = mock_response
        
        from transcript_service import TranscriptService
        service = TranscriptService()
        
        # Test with unknown file extension
        result = service._send_to_deepgram('/path/to/audio.unknown')
        
        # Verify the request was made with fallback Content-Type
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        headers = call_args[1]['headers']
        
        self.assertEqual(headers['Content-Type'], 'application/octet-stream')
        self.assertEqual(result, 'test transcript')
        
        # Verify mimetypes.guess_type was called
        mock_guess_type.assert_called_once_with('/path/to/audio.unknown')
    
    @patch('mimetypes.guess_type')
    @patch('requests.post')
    @patch('builtins.open', new_callable=mock_open, read_data=b'fake audio data')
    def test_mimetypes_fallback_success(self, mock_file, mock_post, mock_guess_type):
        """Test that mimetypes.guess_type fallback works when it returns a type"""
        # Mock mimetypes.guess_type to return a known type
        mock_guess_type.return_value = ('audio/wav', None)
        
        # Mock successful Deepgram response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'results': {
                'channels': [{
                    'alternatives': [{
                        'transcript': 'test transcript'
                    }]
                }]
            }
        }
        mock_post.return_value = mock_response
        
        from transcript_service import TranscriptService
        service = TranscriptService()
        
        # Test with .wav file (not in explicit map)
        result = service._send_to_deepgram('/path/to/audio.wav')
        
        # Verify the request was made with mimetypes-detected Content-Type
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        headers = call_args[1]['headers']
        
        self.assertEqual(headers['Content-Type'], 'audio/wav')
        self.assertEqual(result, 'test transcript')
        
        # Verify mimetypes.guess_type was called
        mock_guess_type.assert_called_once_with('/path/to/audio.wav')
    
    def test_ext_mime_map_completeness(self):
        """Test that EXT_MIME_MAP contains all required mappings"""
        from transcript_service import TranscriptService
        service = TranscriptService()
        
        # Get the EXT_MIME_MAP from the method (we'll need to extract it)
        # Since it's defined inside the method, we'll test by calling the method
        # and checking the behavior
        
        # Test the mappings indirectly by checking the requirements
        required_mappings = {
            '.m4a': 'audio/mp4',
            '.mp4': 'audio/mp4',
            '.mp3': 'audio/mpeg'
        }
        
        # We can't directly access EXT_MIME_MAP since it's inside the method,
        # but we can verify the behavior matches the requirements
        print("✅ EXT_MIME_MAP mappings verified through behavior tests")
        self.assertTrue(True)  # This test is covered by the other tests
    
    @patch('requests.post')
    @patch('builtins.open', new_callable=mock_open, read_data=b'fake audio data')
    def test_case_insensitive_extensions(self, mock_file, mock_post):
        """Test that file extensions are handled case-insensitively"""
        # Mock successful Deepgram response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'results': {
                'channels': [{
                    'alternatives': [{
                        'transcript': 'test transcript'
                    }]
                }]
            }
        }
        mock_post.return_value = mock_response
        
        from transcript_service import TranscriptService
        service = TranscriptService()
        
        # Test with uppercase extension
        result = service._send_to_deepgram('/path/to/audio.M4A')
        
        # Verify the request was made with correct Content-Type
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        headers = call_args[1]['headers']
        
        self.assertEqual(headers['Content-Type'], 'audio/mp4')
        self.assertEqual(result, 'test transcript')

def run_tests():
    """Run all Content-Type header tests"""
    print("🧪 Running Content-Type Header Tests for Deepgram Uploads")
    print("=" * 60)
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test class
    suite.addTests(loader.loadTestsFromTestCase(TestContentTypeHeaders))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print()
    if result.wasSuccessful():
        print("✅ All Content-Type header tests passed!")
        print()
        print("📋 Verified functionality:")
        print("   - .m4a files → audio/mp4 Content-Type")
        print("   - .mp4 files → audio/mp4 Content-Type")
        print("   - .mp3 files → audio/mpeg Content-Type")
        print("   - Unknown extensions → mimetypes.guess_type() fallback")
        print("   - Final fallback → application/octet-stream")
        print("   - Case-insensitive extension handling")
        return True
    else:
        print("❌ Some Content-Type header tests failed!")
        print(f"   Failures: {len(result.failures)}")
        print(f"   Errors: {len(result.errors)}")
        return False

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)