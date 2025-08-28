#!/usr/bin/env python3
"""
Unit tests for DOM helper methods in youtubei_service.py

Tests the _try_consent(), _expand_description(), and _open_transcript() methods
according to task requirements 10.1, 10.2, 10.3.
"""

import unittest
from unittest.mock import AsyncMock, Mock, patch
import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from youtubei_service import DeterministicYouTubeiCapture
    YOUTUBEI_SERVICE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: youtubei_service not available: {e}")
    YOUTUBEI_SERVICE_AVAILABLE = False


class TestDOMHelperMethods(unittest.TestCase):
    """Unit tests for DOM helper methods according to requirements 10.1, 10.2, 10.3"""

    def setUp(self):
        """Set up test fixtures"""
        if not YOUTUBEI_SERVICE_AVAILABLE:
            self.skipTest("youtubei_service not available")
        
        # Create a DeterministicYouTubeiCapture instance
        self.capture = DeterministicYouTubeiCapture(
            job_id="test_job_id",
            video_id="test_video_id"
        )

    def test_try_consent_with_consent_dialog_present(self):
        """Test _try_consent() with mock page showing consent dialog present scenario (Requirement 10.1)"""
        async def run_test():
            # Mock page with consent dialog present
            mock_element = AsyncMock()
            mock_element.is_visible = AsyncMock(return_value=True)
            mock_element.click = AsyncMock()
            
            mock_locator = Mock()
            mock_locator.first = mock_element
            
            mock_page = AsyncMock()
            mock_page.locator = Mock(return_value=mock_locator)
            mock_page.wait_for_timeout = AsyncMock()
            
            self.capture.page = mock_page
            
            # Mock evt function to capture events
            with patch('youtubei_service.evt') as mock_evt:
                await self.capture._try_consent()
                
                # Verify that consent handling was attempted
                self.assertTrue(mock_page.locator.called)
                
                # Verify that success event was logged (should be called with consent handled)
                consent_handled_calls = [call for call in mock_evt.call_args_list 
                                       if call[0][0] == "youtubei_dom_consent_handled"]
                self.assertTrue(len(consent_handled_calls) > 0, "Should log consent handled event")
        
        asyncio.run(run_test())

    def test_try_consent_with_consent_dialog_absent(self):
        """Test _try_consent() with mock page showing consent dialog absent scenario (Requirement 10.1)"""
        async def run_test():
            # Mock page with no consent dialog present
            mock_element = AsyncMock()
            mock_element.is_visible = AsyncMock(return_value=False)
            
            mock_locator = Mock()
            mock_locator.first = mock_element
            
            mock_page = AsyncMock()
            mock_page.locator = Mock(return_value=mock_locator)
            
            self.capture.page = mock_page
            
            # Mock evt function to capture events
            with patch('youtubei_service.evt') as mock_evt:
                await self.capture._try_consent()
                
                # Verify that selectors were tried
                self.assertTrue(mock_page.locator.called)
                
                # Verify that no consent event was logged
                no_consent_calls = [call for call in mock_evt.call_args_list 
                                  if call[0][0] == "youtubei_dom_no_consent"]
                self.assertTrue(len(no_consent_calls) > 0, "Should log no consent event")
        
        asyncio.run(run_test())

    def test_try_consent_timeout_handling(self):
        """Test timeout handling in _try_consent() method (Requirement 10.3)"""
        async def run_test():
            # Mock page with timeout exception
            mock_element = AsyncMock()
            mock_element.is_visible = AsyncMock(side_effect=asyncio.TimeoutError("Timeout"))
            
            mock_locator = Mock()
            mock_locator.first = mock_element
            
            mock_page = AsyncMock()
            mock_page.locator = Mock(return_value=mock_locator)
            
            self.capture.page = mock_page
            
            # Should not raise exception due to graceful degradation
            try:
                await self.capture._try_consent()
            except Exception as e:
                self.fail(f"_try_consent should not raise exception, but got: {e}")
            
            # Test passes if no exception is raised
        
        asyncio.run(run_test())

    def test_try_consent_no_page_error(self):
        """Test _try_consent() graceful handling when page is None (Requirement 10.3)"""
        async def run_test():
            # Set page to None
            self.capture.page = None
            
            # Mock evt function to capture events
            with patch('youtubei_service.evt') as mock_evt:
                await self.capture._try_consent()
                
                # Verify no page event was logged
                no_page_calls = [call for call in mock_evt.call_args_list 
                               if call[0][0] == "youtubei_dom_consent_no_page"]
                self.assertTrue(len(no_page_calls) > 0, "Should log no page event")
        
        asyncio.run(run_test())

    def test_expand_description_with_expander_exists(self):
        """Test _expand_description() with mock page showing expander exists scenario (Requirement 10.2)"""
        async def run_test():
            # Mock page with description expander present
            mock_element = AsyncMock()
            mock_element.is_visible = AsyncMock(return_value=True)
            mock_element.click = AsyncMock()
            
            mock_locator = Mock()
            mock_locator.first = mock_element
            
            mock_page = AsyncMock()
            mock_page.locator = Mock(return_value=mock_locator)
            mock_page.wait_for_timeout = AsyncMock()
            
            self.capture.page = mock_page
            
            # Mock evt function and logger
            with patch('youtubei_service.evt') as mock_evt, \
                 patch('youtubei_service.logger') as mock_logger:
                await self.capture._expand_description()
                
                # Verify that expansion was attempted
                self.assertTrue(mock_page.locator.called)
                
                # Verify success event was logged
                expanded_calls = [call for call in mock_evt.call_args_list 
                                if call[0][0] == "youtubei_dom_expanded_description"]
                self.assertTrue(len(expanded_calls) > 0, "Should log expanded description event")
        
        asyncio.run(run_test())

    def test_expand_description_with_expander_missing(self):
        """Test _expand_description() with mock page showing expander missing scenario (Requirement 10.2)"""
        async def run_test():
            # Mock page with no description expander present
            mock_element = AsyncMock()
            mock_element.is_visible = AsyncMock(return_value=False)
            
            mock_locator = Mock()
            mock_locator.first = mock_element
            
            mock_page = AsyncMock()
            mock_page.locator = Mock(return_value=mock_locator)
            
            self.capture.page = mock_page
            
            # Mock evt function
            with patch('youtubei_service.evt') as mock_evt:
                await self.capture._expand_description()
                
                # Verify that selectors were tried
                self.assertTrue(mock_page.locator.called)
                
                # Verify no expander event was logged
                no_expander_calls = [call for call in mock_evt.call_args_list 
                                   if call[0][0] == "youtubei_dom_no_expander"]
                self.assertTrue(len(no_expander_calls) > 0, "Should log no expander event")
        
        asyncio.run(run_test())

    def test_expand_description_timeout_handling(self):
        """Test timeout handling in _expand_description() method (Requirement 10.3)"""
        async def run_test():
            # Mock page with timeout exception
            mock_element = AsyncMock()
            mock_element.is_visible = AsyncMock(side_effect=asyncio.TimeoutError("Timeout"))
            
            mock_locator = Mock()
            mock_locator.first = mock_element
            
            mock_page = AsyncMock()
            mock_page.locator = Mock(return_value=mock_locator)
            
            self.capture.page = mock_page
            
            # Should not raise exception due to graceful degradation
            try:
                await self.capture._expand_description()
            except Exception as e:
                self.fail(f"_expand_description should not raise exception, but got: {e}")
        
        asyncio.run(run_test())

    def test_expand_description_no_page_error(self):
        """Test _expand_description() graceful handling when page is None (Requirement 10.3)"""
        async def run_test():
            # Set page to None
            self.capture.page = None
            
            # Mock evt function
            with patch('youtubei_service.evt') as mock_evt:
                await self.capture._expand_description()
                
                # Verify no page event was logged
                no_page_calls = [call for call in mock_evt.call_args_list 
                               if call[0][0] == "youtubei_dom_expansion_no_page"]
                self.assertTrue(len(no_page_calls) > 0, "Should log no page event")
        
        asyncio.run(run_test())

    def test_open_transcript_button_found(self):
        """Test _open_transcript() with mock page showing button found scenario (Requirement 10.3)"""
        async def run_test():
            # Mock page with transcript button present and panel appears
            mock_element = AsyncMock()
            mock_element.is_visible = AsyncMock(return_value=True)
            mock_element.click = AsyncMock()
            
            mock_locator = Mock()
            mock_locator.first = mock_element
            
            mock_page = AsyncMock()
            mock_page.locator = Mock(return_value=mock_locator)
            mock_page.wait_for_selector = AsyncMock()
            
            self.capture.page = mock_page
            
            # Mock evt function and logger
            with patch('youtubei_service.evt') as mock_evt, \
                 patch('youtubei_service.logger') as mock_logger:
                result = await self.capture._open_transcript()
                
                # Verify that transcript opening was attempted
                self.assertTrue(mock_page.locator.called)
                
                # Verify method returns True on success
                self.assertTrue(result)
        
        asyncio.run(run_test())

    def test_open_transcript_button_not_found(self):
        """Test _open_transcript() with mock page showing button not found scenario (Requirement 10.3)"""
        async def run_test():
            # Mock page with no transcript button present
            mock_element = AsyncMock()
            mock_element.is_visible = AsyncMock(return_value=False)
            
            mock_locator = Mock()
            mock_locator.first = mock_element
            
            mock_page = AsyncMock()
            mock_page.locator = Mock(return_value=mock_locator)
            
            self.capture.page = mock_page
            
            # Mock evt function and logger
            with patch('youtubei_service.evt') as mock_evt, \
                 patch('youtubei_service.logger') as mock_logger:
                result = await self.capture._open_transcript()
                
                # Verify that selectors were tried
                self.assertTrue(mock_page.locator.called)
                
                # Verify method returns False when button not found
                self.assertFalse(result)
        
        asyncio.run(run_test())

    def test_open_transcript_no_page_error(self):
        """Test _open_transcript() graceful handling when page is None (Requirement 10.3)"""
        async def run_test():
            # Set page to None
            self.capture.page = None
            
            # Mock evt function
            with patch('youtubei_service.evt') as mock_evt:
                result = await self.capture._open_transcript()
                
                # Verify no page event was logged
                no_page_calls = [call for call in mock_evt.call_args_list 
                               if call[0][0] == "youtubei_dom_transcript_no_page"]
                self.assertTrue(len(no_page_calls) > 0, "Should log no page event")
                
                # Should return False
                self.assertFalse(result)
        
        asyncio.run(run_test())

    def test_all_methods_graceful_degradation(self):
        """Test that all DOM helper methods never throw exceptions (Requirement 10.3)"""
        async def run_test():
            # Test that methods handle various exceptions gracefully
            exceptions_to_test = [
                Exception("General error"),
                asyncio.TimeoutError("Timeout"),
                RuntimeError("Runtime error"),
                ValueError("Value error")
            ]
            
            for exception in exceptions_to_test:
                # Mock page that raises exception
                mock_page = AsyncMock()
                mock_page.locator = Mock(side_effect=exception)
                self.capture.page = mock_page
                
                # Test _try_consent
                try:
                    await self.capture._try_consent()
                except Exception as e:
                    self.fail(f"_try_consent raised exception: {e}")
                
                # Test _expand_description
                try:
                    await self.capture._expand_description()
                except Exception as e:
                    self.fail(f"_expand_description raised exception: {e}")
                
                # Test _open_transcript
                try:
                    result = await self.capture._open_transcript()
                    self.assertFalse(result)  # Should return False on error
                except Exception as e:
                    self.fail(f"_open_transcript raised exception: {e}")
        
        asyncio.run(run_test())


def run_tests():
    """Run all DOM helper method tests"""
    if not YOUTUBEI_SERVICE_AVAILABLE:
        print("❌ youtubei_service not available - skipping DOM helper method tests")
        return False
    
    print("🧪 Running DOM Helper Method Unit Tests...")
    print("=" * 60)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestDOMHelperMethods)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print("✅ All DOM helper method unit tests passed!")
        print("Task 7: Add unit tests for DOM helper methods - COMPLETE")
        return True
    else:
        print(f"❌ Some DOM helper method tests failed!")
        print(f"Failures: {len(result.failures)}, Errors: {len(result.errors)}")
        return False


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)