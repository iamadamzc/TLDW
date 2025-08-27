"""
Test transcript service context integration.
"""

import unittest
import logging
import json
from unittest.mock import patch, Mock

from logging_setup import set_job_ctx, clear_job_ctx, configure_logging, JsonFormatter
from transcript_service import TranscriptService


class TestTranscriptContext(unittest.TestCase):
    """Test transcript service context integration."""
    
    def setUp(self):
        """Set up test environment."""
        clear_job_ctx()
        self.logger = configure_logging("INFO", use_json=True)
        
        # Capture log output
        self.log_capture = []
        self.handler = logging.StreamHandler()
        self.handler.emit = lambda record: self.log_capture.append(record)
        self.logger.addHandler(self.handler)
    
    def tearDown(self):
        """Clean up after tests."""
        clear_job_ctx()
        if hasattr(self, 'handler'):
            self.logger.removeHandler(self.handler)
    
    @patch('transcript_service.get_transcript')
    @patch('transcript_service.get_captions_via_timedtext')
    @patch('transcript_service.get_transcript_via_youtubei_with_timeout')
    def test_transcript_service_context_propagation(self, mock_youtubei, mock_timedtext, mock_yt_api):
        """Test that transcript service propagates context through pipeline stages."""
        # Mock all methods to return empty (so we go through all stages)
        mock_yt_api.return_value = ""
        mock_timedtext.return_value = ""
        mock_youtubei.return_value = ""
        
        # Set job context
        job_id = "test-job-transcript"
        video_id = "test-video-transcript"
        set_job_ctx(job_id=job_id, video_id=video_id)
        
        # Create transcript service and call get_transcript
        ts = TranscriptService()
        result = ts.get_transcript(video_id)
        
        # Verify that stage events were logged with context
        stage_logs = []
        for record in self.log_capture:
            if hasattr(record, 'event') and 'stage' in getattr(record, 'event', ''):
                formatter = JsonFormatter()
                log_json = formatter.format(record)
                log_data = json.loads(log_json)
                stage_logs.append(log_data)
        
        # Should have stage events for yt_api, timedtext, youtubei, and potentially asr
        self.assertGreater(len(stage_logs), 0)
        
        # Check that all stage events have proper context
        for log_data in stage_logs:
            self.assertEqual(log_data.get('job_id'), job_id)
            self.assertEqual(log_data.get('video_id'), video_id)
            self.assertIn('stage', log_data)
            self.assertIn('event', log_data)
            
            # Check for stage-specific context
            if log_data.get('stage') in ['timedtext', 'youtubei', 'asr']:
                self.assertIn('use_proxy', log_data)
    
    def test_transcript_service_sets_video_context(self):
        """Test that transcript service sets video context if not already set."""
        # Don't set any context initially
        video_id = "test-video-auto-context"
        
        # Mock to avoid actual transcript fetching
        with patch('transcript_service.get_transcript') as mock_yt_api:
            mock_yt_api.return_value = "Test transcript"
            
            ts = TranscriptService()
            result = ts.get_transcript(video_id)
            
            # Check that video context was set
            stage_logs = []
            for record in self.log_capture:
                if hasattr(record, 'event') and getattr(record, 'event') == 'stage_result':
                    formatter = JsonFormatter()
                    log_json = formatter.format(record)
                    log_data = json.loads(log_json)
                    stage_logs.append(log_data)
            
            # Should have at least one stage event with video_id
            self.assertGreater(len(stage_logs), 0)
            for log_data in stage_logs:
                self.assertEqual(log_data.get('video_id'), video_id)


if __name__ == '__main__':
    unittest.main()