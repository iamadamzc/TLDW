"""
Integration test for FFmpeg error handling enhancements.

This test verifies that the enhanced FFmpeg error handling integrates
properly with the existing transcript service infrastructure.
"""

import unittest
import tempfile
import os
from unittest.mock import patch, Mock
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from transcript_service import ASRAudioExtractor


class TestFFmpegIntegration(unittest.TestCase):
    """Integration tests for FFmpeg error handling."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.extractor = ASRAudioExtractor("test_api_key")
        
    @patch('transcript_service.subprocess.run')
    @patch('transcript_service.os.path.exists')
    @patch('transcript_service.os.path.getsize')
    @patch('log_events.evt')
    def test_ffmpeg_integration_with_structured_logging(self, mock_evt, mock_getsize, mock_exists, mock_run):
        """Test that FFmpeg integration works with structured logging."""
        # Mock successful ffmpeg execution
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = b"FFmpeg version info\nSuccessful conversion"
        mock_run.return_value = mock_result
        
        # Mock file operations
        mock_exists.return_value = True
        mock_getsize.return_value = 2048000  # 2MB file
        
        # Mock other dependencies
        with patch.object(self.extractor, '_build_ffmpeg_headers', return_value="User-Agent: test"):
            with patch('transcript_service._cookie_header_from_env_or_file', return_value=None):
                with patch.object(self.extractor, '_mask_ffmpeg_command_for_logging', return_value=['ffmpeg', 'test']):
                    
                    # Create a temporary file path
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                        wav_path = tmp.name
                    
                    try:
                        # Test the integration
                        result = self.extractor._extract_audio_to_wav(
                            "http://test.com/audio.m4a", 
                            wav_path
                        )
                        
                        # Verify success
                        self.assertTrue(result)
                        
                        # Verify structured logging was called
                        mock_evt.assert_called()
                        
                        # Verify the event structure
                        call_args = mock_evt.call_args
                        self.assertEqual(call_args[0][0], "stage_result")
                        
                        kwargs = call_args[1]
                        self.assertEqual(kwargs['stage'], "ffmpeg")
                        self.assertEqual(kwargs['outcome'], "success")
                        self.assertIn('dur_ms', kwargs)
                        self.assertEqual(kwargs['detail'], "extracted 2048000 bytes")
                        
                    finally:
                        # Clean up temporary file
                        if os.path.exists(wav_path):
                            os.unlink(wav_path)
                            
    def test_stderr_tail_extraction_integration(self):
        """Test that stderr tail extraction works correctly."""
        # Create test stderr with multiple lines
        test_stderr = '\n'.join([f"FFmpeg line {i}" for i in range(1, 51)])  # 50 lines
        stderr_bytes = test_stderr.encode('utf-8')
        
        # Test extraction
        result = self.extractor._extract_stderr_tail(stderr_bytes, max_lines=40)
        
        # Verify we get exactly 40 lines
        result_lines = result.split('\n')
        self.assertEqual(len(result_lines), 40)
        
        # Verify we get the last 40 lines (lines 11-50)
        self.assertEqual(result_lines[0], "FFmpeg line 11")
        self.assertEqual(result_lines[-1], "FFmpeg line 50")
        
    def test_method_exists_and_callable(self):
        """Test that the enhanced methods exist and are callable."""
        # Verify _extract_stderr_tail method exists
        self.assertTrue(hasattr(self.extractor, '_extract_stderr_tail'))
        self.assertTrue(callable(getattr(self.extractor, '_extract_stderr_tail')))
        
        # Verify _extract_audio_to_wav method exists
        self.assertTrue(hasattr(self.extractor, '_extract_audio_to_wav'))
        self.assertTrue(callable(getattr(self.extractor, '_extract_audio_to_wav')))
        
        # Test basic functionality
        result = self.extractor._extract_stderr_tail(b"test line 1\ntest line 2", max_lines=5)
        self.assertEqual(result, "test line 1\ntest line 2")


if __name__ == '__main__':
    unittest.main()