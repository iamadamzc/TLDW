#!/usr/bin/env python3
"""
Integration test for DOM Fallback Implementation
Tests the DOM fallback functionality within the full transcript service context.
"""

import asyncio
import logging
from unittest.mock import Mock, AsyncMock, patch

# Configure logging for tests
logging.basicConfig(level=logging.INFO)

# Import transcript service functions
from transcript_service import (
    DeterministicTranscriptCapture,
    _get_transcript_via_youtubei_internal,
    get_transcript_via_youtubei
)


async def test_dom_fallback_integration():
    """Test DOM fallback integration with the full YouTubei extraction process"""
    
    print("Testing DOM Fallback Integration...")
    print("=" * 50)
    
    # Test 1: Verify DeterministicTranscriptCapture has DOM fallback capability
    capture = DeterministicTranscriptCapture(timeout_seconds=1)
    
    # Check that the DOM fallback method exists
    assert hasattr(capture, '_dom_fallback_extraction'), "DOM fallback method missing"
    assert hasattr(capture, 'page'), "Page reference for DOM fallback missing"
    
    print("✓ DeterministicTranscriptCapture has DOM fallback capability")
    
    # Test 2: Verify DOM fallback is called when network times out
    mock_page = AsyncMock()
    mock_element = AsyncMock()
    mock_element.text_content.return_value = "DOM extracted transcript"
    mock_page.query_selector_all.return_value = [mock_element]
    
    capture.page = mock_page
    capture.transcript_future = asyncio.Future()  # Never resolved
    
    result = await capture.wait_for_transcript()
    
    assert result == "DOM extracted transcript", f"Expected DOM transcript, got: {result}"
    assert mock_page.query_selector_all.called, "DOM selectors were not queried"
    
    print("✓ DOM fallback is triggered when network interception times out")
    
    # Test 3: Verify logging messages are appropriate
    with patch('transcript_service.logging') as mock_logging:
        capture2 = DeterministicTranscriptCapture(timeout_seconds=0.1)
        mock_page2 = AsyncMock()
        mock_element2 = AsyncMock()
        mock_element2.text_content.return_value = "Test transcript"
        mock_page2.query_selector_all.return_value = [mock_element2]
        
        capture2.page = mock_page2
        capture2.transcript_future = asyncio.Future()
        
        result = await capture2.wait_for_transcript()
        
        # Check that appropriate log messages were called
        info_calls = [call for call in mock_logging.info.call_args_list]
        timeout_logged = any("timed out" in str(call) for call in info_calls)
        dom_success_logged = any("DOM fallback: Successfully extracted" in str(call) for call in info_calls)
        
        assert timeout_logged, "Timeout should be logged"
        assert dom_success_logged, "DOM success should be logged"
    
    print("✓ Appropriate logging messages are generated")
    
    # Test 4: Verify selector coverage
    capture3 = DeterministicTranscriptCapture()
    mock_page3 = AsyncMock()
    
    # Track which selectors are tried
    tried_selectors = []
    def track_selectors(selector):
        tried_selectors.append(selector)
        return []  # Return empty to test multiple selectors
    
    mock_page3.query_selector_all.side_effect = track_selectors
    capture3.page = mock_page3
    
    result = await capture3._dom_fallback_extraction()
    
    # Verify multiple selectors were tried
    assert len(tried_selectors) > 5, f"Expected multiple selectors, got {len(tried_selectors)}"
    
    # Check for key selectors
    expected_selectors = [
        '[data-testid="transcript-segment"]',
        '.ytd-transcript-segment-renderer',
        '.segment-text'
    ]
    
    for expected in expected_selectors:
        assert expected in tried_selectors, f"Expected selector {expected} not tried"
    
    print("✓ Multiple transcript selectors are attempted")
    
    # Test 5: Verify error handling
    capture4 = DeterministicTranscriptCapture()
    mock_page4 = AsyncMock()
    mock_page4.query_selector_all.side_effect = Exception("DOM error")
    capture4.page = mock_page4
    
    # Should not crash on DOM errors
    result = await capture4._dom_fallback_extraction()
    assert result is None, "Should return None on DOM errors"
    
    print("✓ Error handling works correctly")
    
    print("=" * 50)
    print("✅ All DOM Fallback Integration tests PASSED!")
    
    return True


async def test_requirements_compliance():
    """Test compliance with specific requirements 7.1-7.5"""
    
    print("\nTesting Requirements Compliance...")
    print("=" * 50)
    
    # Requirement 7.1: Add DOM polling after network route Future timeout
    capture = DeterministicTranscriptCapture(timeout_seconds=0.1)
    mock_page = AsyncMock()
    mock_element = AsyncMock()
    mock_element.text_content.return_value = "Req 7.1 test"
    mock_page.query_selector_all.return_value = [mock_element]
    
    capture.page = mock_page
    capture.transcript_future = asyncio.Future()  # Will timeout
    
    result = await capture.wait_for_transcript()
    assert result == "Req 7.1 test"
    print("✓ Requirement 7.1: DOM polling after network timeout - VERIFIED")
    
    # Requirement 7.2: Implement transcript line selector polling for 3-5 seconds
    capture2 = DeterministicTranscriptCapture()
    mock_page2 = AsyncMock()
    
    call_count = 0
    async def count_calls(selector):
        nonlocal call_count
        call_count += 1
        return []  # Always return empty to force full polling duration
    
    mock_page2.query_selector_all.side_effect = count_calls
    capture2.page = mock_page2
    
    start_time = asyncio.get_event_loop().time()
    result = await capture2._dom_fallback_extraction()
    end_time = asyncio.get_event_loop().time()
    
    duration = end_time - start_time
    assert 3.0 <= duration <= 6.0, f"Polling duration {duration}s not in 3-5s range"
    # With 8 attempts (4s / 0.5s) and multiple selectors, we should have many calls
    assert call_count >= 8, f"Expected at least 8 polling attempts, got {call_count}"
    print("✓ Requirement 7.2: Transcript line selector polling 3-5 seconds - VERIFIED")
    
    # Requirement 7.3: Extract text from DOM nodes when network is blocked
    capture3 = DeterministicTranscriptCapture()
    mock_page3 = AsyncMock()
    
    # Multiple elements with different text
    elements = []
    for i in range(3):
        elem = AsyncMock()
        elem.text_content.return_value = f"Line {i+1}"
        elements.append(elem)
    
    mock_page3.query_selector_all.return_value = elements
    capture3.page = mock_page3
    
    result = await capture3._dom_fallback_extraction()
    expected = "Line 1\nLine 2\nLine 3"
    assert result == expected, f"Expected '{expected}', got '{result}'"
    print("✓ Requirement 7.3: Extract text from DOM nodes - VERIFIED")
    
    # Requirement 7.4: Add logging for successful DOM fallback scenarios
    with patch('transcript_service.logging') as mock_logging:
        capture4 = DeterministicTranscriptCapture()
        mock_page4 = AsyncMock()
        mock_element4 = AsyncMock()
        mock_element4.text_content.return_value = "Success log test"
        mock_page4.query_selector_all.return_value = [mock_element4]
        capture4.page = mock_page4
        
        result = await capture4._dom_fallback_extraction()
        
        # Check for success logging
        success_logged = any(
            "Successfully extracted transcript from DOM" in str(call)
            for call in mock_logging.info.call_args_list
        )
        assert success_logged, "Success logging not found"
    
    print("✓ Requirement 7.4: Logging for successful DOM fallback - VERIFIED")
    
    # Requirement 7.5: Integration in wait_for_transcript method
    capture5 = DeterministicTranscriptCapture(timeout_seconds=0.1)
    mock_page5 = AsyncMock()
    mock_element5 = AsyncMock()
    mock_element5.text_content.return_value = "Integration test"
    mock_page5.query_selector_all.return_value = [mock_element5]
    
    capture5.page = mock_page5
    capture5.transcript_future = asyncio.Future()  # Will timeout
    
    # This should trigger DOM fallback automatically
    result = await capture5.wait_for_transcript()
    assert result == "Integration test"
    print("✓ Requirement 7.5: DOM fallback integration - VERIFIED")
    
    print("=" * 50)
    print("✅ All Requirements Compliance tests PASSED!")
    
    return True


async def main():
    """Run all integration tests"""
    try:
        success1 = await test_dom_fallback_integration()
        success2 = await test_requirements_compliance()
        
        if success1 and success2:
            print("\n🎉 DOM Fallback Implementation COMPLETE!")
            print("\nImplemented Features:")
            print("• DOM polling after network route Future timeout")
            print("• Transcript line selector polling for 3-5 seconds")
            print("• Text extraction from DOM nodes when network is blocked")
            print("• Comprehensive logging for successful DOM fallback scenarios")
            print("• Full integration with wait_for_transcript method")
            print("\nTask 7 - DOM Fallback Implementation: ✅ COMPLETED")
            return True
        else:
            print("\n❌ Some tests failed")
            return False
            
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)