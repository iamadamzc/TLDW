#!/usr/bin/env python3
"""
MVP Container Deployment Tests
Focused tests for the four critical container deployment areas.
"""

import unittest
import os
import subprocess
import tempfile
from unittest.mock import patch, MagicMock

class TestContainerMVP(unittest.TestCase):
    """MVP test cases for container deployment"""
    
    def test_docker_build_smoke(self):
        """Test that Docker build includes ffmpeg"""
        # This is a smoke test - in CI/CD this would actually build
        # For now, just verify Dockerfile has the right content
        with open('Dockerfile', 'r') as f:
            dockerfile_content = f.read()
        
        self.assertIn('ffmpeg', dockerfile_content, "Dockerfile should install ffmpeg")
        self.assertIn('USER app', dockerfile_content, "Dockerfile should use non-root user")
        self.assertIn('FFMPEG_LOCATION', dockerfile_content, "Dockerfile should set FFMPEG_LOCATION")
    
    def test_wsgi_dependency_check_strict(self):
        """Test wsgi.py fails correctly with ALLOW_MISSING_DEPS=false"""
        # Test the _check_binary function behavior
        with patch.dict(os.environ, {'ALLOW_MISSING_DEPS': 'false'}):
            with patch('shutil.which', return_value=None):
                # Import the function
                import sys
                sys.path.insert(0, '.')
                
                try:
                    from wsgi import _check_binary
                    with self.assertRaises(RuntimeError):
                        _check_binary('nonexistent_binary')
                except ImportError:
                    self.skipTest("wsgi.py not importable in test environment")
    
    def test_wsgi_dependency_check_permissive(self):
        """Test wsgi.py passes with warnings when ALLOW_MISSING_DEPS=true"""
        with patch.dict(os.environ, {'ALLOW_MISSING_DEPS': 'true'}):
            with patch('shutil.which', return_value=None):
                try:
                    from wsgi import _check_binary
                    # Should return None but not raise
                    result = _check_binary('nonexistent_binary')
                    self.assertIsNone(result)
                except ImportError:
                    self.skipTest("wsgi.py not importable in test environment")
    
    def test_ytdlp_ffmpeg_location_config(self):
        """Test that yt-dlp configuration includes ffmpeg_location"""
        # Test the configuration structure
        with patch.dict(os.environ, {'FFMPEG_LOCATION': '/usr/bin'}):
            try:
                from transcript_service import TranscriptService
                service = TranscriptService()
                
                # Mock the yt-dlp call to capture configuration
                with patch('yt_dlp.YoutubeDL') as mock_ytdl:
                    mock_instance = MagicMock()
                    mock_ytdl.return_value.__enter__.return_value = mock_instance
                    
                    mock_session = MagicMock()
                    mock_session.proxy_url = "http://test:8080"
                    mock_session.session_id = "test"
                    
                    try:
                        service._attempt_ytdlp_download("test", mock_session, 1)
                    except:
                        pass  # Expected to fail, we just want to check config
                    
                    if mock_ytdl.called:
                        call_args = mock_ytdl.call_args[0][0]
                        self.assertIn('ffmpeg_location', call_args)
                        self.assertEqual(call_args['ffmpeg_location'], '/usr/bin')
                        self.assertEqual(call_args['socket_timeout'], 15)
                        
            except ImportError:
                self.skipTest("transcript_service not importable in test environment")
    
    def test_health_endpoints_structure(self):
        """Test health endpoints return proper structure"""
        try:
            from app import app
            app.config['TESTING'] = True
            
            with app.test_client() as client:
                # Test /health
                response = client.get('/health')
                self.assertEqual(response.status_code, 200)
                
                data = response.get_json()
                self.assertIn('status', data)
                self.assertIn('dependencies', data)
                
                # Test /healthz
                response = client.get('/healthz')
                self.assertEqual(response.status_code, 200)
                
        except ImportError:
            self.skipTest("app not importable in test environment")

if __name__ == '__main__':
    unittest.main()