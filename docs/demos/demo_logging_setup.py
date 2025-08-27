#!/usr/bin/env python3
"""
Demonstration of the new structured JSON logging system.

Shows key features:
- JSON formatting with stable field order
- Thread-local context management
- Rate limiting and suppression
- Library noise suppression
"""

import logging
import time
from logging_setup import configure_logging, set_job_ctx, clear_job_ctx, get_logger, get_perf_logger


def demo_basic_logging():
    """Demonstrate basic JSON logging with context."""
    print("=== Basic JSON Logging Demo ===")
    
    # Configure logging
    configure_logging(log_level='INFO', use_json=True)
    logger = get_logger('demo')
    
    # Set job context
    set_job_ctx(job_id='j-demo-001', video_id='dQw4w9WgXcQ')
    
    # Log a simple message
    logger.info('Starting video processing')
    
    # Log a structured event
    record = logging.LogRecord(
        name='demo', level=logging.INFO, pathname='', lineno=0,
        msg='', args=(), exc_info=None
    )
    record.stage = 'transcript'
    record.event = 'stage_start'
    record.detail = 'Beginning transcript extraction'
    logger.handle(record)
    
    # Log stage completion
    record = logging.LogRecord(
        name='demo', level=logging.INFO, pathname='', lineno=0,
        msg='', args=(), exc_info=None
    )
    record.stage = 'transcript'
    record.event = 'stage_result'
    record.outcome = 'success'
    record.dur_ms = 2500
    record.detail = 'Transcript extracted via youtube-transcript-api'
    record.use_proxy = False
    record.profile = 'desktop'
    logger.handle(record)
    
    print()


def demo_rate_limiting():
    """Demonstrate rate limiting and suppression."""
    print("=== Rate Limiting Demo ===")
    
    logger = get_logger('rate_limit_demo')
    
    # Send repeated messages to trigger rate limiting
    for i in range(8):
        logger.warning('Connection timeout - retrying')
        if i == 4:
            print("  ^ Rate limit should trigger suppression marker here")
    
    print()


def demo_performance_logging():
    """Demonstrate performance metrics separation."""
    print("=== Performance Logging Demo ===")
    
    # Regular application logger
    app_logger = get_logger('app')
    app_logger.info('Processing video batch')
    
    # Performance metrics logger
    perf_logger = get_perf_logger()
    record = logging.LogRecord(
        name='perf', level=logging.INFO, pathname='', lineno=0,
        msg='', args=(), exc_info=None
    )
    record.event = 'performance_metric'
    record.cpu = 15.2
    record.mem_mb = 512
    perf_logger.handle(record)
    
    print()


def demo_error_handling():
    """Demonstrate error logging with context."""
    print("=== Error Handling Demo ===")
    
    logger = get_logger('error_demo')
    
    # Set context for error correlation
    set_job_ctx(job_id='j-error-001', video_id='error-video')
    
    try:
        # Simulate an error
        raise ConnectionError("Failed to connect to YouTube API")
    except Exception as e:
        record = logging.LogRecord(
            name='error_demo', level=logging.ERROR, pathname='', lineno=0,
            msg='', args=(), exc_info=None
        )
        record.stage = 'youtubei'
        record.event = 'stage_result'
        record.outcome = 'error'
        record.dur_ms = 5000
        record.detail = f'{type(e).__name__}: {str(e)}'
        record.attempt = 2
        record.use_proxy = True
        logger.handle(record)
    
    print()


def demo_library_suppression():
    """Demonstrate third-party library noise suppression."""
    print("=== Library Noise Suppression Demo ===")
    
    # These should be suppressed (not shown)
    urllib3_logger = logging.getLogger('urllib3.connectionpool')
    urllib3_logger.info('Starting new HTTPS connection')  # Should be suppressed
    
    playwright_logger = logging.getLogger('playwright')
    playwright_logger.info('Browser launched')  # Should be suppressed
    
    # Application logs should still show
    app_logger = get_logger('app')
    app_logger.info('Application message - should be visible')
    
    print()


if __name__ == '__main__':
    print("TL;DW Structured JSON Logging System Demo")
    print("=" * 50)
    
    demo_basic_logging()
    demo_rate_limiting()
    demo_performance_logging()
    demo_error_handling()
    demo_library_suppression()
    
    # Clean up
    clear_job_ctx()
    
    print("Demo complete! 🎉")