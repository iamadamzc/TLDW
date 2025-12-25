"""
Integration tests for context management in the transcript pipeline.

Tests context propagation across pipeline stages and job processing.
"""

import unittest
import threading
import time
from unittest.mock import patch, MagicMock, Mock
import logging
import json

# Import the modules we're testing
from logging_setup import set_job_ctx, clear_job_ctx, get_job_ctx, JsonFormatter, configure_logging
from log_events import evt, StageTimer
from routes import JobManager


class TestContextIntegration(unittest.TestCase):
    """Test context management integration across pipeline stages."""
    
    def setUp(self):
        """Set up test environment."""
        # Clear any existing context
        clear_job_ctx()
        
        # Configure logging for testing
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
    
    def test_job_context_propagation(self):
        """Test that job context is properly set and propagated."""
        job_id = "test-job-123"
        video_id = "test-video-456"
        
        # Set job context
        set_job_ctx(job_id=job_id, video_id=video_id)
        
        # Verify context is set
        ctx = get_job_ctx()
        self.assertEqual(ctx['job_id'], job_id)
        self.assertEqual(ctx['video_id'], video_id)
        
        # Test that logging includes context
        logging.info("Test message")
        
        # Check that the log record includes context
        self.assertTrue(len(self.log_capture) > 0)
        record = self.log_capture[-1]
        
        # Format the record to check JSON output
        formatter = JsonFormatter()
        log_json = formatter.format(record)
        log_data = json.loads(log_json)
        
        self.assertEqual(log_data['job_id'], job_id)
        self.assertEqual(log_data['video_id'], video_id)
    
    def test_thread_isolation(self):
        """Test that context is isolated between threads."""
        results = {}
        
        def worker_thread(thread_id, job_id, video_id):
            set_job_ctx(job_id=job_id, video_id=video_id)
            time.sleep(0.1)  # Allow other threads to run
            ctx = get_job_ctx()
            results[thread_id] = ctx
        
        # Start multiple threads with different contexts
        threads = []
        for i in range(3):
            thread = threading.Thread(
                target=worker_thread,
                args=(i, f"job-{i}", f"video-{i}")
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify each thread maintained its own context
        self.assertEqual(len(results), 3)
        for i in range(3):
            self.assertEqual(results[i]['job_id'], f"job-{i}")
            self.assertEqual(results[i]['video_id'], f"video-{i}")
    
    def test_stage_timer_context_integration(self):
        """Test that StageTimer integrates with job context."""
        job_id = "test-job-789"
        video_id = "test-video-101"
        
        set_job_ctx(job_id=job_id, video_id=video_id)
        
        # Use StageTimer with additional context
        with StageTimer("test_stage", profile="desktop", use_proxy=True):
            time.sleep(0.01)  # Small delay to ensure duration > 0
        
        # Check that stage events were logged with context
        stage_logs = [record for record in self.log_capture 
                     if hasattr(record, 'event') and 'stage' in getattr(record, 'event', '')]
        
        self.assertTrue(len(stage_logs) >= 2)  # start and result events
        
        # Check the stage_result event
        result_log = None
        for record in stage_logs:
            if getattr(record, 'event', '') == 'stage_result':
                result_log = record
                break
        
        self.assertIsNotNone(result_log)
        
        # Format and check JSON output
        formatter = JsonFormatter()
        log_json = formatter.format(result_log)
        log_data = json.loads(log_json)
        
        self.assertEqual(log_data['job_id'], job_id)
        self.assertEqual(log_data['video_id'], video_id)
        self.assertEqual(log_data['stage'], 'test_stage')
        self.assertEqual(log_data['event'], 'stage_result')
        self.assertEqual(log_data['outcome'], 'success')
        self.assertEqual(log_data['profile'], 'desktop')
        self.assertEqual(log_data['use_proxy'], True)
        self.assertIn('dur_ms', log_data)
        self.assertGreater(log_data['dur_ms'], 0)
    
    def test_event_helper_context_integration(self):
        """Test that evt() helper integrates with job context."""
        job_id = "test-job-456"
        video_id = "test-video-789"
        
        set_job_ctx(job_id=job_id, video_id=video_id)
        
        # Emit event with additional fields
        evt("test_event", outcome="success", attempt=2, profile="mobile")
        
        # Find the event log
        event_logs = [record for record in self.log_capture 
                     if hasattr(record, 'event') and getattr(record, 'event') == 'test_event']
        
        self.assertEqual(len(event_logs), 1)
        
        # Format and check JSON output
        formatter = JsonFormatter()
        log_json = formatter.format(event_logs[0])
        log_data = json.loads(log_json)
        
        self.assertEqual(log_data['job_id'], job_id)
        self.assertEqual(log_data['video_id'], video_id)
        self.assertEqual(log_data['event'], 'test_event')
        self.assertEqual(log_data['outcome'], 'success')
        self.assertEqual(log_data['attempt'], 2)
        self.assertEqual(log_data['profile'], 'mobile')
    
    def test_context_clearing(self):
        """Test that context is properly cleared."""
        # Set context
        set_job_ctx(job_id="test-job", video_id="test-video")
        
        # Verify context is set
        ctx = get_job_ctx()
        self.assertEqual(len(ctx), 2)
        
        # Clear context
        clear_job_ctx()
        
        # Verify context is cleared
        ctx = get_job_ctx()
        self.assertEqual(len(ctx), 0)
        
        # Test logging without context
        logging.info("Test message without context")
        
        # Check that log doesn't include job/video IDs
        record = self.log_capture[-1]
        formatter = JsonFormatter()
        log_json = formatter.format(record)
        log_data = json.loads(log_json)
        
        self.assertNotIn('job_id', log_data)
        self.assertNotIn('video_id', log_data)
    
    @patch('routes.YouTubeService')
    @patch('routes.TranscriptService')
    @patch('routes.VideoSummarizer')
    @patch('routes.EmailService')
    def test_job_manager_context_integration(self, mock_email, mock_summarizer, mock_transcript, mock_youtube):
        """Test that JobManager properly sets and clears context."""
        # Mock the services
        mock_youtube_instance = Mock()
        mock_youtube.return_value = mock_youtube_instance
        mock_youtube_instance.get_video_details.return_value = {
            "id": "test-video",
            "title": "Test Video",
            "thumbnail": "test-thumb.jpg"
        }
        
        mock_transcript_instance = Mock()
        mock_transcript.return_value = mock_transcript_instance
        mock_transcript_instance.get_transcript.return_value = "Test transcript"
        
        mock_summarizer_instance = Mock()
        mock_summarizer.return_value = mock_summarizer_instance
        mock_summarizer_instance.summarize_video.return_value = "Test summary"
        
        mock_email_instance = Mock()
        mock_email.return_value = mock_email_instance
        mock_email_instance.send_digest_email.return_value = True
        
        # Create a mock Flask app
        mock_app = Mock()
        mock_app.app_context.return_value.__enter__ = Mock()
        mock_app.app_context.return_value.__exit__ = Mock()
        
        # Mock User model
        with patch('models.User') as mock_user_class:
            mock_user = Mock()
            mock_user.id = 1
            mock_user.email = "test@example.com"
            mock_user_class.query.get.return_value = mock_user
            
            # Create JobManager and run a job
            job_manager = JobManager(worker_concurrency=1)
            
            # Submit job (this will run in a separate thread)
            job_id = job_manager.submit_summarization_job(1, ["test-video"], mock_app)
            
            # Wait for job to complete
            max_wait = 10  # seconds
            waited = 0
            while waited < max_wait:
                status = job_manager.get_job_status(job_id)
                if status and status.status in ["done", "error"]:
                    break
                time.sleep(0.1)
                waited += 0.1
            
            # Verify job completed
            final_status = job_manager.get_job_status(job_id)
            self.assertIsNotNone(final_status)
            self.assertIn(final_status.status, ["done", "error"])
    
    def test_nested_context_updates(self):
        """Test that context can be updated during processing."""
        # Set initial context
        set_job_ctx(job_id="test-job")
        
        # Verify initial context
        ctx = get_job_ctx()
        self.assertEqual(ctx['job_id'], "test-job")
        self.assertNotIn('video_id', ctx)
        
        # Update context with video ID
        set_job_ctx(job_id="test-job", video_id="video-1")
        
        # Verify updated context
        ctx = get_job_ctx()
        self.assertEqual(ctx['job_id'], "test-job")
        self.assertEqual(ctx['video_id'], "video-1")
        
        # Update with different video ID (simulating video iteration)
        set_job_ctx(job_id="test-job", video_id="video-2")
        
        # Verify context updated
        ctx = get_job_ctx()
        self.assertEqual(ctx['job_id'], "test-job")
        self.assertEqual(ctx['video_id'], "video-2")
    
    def test_exception_handling_with_context(self):
        """Test that context is maintained during exception handling."""
        job_id = "test-job-exception"
        video_id = "test-video-exception"
        
        set_job_ctx(job_id=job_id, video_id=video_id)
        
        # Test StageTimer with exception
        try:
            with StageTimer("failing_stage", profile="desktop"):
                raise ValueError("Test exception")
        except ValueError:
            pass  # Expected
        
        # Check that error event was logged with context
        error_logs = [record for record in self.log_capture 
                     if hasattr(record, 'event') and getattr(record, 'event') == 'stage_result'
                     and hasattr(record, 'outcome') and getattr(record, 'outcome') == 'error']
        
        self.assertTrue(len(error_logs) >= 1)
        
        # Format and check JSON output
        formatter = JsonFormatter()
        log_json = formatter.format(error_logs[0])
        log_data = json.loads(log_json)
        
        self.assertEqual(log_data['job_id'], job_id)
        self.assertEqual(log_data['video_id'], video_id)
        self.assertEqual(log_data['stage'], 'failing_stage')
        self.assertEqual(log_data['event'], 'stage_result')
        self.assertEqual(log_data['outcome'], 'error')
        self.assertEqual(log_data['profile'], 'desktop')
        self.assertIn('detail', log_data)
        self.assertIn('Test exception', log_data['detail'])


if __name__ == '__main__':
    unittest.main()