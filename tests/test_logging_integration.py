"""
Integration test for logging_setup.py to verify end-to-end functionality.
"""

import json
import logging
import sys
import os
from io import StringIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logging_setup import configure_logging, set_job_ctx, clear_job_ctx, get_logger, get_perf_logger


def test_end_to_end_logging():
    """Test complete logging flow with context and JSON output."""
    # Capture log output
    log_capture = StringIO()
    
    # Configure logging to write to our capture buffer
    logger = configure_logging(log_level='INFO', use_json=True)
    
    # Replace the handler's stream with our capture
    handler = logger.handlers[0]
    handler.stream = log_capture
    
    # Set job context
    set_job_ctx(job_id='j-integration-test', video_id='test-video-123')
    
    # Get application logger
    app_logger = get_logger('test_app')
    
    # Log a structured event
    record = logging.LogRecord(
        name='test_app', level=logging.INFO, pathname='', lineno=0,
        msg='', args=(), exc_info=None
    )
    record.stage = 'transcript'
    record.event = 'stage_result'
    record.outcome = 'success'
    record.dur_ms = 1500
    record.detail = 'Transcript extracted successfully'
    record.use_proxy = False
    record.profile = 'desktop'
    
    app_logger.handle(record)
    
    # Get the logged output
    output = log_capture.getvalue().strip()
    
    # Parse JSON
    log_data = json.loads(output)
    
    # Verify structure
    assert 'ts' in log_data
    assert log_data['lvl'] == 'INFO'
    assert log_data['job_id'] == 'j-integration-test'
    assert log_data['video_id'] == 'test-video-123'
    assert log_data['stage'] == 'transcript'
    assert log_data['event'] == 'stage_result'
    assert log_data['outcome'] == 'success'
    assert log_data['dur_ms'] == 1500
    assert log_data['detail'] == 'Transcript extracted successfully'
    assert log_data['use_proxy'] is False
    assert log_data['profile'] == 'desktop'
    
    print("✓ End-to-end logging test passed")
    
    # Test performance logger separation
    perf_logger = get_perf_logger()
    assert perf_logger.name == 'perf'
    print("✓ Performance logger separation test passed")
    
    # Clean up
    clear_job_ctx()


def test_rate_limiting_integration():
    """Test rate limiting in realistic scenario."""
    # Capture log output
    log_capture = StringIO()
    
    # Configure logging
    logger = configure_logging(log_level='INFO', use_json=True)
    handler = logger.handlers[0]
    handler.stream = log_capture
    
    app_logger = get_logger('test_rate_limit')
    
    # Send multiple identical messages
    for i in range(7):  # More than the default limit of 5
        app_logger.info('Repeated warning message')
    
    # Get all output
    output = log_capture.getvalue().strip()
    lines = output.split('\n')
    
    # Should have exactly 6 lines (5 regular + 1 suppression marker)
    assert len(lines) == 6, f"Expected 6 lines, got {len(lines)}"
    
    # Last allowed message should contain [suppressed]
    last_log = json.loads(lines[5])
    assert '[suppressed]' in last_log['detail']
    
    print("✓ Rate limiting integration test passed")


if __name__ == '__main__':
    test_end_to_end_logging()
    test_rate_limiting_integration()
    print("\n✅ All integration tests passed!")