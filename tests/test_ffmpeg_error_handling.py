"""
Unit tests for FFmpeg error handling enhancements.

Tests stderr capture, tail extraction, structured logging,
and timeout handling for the enhanced FFmpeg implementation.
"""

import unittest
import subprocess
import time
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

# Import the transcript service for testing
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_service import ASRAudioExtractor


class TestFFmpegErrorHandling(unittest.TestCase):
    """Test cases for enhanced FFmpeg error handling."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.service = ASRAudioExtractor("test_api_key")
        
    def test_extract_stderr_tail_basic(self):
        """Test basic stderr tail extraction functionality."""
        # Test with simple stderr content
        stderr_content = b"Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        result = self.service._extract_stderr_tail(stderr_content, max_lines=3)
        
        expected = "Line 3\nLine 4\nLine 5"
        self.assertEqual(result, expected)
        
    def test_extract_stderr_tail_fewer_lines_than_max(self):
        """Test stderr tail extraction when content has fewer lines than max."""
        stderr_content = b"Line 1\nLine 2"
        result = self.service._extract_stderr_tail(stderr_content, max_lines=5)
        
        expected = "Line 1\nLine 2"
        self.assertEqual(result, expected)
        
    def test_extract_stderr_tail_empty_stderr(self):
        """Test stderr tail extraction with empty stderr."""
        result = self.service._extract_stderr_tail(b"", max_lines=40)
        self.assertEqual(result, "")
        
        result = self.service._extract_stderr_tail(None, max_lines=40)
        self.assertEqual(result, "")
        
    def test_extract_stderr_tail_unicode_handling(self):
        """Test stderr tail extraction with unicode content."""
        # Test with unicode characters
        stderr_content = "Line with émojis 🎵\nAnother line with ñ\nFinal line".encode('utf-8')
        result = self.service._extract_stderr_tail(stderr_content, max_lines=2)
        
        expected = "Another line with ñ\nFinal line"
        self.assertEqual(result, expected)
        
    def test_extract_stderr_tail_decode_error_handling(self):
        """Test stderr tail extraction with invalid utf-8 bytes."""
        # Create invalid utf-8 bytes
        stderr_content = b'\xff\xfe\x00\x00invalid utf-8'
        result = self.service._extract_stderr_tail(stderr_content, max_lines=40)
        
        # Should handle decode error gracefully
        self.assertIn("stderr_decode_error", result)
        
    def test_extract_stderr_tail_forty_lines(self):
        """Test stderr tail extraction with exactly 40 lines (requirement)."""
        # Create 50 lines of stderr content
        lines = [f"Line {i+1}" for i in range(50)]
        stderr_content = '\n'.join(lines).encode('utf-8')
        
        result = self.service._extract_stderr_tail(stderr_content, max_lines=40)
        
        # Should get last 40 lines (lines 11-50)
        result_lines = result.split('\n')
        self.assertEqual(len(result_lines), 40)
        self.assertEqual(result_lines[0], "Line 11")
        self.assertEqual(result_lines[-1], "Line 50")
        
    @patch('transcript_service.subprocess.run')
    @patch('transcript_service.os.path.exists')
    @patch('transcript_service.os.path.getsize')
    @patch('log_events.evt')
    def test_ffmpeg_success_logging(self, mock_evt, mock_getsize, mock_exists, mock_run):
        """Test structured logging for FFmpeg success with byte counts."""
        # Mock successful ffmpeg execution
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = b""
        mock_run.return_value = mock_result
        
        # Mock file existence and size
        mock_exists.return_value = True
        mock_getsize.return_value = 1024000  # 1MB
        
        # Mock other dependencies
        with patch.object(self.service, '_build_ffmpeg_headers', return_value="User-Agent: test"):
            with patch('transcript_service._cookie_header_from_env_or_file', return_value=None):
                with patch.object(self.service, '_mask_ffmpeg_command_for_logging', return_value=['ffmpeg', 'test']):
                    
                    result = self.service._extract_audio_to_wav("http://test.com/audio.m4a", "/tmp/test.wav")
                    
                    # Should return True for success
                    self.assertTrue(result)
                    
                    # Should call evt with success outcome and byte count
                    mock_evt.assert_called()
                    call_args = mock_evt.call_args
                    self.assertEqual(call_args[0][0], "stage_result")  # First positional arg
                    
                    kwargs = call_args[1]
                    self.assertEqual(kwargs['stage'], "ffmpeg")
                    self.assertEqual(kwargs['outcome'], "success")
                    self.assertIn('dur_ms', kwargs)
                    self.assertEqual(kwargs['detail'], "extracted 1024000 bytes")
                    
    @patch('transcript_service.subprocess.run')
    @patch('log_events.evt')
    def test_ffmpeg_timeout_logging(self, mock_evt, mock_run):
        """Test structured logging for FFmpeg timeout with duration."""
        # Mock timeout exception
        timeout_exception = subprocess.TimeoutExpired(['ffmpeg'], 120)
        timeout_exception.stderr = b"FFmpeg timeout stderr\nLast line of output"
        mock_run.side_effect = timeout_exception
        
        # Mock other dependencies
        with patch.object(self.service, '_build_ffmpeg_headers', return_value="User-Agent: test"):
            with patch('transcript_service._cookie_header_from_env_or_file', return_value=None):
                with patch.object(self.service, '_mask_ffmpeg_command_for_logging', return_value=['ffmpeg', 'test']):
                    
                    result = self.service._extract_audio_to_wav("http://test.com/audio.m4a", "/tmp/test.wav")
                    
                    # Should return False for timeout
                    self.assertFalse(result)
                    
                    # Should call evt with timeout outcome and duration
                    mock_evt.assert_called()
                    call_args = mock_evt.call_args
                    self.assertEqual(call_args[0][0], "stage_result")
                    
                    kwargs = call_args[1]
                    self.assertEqual(kwargs['stage'], "ffmpeg")
                    self.assertEqual(kwargs['outcome'], "timeout")
                    self.assertIn('dur_ms', kwargs)
                    self.assertIn('timeout after', kwargs['detail'])
                    self.assertEqual(kwargs['stderr_tail'], "FFmpeg timeout stderr\nLast line of output")
                    
    @patch('transcript_service.subprocess.run')
    @patch('log_events.evt')
    def test_ffmpeg_error_logging_with_stderr_tail(self, mock_evt, mock_run):
        """Test structured logging for FFmpeg errors with stderr tail extraction."""
        # Create stderr with more than 40 lines
        stderr_lines = [f"FFmpeg error line {i+1}" for i in range(50)]
        stderr_content = '\n'.join(stderr_lines).encode('utf-8')
        
        # Mock CalledProcessError with stderr
        error = subprocess.CalledProcessError(1, ['ffmpeg'])
        error.stderr = stderr_content
        mock_run.side_effect = error
        
        # Mock other dependencies
        with patch.object(self.service, '_build_ffmpeg_headers', return_value="User-Agent: test"):
            with patch('transcript_service._cookie_header_from_env_or_file', return_value=None):
                with patch.object(self.service, '_mask_ffmpeg_command_for_logging', return_value=['ffmpeg', 'test']):
                    
                    result = self.service._extract_audio_to_wav("http://test.com/audio.m4a", "/tmp/test.wav")
                    
                    # Should return False for error
                    self.assertFalse(result)
                    
                    # Should call evt with error outcome and stderr tail
                    mock_evt.assert_called()
                    call_args = mock_evt.call_args
                    self.assertEqual(call_args[0][0], "stage_result")
                    
                    kwargs = call_args[1]
                    self.assertEqual(kwargs['stage'], "ffmpeg")
                    self.assertEqual(kwargs['outcome'], "error")
                    self.assertIn('dur_ms', kwargs)
                    self.assertEqual(kwargs['detail'], "exit_code=1")
                    
                    # Check stderr tail contains last 40 lines
                    stderr_tail = kwargs['stderr_tail']
                    tail_lines = stderr_tail.split('\n')
                    self.assertEqual(len(tail_lines), 40)
                    self.assertEqual(tail_lines[0], "FFmpeg error line 11")  # Line 11 is first of last 40
                    self.assertEqual(tail_lines[-1], "FFmpeg error line 50")  # Line 50 is last
                    
    @patch('transcript_service.subprocess.run')
    @patch('transcript_service.os.path.exists')
    @patch('transcript_service.os.path.getsize')
    @patch('log_events.evt')
    def test_ffmpeg_empty_file_error_logging(self, mock_evt, mock_getsize, mock_exists, mock_run):
        """Test structured logging when FFmpeg produces empty file."""
        # Mock successful ffmpeg execution but empty file
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = b""
        mock_run.return_value = mock_result
        
        # Mock file exists but is empty
        mock_exists.return_value = True
        mock_getsize.return_value = 0  # Empty file
        
        # Mock other dependencies
        with patch.object(self.service, '_build_ffmpeg_headers', return_value="User-Agent: test"):
            with patch('transcript_service._cookie_header_from_env_or_file', return_value=None):
                with patch.object(self.service, '_mask_ffmpeg_command_for_logging', return_value=['ffmpeg', 'test']):
                    
                    result = self.service._extract_audio_to_wav("http://test.com/audio.m4a", "/tmp/test.wav")
                    
                    # Should return False for empty file
                    self.assertFalse(result)
                    
                    # Should call evt with error outcome for empty file
                    mock_evt.assert_called()
                    call_args = mock_evt.call_args
                    self.assertEqual(call_args[0][0], "stage_result")
                    
                    kwargs = call_args[1]
                    self.assertEqual(kwargs['stage'], "ffmpeg")
                    self.assertEqual(kwargs['outcome'], "error")
                    self.assertIn('dur_ms', kwargs)
                    self.assertEqual(kwargs['detail'], "empty file produced")
                    
    def test_duration_calculation_accuracy(self):
        """Test that duration calculation is accurate and in milliseconds."""
        # Test the duration calculation by mocking time.time()
        start_time = 1000.0
        end_time = 1001.5  # 1.5 seconds later
        
        with patch('time.time', side_effect=[start_time, end_time]):
            with patch('transcript_service.subprocess.run') as mock_run:
                with patch('transcript_service.os.path.exists', return_value=True):
                    with patch('transcript_service.os.path.getsize', return_value=1000):
                        with patch('log_events.evt') as mock_evt:
                            with patch.object(self.service, '_build_ffmpeg_headers', return_value="User-Agent: test"):
                                with patch('transcript_service._cookie_header_from_env_or_file', return_value=None):
                                    with patch.object(self.service, '_mask_ffmpeg_command_for_logging', return_value=['ffmpeg', 'test']):
                                        
                                        # Mock successful execution
                                        mock_result = Mock()
                                        mock_result.returncode = 0
                                        mock_result.stderr = b""
                                        mock_run.return_value = mock_result
                                        
                                        self.service._extract_audio_to_wav("http://test.com/audio.m4a", "/tmp/test.wav")
                                        
                                        # Check that duration is calculated correctly (1500ms)
                                        call_args = mock_evt.call_args
                                        kwargs = call_args[1]
                                        self.assertEqual(kwargs['dur_ms'], 1500)


if __name__ == '__main__':
    unittest.main()