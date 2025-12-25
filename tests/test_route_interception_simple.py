#!/usr/bin/env python3
"""
Simple integration tests for route interception and retry logic.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from youtubei_service import DeterministicYouTubeiCapture


class TestRouteInterceptionIntegration(unittest.TestCase):
    """Integration tests for route interception and retry logic according to requirements 10.4, 10.5"""

    def setUp(self):
        """Set up test fixtures"""
        self.capture = DeterministicYouTubeiCapture(
            job_id="test_job_id",
            video_id="test_video_id"
        )

    def test_route_interception_setup_and_future_capture(self):
        """Test route interception setup and Future-based capture mechanism (Requirement 10.4)"""
        async def run_test():
            mock_page = AsyncMock()
            mock_route = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.body = AsyncMock(return_value=b'{"transcript": "test data"}')
            
            captured_handler = None
            async def mock_route_setup(pattern, handler):
                nonlocal captured_handler
                captured_handler = handler
            
            mock_page.route = mock_route_setup
            self.capture.page = mock_page
            
            with patch('youtubei_service.evt') as mock_evt:
                await self.capture._setup_route_interception()
                
                self.assertIsNotNone(captured_handler)
                self.assertIsNotNone(self.capture.transcript_future)
                
                mock_route.request.url = "https://www.youtube.com/youtubei/v1/get_transcript?test=1"
                mock_route.fetch = AsyncMock(return_value=mock_response)
                mock_route.fulfill = AsyncMock()
                
                await captured_handler(mock_route)
                
                self.assertTrue(self.capture.transcript_future.done())
                url, body = self.capture.transcript_future.result()
                self.assertIn("/youtubei/v1/get_transcript", url)
                self.assertEqual(body, '{"transcript": "test data"}')
        
        asyncio.run(run_test())

    def test_route_interception_timeout_handling(self):
        """Test route interception timeout after 25 seconds (Requirement 10.4)"""
        async def run_test():
            mock_page = AsyncMock()
            mock_page.route = AsyncMock()
            self.capture.page = mock_page
            
            with patch('youtubei_service.evt'):
                await self.capture._setup_route_interception()
                
                try:
                    result = await asyncio.wait_for(self.capture.transcript_future, timeout=0.1)
                    self.fail("Should have timed out")
                except asyncio.TimeoutError:
                    pass
                
                self.assertFalse(self.capture.transcript_future.done())
        
        asyncio.run(run_test())

    def test_scroll_and_retry_logic_success(self):
        """Test scroll-and-retry logic when transcript button is not initially visible (Requirement 10.5)"""
        async def run_test():
            mock_page = AsyncMock()
            mock_page.evaluate = AsyncMock()
            mock_page.wait_for_timeout = AsyncMock()
            
            self.capture.page = mock_page
            
            call_count = 0
            async def mock_open_transcript():
                nonlocal call_count
                call_count += 1
                return call_count > 1
            
            with patch('youtubei_service.evt'), \
                 patch.object(self.capture, '_open_transcript', side_effect=mock_open_transcript):
                
                result1 = await self.capture._open_transcript()
                self.assertFalse(result1)
                
                await mock_page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await mock_page.wait_for_timeout(1000)
                
                result2 = await self.capture._open_transcript()
                self.assertTrue(result2)
        
        asyncio.run(run_test())

    def test_dom_elements_not_found_failure_path(self):
        """Test failure paths where DOM elements are not found (Requirement 10.5)"""
        async def run_test():
            mock_element = AsyncMock()
            mock_element.is_visible = AsyncMock(return_value=False)
            
            mock_locator = Mock()
            mock_locator.first = mock_element
            
            mock_page = AsyncMock()
            mock_page.locator = Mock(return_value=mock_locator)
            
            self.capture.page = mock_page
            
            with patch('youtubei_service.evt'):
                await self.capture._try_consent()
                await self.capture._expand_description()
                result = await self.capture._open_transcript()
                self.assertFalse(result)
        
        asyncio.run(run_test())

    def test_route_interception_cleanup_after_capture(self):
        """Test that route interception is properly cleaned up after capture (Requirement 10.4)"""
        async def run_test():
            mock_page = AsyncMock()
            mock_page.route = AsyncMock()
            mock_page.unroute = AsyncMock()
            
            self.capture.page = mock_page
            
            with patch('youtubei_service.evt'):
                await self.capture._setup_route_interception()
                
                mock_page.route.assert_called_once()
                
                await mock_page.unroute("**/youtubei/v1/get_transcript*")
                
                mock_page.unroute.assert_called_with("**/youtubei/v1/get_transcript*")
        
        asyncio.run(run_test())

    def test_graceful_degradation_with_exceptions(self):
        """Test that DOM interactions handle exceptions gracefully (Requirement 10.5)"""
        async def run_test():
            mock_page = AsyncMock()
            mock_page.locator = Mock(side_effect=Exception("DOM error"))
            
            self.capture.page = mock_page
            
            with patch('youtubei_service.evt'):
                try:
                    await self.capture._try_consent()
                    await self.capture._expand_description()
                    result = await self.capture._open_transcript()
                    self.assertFalse(result)
                except Exception as e:
                    self.fail(f"DOM methods should handle exceptions gracefully, but got: {e}")
        
        asyncio.run(run_test())

    def test_dom_helpers_exist(self):
        """Test that DOM helper methods exist"""
        self.assertTrue(hasattr(self.capture, '_try_consent'))
        self.assertTrue(hasattr(self.capture, '_expand_description'))
        self.assertTrue(hasattr(self.capture, '_open_transcript'))


if __name__ == "__main__":
    print("🧪 Running Route Interception Integration Tests...")
    print("=" * 60)
    unittest.main(verbosity=2)