#!/usr/bin/env python3
"""
Unit tests for individual reliability fix components.

Tests Playwright API fixes, content validation, and proxy enforcement logic
with mocked interactions according to task 13.1 requirements.
"""

import unittest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import asyncio
import sys
import os
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from youtubei_service import DeterministicYouTubeiCapture
    from ffmpeg_service import FFmpegService
    from transcript_service import (
        _validate_xml_content, 
        _validate_and_parse_xml, 
        ContentValidationError,
        _is_html_response,
        _is_consent_or_captcha_response
    )
    from reliability_config import ReliabilityConfig
    SERVICES_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Services not available: {e}")
    SERVICES_AVAILABLE = False


class TestPlaywrightAPIFixes(unittest.TestCase):
    """Test Playwright API fixes with mocked page interactions (Requirement 1.1)."""
    
    def setUp(self):
        """Set up test fixtures."""
        if not SERVICES_AVAILABLE:
            self.skipTest("Services not available")
        
        self.capture = DeterministicYouTubeiCapture(
            job_id="test_job_123",
            video_id="test_video_456"
        )
    
    def test_playwright_wait_for_api_usage(self):
        """Test that locator.wait_for(state="visible") is used instead of is_visible()."""
        async def run_test():
            # Mock page and locator
            mock_locator = AsyncMock()
            mock_locator.wait_for = AsyncMock()
            mock_locator.click = AsyncMock()
            mock_locator.first = mock_locator
            
            mock_page = AsyncMock()
            mock_page.locator = Mock(return_value=mock_locator)
            mock_page.wait_for_selector = AsyncMock()
            
            self.capture.page = mock_page
            
            # Test the title menu method which should use proper wait API
            result = await self.capture._open_transcript_via_title_menu()
            
            # Verify wait_for was called with proper parameters
            mock_locator.wait_for.assert_called_with(state="visible", timeout=5000)
            
            # Verify is_visible was NOT called (this would be the old incorrect API)
            self.assertFalse(hasattr(mock_locator, 'is_visible') and mock_locator.is_visible.called)
        
        asyncio.run(run_test())
    
    def test_playwright_wait_timeout_handling(self):
        """Test proper timeout handling in Playwright wait operations."""
        async def run_test():
            # Mock locator that times out
            mock_locator = AsyncMock()
            mock_locator.wait_for = AsyncMock(side_effect=Exception("Timeout waiting for element"))
            mock_locator.first = mock_locator
            
            mock_page = AsyncMock()
            mock_page.locator = Mock(return_value=mock_locator)
            
            self.capture.page = mock_page
            
            # Test that timeout is handled gracefully
            result = await self.capture._open_transcript_via_title_menu()
            
            # Should return False on timeout, not raise exception
            self.assertFalse(result)
            
            # Should still attempt to wait with proper timeout
            mock_locator.wait_for.assert_called_with(state="visible", timeout=5000)
        
        asyncio.run(run_test())
    
    def test_playwright_element_interaction_sequence(self):
        """Test proper element interaction sequence with wait operations."""
        async def run_test():
            # Mock successful interaction sequence
            mock_menu_locator = AsyncMock()
            mock_menu_locator.wait_for = AsyncMock()
            mock_menu_locator.click = AsyncMock()
            mock_menu_locator.first = mock_menu_locator
            
            mock_transcript_locator = AsyncMock()
            mock_transcript_locator.wait_for = AsyncMock()
            mock_transcript_locator.click = AsyncMock()
            mock_transcript_locator.first = mock_transcript_locator
            
            mock_page = AsyncMock()
            mock_page.locator = Mock(side_effect=lambda selector: {
                "ytd-menu-renderer #button-shape button[aria-label*='More actions']": mock_menu_locator,
                "tp-yt-paper-listbox [role='menuitem']:has-text('Show transcript')": mock_transcript_locator
            }.get(selector, Mock()))
            mock_page.wait_for_selector = AsyncMock()
            
            self.capture.page = mock_page
            
            # Test interaction sequence
            result = await self.capture._open_transcript_via_title_menu()
            
            # Verify proper sequence: wait -> click -> wait -> click
            self.assertTrue(result)
            
            # Menu button: wait then click
            mock_menu_locator.wait_for.assert_called_with(state="visible", timeout=5000)
            mock_menu_locator.click.assert_called_with(timeout=5000)
            
            # Dropdown state verification
            mock_page.wait_for_selector.assert_called()
            
            # Transcript item: wait then click
            mock_transcript_locator.wait_for.assert_called_with(state="visible", timeout=5000)
            mock_transcript_locator.click.assert_called_with(timeout=5000)
        
        asyncio.run(run_test())


class TestContentValidation(unittest.TestCase):
    """Test content validation with various response types (Requirements 3.1, 3.3)."""
    
    def test_validate_xml_content_valid_xml(self):
        """Test validation of valid XML content."""
        valid_xml = '<?xml version="1.0"?><transcript><text start="0" dur="2">Hello world</text></transcript>'
        
        is_valid, error_reason = _validate_xml_content(valid_xml)
        
        self.assertTrue(is_valid)
        self.assertEqual(error_reason, "valid")
    
    def test_validate_xml_content_empty_body(self):
        """Test validation of empty response body."""
        empty_responses = ["", "   ", "\n\t  \n"]
        
        for empty_content in empty_responses:
            with self.subTest(content=repr(empty_content)):
                is_valid, error_reason = _validate_xml_content(empty_content)
                
                self.assertFalse(is_valid)
                self.assertEqual(error_reason, "empty_body")
    
    def test_validate_xml_content_html_response(self):
        """Test validation detects HTML responses."""
        html_responses = [
            "<!DOCTYPE html><html><head><title>YouTube</title></head></html>",
            "<html><body>Not XML</body></html>",
            "<head><meta charset='utf-8'></head>",
            "<script>console.log('blocked');</script>",
            "<style>body { margin: 0; }</style>"
        ]
        
        for html_content in html_responses:
            with self.subTest(content=html_content[:50]):
                is_valid, error_reason = _validate_xml_content(html_content)
                
                self.assertFalse(is_valid)
                self.assertIn("html_response", error_reason)
    
    def test_validate_xml_content_consent_captcha_detection(self):
        """Test validation detects consent walls and captcha pages."""
        blocking_responses = [
            "<!DOCTYPE html><html><body>Before you continue to YouTube</body></html>",
            "<html><div>We need your consent</div></html>",
            "<html><title>Verify you are human</title></html>",
            "<html><body>Unusual traffic from your computer network</body></html>",
            "<html><div>Access denied - automated requests detected</div></html>",
            "<html><body>CAPTCHA verification required</body></html>"
        ]
        
        for blocking_content in blocking_responses:
            with self.subTest(content=blocking_content[:50]):
                is_valid, error_reason = _validate_xml_content(blocking_content)
                
                self.assertFalse(is_valid)
                self.assertEqual(error_reason, "html_consent_or_captcha")
    
    def test_validate_xml_content_not_xml_format(self):
        """Test validation detects non-XML content."""
        non_xml_responses = [
            "This is plain text",
            "JSON: {\"error\": \"not found\"}",
            "404 Not Found",
            "Internal Server Error"
        ]
        
        for non_xml_content in non_xml_responses:
            with self.subTest(content=non_xml_content):
                is_valid, error_reason = _validate_xml_content(non_xml_content)
                
                self.assertFalse(is_valid)
                self.assertEqual(error_reason, "not_xml_format")
    
    def test_validate_xml_content_malformed_xml(self):
        """Test validation detects malformed XML."""
        malformed_xml_responses = [
            "<transcript><text>Unclosed tag",
            "<transcript><text start='0'>Missing end tag</transcript>",
            "<transcript><text start='invalid'>Bad attribute</text></transcript>",
            "<?xml version='1.0'?><transcript><text>Nested <inner>tags</text></transcript>"
        ]
        
        for malformed_content in malformed_xml_responses:
            with self.subTest(content=malformed_content):
                is_valid, error_reason = _validate_xml_content(malformed_content)
                
                self.assertFalse(is_valid)
                self.assertIn("xml_parse_error", error_reason)
    
    @patch('transcript_service.evt')
    def test_validate_and_parse_xml_success(self, mock_evt):
        """Test successful XML validation and parsing."""
        valid_xml = '<?xml version="1.0"?><transcript><text start="0" dur="2">Hello</text></transcript>'
        
        # Mock response object
        mock_response = Mock()
        mock_response.text = valid_xml
        
        # Test validation and parsing
        root = _validate_and_parse_xml(mock_response, "test_context")
        
        # Verify XML was parsed correctly
        self.assertEqual(root.tag, "transcript")
        text_elements = root.findall("text")
        self.assertEqual(len(text_elements), 1)
        self.assertEqual(text_elements[0].text, "Hello")
        
        # No error events should be logged for valid XML
        error_calls = [call for call in mock_evt.call_args_list 
                      if any(error_type in str(call) for error_type in 
                            ["timedtext_empty_body", "timedtext_html_or_block", "timedtext_not_xml"])]
        self.assertEqual(len(error_calls), 0)
    
    @patch('transcript_service.evt')
    def test_validate_and_parse_xml_empty_body(self, mock_evt):
        """Test XML validation with empty body."""
        # Mock response with empty body
        mock_response = Mock()
        mock_response.text = ""
        
        # Test validation - should raise ContentValidationError
        with self.assertRaises(ContentValidationError) as cm:
            _validate_and_parse_xml(mock_response, "test_context")
        
        # Verify error details
        self.assertEqual(cm.exception.error_reason, "empty_body")
        self.assertFalse(cm.exception.should_retry_with_cookies)
        
        # Verify correct event was logged
        mock_evt.assert_called_with("timedtext_empty_body", context="test_context")
    
    @patch('transcript_service.evt')
    def test_validate_and_parse_xml_html_consent(self, mock_evt):
        """Test XML validation with HTML consent response."""
        html_consent = "<!DOCTYPE html><html><body>Before you continue to YouTube, we need your consent</body></html>"
        
        # Mock response with HTML consent
        mock_response = Mock()
        mock_response.text = html_consent
        
        # Test validation - should raise ContentValidationError with retry suggestion
        with self.assertRaises(ContentValidationError) as cm:
            _validate_and_parse_xml(mock_response, "test_context")
        
        # Verify error details
        self.assertIn("html_consent_or_captcha", cm.exception.error_reason)
        self.assertTrue(cm.exception.should_retry_with_cookies)
        
        # Verify correct event was logged
        mock_evt.assert_called_with("timedtext_html_or_block", 
                                   context="test_context", 
                                   content_preview=html_consent[:200])
    
    @patch('transcript_service.evt')
    def test_validate_and_parse_xml_not_xml(self, mock_evt):
        """Test XML validation with non-XML content."""
        non_xml_content = "This is not XML content"
        
        # Mock response with non-XML content
        mock_response = Mock()
        mock_response.text = non_xml_content
        
        # Test validation - should raise ContentValidationError
        with self.assertRaises(ContentValidationError) as cm:
            _validate_and_parse_xml(mock_response, "test_context")
        
        # Verify error details
        self.assertEqual(cm.exception.error_reason, "not_xml_format")
        self.assertFalse(cm.exception.should_retry_with_cookies)
        
        # Verify correct event was logged
        mock_evt.assert_called_with("timedtext_not_xml", 
                                   context="test_context", 
                                   content_preview=non_xml_content[:120])


class TestProxyEnforcement(unittest.TestCase):
    """Test proxy enforcement logic with different configuration scenarios (Requirements 2.1, 2.2)."""
    
    def setUp(self):
        """Set up test fixtures."""
        if not SERVICES_AVAILABLE:
            self.skipTest("Services not available")
    
    @patch('ffmpeg_service._config')
    def test_ffmpeg_proxy_enforcement_enabled_no_proxy(self, mock_config):
        """Test FFmpeg proxy enforcement when enabled but no proxy available."""
        # Configure enforcement enabled
        mock_config.enforce_proxy_all = True
        
        # Create FFmpeg service with no proxy manager
        ffmpeg_service = FFmpegService(job_id="test_job", proxy_manager=None)
        
        # Test extraction attempt - should be blocked
        success, returncode, error_classification = ffmpeg_service.extract_audio_to_wav(
            "https://example.com/audio.m4a",
            "/tmp/test_output.wav"
        )
        
        # Should fail due to proxy enforcement
        self.assertFalse(success)
        self.assertEqual(error_classification, "proxy_enforcement_error")
    
    @patch('ffmpeg_service._config')
    def test_ffmpeg_proxy_enforcement_enabled_with_proxy(self, mock_config):
        """Test FFmpeg proxy enforcement when enabled with proxy available."""
        # Configure enforcement enabled
        mock_config.enforce_proxy_all = True
        
        # Mock proxy manager
        mock_proxy_manager = Mock()
        mock_proxy_manager.in_use = True
        mock_proxy_manager.proxy_env_for_job = Mock(return_value={"https_proxy": "http://proxy:8080"})
        mock_proxy_manager.proxy_dict_for_job = Mock(return_value={"https": "http://proxy:8080"})
        
        # Create FFmpeg service with proxy manager
        ffmpeg_service = FFmpegService(job_id="test_job", proxy_manager=mock_proxy_manager)
        
        # Verify proxy configuration was set up
        self.assertTrue(ffmpeg_service.proxy_env)
        self.assertTrue(ffmpeg_service.proxy_url)
        self.assertTrue(ffmpeg_service.enforce_proxy)
    
    @patch('ffmpeg_service._config')
    def test_ffmpeg_proxy_enforcement_disabled(self, mock_config):
        """Test FFmpeg behavior when proxy enforcement is disabled."""
        # Configure enforcement disabled
        mock_config.enforce_proxy_all = False
        
        # Create FFmpeg service with no proxy manager
        ffmpeg_service = FFmpegService(job_id="test_job", proxy_manager=None)
        
        # Verify enforcement is disabled
        self.assertFalse(ffmpeg_service.enforce_proxy)
        self.assertFalse(ffmpeg_service.proxy_env)
        self.assertIsNone(ffmpeg_service.proxy_url)
    
    @patch('ffmpeg_service.evt')
    @patch('ffmpeg_service._config')
    def test_requests_fallback_blocked_by_proxy_enforcement(self, mock_config, mock_evt):
        """Test that requests fallback is blocked when proxy enforcement is enabled."""
        # Configure enforcement enabled
        mock_config.enforce_proxy_all = True
        
        # Create FFmpeg service with no proxy
        ffmpeg_service = FFmpegService(job_id="test_job", proxy_manager=None)
        
        # Test requests fallback - should be blocked
        result = ffmpeg_service._requests_streaming_fallback(
            "https://example.com/audio.m4a",
            "/tmp/test_output.wav",
            None
        )
        
        # Should be blocked
        self.assertFalse(result)
        
        # Should log blocking event
        mock_evt.assert_called_with("requests_fallback_blocked", 
                                   job_id="test_job", 
                                   reason="enforce_proxy_no_proxy")
    
    def test_youtubei_proxy_enforcement_in_http_fetch(self):
        """Test proxy enforcement in YouTubei HTTP fetch operations."""
        async def run_test():
            # Mock config with proxy enforcement
            with patch('youtubei_service._config') as mock_config:
                mock_config.enforce_proxy_all = True
                
                # Create capture instance with no proxy manager
                capture = DeterministicYouTubeiCapture(
                    job_id="test_job",
                    video_id="test_video",
                    proxy_manager=None
                )
                
                # Test HTTP fetch - should be blocked
                result = await capture._fetch_transcript_xml_via_requests(
                    "https://example.com/timedtext",
                    None
                )
                
                # Should return None due to proxy enforcement
                self.assertIsNone(result)
        
        asyncio.run(run_test())
    
    def test_proxy_configuration_validation(self):
        """Test proxy configuration validation in different scenarios."""
        # Test with valid proxy manager
        mock_proxy_manager = Mock()
        mock_proxy_manager.in_use = True
        mock_proxy_manager.proxy_env_for_job = Mock(return_value={"https_proxy": "http://proxy:8080"})
        mock_proxy_manager.proxy_dict_for_job = Mock(return_value={"https": "http://proxy:8080"})
        
        ffmpeg_service = FFmpegService(job_id="test_job", proxy_manager=mock_proxy_manager)
        
        # Should have proxy configuration
        self.assertTrue(ffmpeg_service.proxy_env)
        self.assertTrue(ffmpeg_service.proxy_url)
        
        # Test with proxy manager that fails
        mock_failing_proxy_manager = Mock()
        mock_failing_proxy_manager.in_use = True
        mock_failing_proxy_manager.proxy_env_for_job = Mock(side_effect=Exception("Proxy error"))
        mock_failing_proxy_manager.proxy_dict_for_job = Mock(side_effect=Exception("Proxy error"))
        
        ffmpeg_service = FFmpegService(job_id="test_job", proxy_manager=mock_failing_proxy_manager)
        
        # Should handle proxy errors gracefully
        self.assertFalse(ffmpeg_service.proxy_env)
        self.assertIsNone(ffmpeg_service.proxy_url)


class TestReliabilityConfigIntegration(unittest.TestCase):
    """Test that services correctly use centralized reliability configuration."""
    
    def test_ffmpeg_timeout_from_config(self):
        """Test that FFmpeg service uses timeout from centralized config."""
        with patch('ffmpeg_service._config') as mock_config:
            mock_config.ffmpeg_timeout = 90
            
            # Import should use the mocked config
            from ffmpeg_service import FFMPEG_TIMEOUT
            self.assertEqual(FFMPEG_TIMEOUT, 90)
    
    def test_youtubei_timeout_from_config(self):
        """Test that transcript service uses YouTubei timeout from centralized config."""
        with patch('transcript_service._config') as mock_config:
            mock_config.youtubei_hard_timeout = 30
            
            # Import should use the mocked config
            from transcript_service import YOUTUBEI_HARD_TIMEOUT
            self.assertEqual(YOUTUBEI_HARD_TIMEOUT, 30)
    
    def test_proxy_enforcement_from_config(self):
        """Test that services use proxy enforcement setting from centralized config."""
        with patch('transcript_service._config') as mock_config:
            mock_config.enforce_proxy_all = True
            
            # Import should use the mocked config
            from transcript_service import ENFORCE_PROXY_ALL
            self.assertTrue(ENFORCE_PROXY_ALL)


def main():
    """Run the unit tests."""
    print("🧪 Testing reliability fixes - Unit tests...")
    print("=" * 60)
    
    # Run tests
    unittest.main(verbosity=2, exit=False)


if __name__ == "__main__":
    main()