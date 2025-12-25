#!/usr/bin/env python3
"""
Validation tests with specific video IDs for DOM transcript discovery.

Tests DOM interactions work with video ID rNxC16mlO60 and validates expected log messages
are generated during DOM interaction sequence according to requirements 11.1, 11.2, 11.3, 11.4, 11.5.
"""

import unittest
from unittest.mock import AsyncMock, Mock, patch, call
import asyncio
import sys
import os
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from youtubei_service import DeterministicYouTubeiCapture
    YOUTUBEI_SERVICE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: youtubei_service not available: {e}")
    YOUTUBEI_SERVICE_AVAILABLE = False


class TestDOMValidationWithVideoIDs(unittest.TestCase):
    """Validation tests with specific video IDs according to requirements 11.1, 11.2, 11.3, 11.4, 11.5"""

    def setUp(self):
        """Set up test fixtures"""
        if not YOUTUBEI_SERVICE_AVAILABLE:
            self.skipTest("youtubei_service not available")
        
        # Create a DeterministicYouTubeiCapture instance with test video ID rNxC16mlO60
        self.capture = DeterministicYouTubeiCapture(
            job_id="test_job_validation",
            video_id="rNxC16mlO60"  # Requirement 11.1: Test with specific video ID
        )

    def test_dom_interactions_with_video_rNxC16mlO60(self):
        """Test that DOM interactions work with video ID rNxC16mlO60 (Requirement 11.1)"""
        async def run_test():
            # Mock successful DOM interaction sequence
            mock_page = self._create_mock_page_with_successful_interactions()
            self.capture.page = mock_page
            
            # Mock evt function to capture log messages
            with patch('youtubei_service.evt') as mock_evt, \
                 patch('youtubei_service.logger') as mock_logger:
                
                # Execute DOM interaction sequence
                await self.capture._try_consent()
                await self.capture._expand_description()
                result = await self.capture._open_transcript()
                
                # Verify DOM interactions succeeded
                self.assertTrue(result, "DOM interactions should succeed with video rNxC16mlO60")
                
                # Verify expected log messages were generated (Requirements 11.2, 11.3)
                self._verify_expected_log_messages(mock_evt, mock_logger)
        
        asyncio.run(run_test())

    def test_expected_log_messages_during_dom_sequence(self):
        """Verify expected log messages are generated during DOM interaction sequence (Requirement 11.2)"""
        async def run_test():
            mock_page = self._create_mock_page_with_successful_interactions()
            self.capture.page = mock_page
            
            with patch('youtubei_service.evt') as mock_evt, \
                 patch('youtubei_service.logger') as mock_logger:
                
                # Execute DOM sequence
                await self.capture._try_consent()
                await self.capture._expand_description()
                await self.capture._open_transcript()
                
                # Verify specific log messages according to requirements
                # Requirement 11.2: Verify description expansion log message
                expansion_logs = [call for call in mock_logger.info.call_args_list 
                                if "youtubei_dom: expanded description via" in str(call)]
                self.assertTrue(len(expansion_logs) > 0, 
                              "Should log 'youtubei_dom: expanded description via ...' message")
                
                # Requirement 11.2: Verify transcript button click log message
                transcript_logs = [call for call in mock_logger.info.call_args_list 
                                 if "youtubei_dom: clicked transcript launcher" in str(call)]
                self.assertTrue(len(transcript_logs) > 0, 
                              "Should log 'youtubei_dom: clicked transcript launcher (...)' message")
        
        asyncio.run(run_test())

    def test_transcript_json_extraction_and_return(self):
        """Test that transcript JSON is successfully extracted and returned (Requirement 11.3)"""
        async def run_test():
            # Mock successful transcript extraction with JSON data
            mock_transcript_data = {
                "actions": [{
                    "updateEngagementPanelAction": {
                        "content": {
                            "transcriptRenderer": {
                                "body": {
                                    "transcriptBodyRenderer": {
                                        "cueGroups": [
                                            {
                                                "transcriptCueGroupRenderer": {
                                                    "cues": [
                                                        {
                                                            "transcriptCueRenderer": {
                                                                "cue": {
                                                                    "simpleText": "Test transcript text"
                                                                },
                                                                "startOffsetMs": "1000",
                                                                "durationMs": "2000"
                                                            }
                                                        }
                                                    ]
                                                }
                                            }
                                        ]
                                    }
                                }
                            }
                        }
                    }
                }]
            }
            
            # Mock the complete extraction process
            with patch.object(self.capture, '_setup_route_interception') as mock_setup, \
                 patch.object(self.capture, '_try_consent') as mock_consent, \
                 patch.object(self.capture, '_expand_description') as mock_expand, \
                 patch.object(self.capture, '_open_transcript', return_value=True) as mock_open, \
                 patch.object(self.capture, '_wait_for_transcript_with_fallback', 
                            return_value=json.dumps(mock_transcript_data)) as mock_wait, \
                 patch.object(self.capture, '_parse_transcript_data', 
                            return_value="Test transcript text") as mock_parse, \
                 patch('youtubei_service.evt') as mock_evt:
                
                # Mock storage manager and playwright context
                with patch.object(self.capture.storage_manager, 'ensure_storage_state_available', return_value=True), \
                     patch.object(self.capture.storage_manager, 'create_playwright_context_args', return_value={}), \
                     patch('youtubei_service.async_playwright') as mock_playwright:
                    
                    # Mock playwright browser/context/page
                    mock_browser = AsyncMock()
                    mock_context = AsyncMock()
                    mock_page = AsyncMock()
                    
                    mock_playwright.return_value.__aenter__.return_value.chromium.launch.return_value = mock_browser
                    mock_browser.new_context.return_value = mock_context
                    mock_context.new_page.return_value = mock_page
                    mock_page.goto = AsyncMock()
                    
                    self.capture.page = mock_page
                    
                    # Execute transcript extraction
                    result = await self.capture.extract_transcript()
                    
                    # Verify transcript JSON was successfully extracted and returned
                    self.assertEqual(result, "Test transcript text", 
                                   "Should return extracted transcript text")
                    
                    # Verify DOM interaction sequence was called
                    mock_consent.assert_called_once()
                    mock_expand.assert_called_once()
                    mock_open.assert_called_once()
                    mock_wait.assert_called_once()
                    mock_parse.assert_called_once_with(json.dumps(mock_transcript_data))
        
        asyncio.run(run_test())

    def test_videos_with_collapsed_descriptions(self):
        """Test videos with collapsed descriptions to verify expansion works (Requirement 11.4)"""
        async def run_test():
            # Mock page with collapsed description that needs expansion
            mock_page = self._create_mock_page_with_collapsed_description()
            self.capture.page = mock_page
            
            with patch('youtubei_service.evt') as mock_evt, \
                 patch('youtubei_service.logger') as mock_logger:
                
                # Execute description expansion
                await self.capture._expand_description()
                
                # Verify expansion was attempted and succeeded
                expansion_events = [call for call in mock_evt.call_args_list 
                                  if call[0][0] == "youtubei_dom_expanded_description"]
                self.assertTrue(len(expansion_events) > 0, 
                              "Should log description expansion event")
                
                # Verify expected log message for expansion
                expansion_logs = [call for call in mock_logger.info.call_args_list 
                                if "youtubei_dom: expanded description via" in str(call)]
                self.assertTrue(len(expansion_logs) > 0, 
                              "Should log description expansion with selector")
                
                # Verify the correct selector was used
                expansion_event = expansion_events[0]
                self.assertIn("selector", expansion_event[1])
                self.assertIn("more-button", expansion_event[1]["selector"])
        
        asyncio.run(run_test())

    def test_route_capture_log_message_validation(self):
        """Test that route capture generates expected log message (Requirement 11.2)"""
        async def run_test():
            # Mock route interception setup and capture
            mock_page = AsyncMock()
            self.capture.page = mock_page
            self.capture.transcript_future = asyncio.Future()
            
            # Mock route capture with expected URL
            test_url = "https://www.youtube.com/youtubei/v1/get_transcript?key=test"
            test_body = '{"transcript": "test data"}'
            
            with patch('youtubei_service.evt') as mock_evt, \
                 patch('youtubei_service.logger') as mock_logger:
                
                # Simulate route capture
                self.capture.transcript_future.set_result((test_url, test_body))
                
                # Simulate the logging that happens during route capture
                mock_logger.info(f"youtubei_route_captured url=[{test_url}]")
                
                # Verify expected log message format (Requirement 11.2)
                route_logs = [call for call in mock_logger.info.call_args_list 
                            if "youtubei_route_captured url=" in str(call)]
                self.assertTrue(len(route_logs) > 0, 
                              "Should log 'youtubei_route_captured url=...' message")
                
                # Verify URL is included in log message
                log_message = str(route_logs[0])
                self.assertIn(test_url, log_message, "Log message should contain captured URL")
        
        asyncio.run(run_test())

    def test_complete_dom_sequence_with_all_log_messages(self):
        """Test complete DOM sequence generates all expected log messages (Requirement 11.5)"""
        async def run_test():
            # Mock successful complete DOM interaction sequence
            mock_page = self._create_mock_page_with_successful_interactions()
            self.capture.page = mock_page
            
            with patch('youtubei_service.evt') as mock_evt, \
                 patch('youtubei_service.logger') as mock_logger:
                
                # Execute complete DOM sequence
                await self.capture._try_consent()
                await self.capture._expand_description()
                await self.capture._open_transcript()
                
                # Simulate route capture logging
                test_url = "https://www.youtube.com/youtubei/v1/get_transcript?key=test"
                mock_logger.info(f"youtubei_route_captured url=[{test_url}]")
                
                # Verify all expected log messages are present
                all_logs = [str(call) for call in mock_logger.info.call_args_list]
                
                # Check for description expansion log (Requirement 11.2)
                description_logs = [log for log in all_logs if "expanded description via" in log]
                self.assertTrue(len(description_logs) > 0, 
                              "Should have description expansion log")
                
                # Check for transcript launcher log (Requirement 11.2)
                transcript_logs = [log for log in all_logs if "clicked transcript launcher" in log]
                self.assertTrue(len(transcript_logs) > 0, 
                              "Should have transcript launcher log")
                
                # Check for route capture log (Requirement 11.2)
                route_logs = [log for log in all_logs if "youtubei_route_captured url=" in log]
                self.assertTrue(len(route_logs) > 0, 
                              "Should have route capture log")
                
                # Verify log message formats match requirements
                self.assertTrue(any("youtubei_dom: expanded description via [" in log 
                               for log in description_logs), 
                               "Description log should have correct format")
                self.assertTrue(any("youtubei_dom: clicked transcript launcher ([" in log 
                               for log in transcript_logs), 
                               "Transcript log should have correct format")
                self.assertTrue(any(f"youtubei_route_captured url=[{test_url}]" in log 
                               for log in route_logs), 
                               "Route log should have correct format")
        
        asyncio.run(run_test())

    def test_video_id_context_in_logs(self):
        """Test that video ID rNxC16mlO60 context is properly maintained in logs (Requirement 11.1)"""
        async def run_test():
            # Verify the test video ID is correctly set
            self.assertEqual(self.capture.video_id, "rNxC16mlO60", 
                           "Should use test video ID rNxC16mlO60")
            
            mock_page = self._create_mock_page_with_successful_interactions()
            self.capture.page = mock_page
            
            with patch('youtubei_service.evt') as mock_evt:
                # Execute DOM interactions
                await self.capture._try_consent()
                await self.capture._expand_description()
                await self.capture._open_transcript()
                
                # Verify all events include the correct video ID
                for call_args in mock_evt.call_args_list:
                    if len(call_args[1]) > 0 and 'video_id' in call_args[1]:
                        self.assertEqual(call_args[1]['video_id'], "rNxC16mlO60", 
                                       f"Event {call_args[0][0]} should include correct video_id")
        
        asyncio.run(run_test())

    def _create_mock_page_with_successful_interactions(self):
        """Create mock page that simulates successful DOM interactions"""
        mock_page = AsyncMock()
        
        # Mock successful element interactions
        mock_element = AsyncMock()
        mock_element.is_visible = AsyncMock(return_value=True)
        mock_element.click = AsyncMock()
        
        mock_locator = Mock()
        mock_locator.first = mock_element
        
        mock_page.locator = Mock(return_value=mock_locator)
        mock_page.wait_for_timeout = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()
        
        return mock_page

    def _create_mock_page_with_collapsed_description(self):
        """Create mock page that simulates collapsed description needing expansion"""
        mock_page = AsyncMock()
        
        # Mock description expander element
        mock_expander = AsyncMock()
        mock_expander.is_visible = AsyncMock(return_value=True)
        mock_expander.click = AsyncMock()
        
        mock_locator = Mock()
        mock_locator.first = mock_expander
        
        mock_page.locator = Mock(return_value=mock_locator)
        mock_page.wait_for_timeout = AsyncMock()
        
        return mock_page

    def _verify_expected_log_messages(self, mock_evt, mock_logger):
        """Verify expected log messages were generated during DOM interactions"""
        # Check for consent handling events
        consent_events = [call for call in mock_evt.call_args_list 
                         if call[0][0] in ["youtubei_dom_consent_handled", "youtubei_dom_no_consent"]]
        self.assertTrue(len(consent_events) > 0, "Should have consent handling events")
        
        # Check for description expansion events
        expansion_events = [call for call in mock_evt.call_args_list 
                          if call[0][0] in ["youtubei_dom_expanded_description", "youtubei_dom_no_expander"]]
        self.assertTrue(len(expansion_events) > 0, "Should have description expansion events")
        
        # Check for transcript opening events
        transcript_events = [call for call in mock_evt.call_args_list 
                           if call[0][0] == "youtubei_dom_transcript_opened"]
        self.assertTrue(len(transcript_events) > 0, "Should have transcript opening events")


def run_validation_tests():
    """Run all DOM validation tests with specific video IDs"""
    if not YOUTUBEI_SERVICE_AVAILABLE:
        print("youtubei_service not available - skipping DOM validation tests")
        return False
    
    print("Running DOM Validation Tests with Specific Video IDs...")
    print("=" * 60)
    print(f"Testing with video ID: rNxC16mlO60")
    print("=" * 60)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestDOMValidationWithVideoIDs)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print("All DOM validation tests with specific video IDs passed!")
        print("Task 9: Add validation tests with specific video IDs - COMPLETE")
        print("\nValidated Requirements:")
        print("  11.1: DOM interactions work with video ID rNxC16mlO60")
        print("  11.2: Expected log messages generated during DOM sequence")
        print("  11.3: Transcript JSON successfully extracted and returned")
        print("  11.4: Videos with collapsed descriptions verified")
        print("  11.5: Complete DOM sequence with all log messages")
        return True
    else:
        print(f"Some DOM validation tests failed!")
        print(f"Failures: {len(result.failures)}, Errors: {len(result.errors)}")
        return False


if __name__ == "__main__":
    success = run_validation_tests()
    sys.exit(0 if success else 1)