#!/usr/bin/env python3
"""
Integration tests for end-to-end transcript reliability fixes pipeline.

Tests complete transcript extraction with reliability fixes enabled,
fallback behavior between extraction methods, and logging output validation
according to task 13.2 requirements.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, AsyncMock, call
import asyncio
import sys
import os
import json
import tempfile
import logging
from io import StringIO
from typing import Dict, List, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from transcript_service import (
        get_transcript_with_job_proxy,
        _execute_transcript_pipeline,
        _enhanced_youtubei_stage,
        _enhanced_asr_stage,
        ContentValidationError
    )
    from youtubei_service import DeterministicYouTubeiCapture
    from ffmpeg_service import FFmpegService
    from timedtext_service import timedtext_with_job_proxy
    from reliability_config import ReliabilityConfig
    from log_events import evt
    SERVICES_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Services not available: {e}")
    SERVICES_AVAILABLE = False


class LogCapture:
    """Helper class to capture log events for testing."""
    
    def __init__(self):
        self.events = []
        self.original_evt = None
    
    def __enter__(self):
        # Patch the evt function to capture events
        import log_events
        self.original_evt = log_events.evt
        log_events.evt = self.capture_event
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original evt function
        import log_events
        log_events.evt = self.original_evt
    
    def capture_event(self, event_name: str, **kwargs):
        """Capture log events for testing."""
        self.events.append({
            'event_name': event_name,
            'kwargs': kwargs
        })
        # Also call original function to maintain normal logging
        if self.original_evt:
            self.original_evt(event_name, **kwargs)
    
    def get_events(self, event_name: str) -> List[Dict[str, Any]]:
        """Get all captured events with the specified name."""
        return [event for event in self.events if event['event_name'] == event_name]
    
    def has_event(self, event_name: str, **expected_kwargs) -> bool:
        """Check if an event with specified parameters was logged."""
        for event in self.events:
            if event['event_name'] == event_name:
                # Check if all expected kwargs match
                if all(event['kwargs'].get(k) == v for k, v in expected_kwargs.items()):
                    return True
        return False
    
    def clear(self):
        """Clear captured events."""
        self.events.clear()


class TestReliabilityFixesIntegration(unittest.TestCase):
    """Integration tests for complete transcript extraction with reliability fixes."""
    
    def setUp(self):
        """Set up test fixtures."""
        if not SERVICES_AVAILABLE:
            self.skipTest("Services not available")
        
        self.test_video_id = "test_video_123"
        self.test_job_id = "test_job_456"
        self.log_capture = LogCapture()
    
    def test_complete_transcript_extraction_success_path(self):
        """Test complete transcript extraction through successful path."""
        with self.log_capture:
            # Mock successful youtube-transcript-api response
            mock_transcript_data = [
                {"text": "Hello world", "start": 0.0, "duration": 2.0},
                {"text": "This is a test", "start": 2.0, "duration": 3.0}
            ]
            
            with patch('transcript_service.get_transcript') as mock_get_transcript:
                mock_get_transcript.return_value = mock_transcript_data
                
                # Mock proxy manager
                mock_proxy_manager = Mock()
                mock_proxy_manager.in_use = False
                
                # Test transcript extraction
                result = get_transcript_with_job_proxy(
                    self.test_video_id,
                    self.test_job_id,
                    mock_proxy_manager
                )
                
                # Should succeed with transcript text
                self.assertIsNotNone(result)
                self.assertIn("Hello world", result)
                self.assertIn("This is a test", result)
                
                # Should log successful extraction
                self.assertTrue(self.log_capture.has_event(
                    "transcript_success",
                    video_id=self.test_video_id,
                    method="youtube_transcript_api"
                ))
    
    def test_fallback_behavior_youtube_api_to_timedtext(self):
        """Test fallback from YouTube API to timedtext service."""
        with self.log_capture:
            # Mock YouTube API failure
            with patch('transcript_service.get_transcript') as mock_get_transcript:
                mock_get_transcript.side_effect = Exception("API unavailable")
                
                # Mock successful timedtext response
                with patch('transcript_service.timedtext_with_job_proxy') as mock_timedtext:
                    mock_timedtext.return_value = "Timedtext transcript content"
                    
                    # Mock proxy manager
                    mock_proxy_manager = Mock()
                    mock_proxy_manager.in_use = False
                    
                    # Test transcript extraction
                    result = get_transcript_with_job_proxy(
                        self.test_video_id,
                        self.test_job_id,
                        mock_proxy_manager
                    )
                    
                    # Should succeed with timedtext result
                    self.assertEqual(result, "Timedtext transcript content")
                    
                    # Should log API failure and timedtext success
                    self.assertTrue(self.log_capture.has_event(
                        "youtube_api_failed",
                        video_id=self.test_video_id
                    ))
                    self.assertTrue(self.log_capture.has_event(
                        "transcript_success",
                        video_id=self.test_video_id,
                        method="timedtext"
                    ))
    
    def test_fallback_behavior_timedtext_to_youtubei(self):
        """Test fallback from timedtext to YouTubei service."""
        with self.log_capture:
            # Mock YouTube API and timedtext failures
            with patch('transcript_service.get_transcript') as mock_get_transcript, \
                 patch('transcript_service.timedtext_with_job_proxy') as mock_timedtext:
                
                mock_get_transcript.side_effect = Exception("API unavailable")
                mock_timedtext.return_value = None  # Timedtext failed
                
                # Mock successful YouTubei response
                with patch('transcript_service.extract_transcript_with_job_proxy') as mock_youtubei:
                    mock_youtubei.return_value = "YouTubei transcript content"
                    
                    # Mock proxy manager
                    mock_proxy_manager = Mock()
                    mock_proxy_manager.in_use = False
                    
                    # Test transcript extraction
                    result = get_transcript_with_job_proxy(
                        self.test_video_id,
                        self.test_job_id,
                        mock_proxy_manager
                    )
                    
                    # Should succeed with YouTubei result
                    self.assertEqual(result, "YouTubei transcript content")
                    
                    # Should log progression through fallback chain
                    self.assertTrue(self.log_capture.has_event(
                        "youtube_api_failed",
                        video_id=self.test_video_id
                    ))
                    self.assertTrue(self.log_capture.has_event(
                        "timedtext_failed",
                        video_id=self.test_video_id
                    ))
                    self.assertTrue(self.log_capture.has_event(
                        "transcript_success",
                        video_id=self.test_video_id,
                        method="youtubei"
                    ))
    
    def test_fallback_behavior_complete_chain_to_asr(self):
        """Test complete fallback chain ending with ASR."""
        with self.log_capture:
            # Mock all transcript methods failing
            with patch('transcript_service.get_transcript') as mock_get_transcript, \
                 patch('transcript_service.timedtext_with_job_proxy') as mock_timedtext, \
                 patch('transcript_service.extract_transcript_with_job_proxy') as mock_youtubei:
                
                mock_get_transcript.side_effect = Exception("API unavailable")
                mock_timedtext.return_value = None
                mock_youtubei.return_value = ""  # Empty string indicates failure
                
                # Mock successful ASR response
                with patch('transcript_service.ASRAudioExtractor.extract_transcript') as mock_asr:
                    mock_asr.return_value = "ASR transcript content"
                    
                    # Mock proxy manager
                    mock_proxy_manager = Mock()
                    mock_proxy_manager.in_use = False
                    
                    # Test transcript extraction
                    result = get_transcript_with_job_proxy(
                        self.test_video_id,
                        self.test_job_id,
                        mock_proxy_manager
                    )
                    
                    # Should succeed with ASR result
                    self.assertEqual(result, "ASR transcript content")
                    
                    # Should log complete fallback chain
                    self.assertTrue(self.log_capture.has_event(
                        "youtube_api_failed",
                        video_id=self.test_video_id
                    ))
                    self.assertTrue(self.log_capture.has_event(
                        "timedtext_failed",
                        video_id=self.test_video_id
                    ))
                    self.assertTrue(self.log_capture.has_event(
                        "youtubei_failed",
                        video_id=self.test_video_id
                    ))
                    self.assertTrue(self.log_capture.has_event(
                        "transcript_success",
                        video_id=self.test_video_id,
                        method="asr"
                    ))
    
    def test_youtubei_caption_tracks_shortcircuit_integration(self):
        """Test YouTubei caption tracks shortcircuit integration (Requirement 1.3)."""
        async def run_test():
            with self.log_capture:
                # Mock page with caption tracks in ytInitialPlayerResponse
                mock_page = AsyncMock()
                mock_page.evaluate = AsyncMock(return_value=[
                    {
                        "baseUrl": "https://example.com/timedtext?lang=en",
                        "languageCode": "en",
                        "kind": "",  # Not ASR
                        "name": "English"
                    }
                ])
                
                # Mock successful HTTP fetch
                with patch('youtubei_service.httpx.AsyncClient') as mock_client_class:
                    mock_client = AsyncMock()
                    mock_response = AsyncMock()
                    mock_response.text = '<?xml version="1.0"?><transcript><text start="0" dur="2">Hello</text></transcript>'
                    mock_response.status_code = 200
                    mock_response.raise_for_status = Mock()
                    
                    mock_client.get = AsyncMock(return_value=mock_response)
                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.__aexit__ = AsyncMock(return_value=None)
                    mock_client_class.return_value = mock_client
                    
                    # Create capture instance
                    capture = DeterministicYouTubeiCapture(
                        job_id=self.test_job_id,
                        video_id=self.test_video_id
                    )
                    capture.page = mock_page
                    
                    # Test caption tracks extraction
                    result = await capture._extract_captions_from_player_response()
                    
                    # Should succeed with shortcircuit
                    self.assertIsNotNone(result)
                    
                    # Should log shortcircuit event with required fields
                    self.assertTrue(self.log_capture.has_event(
                        "youtubei_captiontracks_shortcircuit",
                        video_id=self.test_video_id,
                        job_id=self.test_job_id,
                        lang="en",
                        asr=False
                    ))
        
        asyncio.run(run_test())
    
    def test_content_validation_with_retry_integration(self):
        """Test content validation with cookie retry integration (Requirements 3.1, 3.2)."""
        with self.log_capture:
            # Mock timedtext response with HTML consent page
            html_consent = "<!DOCTYPE html><html><body>Before you continue to YouTube</body></html>"
            
            # Mock first response (HTML), second response (valid XML)
            mock_responses = [
                Mock(text=html_consent, status_code=200),
                Mock(text='<?xml version="1.0"?><transcript><text>Valid</text></transcript>', status_code=200)
            ]
            
            with patch('timedtext_service.requests.get') as mock_get:
                mock_get.side_effect = mock_responses
                
                # Mock proxy manager
                mock_proxy_manager = Mock()
                mock_proxy_manager.in_use = False
                
                # Test timedtext with retry
                result = timedtext_with_job_proxy(
                    self.test_video_id,
                    self.test_job_id,
                    mock_proxy_manager,
                    cookies="test_cookies"
                )
                
                # Should succeed after retry
                self.assertIsNotNone(result)
                
                # Should log validation failure and retry
                self.assertTrue(self.log_capture.has_event(
                    "timedtext_html_or_block"
                ))
                self.assertTrue(self.log_capture.has_event(
                    "timedtext_retry_with_cookies"
                ))
    
    def test_proxy_enforcement_integration(self):
        """Test proxy enforcement integration across services (Requirements 2.1, 2.2)."""
        with self.log_capture:
            # Mock config with proxy enforcement enabled
            with patch('ffmpeg_service._config') as mock_config:
                mock_config.enforce_proxy_all = True
                
                # Create FFmpeg service with no proxy
                ffmpeg_service = FFmpegService(
                    job_id=self.test_job_id,
                    proxy_manager=None
                )
                
                # Test audio extraction - should be blocked
                success, returncode, error_classification = ffmpeg_service.extract_audio_to_wav(
                    "https://example.com/audio.m4a",
                    "/tmp/test_output.wav"
                )
                
                # Should fail due to proxy enforcement
                self.assertFalse(success)
                self.assertEqual(error_classification, "proxy_enforcement_error")
                
                # Should log blocking event
                self.assertTrue(self.log_capture.has_event(
                    "ffmpeg_blocked",
                    reason="enforce_proxy_no_proxy",
                    job_id=self.test_job_id
                ))
    
    def test_fast_fail_youtubei_to_asr_integration(self):
        """Test fast-fail YouTubei to ASR transition (Requirements 3.4, 5.1)."""
        with self.log_capture:
            # Mock YouTubei timeout
            with patch('transcript_service.extract_transcript_with_job_proxy') as mock_youtubei:
                mock_youtubei.side_effect = Exception("navigation timeout exceeded")
                
                # Mock successful ASR
                with patch('transcript_service.ASRAudioExtractor.extract_transcript') as mock_asr:
                    mock_asr.return_value = "ASR transcript after timeout"
                    
                    # Mock proxy manager
                    mock_proxy_manager = Mock()
                    mock_proxy_manager.in_use = False
                    
                    # Test enhanced YouTubei stage
                    result = _enhanced_youtubei_stage(
                        self.test_video_id,
                        self.test_job_id,
                        mock_proxy_manager
                    )
                    
                    # Should fail and trigger fast-fail
                    self.assertIsNone(result)
                    
                    # Should log timeout short circuit
                    self.assertTrue(self.log_capture.has_event(
                        "youtubei_nav_timeout_short_circuit"
                    ))
    
    def test_asr_playback_triggering_integration(self):
        """Test ASR playback triggering integration (Requirements 3.5, 3.6)."""
        async def run_test():
            with self.log_capture:
                # Mock page for ASR playback
                mock_page = AsyncMock()
                mock_page.keyboard = AsyncMock()
                mock_page.keyboard.press = AsyncMock()
                mock_page.locator = Mock()
                mock_video_locator = AsyncMock()
                mock_video_locator.click = AsyncMock()
                mock_page.locator.return_value.first = mock_video_locator
                
                # Mock ASR service with playback triggering
                with patch('transcript_service.async_playwright') as mock_playwright:
                    mock_browser = AsyncMock()
                    mock_context = AsyncMock()
                    mock_context.new_page = AsyncMock(return_value=mock_page)
                    mock_browser.new_context = AsyncMock(return_value=mock_context)
                    mock_playwright_instance = AsyncMock()
                    mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
                    mock_playwright.return_value.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
                    mock_playwright.return_value.__aexit__ = AsyncMock(return_value=None)
                    
                    # Test ASR stage with playback triggering
                    result = await _enhanced_asr_stage(
                        self.test_video_id,
                        self.test_job_id,
                        None  # No proxy manager
                    )
                    
                    # Should log playback initiation
                    self.assertTrue(self.log_capture.has_event(
                        "asr_playback_initiated"
                    ))
        
        asyncio.run(run_test())
    
    def test_logging_output_validation(self):
        """Test that logging output matches expected events for each scenario."""
        with self.log_capture:
            # Test scenario: Complete failure chain
            with patch('transcript_service.get_transcript') as mock_get_transcript, \
                 patch('transcript_service.timedtext_with_job_proxy') as mock_timedtext, \
                 patch('transcript_service.extract_transcript_with_job_proxy') as mock_youtubei, \
                 patch('transcript_service.ASRAudioExtractor.extract_transcript') as mock_asr:
                
                # Configure all methods to fail
                mock_get_transcript.side_effect = Exception("API error")
                mock_timedtext.return_value = None
                mock_youtubei.return_value = ""
                mock_asr.return_value = None
                
                # Mock proxy manager
                mock_proxy_manager = Mock()
                mock_proxy_manager.in_use = False
                
                # Test transcript extraction
                result = get_transcript_with_job_proxy(
                    self.test_video_id,
                    self.test_job_id,
                    mock_proxy_manager
                )
                
                # Should fail completely
                self.assertIsNone(result)
                
                # Validate expected logging sequence
                expected_events = [
                    "transcript_extraction_start",
                    "youtube_api_failed",
                    "timedtext_failed", 
                    "youtubei_failed",
                    "asr_failed",
                    "transcript_extraction_failed"
                ]
                
                for event_name in expected_events:
                    self.assertTrue(
                        len(self.log_capture.get_events(event_name)) > 0,
                        f"Expected event '{event_name}' was not logged"
                    )
    
    def test_reliability_events_context_validation(self):
        """Test that reliability events include proper context fields."""
        with self.log_capture:
            # Test YouTubei caption tracks shortcircuit event
            async def run_test():
                # Mock successful caption tracks extraction
                mock_page = AsyncMock()
                mock_page.evaluate = AsyncMock(return_value=[
                    {
                        "baseUrl": "https://example.com/timedtext?lang=es",
                        "languageCode": "es", 
                        "kind": "asr",  # ASR track
                        "name": "Spanish (auto-generated)"
                    }
                ])
                
                # Mock HTTP response
                with patch('youtubei_service.httpx.AsyncClient') as mock_client_class:
                    mock_client = AsyncMock()
                    mock_response = AsyncMock()
                    mock_response.text = '<?xml version="1.0"?><transcript><text>Hola</text></transcript>'
                    mock_response.status_code = 200
                    mock_response.raise_for_status = Mock()
                    
                    mock_client.get = AsyncMock(return_value=mock_response)
                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.__aexit__ = AsyncMock(return_value=None)
                    mock_client_class.return_value = mock_client
                    
                    # Create capture and test
                    capture = DeterministicYouTubeiCapture(
                        job_id=self.test_job_id,
                        video_id=self.test_video_id
                    )
                    capture.page = mock_page
                    
                    result = await capture._extract_captions_from_player_response()
                    
                    # Validate event context
                    shortcircuit_events = self.log_capture.get_events("youtubei_captiontracks_shortcircuit")
                    self.assertEqual(len(shortcircuit_events), 1)
                    
                    event = shortcircuit_events[0]
                    self.assertEqual(event['kwargs']['video_id'], self.test_video_id)
                    self.assertEqual(event['kwargs']['job_id'], self.test_job_id)
                    self.assertEqual(event['kwargs']['lang'], "es")
                    self.assertTrue(event['kwargs']['asr'])  # Should be True for ASR track
            
            asyncio.run(run_test())
    
    def test_error_handling_and_graceful_degradation(self):
        """Test error handling and graceful degradation throughout pipeline."""
        with self.log_capture:
            # Test with various error conditions
            error_scenarios = [
                ("network_error", Exception("Network unreachable")),
                ("timeout_error", Exception("Request timeout")),
                ("parsing_error", Exception("Invalid XML")),
                ("auth_error", Exception("Authentication failed"))
            ]
            
            for error_type, error_exception in error_scenarios:
                with self.subTest(error_type=error_type):
                    self.log_capture.clear()
                    
                    # Mock first method failing with specific error
                    with patch('transcript_service.get_transcript') as mock_get_transcript:
                        mock_get_transcript.side_effect = error_exception
                        
                        # Mock second method succeeding
                        with patch('transcript_service.timedtext_with_job_proxy') as mock_timedtext:
                            mock_timedtext.return_value = f"Success after {error_type}"
                            
                            # Mock proxy manager
                            mock_proxy_manager = Mock()
                            mock_proxy_manager.in_use = False
                            
                            # Test extraction
                            result = get_transcript_with_job_proxy(
                                self.test_video_id,
                                self.test_job_id,
                                mock_proxy_manager
                            )
                            
                            # Should succeed via fallback
                            self.assertIsNotNone(result)
                            self.assertIn("Success after", result)
                            
                            # Should log error and recovery
                            self.assertTrue(self.log_capture.has_event("youtube_api_failed"))
                            self.assertTrue(self.log_capture.has_event("transcript_success", method="timedtext"))


class TestReliabilityMetricsIntegration(unittest.TestCase):
    """Test reliability metrics and monitoring integration."""
    
    def setUp(self):
        """Set up test fixtures."""
        if not SERVICES_AVAILABLE:
            self.skipTest("Services not available")
        
        self.log_capture = LogCapture()
    
    def test_performance_metrics_collection(self):
        """Test that performance metrics are collected during transcript extraction."""
        with self.log_capture:
            # Mock successful extraction with timing
            with patch('transcript_service.get_transcript') as mock_get_transcript:
                mock_get_transcript.return_value = [{"text": "Test", "start": 0, "duration": 1}]
                
                # Mock proxy manager
                mock_proxy_manager = Mock()
                mock_proxy_manager.in_use = False
                
                # Test extraction
                result = get_transcript_with_job_proxy(
                    "test_video",
                    "test_job",
                    mock_proxy_manager
                )
                
                # Should collect timing metrics
                timing_events = [event for event in self.log_capture.events 
                               if 'duration_ms' in event.get('kwargs', {})]
                self.assertTrue(len(timing_events) > 0)
    
    def test_circuit_breaker_integration(self):
        """Test circuit breaker integration with reliability fixes."""
        with self.log_capture:
            # Mock repeated YouTubei failures to trigger circuit breaker
            with patch('transcript_service.extract_transcript_with_job_proxy') as mock_youtubei:
                mock_youtubei.side_effect = Exception("Repeated failure")
                
                # Mock proxy manager
                mock_proxy_manager = Mock()
                mock_proxy_manager.in_use = False
                
                # Test multiple extractions to trigger circuit breaker
                for i in range(5):
                    try:
                        _enhanced_youtubei_stage("test_video", f"test_job_{i}", mock_proxy_manager)
                    except:
                        pass
                
                # Should log circuit breaker events
                circuit_breaker_events = [event for event in self.log_capture.events 
                                        if 'circuit_breaker' in event['event_name']]
                self.assertTrue(len(circuit_breaker_events) > 0)


def main():
    """Run the integration tests."""
    print("🧪 Testing reliability fixes - Integration tests...")
    print("=" * 60)
    
    # Run tests
    unittest.main(verbosity=2, exit=False)


if __name__ == "__main__":
    main()