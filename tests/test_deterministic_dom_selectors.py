#!/usr/bin/env python3
"""
Unit tests for deterministic DOM selectors in youtubei_service.py

Tests the new _open_transcript_via_title_menu() method and deterministic selectors
according to task 3 requirements.
"""

import unittest
from unittest.mock import AsyncMock, Mock, patch
import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from youtubei_service import DeterministicYouTubeiCapture, TITLE_ROW_MENU, SHOW_TRANSCRIPT_ITEM
    YOUTUBEI_SERVICE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: youtubei_service not available: {e}")
    YOUTUBEI_SERVICE_AVAILABLE = False


class TestDeterministicDOMSelectors(unittest.TestCase):
    """Unit tests for deterministic DOM selectors according to task 3 requirements"""

    def setUp(self):
        """Set up test fixtures"""
        if not YOUTUBEI_SERVICE_AVAILABLE:
            self.skipTest("youtubei_service not available")
        
        # Create a DeterministicYouTubeiCapture instance
        self.capture = DeterministicYouTubeiCapture(
            job_id="test_job_id",
            video_id="test_video_id"
        )

    def test_deterministic_selectors_constants(self):
        """Test that deterministic selector constants are defined correctly (Requirement 1.4)"""
        # Verify TITLE_ROW_MENU selector matches requirement
        expected_title_menu = "ytd-menu-renderer #button-shape button[aria-label*='More actions']"
        self.assertEqual(TITLE_ROW_MENU, expected_title_menu)
        
        # Verify SHOW_TRANSCRIPT_ITEM selector is defined
        expected_transcript_item = "tp-yt-paper-listbox [role='menuitem']:has-text('Show transcript')"
        self.assertEqual(SHOW_TRANSCRIPT_ITEM, expected_transcript_item)

    def test_open_transcript_via_title_menu_method_exists(self):
        """Test that _open_transcript_via_title_menu method exists"""
        self.assertTrue(hasattr(self.capture, '_open_transcript_via_title_menu'))
        self.assertTrue(callable(getattr(self.capture, '_open_transcript_via_title_menu')))

    def test_open_transcript_via_title_menu_success_flow(self):
        """Test _open_transcript_via_title_menu() successful execution flow"""
        async def run_test():
            # Mock page and elements
            mock_menu_element = AsyncMock()
            mock_menu_element.wait_for = AsyncMock()
            mock_menu_element.click = AsyncMock()
            
            mock_transcript_element = AsyncMock()
            mock_transcript_element.wait_for = AsyncMock()
            mock_transcript_element.click = AsyncMock()
            
            mock_menu_locator = Mock()
            mock_menu_locator.first = mock_menu_element
            
            mock_transcript_locator = Mock()
            mock_transcript_locator.first = mock_transcript_element
            
            mock_page = AsyncMock()
            mock_page.locator = Mock(side_effect=lambda selector: {
                TITLE_ROW_MENU: mock_menu_locator,
                SHOW_TRANSCRIPT_ITEM: mock_transcript_locator
            }.get(selector, Mock()))
            mock_page.wait_for_selector = AsyncMock()
            
            self.capture.page = mock_page
            
            # Test successful execution
            result = await self.capture._open_transcript_via_title_menu()
            
            # Verify result
            self.assertTrue(result)
            self.assertTrue(self.capture.transcript_button_clicked)
            
            # Verify method calls
            mock_menu_element.wait_for.assert_called_once_with(state="visible", timeout=5000)
            mock_menu_element.click.assert_called_once_with(timeout=5000)
            mock_transcript_element.wait_for.assert_called_once_with(state="visible", timeout=5000)
            mock_transcript_element.click.assert_called_once_with(timeout=5000)
            
            # Verify dropdown state verification
            mock_page.wait_for_selector.assert_called()

        # Run the async test
        asyncio.run(run_test())

    def test_open_transcript_via_title_menu_no_page(self):
        """Test _open_transcript_via_title_menu() with no page available"""
        async def run_test():
            # Set page to None
            self.capture.page = None
            
            # Test execution
            result = await self.capture._open_transcript_via_title_menu()
            
            # Verify result
            self.assertFalse(result)
            self.assertFalse(self.capture.transcript_button_clicked)

        # Run the async test
        asyncio.run(run_test())

    def test_open_transcript_via_title_menu_menu_button_not_found(self):
        """Test _open_transcript_via_title_menu() when menu button is not found"""
        async def run_test():
            # Mock page with menu button that times out
            mock_menu_element = AsyncMock()
            mock_menu_element.wait_for = AsyncMock(side_effect=Exception("Timeout"))
            
            mock_menu_locator = Mock()
            mock_menu_locator.first = mock_menu_element
            
            mock_page = AsyncMock()
            mock_page.locator = Mock(return_value=mock_menu_locator)
            
            self.capture.page = mock_page
            
            # Test execution
            result = await self.capture._open_transcript_via_title_menu()
            
            # Verify result
            self.assertFalse(result)
            self.assertFalse(self.capture.transcript_button_clicked)

        # Run the async test
        asyncio.run(run_test())

    def test_open_transcript_via_title_menu_dropdown_not_opened(self):
        """Test _open_transcript_via_title_menu() when dropdown doesn't open"""
        async def run_test():
            # Mock page with menu button that clicks but dropdown doesn't open
            mock_menu_element = AsyncMock()
            mock_menu_element.wait_for = AsyncMock()
            mock_menu_element.click = AsyncMock()
            
            mock_menu_locator = Mock()
            mock_menu_locator.first = mock_menu_element
            
            mock_page = AsyncMock()
            mock_page.locator = Mock(return_value=mock_menu_locator)
            mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Dropdown timeout"))
            
            self.capture.page = mock_page
            
            # Test execution
            result = await self.capture._open_transcript_via_title_menu()
            
            # Verify result
            self.assertFalse(result)
            self.assertFalse(self.capture.transcript_button_clicked)

        # Run the async test
        asyncio.run(run_test())


def main():
    """Run the tests"""
    print("🧪 Testing deterministic DOM selectors...")
    print("=" * 60)
    
    # Run tests
    unittest.main(verbosity=2, exit=False)


if __name__ == "__main__":
    main()