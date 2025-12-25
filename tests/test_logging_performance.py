"""
Performance tests for structured JSON logging system.

Tests logging overhead, memory usage, and performance under load
to ensure the logging system meets performance requirements.
"""

import json
import logging
import time
import threading
import statistics
import unittest
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None
import os
from io import StringIO
from concurrent.futures import ThreadPoolExecutor
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logging_setup import (
    JsonFormatter, RateLimitFilter, configure_logging, 
    set_job_ctx, clear_job_ctx
)
from log_events import evt, StageTimer, perf_evt


class TestLoggingPerformance(unittest.TestCase):
    """Performance tests for logging overhead measurement."""
    
    def setUp(self):
        """Set up performance test environment."""
        # Configure logging to write to a buffer for performance testing
        self.log_buffer = StringIO()
        self.handler = logging.StreamHandler(self.log_buffer)
        self.handler.setFormatter(JsonFormatter())
        
        self.logger = logging.getLogger()
        # Clear existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)
        
        # Set up context for realistic testing
        set_job_ctx(job_id='j-perf-test', video_id='perf-video-123')
    
    def tearDown(self):
        """Clean up after performance tests."""
        self.logger.removeHandler(self.handler)
        self.handler.close()
        clear_job_ctx()
    
    def test_json_formatter_performance(self):
        """Test JsonFormatter performance under load."""
        formatter = JsonFormatter()
        
        # Create a realistic log record
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='Stage processing completed', args=(), exc_info=None
        )
        record.stage = 'youtubei'
        record.event = 'stage_result'
        record.outcome = 'success'
        record.dur_ms = 1500
        record.detail = 'Transcript extracted successfully'
        record.use_proxy = True
        record.profile = 'mobile'
        
        # Measure formatting performance
        iterations = 1000
        start_time = time.perf_counter()
        
        for _ in range(iterations):
            formatted = formatter.format(record)
            # Verify it's valid JSON (adds realistic overhead)
            json.loads(formatted)
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        avg_time_ms = (total_time / iterations) * 1000
        
        # Performance requirement: <1ms per log event
        self.assertLess(avg_time_ms, 1.0, 
                       f"Average formatting time {avg_time_ms:.3f}ms exceeds 1ms target")
        
        print(f"JsonFormatter performance: {avg_time_ms:.3f}ms per event ({iterations} iterations)")
    
    def test_evt_function_performance(self):
        """Test evt() function performance."""
        iterations = 1000
        start_time = time.perf_counter()
        
        for i in range(iterations):
            evt("performance_test", 
                stage="test_stage", 
                outcome="success", 
                dur_ms=1000 + i,
                attempt=1,
                use_proxy=True)
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        avg_time_ms = (total_time / iterations) * 1000
        
        # Should be very fast
        self.assertLess(avg_time_ms, 2.0,
                       f"Average evt() time {avg_time_ms:.3f}ms exceeds 2ms target")
        
        print(f"evt() function performance: {avg_time_ms:.3f}ms per call ({iterations} iterations)")
    
    def test_stage_timer_performance(self):
        """Test StageTimer context manager performance."""
        iterations = 100  # Fewer iterations due to sleep overhead
        total_overhead = 0
        
        for _ in range(iterations):
            # Measure just the timer overhead, not the work being timed
            start_time = time.perf_counter()
            
            with StageTimer("perf_test_stage", profile="mobile"):
                # Minimal work to isolate timer overhead
                pass
            
            end_time = time.perf_counter()
            total_overhead += (end_time - start_time)
        
        avg_overhead_ms = (total_overhead / iterations) * 1000
        
        # Timer overhead should be minimal
        self.assertLess(avg_overhead_ms, 5.0,
                       f"Average StageTimer overhead {avg_overhead_ms:.3f}ms exceeds 5ms target")
        
        print(f"StageTimer overhead: {avg_overhead_ms:.3f}ms per use ({iterations} iterations)")
    
    def test_concurrent_logging_performance(self):
        """Test logging performance under concurrent load."""
        def worker(worker_id, iterations_per_worker):
            """Worker function for concurrent logging."""
            set_job_ctx(job_id=f'j-worker-{worker_id}', video_id=f'vid-{worker_id}')
            
            for i in range(iterations_per_worker):
                evt("concurrent_test",
                    worker_id=worker_id,
                    iteration=i,
                    stage="concurrent_stage",
                    outcome="success",
                    dur_ms=100 + i)
        
        num_workers = 4
        iterations_per_worker = 250
        total_events = num_workers * iterations_per_worker
        
        start_time = time.perf_counter()
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = []
            for worker_id in range(num_workers):
                future = executor.submit(worker, worker_id, iterations_per_worker)
                futures.append(future)
            
            # Wait for all workers to complete
            for future in futures:
                future.result()
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        events_per_second = total_events / total_time
        
        # Should handle at least 1000 events per second under concurrent load
        self.assertGreater(events_per_second, 1000,
                          f"Concurrent throughput {events_per_second:.0f} events/sec below 1000 target")
        
        print(f"Concurrent logging performance: {events_per_second:.0f} events/sec "
              f"({num_workers} workers, {total_events} total events)")
    
    def test_memory_usage_under_load(self):
        """Test memory usage during sustained logging."""
        if not PSUTIL_AVAILABLE:
            self.skipTest("psutil not available for memory testing")
        
        process = psutil.Process(os.getpid())
        
        # Get baseline memory usage
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Generate sustained logging load
        iterations = 5000
        for i in range(iterations):
            evt("memory_test",
                iteration=i,
                stage="memory_stage",
                outcome="success",
                dur_ms=100,
                detail=f"Memory test iteration {i}")
            
            # Check memory every 1000 iterations
            if i % 1000 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_increase = current_memory - baseline_memory
                
                # Memory increase should be reasonable (less than 50MB for 5000 events)
                self.assertLess(memory_increase, 50,
                               f"Memory usage increased by {memory_increase:.1f}MB after {i} events")
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_increase = final_memory - baseline_memory
        
        print(f"Memory usage: {baseline_memory:.1f}MB baseline, "
              f"{final_memory:.1f}MB final, {total_increase:.1f}MB increase")
    
    def test_rate_limiting_performance_under_spam(self):
        """Test rate limiting performance under spam conditions."""
        # Create filter with realistic settings
        rate_filter = RateLimitFilter(per_key=5, window_sec=60)
        
        # Create identical records to trigger rate limiting
        def create_spam_record():
            record = logging.LogRecord(
                name='spam_test', level=logging.WARNING, pathname='', lineno=0,
                msg='Repeated warning message', args=(), exc_info=None
            )
            return record
        
        # Test performance under spam conditions
        iterations = 10000
        start_time = time.perf_counter()
        
        allowed_count = 0
        for _ in range(iterations):
            record = create_spam_record()
            if rate_filter.filter(record):
                allowed_count += 1
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        avg_time_us = (total_time / iterations) * 1000000  # microseconds
        
        # Rate limiting should be very fast even under spam
        self.assertLess(avg_time_us, 100,
                       f"Average rate limit check {avg_time_us:.1f}μs exceeds 100μs target")
        
        # Should have allowed exactly 6 messages (5 + 1 suppression marker)
        self.assertEqual(allowed_count, 6,
                        f"Expected 6 allowed messages, got {allowed_count}")
        
        print(f"Rate limiting performance: {avg_time_us:.1f}μs per check "
              f"({iterations} spam messages, {allowed_count} allowed)")
    
    def test_context_lookup_performance(self):
        """Test thread-local context lookup performance."""
        set_job_ctx(job_id='j-context-perf', video_id='vid-context-perf')
        
        iterations = 10000
        start_time = time.perf_counter()
        
        for _ in range(iterations):
            # This simulates what JsonFormatter does
            from logging_setup import get_job_ctx
            context = get_job_ctx()
            # Access context fields
            job_id = context.get('job_id')
            video_id = context.get('video_id')
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        avg_time_us = (total_time / iterations) * 1000000  # microseconds
        
        # Context lookup should be very fast
        self.assertLess(avg_time_us, 10,
                       f"Average context lookup {avg_time_us:.1f}μs exceeds 10μs target")
        
        print(f"Context lookup performance: {avg_time_us:.1f}μs per lookup ({iterations} iterations)")
    
    def test_json_serialization_performance(self):
        """Test JSON serialization performance with realistic data."""
        # Create realistic log data
        log_data = {
            'ts': '2025-08-27T16:24:06.123Z',
            'lvl': 'INFO',
            'job_id': 'j-7f3d',
            'video_id': 'bbz2boNSeL0',
            'stage': 'youtubei',
            'event': 'stage_result',
            'outcome': 'success',
            'dur_ms': 1500,
            'detail': 'Transcript extracted successfully from YouTubei API',
            'attempt': 2,
            'use_proxy': True,
            'profile': 'mobile',
            'cookie_source': 's3'
        }
        
        iterations = 10000
        start_time = time.perf_counter()
        
        for _ in range(iterations):
            json_str = json.dumps(log_data, separators=(',', ':'), ensure_ascii=False)
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        avg_time_us = (total_time / iterations) * 1000000  # microseconds
        
        # JSON serialization should be fast
        self.assertLess(avg_time_us, 50,
                       f"Average JSON serialization {avg_time_us:.1f}μs exceeds 50μs target")
        
        print(f"JSON serialization performance: {avg_time_us:.1f}μs per serialization ({iterations} iterations)")


class TestRateLimitingLoadTest(unittest.TestCase):
    """Load tests for rate limiting under spam conditions."""
    
    def test_rate_limiting_under_concurrent_spam(self):
        """Test rate limiting behavior under concurrent spam load."""
        rate_filter = RateLimitFilter(per_key=5, window_sec=2)  # Shorter window for testing
        
        def spam_worker(worker_id, spam_count):
            """Worker that generates spam messages."""
            results = []
            for i in range(spam_count):
                record = logging.LogRecord(
                    name=f'spam_worker_{worker_id}', level=logging.WARNING, 
                    pathname='', lineno=0,
                    msg=f'Spam message from worker {worker_id}', args=(), exc_info=None
                )
                result = rate_filter.filter(record)
                results.append(result)
            return results
        
        num_workers = 5
        spam_per_worker = 100
        
        start_time = time.perf_counter()
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = []
            for worker_id in range(num_workers):
                future = executor.submit(spam_worker, worker_id, spam_per_worker)
                futures.append(future)
            
            # Collect results
            all_results = []
            for future in futures:
                worker_results = future.result()
                all_results.extend(worker_results)
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        
        # Analyze results
        total_messages = len(all_results)
        allowed_messages = sum(1 for r in all_results if r)
        blocked_messages = total_messages - allowed_messages
        
        # Each worker should have had some messages allowed and some blocked
        # With 5 workers * 100 messages each = 500 total messages
        # Each worker's messages are different, so each should get 5 + 1 suppression = 6 allowed
        # Total allowed should be approximately 5 * 6 = 30
        self.assertGreater(allowed_messages, 20)  # At least some allowed
        self.assertLess(allowed_messages, 50)     # But most should be blocked
        
        print(f"Concurrent spam test: {total_messages} messages, "
              f"{allowed_messages} allowed, {blocked_messages} blocked "
              f"in {total_time:.2f}s")
    
    def test_rate_limiting_memory_efficiency(self):
        """Test that rate limiting doesn't leak memory under sustained load."""
        if not PSUTIL_AVAILABLE:
            self.skipTest("psutil not available for memory testing")
        
        rate_filter = RateLimitFilter(per_key=3, window_sec=1)
        process = psutil.Process(os.getpid())
        
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Generate many different message types to test cache behavior
        iterations = 10000
        for i in range(iterations):
            # Create unique messages to test cache growth
            record = logging.LogRecord(
                name='memory_test', level=logging.INFO, pathname='', lineno=0,
                msg=f'Unique message {i % 100}', args=(), exc_info=None  # 100 unique messages
            )
            rate_filter.filter(record)
            
            # Check memory periodically
            if i % 2000 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_increase = current_memory - baseline_memory
                
                # Memory should not grow excessively
                self.assertLess(memory_increase, 20,
                               f"Rate filter memory increased by {memory_increase:.1f}MB after {i} messages")
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_increase = final_memory - baseline_memory
        
        print(f"Rate limiting memory test: {total_increase:.1f}MB increase after {iterations} messages")


if __name__ == '__main__':
    # Run performance tests
    unittest.main(verbosity=2)