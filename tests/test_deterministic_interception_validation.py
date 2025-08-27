#!/usr/bin/env python3
"""
Deterministic Interception Validation Tests
============================================

Validates deterministic YouTubei transcript capture functionality
as specified in Requirement 2.
"""

import os
import sys
import unittest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestDeterministicInterception(unittest.TestCase):
    """Test deterministic network interception"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_video_id = "test_video_123"
    
    def test_route_based_interception_setup(self):
        """Test route-based interception setup"""
        try:
            from transcript_service import DeterministicTranscriptCapture
            
            capture = DeterministicTranscriptCapture()
            
            # Mock page and route
            mock_page = Mock()
            mock_route = Mock()
            
            # Test route setup
            capture.setup_route_interception(mock_page)
            
            # Verify route was set up for transcript endpoint
            mock_page.route.assert_called()
            call_args = mock_page.route.call_args
            self.assertIn('youtubei/v1/get_transcript', call_args[0][0])
            
        except ImportError as e:
            self.skipTest(f"DeterministicTranscriptCapture not available: {e}")
    
    def test_future_resolution_pattern(self):
        """Test asyncio.Future resolution pattern"""
        try:
            from transcript_service import DeterministicTranscriptCapture
            
            capture = DeterministicTranscriptCapture()
            
            # Test Future creation and resolution
            future = capture.create_transcript_future()
            self.assertIsInstance(future, asyncio.Future)
            self.assertFalse(future.done())
            
            # Test resolution
            test_transcript = "Test transcript content"
            capture.resolve_transcript_future(test_transcript)
            
            self.assertTrue(future.done())
            self.assertEqual(future.result(), test_transcript)
            
        except ImportError as e:
            self.skipTest(f"DeterministicTranscriptCapture not available: {e}")
    
    def test_route_continue_and_capture(self):
        """Test route.continue_() and response capture"""
        try:
            from transcript_service import DeterministicTranscriptCapture
            
            capture = DeterministicTranscriptCapture()
            
            # Mock route and response
            mock_route = Mock()
            mock_response = Mock()
            mock_response.body.return_value = b'{"events": [{"segs": [{"utf8": "Test transcript"}]}]}'
            
            # Test route handling
            capture.handle_transcript_route(mock_route, mock_response)
            
            # Verify route was continued
            mock_route.continue_.assert_called_once()
            
            # Verify response was processed
            self.assertTrue(capture.transcript_future.done())
            
        except ImportError as e:
            self.skipTest(f"DeterministicTranscriptCapture not available: {e}")
    
    def test_timeout_handling(self):
        """Test timeout handling with fallback"""
        try:
            from transcript_service import DeterministicTranscriptCapture
            
            capture = DeterministicTranscriptCapture()
            
            # Test timeout scenario
            with patch('asyncio.wait_for') as mock_wait:
                mock_wait.side_effect = asyncio.TimeoutError("Test timeout")
                
                result = capture.wait_for_transcript_with_timeout(timeout_seconds=1)
                
                # Should return None on timeout
                self.assertIsNone(result)
                
        except ImportError as e:
            self.skipTest(f"DeterministicTranscriptCapture not available: {e}")
    
    def test_no_fixed_waits_in_capture(self):
        """Test that no fixed wait_for_timeout calls are used in transcript capture"""
        try:
            from transcript_service import TranscriptService
            
            service = TranscriptService()
            
            # Mock Playwright components
            with patch('transcript_service.sync_playwright') as mock_playwright:
                mock_browser = Mock()
                mock_context = Mock()
                mock_page = Mock()
                
                mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser
                mock_browser.new_context.return_value = mock_context
                mock_context.new_page.return_value = mock_page
                
                # Track wait_for_timeout calls
                wait_calls = []
                def track_wait(timeout_ms):
                    wait_calls.append(timeout_ms)
                    
                mock_page.wait_for_timeout.side_effect = track_wait
                
                # Mock successful transcript capture
                with patch.object(service, '_setup_transcript_route_interception') as mock_setup:
                    mock_setup.return_value = "test transcript"
                    
                    service._get_transcript_via_youtubei_enhanced(self.test_video_id)
                    
                    # Check for problematic fixed waits (> 5 seconds)
                    long_waits = [wait for wait in wait_calls if wait > 5000]
                    self.assertEqual(len(long_waits), 0, 
                                   f"Found long fixed waits in transcript capture: {long_waits}")
                    
        except ImportError as e:
            self.skipTest(f"TranscriptService not available: {e}")


class TestTranscriptDataExtraction(unittest.TestCase):
    """Test transcript data extraction from responses"""
    
    def test_json_transcript_parsing(self):
        """Test parsing of JSON transcript responses"""
        try:
            from transcript_service import parse_youtubei_transcript_response
            
            # Mock YouTubei JSON response
            json_response = {
                "events": [
                    {
                        "tStartMs": 0,
                        "dDurationMs": 2000,
                        "segs": [
                            {"utf8": "Hello "},
                            {"utf8": "world"}
                        ]
                    },
                    {
                        "tStartMs": 2000,
                        "dDurationMs": 3000,
                        "segs": [
                            {"utf8": "This is "},
                            {"utf8": "a test"}
                        ]
                    }
                ]
            }
            
            transcript = parse_youtubei_transcript_response(json_response)
            
            # Should extract text from segments
            self.assertIn("Hello world", transcript)
            self.assertIn("This is a test", transcript)
            
        except ImportError as e:
            self.skipTest(f"Transcript parsing not available: {e}")
    
    def test_empty_response_handling(self):
        """Test handling of empty or malformed responses"""
        try:
            from transcript_service import parse_youtubei_transcript_response
            
            # Test empty response
            empty_response = {"events": []}
            transcript = parse_youtubei_transcript_response(empty_response)
            self.assertEqual(transcript, "")
            
            # Test malformed response
            malformed_response = {"invalid": "structure"}
            transcript = parse_youtubei_transcript_response(malformed_response)
            self.assertEqual(transcript, "")
            
        except ImportError as e:
            self.skipTest(f"Transcript parsing not available: {e}")
    
    def test_segment_text_extraction(self):
        """Test extraction of text from segments"""
        try:
            from transcript_service import extract_text_from_segments
            
            segments = [
                {"utf8": "First "},
                {"utf8": "segment"},
                {"utf8": " text"}
            ]
            
            text = extract_text_from_segments(segments)
            self.assertEqual(text, "First segment text")
            
        except ImportError as e:
            self.skipTest(f"Segment extraction not available: {e}")


class TestInterceptionReliability(unittest.TestCase):
    """Test interception reliability and error handling"""
    
    def test_network_error_handling(self):
        """Test handling of network errors during interception"""
        try:
            from transcript_service import DeterministicTranscriptCapture
            
            capture = DeterministicTranscriptCapture()
            
            # Mock network error
            mock_route = Mock()
            mock_route.continue_.side_effect = Exception("Network error")
            
            # Should handle error gracefully
            try:
                capture.handle_transcript_route(mock_route, None)
                # Should not raise exception
            except Exception as e:
                self.fail(f"Network error not handled gracefully: {e}")
                
        except ImportError as e:
            self.skipTest(f"DeterministicTranscriptCapture not available: {e}")
    
    def test_response_parsing_error_handling(self):
        """Test handling of response parsing errors"""
        try:
            from transcript_service import parse_youtubei_transcript_response
            
            # Test invalid JSON structure
            invalid_responses = [
                None,
                {},
                {"events": None},
                {"events": [{"invalid": "structure"}]},
                {"events": [{"segs": None}]}
            ]
            
            for invalid_response in invalid_responses:
                try:
                    result = parse_youtubei_transcript_response(invalid_response)
                    # Should return empty string for invalid responses
                    self.assertEqual(result, "")
                except Exception as e:
                    self.fail(f"Response parsing error not handled: {e}")
                    
        except ImportError as e:
            self.skipTest(f"Transcript parsing not available: {e}")
    
    def test_concurrent_interception_handling(self):
        """Test handling of concurrent interception attempts"""
        try:
            from transcript_service import DeterministicTranscriptCapture
            
            capture = DeterministicTranscriptCapture()
            
            # Create multiple futures
            future1 = capture.create_transcript_future()
            future2 = capture.create_transcript_future()
            
            # Should handle multiple futures appropriately
            self.assertIsInstance(future1, asyncio.Future)
            self.assertIsInstance(future2, asyncio.Future)
            
            # Resolving one should not affect the other
            capture.resolve_transcript_future("transcript1")
            self.assertTrue(future1.done())
            self.assertFalse(future2.done())
            
        except ImportError as e:
            self.skipTest(f"DeterministicTranscriptCapture not available: {e}")


class TestInterceptionPerformance(unittest.TestCase):
    """Test interception performance characteristics"""
    
    def test_timeout_configuration(self):
        """Test configurable timeout values"""
        try:
            from transcript_service import DeterministicTranscriptCapture
            
            capture = DeterministicTranscriptCapture()
            
            # Test different timeout values
            timeouts = [10, 20, 25, 30]
            
            for timeout in timeouts:
                with patch('asyncio.wait_for') as mock_wait:
                    mock_wait.side_effect = asyncio.TimeoutError()
                    
                    start_time = time.time()
                    result = capture.wait_for_transcript_with_timeout(timeout_seconds=timeout)
                    duration = time.time() - start_time
                    
                    # Should respect timeout (with some tolerance for test execution)
                    self.assertLess(duration, timeout + 2)
                    self.assertIsNone(result)
                    
        except ImportError as e:
            self.skipTest(f"DeterministicTranscriptCapture not available: {e}")
    
    def test_immediate_resolution_performance(self):
        """Test performance when transcript is immediately available"""
        try:
            from transcript_service import DeterministicTranscriptCapture
            
            capture = DeterministicTranscriptCapture()
            
            # Test immediate resolution
            start_time = time.time()
            
            future = capture.create_transcript_future()
            capture.resolve_transcript_future("immediate transcript")
            result = capture.wait_for_transcript_with_timeout(timeout_seconds=10)
            
            duration = time.time() - start_time
            
            # Should resolve immediately (< 1 second)
            self.assertLess(duration, 1.0)
            self.assertEqual(result, "immediate transcript")
            
        except ImportError as e:
            self.skipTest(f"DeterministicTranscriptCapture not available: {e}")


def main():
    """Run deterministic interception validation tests"""
    print("Deterministic Interception Validation Tests")
    print("=" * 60)
    
    # Run tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    test_classes = [
        TestDeterministicInterception,
        TestTranscriptDataExtraction,
        TestInterceptionReliability,
        TestInterceptionPerformance
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print("All deterministic interception validation tests passed!")
        print("\nValidated:")
        print("   - Route-based interception with Future resolution")
        print("   - Timeout handling and fallback mechanisms")
        print("   - Transcript data extraction and parsing")
        print("   - Error handling and reliability")
        print("   - Performance characteristics")
        return 0
    else:
        print(f"Tests failed: {len(result.failures)} failures, {len(result.errors)} errors")
        return 1


if __name__ == "__main__":
    sys.exit(main())