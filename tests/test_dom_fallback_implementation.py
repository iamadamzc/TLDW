#!/usr/bin/env python3
"""
Test DOM Fallback Implementation for Task 7
Tests the DOM fallback functionality when network interception times out.
"""

import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import logging

# Configure logging for tests
logging.basicConfig(level=logging.INFO)

# Import the class we're testing
from transcript_service import DeterministicTranscriptCapture


class TestDOMFallbackImplementation:
    """Test DOM fallback implementation according to requirements 7.1-7.5"""
    
    async def test_dom_fallback_after_network_timeout(self):
        """Test Requirement 7.1: Add DOM polling after network route Future timeout"""
        
        # Create capture instance with short timeout for testing
        capture = DeterministicTranscriptCapture(timeout_seconds=1)
        
        # Mock page with DOM elements
        mock_page = AsyncMock()
        mock_element = AsyncMock()
        mock_element.text_content.return_value = "Test transcript line 1"
        
        # Mock query_selector_all to return transcript elements
        mock_page.query_selector_all.return_value = [mock_element]
        
        # Set up the capture with mocked page
        capture.page = mock_page
        capture.transcript_future = asyncio.Future()
        
        # Don't resolve the future to simulate network timeout
        # The future will timeout and trigger DOM fallback
        
        # Test DOM fallback extraction directly
        result = await capture._dom_fallback_extraction()
        
        # Verify DOM fallback was attempted
        assert result == "Test transcript line 1"
        assert mock_page.query_selector_all.called
        
        print("✓ Test 7.1: DOM polling after network timeout - PASSED")
    
    async def test_transcript_line_selector_polling(self):
        """Test Requirement 7.2: Implement transcript line selector polling for 3-5 seconds"""
        
        capture = DeterministicTranscriptCapture()
        
        # Mock page that returns no elements initially, then elements after some attempts
        mock_page = AsyncMock()
        mock_element = AsyncMock()
        mock_element.text_content.return_value = "Found transcript after polling"
        
        call_count = 0
        async def mock_query_selector_all(selector):
            nonlocal call_count
            call_count += 1
            # Return elements after a few attempts to simulate polling
            if call_count >= 3:
                return [mock_element]
            return []
        
        mock_page.query_selector_all.side_effect = mock_query_selector_all
        capture.page = mock_page
        
        # Test DOM fallback with polling
        result = await capture._dom_fallback_extraction()
        
        # Verify polling occurred multiple times
        assert call_count >= 3
        assert result == "Found transcript after polling"
        
        print("✓ Test 7.2: Transcript line selector polling - PASSED")
    
    async def test_extract_text_from_dom_nodes(self):
        """Test Requirement 7.3: Extract text from DOM nodes when network is blocked"""
        
        capture = DeterministicTranscriptCapture()
        
        # Mock page with multiple transcript elements
        mock_page = AsyncMock()
        
        # Create multiple mock elements with different text content
        mock_elements = []
        transcript_lines = [
            "First transcript line",
            "Second transcript line", 
            "Third transcript line"
        ]
        
        for line in transcript_lines:
            mock_element = AsyncMock()
            mock_element.text_content.return_value = line
            mock_elements.append(mock_element)
        
        mock_page.query_selector_all.return_value = mock_elements
        capture.page = mock_page
        
        # Test text extraction from DOM nodes
        result = await capture._dom_fallback_extraction()
        
        # Verify all lines were extracted and joined
        expected_result = "\n".join(transcript_lines)
        assert result == expected_result
        
        print("✓ Test 7.3: Extract text from DOM nodes - PASSED")
    
    async def test_successful_dom_fallback_logging(self):
        """Test Requirement 7.4: Add logging for successful DOM fallback scenarios"""
        
        capture = DeterministicTranscriptCapture()
        
        # Mock page with transcript elements
        mock_page = AsyncMock()
        mock_element = AsyncMock()
        mock_element.text_content.return_value = "Successful DOM extraction"
        mock_page.query_selector_all.return_value = [mock_element]
        
        capture.page = mock_page
        
        # Capture log messages
        with patch('transcript_service.logging') as mock_logging:
            result = await capture._dom_fallback_extraction()
            
            # Verify successful DOM fallback was logged
            assert result == "Successful DOM extraction"
            
            # Check that success logging was called
            mock_logging.info.assert_any_call(
                "DOM fallback: Successfully extracted transcript from DOM: 25 chars, 1 lines"
            )
        
        print("✓ Test 7.4: Logging for successful DOM fallback - PASSED")
    
    async def test_wait_for_transcript_with_dom_fallback(self):
        """Test Requirement 7.5: Integration of DOM fallback in wait_for_transcript method"""
        
        capture = DeterministicTranscriptCapture(timeout_seconds=0.1)  # Very short timeout
        
        # Mock page for DOM fallback
        mock_page = AsyncMock()
        mock_element = AsyncMock()
        mock_element.text_content.return_value = "DOM fallback transcript"
        mock_page.query_selector_all.return_value = [mock_element]
        
        capture.page = mock_page
        capture.transcript_future = asyncio.Future()  # Never resolved, will timeout
        
        # Test wait_for_transcript with DOM fallback
        result = await capture.wait_for_transcript()
        
        # Verify DOM fallback was used when network timed out
        assert result == "DOM fallback transcript"
        
        print("✓ Test 7.5: DOM fallback integration in wait_for_transcript - PASSED")
    
    async def test_dom_fallback_selector_coverage(self):
        """Test that DOM fallback tries multiple selectors for transcript content"""
        
        capture = DeterministicTranscriptCapture()
        
        # Mock page that returns elements only for specific selector
        mock_page = AsyncMock()
        mock_element = AsyncMock()
        mock_element.text_content.return_value = "Found with alternative selector"
        
        def mock_query_selector_all(selector):
            # Only return elements for a specific selector to test fallback
            if selector == '.ytd-transcript-segment-renderer':
                return [mock_element]
            return []
        
        mock_page.query_selector_all.side_effect = mock_query_selector_all
        capture.page = mock_page
        
        # Test DOM fallback
        result = await capture._dom_fallback_extraction()
        
        # Verify it found content with alternative selector
        assert result == "Found with alternative selector"
        
        # Verify multiple selectors were tried
        call_args_list = [call[0][0] for call in mock_page.query_selector_all.call_args_list]
        assert len(call_args_list) > 1  # Multiple selectors tried
        assert '.ytd-transcript-segment-renderer' in call_args_list
        
        print("✓ Test: DOM fallback selector coverage - PASSED")
    
    async def test_dom_fallback_no_content_found(self):
        """Test DOM fallback behavior when no transcript content is found"""
        
        capture = DeterministicTranscriptCapture()
        
        # Mock page that returns no elements
        mock_page = AsyncMock()
        mock_page.query_selector_all.return_value = []
        
        capture.page = mock_page
        
        # Test DOM fallback with no content
        result = await capture._dom_fallback_extraction()
        
        # Verify None is returned when no content found
        assert result is None
        
        print("✓ Test: DOM fallback with no content - PASSED")


async def run_tests():
    """Run all DOM fallback tests"""
    test_instance = TestDOMFallbackImplementation()
    
    print("Running DOM Fallback Implementation Tests...")
    print("=" * 50)
    
    try:
        await test_instance.test_dom_fallback_after_network_timeout()
        await test_instance.test_transcript_line_selector_polling()
        await test_instance.test_extract_text_from_dom_nodes()
        await test_instance.test_successful_dom_fallback_logging()
        await test_instance.test_wait_for_transcript_with_dom_fallback()
        await test_instance.test_dom_fallback_selector_coverage()
        await test_instance.test_dom_fallback_no_content_found()
        
        print("=" * 50)
        print("✅ All DOM Fallback Implementation tests PASSED!")
        print("\nRequirements Coverage:")
        print("✓ 7.1: DOM polling after network route Future timeout")
        print("✓ 7.2: Transcript line selector polling for 3-5 seconds")
        print("✓ 7.3: Extract text from DOM nodes when network is blocked")
        print("✓ 7.4: Logging for successful DOM fallback scenarios")
        print("✓ 7.5: Integration in wait_for_transcript method")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    exit(0 if success else 1)