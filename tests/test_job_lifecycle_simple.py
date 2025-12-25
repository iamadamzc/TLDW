"""
Simple test to verify job lifecycle tracking functionality.
"""

import unittest
import logging
import json
from io import StringIO

from log_events import job_received, job_finished, video_processed, classify_error_type
from logging_setup import configure_logging, set_job_ctx, clear_job_ctx, JsonFormatter


class TestJobLifecycleSimple(unittest.TestCase):
    """Simple test for job lifecycle events."""
    
    def setUp(self):
        """Set up test logging."""
        self.log_stream = StringIO()
        self.handler = logging.StreamHandler(self.log_stream)
        self.handler.setFormatter(JsonFormatter())
        
        self.logger = logging.getLogger()
        self.logger.handlers.clear()
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)
        
        clear_job_ctx()
    
    def tearDown(self):
        """Clean up."""
        clear_job_ctx()
        self.logger.handlers.clear()
    
    def get_log_events(self):
        """Parse JSON log events."""
        events = []
        for line in self.log_stream.getvalue().strip().split('\n'):
            if line.strip():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return events
    
    def test_basic_job_lifecycle(self):
        """Test basic job lifecycle events."""
        set_job_ctx(job_id="test-job")
        
        # Job starts
        job_received(video_count=2, use_cookies=True)
        
        # Process video
        set_job_ctx(job_id="test-job", video_id="video1")
        video_processed("video1", "success", 5000, "yt_api")
        
        # Job finishes
        set_job_ctx(job_id="test-job")
        job_finished(10000, 1, 2, "partial_success", email_sent=True)
        
        events = self.get_log_events()
        
        # Should have 3 events
        self.assertGreaterEqual(len(events), 3)
        
        # Find our events
        job_events = [e for e in events if e.get('event') in ['job_received', 'video_processed', 'job_finished']]
        self.assertEqual(len(job_events), 3)
        
        # Verify job_received
        job_received_event = next(e for e in job_events if e['event'] == 'job_received')
        self.assertEqual(job_received_event['video_count'], 2)
        self.assertTrue(job_received_event['use_cookies'])
        
        # Verify video_processed
        video_event = next(e for e in job_events if e['event'] == 'video_processed')
        self.assertEqual(video_event['video_id'], 'video1')
        self.assertEqual(video_event['outcome'], 'success')
        
        # Verify job_finished
        job_finished_event = next(e for e in job_events if e['event'] == 'job_finished')
        self.assertEqual(job_finished_event['outcome'], 'partial_success')
        self.assertEqual(job_finished_event['processed_count'], 1)
    
    def test_error_classification(self):
        """Test error classification."""
        # Test a few key error types
        auth_error = Exception("Authentication failed")
        self.assertEqual(classify_error_type(auth_error), "auth_error")
        
        network_error = Exception("Connection timeout")
        self.assertEqual(classify_error_type(network_error), "network_error")
        
        generic_error = Exception("Something went wrong")
        self.assertEqual(classify_error_type(generic_error), "service_error")


if __name__ == '__main__':
    unittest.main()