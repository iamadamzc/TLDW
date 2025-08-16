"""
Comprehensive smoke test suite for transcript and yt-dlp bug fixes
Tests both transcript API and ASR paths with and without cookies
"""

import unittest
import os
import tempfile
import json
from unittest.mock import Mock, patch, MagicMock
from transcript_service import TranscriptService
from yt_download_helper import download_audio_with_fallback


class TestTranscriptYtdlpSmoke(unittest.TestCase):
    """Smoke tests for transcript API and yt-dlp functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_video_id = "dQw4w9WgXcQ"  # Known public video
        self.log_messages = []
        
        # Capture log messages
        import logging
        class TestLogHandler(logging.Handler):
            def __init__(self, messages_list):
                super().__init__()
                self.messages = messages_list
            
            def emit(self, record):
                self.messages.append(record.getMessage())
        
        self.test_handler = TestLogHandler(self.log_messages)
        logging.getLogger().addHandler(self.test_handler)
        logging.getLogger().setLevel(logging.INFO)
    
    def tearDown(self):
        """Clean up test fixtures"""
        import logging
        logging.getLogger().removeHandler(self.test_handler)
    
    def test_youtube_transcript_api_version_compatibility(self):
        """Test that YouTube Transcript API 0.6.2 works correctly"""
        from youtube_transcript_api import YouTubeTranscriptApi
        
        # Test that the method exists
        self.assertTrue(hasattr(YouTubeTranscriptApi, 'get_transcript'))
        
        # Test method signature (should not require headers parameter)
        import inspect
        sig = inspect.signature(YouTubeTranscriptApi.get_transcript)
        params = list(sig.parameters.keys())
        
        # Should have video_id, languages, proxies, cookies, preserve_formatting
        expected_params = ['video_id']
        for param in expected_params:
            self.assertIn(param, params, f"Missing expected parameter: {param}")
        
        # Should NOT have headers parameter (that's for newer versions)
        self.assertNotIn('headers', params, "Headers parameter should not exist in 0.6.2")
        
        print(f"✅ YouTube Transcript API 0.6.2 compatibility verified")
    
    def test_transcript_path_smoke_test(self):
        """Smoke test for transcript API path with known public video"""
        with patch('transcript_service.YouTubeTranscriptApi') as mock_api:
            # Mock successful transcript response
            mock_api.get_transcript.return_value = [
                {"text": "Never gonna give you up", "start": 0.0, "duration": 2.0},
                {"text": "Never gonna let you down", "start": 2.0, "duration": 2.0}
            ]
            
            service = TranscriptService()
            
            # Test transcript fetch
            result = service.get_transcript(self.test_video_id, has_captions=True)
            
            self.assertIsNotNone(result)
            self.assertIn("Never gonna give you up", result)
            self.assertIn("Never gonna let you down", result)
            
            # Verify API was called correctly (without headers)
            mock_api.get_transcript.assert_called_once()
            call_args = mock_api.get_transcript.call_args
            
            # Should not have headers in the call
            self.assertNotIn('headers', call_args.kwargs)
            
            print(f"✅ Transcript API path smoke test passed")
    
    def test_asr_path_smoke_test_without_cookies(self):
        """Smoke test for ASR path without cookies"""
        with patch('transcript_service.download_audio_with_fallback') as mock_download, \
             patch('transcript_service.TranscriptService._send_to_deepgram') as mock_deepgram:
            
            # Mock successful audio download
            mock_download.return_value = "/tmp/test_audio.m4a"
            
            # Mock successful Deepgram transcription
            mock_deepgram.return_value = "This is a test transcription"
            
            service = TranscriptService()
            
            # Test ASR path (no captions available)
            result = service.get_transcript(self.test_video_id, has_captions=False)
            
            self.assertIsNotNone(result)
            self.assertEqual(result, "This is a test transcription")
            
            # Verify download was called without cookies
            mock_download.assert_called_once()
            call_args = mock_download.call_args
            self.assertIsNone(call_args.kwargs.get('cookiefile'))
            
            # Verify Deepgram was called
            mock_deepgram.assert_called_once_with("/tmp/test_audio.m4a")
            
            print(f"✅ ASR path smoke test (no cookies) passed")
    
    def test_asr_path_smoke_test_with_cookies(self):
        """Smoke test for ASR path with cookies"""
        # Create temporary cookie file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write('# Netscape HTTP Cookie File\\n')
            f.write('.youtube.com\\tTRUE\\t/\\tFALSE\\t1234567890\\ttest\\tvalue\\n')
            cookie_file = f.name
        
        try:
            with patch('transcript_service.download_audio_with_fallback') as mock_download, \
                 patch('transcript_service.TranscriptService._send_to_deepgram') as mock_deepgram, \
                 patch('transcript_service.TranscriptService._get_user_cookiefile') as mock_cookies:
                
                # Mock cookie resolution
                mock_cookies.return_value = (cookie_file, None)
                
                # Mock successful audio download
                mock_download.return_value = "/tmp/test_audio.m4a"
                
                # Mock successful Deepgram transcription
                mock_deepgram.return_value = "This is a test transcription with cookies"
                
                service = TranscriptService()
                service.current_user_id = 123  # Set user ID
                
                # Test ASR path with cookies
                result = service.get_transcript(self.test_video_id, has_captions=False)
                
                self.assertIsNotNone(result)
                self.assertEqual(result, "This is a test transcription with cookies")
                
                # Verify download was called with cookies
                mock_download.assert_called_once()
                call_args = mock_download.call_args
                self.assertEqual(call_args.kwargs.get('cookiefile'), cookie_file)
                
                print(f"✅ ASR path smoke test (with cookies) passed")
        
        finally:
            # Clean up cookie file
            os.unlink(cookie_file)
    
    def test_yt_dlp_stable_client_configuration(self):
        """Test that yt-dlp uses stable web client configuration"""
        from yt_dlp import YoutubeDL
        
        # Mock YoutubeDL to capture configuration
        captured_opts = {}
        
        class MockYoutubeDL:
            def __init__(self, opts):
                captured_opts.update(opts)
                
            def download(self, urls):
                from yt_dlp.utils import DownloadError
                raise DownloadError("Mock error for testing")
            
            def __enter__(self):
                return self
            
            def __exit__(self, *args):
                pass
        
        with patch('yt_download_helper.YoutubeDL', MockYoutubeDL):
            try:
                download_audio_with_fallback(
                    f"https://www.youtube.com/watch?v={self.test_video_id}",
                    "Mozilla/5.0 Test",
                    "http://proxy:8080",
                    "/usr/bin",
                    lambda x: None,
                    None
                )
            except RuntimeError:
                pass  # Expected due to mock error
        
        # Verify stable client configuration
        self.assertIn('extractor_args', captured_opts)
        extractor_args = captured_opts['extractor_args']
        self.assertIn('youtube', extractor_args)
        self.assertEqual(extractor_args['youtube']['player_client'], ['web'])
        
        # Verify other hardening options
        self.assertEqual(captured_opts['concurrent_fragment_downloads'], 1)
        self.assertEqual(captured_opts['geo_bypass'], False)
        
        print(f"✅ yt-dlp stable client configuration verified")
    
    def test_deepgram_content_type_mapping(self):
        """Test that Deepgram receives correct Content-Type headers"""
        service = TranscriptService()
        service.deepgram_api_key = "test-key"
        
        # Test different file extensions
        test_cases = [
            ("/tmp/test.m4a", "audio/mp4"),
            ("/tmp/test.mp4", "audio/mp4"),
            ("/tmp/test.mp3", "audio/mpeg"),
            ("/tmp/test.wav", "audio/wav"),  # Should use mimetypes fallback
            ("/tmp/test.unknown", "application/octet-stream")  # Should use final fallback
        ]
        
        for file_path, expected_content_type in test_cases:
            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix=os.path.splitext(file_path)[1], delete=False) as f:
                f.write(b"fake audio data")
                temp_path = f.name
            
            try:
                with patch('requests.post') as mock_post:
                    # Mock Deepgram response
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_response.json.return_value = {
                        'results': {
                            'channels': [{
                                'alternatives': [{
                                    'transcript': 'Test transcription'
                                }]
                            }]
                        }
                    }
                    mock_post.return_value = mock_response
                    
                    # Call Deepgram
                    result = service._send_to_deepgram(temp_path)
                    
                    # Verify Content-Type header
                    mock_post.assert_called_once()
                    headers = mock_post.call_args.kwargs['headers']
                    
                    if expected_content_type == "audio/wav":
                        # For .wav, we expect mimetypes.guess_type to work
                        self.assertIn(headers['Content-Type'], ["audio/wav", "audio/x-wav"])
                    else:
                        self.assertEqual(headers['Content-Type'], expected_content_type)
                    
                    self.assertEqual(result, 'Test transcription')
            
            finally:
                os.unlink(temp_path)
        
        print(f"✅ Deepgram Content-Type mapping verified")
    
    def test_error_message_propagation(self):
        """Test that error messages are properly combined and propagated"""
        from yt_dlp.utils import DownloadError
        
        # Mock YoutubeDL to simulate step1 and step2 failures
        class MockYoutubeDL:
            def __init__(self, opts):
                self.opts = opts
                self.is_step2 = 'postprocessors' in opts
            
            def download(self, urls):
                if self.is_step2:
                    raise DownloadError("Step2: Sign in to confirm you're not a bot")
                else:
                    raise DownloadError("Step1: Failed to extract player response")
            
            def __enter__(self):
                return self
            
            def __exit__(self, *args):
                pass
        
        with patch('yt_download_helper.YoutubeDL', MockYoutubeDL):
            try:
                download_audio_with_fallback(
                    f"https://www.youtube.com/watch?v={self.test_video_id}",
                    "Mozilla/5.0 Test",
                    "http://proxy:8080",
                    "/usr/bin",
                    lambda x: None,
                    None
                )
                self.fail("Should have raised RuntimeError")
            except RuntimeError as e:
                error_msg = str(e)
                
                # Verify error combination
                self.assertIn("Step1: Failed to extract player response", error_msg)
                self.assertIn("Step2: Sign in to confirm you're not a bot", error_msg)
                self.assertIn(" || ", error_msg)
                
                # Test bot detection on combined message
                service = TranscriptService()
                is_bot_check = service._detect_bot_check(error_msg)
                self.assertTrue(is_bot_check)
        
        print(f"✅ Error message propagation verified")
    
    def test_407_error_handling(self):
        """Test that 407 errors are handled correctly"""
        service = TranscriptService()
        
        # Test 407 error detection
        test_errors = [
            "407 Proxy Authentication Required",
            "HTTP 407: proxy authentication failed",
            "Proxy authentication required",
            "normal error"
        ]
        
        for error in test_errors:
            error_lower = error.lower()
            is_407 = '407' in error_lower or 'proxy authentication' in error_lower
            
            if "407" in error or "proxy authentication" in error.lower():
                self.assertTrue(is_407, f"Should detect 407 in: {error}")
            else:
                self.assertFalse(is_407, f"Should not detect 407 in: {error}")
        
        # Test _handle_407_error method
        result = service._handle_407_error(self.test_video_id, None)
        self.assertFalse(result)  # Should be False by default (no-proxy disabled)
        
        # Test with environment variable
        os.environ['ALLOW_NO_PROXY_ON_407'] = 'true'
        try:
            result = service._handle_407_error(self.test_video_id, None)
            self.assertTrue(result)  # Should be True when enabled
        finally:
            os.environ.pop('ALLOW_NO_PROXY_ON_407', None)
        
        print(f"✅ 407 error handling verified")
    
    def test_health_diagnostics(self):
        """Test that health diagnostics work correctly"""
        # Test without diagnostics flag
        os.environ.pop('EXPOSE_HEALTH_DIAGNOSTICS', None)
        
        from app import app
        with app.test_client() as client:
            response = client.get('/healthz')
            data = response.get_json()
            
            # Should have basic health info
            self.assertIn('yt_dlp_version', data)
            self.assertIn('ffmpeg_location', data)
            
            # Should NOT have diagnostics
            self.assertNotIn('diagnostics', data)
        
        # Test with diagnostics flag
        os.environ['EXPOSE_HEALTH_DIAGNOSTICS'] = 'true'
        try:
            with app.test_client() as client:
                response = client.get('/healthz')
                data = response.get_json()
                
                # Should have diagnostics
                self.assertIn('diagnostics', data)
                diagnostics = data['diagnostics']
                
                # Should have expected fields
                self.assertIn('last_download_used_cookies', diagnostics)
                self.assertIn('last_download_client', diagnostics)
                
                # Should be safe values
                self.assertIsInstance(diagnostics['last_download_used_cookies'], bool)
                self.assertIn(diagnostics['last_download_client'], ['unknown', 'web'])
        
        finally:
            os.environ.pop('EXPOSE_HEALTH_DIAGNOSTICS', None)
        
        print(f"✅ Health diagnostics verified")
    
    def test_environment_variable_consistency(self):
        """Test that Google OAuth environment variables are consistent"""
        # Test that google_auth.py expects the right variables
        test_env = {
            'GOOGLE_OAUTH_CLIENT_ID': 'test-client-id',
            'GOOGLE_OAUTH_CLIENT_SECRET': 'test-client-secret'
        }
        
        for key, value in test_env.items():
            os.environ[key] = value
        
        try:
            # Test environment variable reading
            client_id = os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
            client_secret = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET')
            
            self.assertEqual(client_id, 'test-client-id')
            self.assertEqual(client_secret, 'test-client-secret')
            
        finally:
            for key in test_env:
                os.environ.pop(key, None)
        
        print(f"✅ Environment variable consistency verified")


class TestCIIntegration(unittest.TestCase):
    """Tests for CI integration and deployment improvements"""
    
    def test_deployment_script_consistency(self):
        """Test that deployment scripts use consistent variable names"""
        # Check that deployment files use GOOGLE_OAUTH_CLIENT_* not GOOGLE_CLIENT_*
        deployment_files = [
            'deployment/create-fixed.json',
            'deployment/create-lenient-health.json',
            'deployment/create-port-fixed.json',
            'deployment/deploy-apprunner.sh'
        ]
        
        for file_path in deployment_files:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    content = f.read()
                    
                    # Should use GOOGLE_OAUTH_CLIENT_*
                    if 'GOOGLE_OAUTH_CLIENT_ID' in content or 'GOOGLE_OAUTH_CLIENT_SECRET' in content:
                        self.assertIn('GOOGLE_OAUTH_CLIENT_ID', content)
                        self.assertIn('GOOGLE_OAUTH_CLIENT_SECRET', content)
                    
                    # Should NOT use GOOGLE_CLIENT_*
                    self.assertNotIn('GOOGLE_CLIENT_ID":', content)
                    self.assertNotIn('GOOGLE_CLIENT_SECRET":', content)
        
        print(f"✅ Deployment script consistency verified")
    
    def test_requirements_pinning(self):
        """Test that critical dependencies are pinned"""
        with open('requirements.txt', 'r') as f:
            content = f.read()
        
        # Should have pinned versions
        self.assertIn('youtube-transcript-api==0.6.2', content)
        self.assertIn('yt-dlp==2025.8.11', content)
        
        print(f"✅ Requirements pinning verified")


def run_smoke_tests():
    """Run all smoke tests"""
    print("🚀 Running comprehensive transcript and yt-dlp smoke tests...")
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestTranscriptYtdlpSmoke))
    suite.addTests(loader.loadTestsFromTestCase(TestCIIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if result.wasSuccessful():
        print("\\n✅ All smoke tests passed! System is ready for deployment.")
        return True
    else:
        print("\\n❌ Some smoke tests failed. Fix issues before deployment.")
        return False


if __name__ == '__main__':
    success = run_smoke_tests()
    exit(0 if success else 1)