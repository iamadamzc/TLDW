"""
Load tests for rate limiting under spam conditions.

Tests the rate limiting system under extreme load to ensure it
performs well and maintains memory efficiency under spam attacks.
"""

import logging
import threading
import time
import unittest
import statistics
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logging_setup import RateLimitFilter


class TestRateLimitingLoadConditions(unittest.TestCase):
    """Load tests for rate limiting under spam conditions."""
    
    def setUp(self):
        """Set up load test environment."""
        if PSUTIL_AVAILABLE:
            self.process = psutil.Process(os.getpid())
            self.baseline_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        else:
            self.process = None
            self.baseline_memory = 0
    
    def test_high_volume_spam_attack(self):
        """Test rate limiting under high-volume spam attack."""
        rate_filter = RateLimitFilter(per_key=5, window_sec=10)  # Longer window for load test
        
        # Simulate spam attack parameters
        spam_messages_per_second = 1000
        attack_duration_seconds = 5
        total_spam_messages = spam_messages_per_second * attack_duration_seconds
        
        def create_spam_record(message_id):
            """Create a spam log record."""
            return logging.LogRecord(
                name='spam_attack', level=logging.WARNING, pathname='', lineno=0,
                msg=f'Spam message {message_id % 10}', args=(), exc_info=None  # 10 unique messages
            )
        
        # Measure performance under spam
        start_time = time.perf_counter()
        allowed_count = 0
        blocked_count = 0
        
        for i in range(total_spam_messages):
            record = create_spam_record(i)
            if rate_filter.filter(record):
                allowed_count += 1
            else:
                blocked_count += 1
            
            # Brief pause to simulate realistic timing
            if i % 100 == 0:
                time.sleep(0.001)  # 1ms pause every 100 messages
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        messages_per_second = total_spam_messages / total_time
        
        # Performance assertions
        self.assertGreater(messages_per_second, 500, 
                          f"Rate limiting should handle >500 msg/sec, got {messages_per_second:.0f}")
        
        # Rate limiting effectiveness assertions
        # With 10 unique messages, each should allow 5 + 1 suppression = 6 messages
        # Total allowed should be approximately 10 * 6 = 60
        expected_allowed = 10 * 6  # 10 unique messages * 6 allowed each
        self.assertLessEqual(allowed_count, expected_allowed + 10)  # Allow some variance
        self.assertGreater(allowed_count, expected_allowed - 10)
        
        # Most messages should be blocked
        self.assertGreater(blocked_count, allowed_count * 5)
        
        print(f"Spam attack test: {total_spam_messages} messages in {total_time:.2f}s")
        print(f"Performance: {messages_per_second:.0f} messages/sec")
        print(f"Allowed: {allowed_count}, Blocked: {blocked_count}")
        print(f"Block rate: {(blocked_count / total_spam_messages) * 100:.1f}%")
    
    def test_concurrent_spam_from_multiple_sources(self):
        """Test rate limiting with concurrent spam from multiple sources."""
        rate_filter = RateLimitFilter(per_key=3, window_sec=5)
        
        def spam_worker(worker_id, messages_per_worker):
            """Worker function that generates spam messages."""
            results = {'allowed': 0, 'blocked': 0}
            
            for i in range(messages_per_worker):
                # Each worker sends unique messages to test different keys
                record = logging.LogRecord(
                    name=f'worker_{worker_id}', level=logging.ERROR, pathname='', lineno=0,
                    msg=f'Worker {worker_id} error message {i % 5}', args=(), exc_info=None
                )
                
                if rate_filter.filter(record):
                    results['allowed'] += 1
                else:
                    results['blocked'] += 1
                
                # Small delay to simulate realistic load
                if i % 50 == 0:
                    time.sleep(0.001)
            
            return results
        
        # Test parameters
        num_workers = 10
        messages_per_worker = 500
        total_messages = num_workers * messages_per_worker
        
        start_time = time.perf_counter()
        
        # Run concurrent spam attack
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = []
            for worker_id in range(num_workers):
                future = executor.submit(spam_worker, worker_id, messages_per_worker)
                futures.append(future)
            
            # Collect results
            total_allowed = 0
            total_blocked = 0
            
            for future in as_completed(futures):
                result = future.result()
                total_allowed += result['allowed']
                total_blocked += result['blocked']
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        throughput = total_messages / total_time
        
        # Performance assertions
        self.assertGreater(throughput, 1000, 
                          f"Concurrent throughput should be >1000 msg/sec, got {throughput:.0f}")
        
        # Rate limiting assertions
        # Each worker has 5 unique messages, each allows 3 + 1 suppression = 4
        # 10 workers * 5 messages * 4 allowed = 200 total allowed
        expected_allowed = num_workers * 5 * 4
        self.assertLessEqual(total_allowed, expected_allowed + 50)  # Allow variance
        
        # Verify most messages were blocked
        block_rate = (total_blocked / total_messages) * 100
        self.assertGreater(block_rate, 80, f"Block rate should be >80%, got {block_rate:.1f}%")
        
        print(f"Concurrent spam test: {num_workers} workers, {total_messages} total messages")
        print(f"Performance: {throughput:.0f} messages/sec")
        print(f"Allowed: {total_allowed}, Blocked: {total_blocked}")
        print(f"Block rate: {block_rate:.1f}%")
    
    def test_memory_efficiency_under_sustained_load(self):
        """Test memory efficiency during sustained spam load."""
        if not PSUTIL_AVAILABLE:
            self.skipTest("psutil not available for memory testing")
        
        rate_filter = RateLimitFilter(per_key=5, window_sec=30)  # Longer window
        
        # Generate sustained load with many unique message types
        unique_message_types = 1000
        messages_per_type = 50
        total_messages = unique_message_types * messages_per_type
        
        memory_samples = []
        
        start_time = time.perf_counter()
        allowed_count = 0
        
        for message_type in range(unique_message_types):
            for message_instance in range(messages_per_type):
                record = logging.LogRecord(
                    name='memory_test', level=logging.WARNING, pathname='', lineno=0,
                    msg=f'Message type {message_type} instance {message_instance}', 
                    args=(), exc_info=None
                )
                
                if rate_filter.filter(record):
                    allowed_count += 1
                
                # Sample memory usage periodically
                if (message_type * messages_per_type + message_instance) % 5000 == 0:
                    current_memory = self.process.memory_info().rss / 1024 / 1024  # MB
                    memory_increase = current_memory - self.baseline_memory
                    memory_samples.append(memory_increase)
                    
                    # Memory should not grow excessively
                    self.assertLess(memory_increase, 100, 
                                  f"Memory increased by {memory_increase:.1f}MB, should be <100MB")
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        
        # Final memory check
        final_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        total_memory_increase = final_memory - self.baseline_memory
        
        # Performance metrics
        throughput = total_messages / total_time
        
        # Assertions
        self.assertLess(total_memory_increase, 150, 
                       f"Total memory increase {total_memory_increase:.1f}MB should be <150MB")
        self.assertGreater(throughput, 2000, 
                          f"Throughput {throughput:.0f} msg/sec should be >2000")
        
        # Rate limiting should be effective
        # With 1000 unique message types, each allowing 5 + 1 = 6 messages
        # Total allowed should be approximately 1000 * 6 = 6000
        expected_allowed = unique_message_types * 6
        self.assertLessEqual(allowed_count, expected_allowed + 500)  # Allow variance
        
        print(f"Memory efficiency test: {total_messages} messages, {unique_message_types} unique types")
        print(f"Performance: {throughput:.0f} messages/sec")
        print(f"Memory increase: {total_memory_increase:.1f}MB")
        print(f"Allowed: {allowed_count}/{total_messages} ({(allowed_count/total_messages)*100:.1f}%)")
        
        if memory_samples:
            avg_memory = statistics.mean(memory_samples)
            max_memory = max(memory_samples)
            print(f"Memory usage: avg={avg_memory:.1f}MB, max={max_memory:.1f}MB")
    
    def test_rate_limiting_accuracy_under_load(self):
        """Test that rate limiting remains accurate under load."""
        rate_filter = RateLimitFilter(per_key=10, window_sec=2)  # Higher limit for accuracy testing
        
        # Test with a single message type to verify exact counting
        test_message = "Accuracy test message"
        total_attempts = 100
        
        def send_messages(count):
            """Send a specific number of identical messages."""
            allowed = 0
            for i in range(count):
                record = logging.LogRecord(
                    name='accuracy_test', level=logging.INFO, pathname='', lineno=0,
                    msg=test_message, args=(), exc_info=None
                )
                if rate_filter.filter(record):
                    allowed += 1
                
                # Small delay to prevent overwhelming
                time.sleep(0.001)
            return allowed
        
        # Send messages in batches to test accuracy
        batch_size = 20
        batches = total_attempts // batch_size
        
        total_allowed = 0
        for batch in range(batches):
            batch_allowed = send_messages(batch_size)
            total_allowed += batch_allowed
            
            print(f"Batch {batch + 1}: {batch_allowed}/{batch_size} allowed")
            
            # Wait for partial window reset between batches
            time.sleep(0.5)
        
        # Should have allowed exactly 10 + 1 suppression marker per window
        # With multiple batches and window resets, should allow more than just 11
        self.assertGreater(total_allowed, 15, 
                          f"Should allow >15 messages across batches, got {total_allowed}")
        self.assertLess(total_allowed, total_attempts * 0.8, 
                       f"Should block most messages, allowed {total_allowed}/{total_attempts}")
        
        print(f"Accuracy test: {total_allowed}/{total_attempts} messages allowed")
        print(f"Block rate: {((total_attempts - total_allowed) / total_attempts) * 100:.1f}%")
    
    def test_thread_safety_under_extreme_concurrency(self):
        """Test thread safety under extreme concurrent load."""
        rate_filter = RateLimitFilter(per_key=5, window_sec=3)
        
        def concurrent_worker(worker_id, iterations):
            """Worker that hammers the rate filter concurrently."""
            results = []
            for i in range(iterations):
                record = logging.LogRecord(
                    name=f'thread_safety_test_{worker_id}', level=logging.WARNING, 
                    pathname='', lineno=0,
                    msg='Concurrent test message', args=(), exc_info=None
                )
                result = rate_filter.filter(record)
                results.append(result)
            return results
        
        # Extreme concurrency test
        num_threads = 20
        iterations_per_thread = 100
        
        start_time = time.perf_counter()
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = []
            for worker_id in range(num_threads):
                future = executor.submit(concurrent_worker, worker_id, iterations_per_thread)
                futures.append(future)
            
            # Collect all results
            all_results = []
            for future in as_completed(futures):
                worker_results = future.result()
                all_results.extend(worker_results)
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        
        # Analyze results
        total_messages = len(all_results)
        allowed_messages = sum(1 for r in all_results if r)
        blocked_messages = total_messages - allowed_messages
        
        # Performance check
        throughput = total_messages / total_time
        self.assertGreater(throughput, 5000, 
                          f"Thread safety test throughput {throughput:.0f} should be >5000 msg/sec")
        
        # Thread safety check - no crashes or exceptions should occur
        self.assertEqual(total_messages, num_threads * iterations_per_thread)
        
        # Rate limiting should still be effective
        # All threads use the same message, so should allow 5 + 1 = 6 total
        self.assertLessEqual(allowed_messages, 10)  # Allow some variance for thread timing
        self.assertGreater(blocked_messages, allowed_messages * 10)
        
        print(f"Thread safety test: {num_threads} threads, {total_messages} total messages")
        print(f"Performance: {throughput:.0f} messages/sec")
        print(f"Allowed: {allowed_messages}, Blocked: {blocked_messages}")
        print(f"No crashes or exceptions - thread safety verified")


if __name__ == '__main__':
    print("Running Rate Limiting Load Tests...")
    print("These tests may take several minutes to complete.")
    print("-" * 60)
    
    unittest.main(verbosity=2)