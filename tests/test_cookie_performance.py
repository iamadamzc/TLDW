#!/usr/bin/env python3
"""
Performance and load tests for cookie functionality
"""

import os
import sys
import time
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path to import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from transcript_service import TranscriptService


class TestCookiePerformance(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment"""
        self.service = TranscriptService()
        
    def test_cookie_resolution_latency(self):
        """Test that cookie resolution has minimal latency impact"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create multiple cookie files
            user_ids = [100, 200, 300, 400, 500]
            for user_id in user_ids:
                cookie_file = os.path.join(temp_dir, f"{user_id}.txt")
                with open(cookie_file, 'w') as f:
                    f.write(f"# Cookie for user {user_id}\n.youtube.com\tTRUE\t/\tFALSE\t1234567890\ttest\tvalue{user_id}")
            
            with patch.dict(os.environ, {'COOKIE_LOCAL_DIR': temp_dir}):
                # Measure resolution time for each user
                resolution_times = []
                
                for user_id in user_ids:
                    start_time = time.perf_counter()
                    cookiefile, tmp_cookie = self.service._get_user_cookiefile(user_id)
                    end_time = time.perf_counter()
                    
                    resolution_time = end_time - start_time
                    resolution_times.append(resolution_time)
                    
                    # Verify cookie was found
                    self.assertIsNotNone(cookiefile)
                
                # Calculate statistics
                avg_time = sum(resolution_times) / len(resolution_times)
                max_time = max(resolution_times)
                
                # Performance assertions
                self.assertLess(avg_time, 0.001, f"Average resolution time too high: {avg_time:.4f}s")
                self.assertLess(max_time, 0.005, f"Max resolution time too high: {max_time:.4f}s")
                
                print(f"Cookie resolution performance:")
                print(f"  Average: {avg_time*1000:.2f}ms")
                print(f"  Maximum: {max_time*1000:.2f}ms")
    
    def test_s3_download_caching_need(self):
        """Test S3 download performance to determine if caching is needed"""
        user_id = 123
        
        with patch.dict(os.environ, {'COOKIE_S3_BUCKET': 'test-bucket'}):
            with patch('boto3.client') as mock_boto3:
                mock_s3 = MagicMock()
                mock_boto3.return_value = mock_s3
                
                # Simulate S3 download latency
                def slow_download(*args, **kwargs):
                    time.sleep(0.1)  # Simulate 100ms S3 latency
                
                mock_s3.download_file.side_effect = slow_download
                
                with patch('tempfile.NamedTemporaryFile') as mock_temp:
                    mock_file = MagicMock()
                    mock_file.name = '/tmp/test_cookie.txt'
                    mock_temp.return_value.__enter__.return_value = mock_file
                    
                    with patch('os.path.exists', return_value=True):
                        with patch('os.path.getsize', return_value=100):
                            
                            # Measure multiple S3 downloads
                            download_times = []
                            for _ in range(3):
                                start_time = time.perf_counter()
                                cookiefile, tmp_cookie = self.service._get_user_cookiefile(user_id)
                                end_time = time.perf_counter()
                                
                                download_time = end_time - start_time
                                download_times.append(download_time)
                            
                            avg_download_time = sum(download_times) / len(download_times)
                            
                            print(f"S3 download performance:")
                            print(f"  Average: {avg_download_time*1000:.2f}ms")
                            
                            # If S3 downloads are consistently slow, caching might be beneficial
                            if avg_download_time > 0.05:  # 50ms threshold
                                print("  Recommendation: Consider implementing S3 download caching")
    
    def test_concurrent_cookie_operations(self):
        """Test performance under concurrent cookie operations"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create cookie files for multiple users
            user_ids = list(range(1, 21))  # 20 users
            for user_id in user_ids:
                cookie_file = os.path.join(temp_dir, f"{user_id}.txt")
                with open(cookie_file, 'w') as f:
                    f.write(f"# Cookie for user {user_id}\n.youtube.com\tTRUE\t/\tFALSE\t1234567890\ttest\tvalue{user_id}")
            
            def resolve_cookie(user_id):
                """Resolve cookie for a specific user"""
                service = TranscriptService()  # Each thread gets its own service instance
                with patch.dict(os.environ, {'COOKIE_LOCAL_DIR': temp_dir}):
                    start_time = time.perf_counter()
                    cookiefile, tmp_cookie = service._get_user_cookiefile(user_id)
                    end_time = time.perf_counter()
                    return end_time - start_time, cookiefile is not None
            
            # Test concurrent resolution
            start_time = time.perf_counter()
            
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(resolve_cookie, user_id) for user_id in user_ids]
                results = [future.result() for future in as_completed(futures)]
            
            end_time = time.perf_counter()
            total_time = end_time - start_time
            
            # Analyze results
            resolution_times = [result[0] for result in results]
            success_count = sum(1 for result in results if result[1])
            
            avg_resolution_time = sum(resolution_times) / len(resolution_times)
            max_resolution_time = max(resolution_times)
            
            # Performance assertions
            self.assertEqual(success_count, len(user_ids), "Not all cookie resolutions succeeded")
            self.assertLess(total_time, 2.0, f"Total concurrent resolution time too high: {total_time:.2f}s")
            self.assertLess(avg_resolution_time, 0.01, f"Average concurrent resolution time too high: {avg_resolution_time:.4f}s")
            
            print(f"Concurrent cookie resolution performance ({len(user_ids)} users):")
            print(f"  Total time: {total_time:.2f}s")
            print(f"  Average per operation: {avg_resolution_time*1000:.2f}ms")
            print(f"  Maximum per operation: {max_resolution_time*1000:.2f}ms")
            print(f"  Success rate: {success_count}/{len(user_ids)}")
    
    def test_memory_usage_under_load(self):
        """Test memory usage doesn't grow excessively with cookie operations"""
        import gc
        import psutil
        import os as os_module
        
        process = psutil.Process(os_module.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create many cookie files
            user_ids = list(range(1, 101))  # 100 users
            for user_id in user_ids:
                cookie_file = os.path.join(temp_dir, f"{user_id}.txt")
                with open(cookie_file, 'w') as f:
                    # Create larger cookie files to test memory usage
                    cookie_data = f"# Cookie for user {user_id}\n"
                    for i in range(10):  # Multiple cookie entries
                        cookie_data += f".youtube.com\tTRUE\t/\tFALSE\t1234567890\ttest{i}\tvalue{user_id}_{i}\n"
                    f.write(cookie_data)
            
            with patch.dict(os.environ, {'COOKIE_LOCAL_DIR': temp_dir}):
                # Perform many cookie operations
                for _ in range(5):  # 5 rounds
                    for user_id in user_ids:
                        cookiefile, tmp_cookie = self.service._get_user_cookiefile(user_id)
                        # Simulate some processing
                        if cookiefile:
                            with open(cookiefile, 'r') as f:
                                content = f.read()
                                # Process content (simulate real usage)
                                lines = content.split('\n')
                
                # Force garbage collection
                gc.collect()
                
                final_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_increase = final_memory - initial_memory
                
                print(f"Memory usage test:")
                print(f"  Initial memory: {initial_memory:.1f} MB")
                print(f"  Final memory: {final_memory:.1f} MB")
                print(f"  Memory increase: {memory_increase:.1f} MB")
                
                # Memory increase should be reasonable (< 50MB for this test)
                self.assertLess(memory_increase, 50, f"Memory usage increased too much: {memory_increase:.1f} MB")
    
    def test_cookie_failure_tracking_performance(self):
        """Test that cookie failure tracking doesn't impact performance"""
        user_ids = list(range(1, 51))  # 50 users
        
        # Measure time for many failure tracking operations
        start_time = time.perf_counter()
        
        for user_id in user_ids:
            for _ in range(10):  # 10 failures per user
                self.service._track_cookie_failure(user_id, "bot_check")
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        operations = len(user_ids) * 10
        avg_time_per_op = total_time / operations
        
        print(f"Cookie failure tracking performance:")
        print(f"  Total operations: {operations}")
        print(f"  Total time: {total_time:.3f}s")
        print(f"  Average per operation: {avg_time_per_op*1000:.3f}ms")
        
        # Should be very fast
        self.assertLess(avg_time_per_op, 0.001, f"Failure tracking too slow: {avg_time_per_op:.4f}s per operation")


if __name__ == '__main__':
    # Only run if psutil is available
    try:
        import psutil
        unittest.main()
    except ImportError:
        print("psutil not available, skipping memory usage tests")
        # Run tests without memory test
        suite = unittest.TestLoader().loadTestsFromTestCase(TestCookiePerformance)
        # Remove memory test
        suite._tests = [test for test in suite._tests if 'memory_usage' not in test._testMethodName]
        unittest.TextTestRunner().run(suite)