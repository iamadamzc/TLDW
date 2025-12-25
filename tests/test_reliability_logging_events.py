#!/usr/bin/env python3
"""
Test suite for reliability logging events.

Tests the comprehensive reliability logging implementation for the transcript
reliability fix pack, ensuring all events are properly defined and validated.
"""

import unittest
from unittest.mock import patch, MagicMock
import logging
import json
import sys
import os

# Add the parent directory to the path so we can import log_events
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from log_events import (
    evt, 
    RELIABILITY_EVENTS, 
    get_reliability_event_info, 
    validate_reliability_event,
    log_reliability_event
)


class TestReliabilityLoggingEvents(unittest.TestCase):
    """Test reliability logging events and validation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_logger = logging.getLogger("test_reliability")
        self.test_logger.setLevel(logging.DEBUG)
        
        # Create a handler to capture log output
        self.log_handler = logging.StreamHandler()
        self.test_logger.addHandler(self.log_handler)
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.test_logger.removeHandler(self.log_handler)
    
    def test_reliability_events_defined(self):
        """Test that all required reliability events are defined."""
        required_events = [
            "youtubei_captiontracks_shortcircuit",
            "youtubei_captiontracks_probe_failed", 
            "youtubei_title_menu_open_failed",
            "youtubei_direct_missing_ctx",
            "youtubei_nav_timeout_short_circuit",
            "requests_fallback_blocked",
            "ffmpeg_timeout_exceeded",
            "timedtext_empty_body",
            "timedtext_html_or_block", 
            "timedtext_not_xml",
            "asr_playback_initiated"
        ]
        
        for event_name in required_events:
            self.assertIn(event_name, RELIABILITY_EVENTS, 
                         f"Required reliability event '{event_name}' not defined")
            
            # Check that each event has required metadata
            event_info = RELIABILITY_EVENTS[event_name]
            self.assertIn("description", event_info)
            self.assertIn("requirements", event_info)
            self.assertIn("context_fields", event_info)
            
            # Check that description is not empty
            self.assertTrue(event_info["description"], 
                           f"Event '{event_name}' has empty description")
            
            # Check that requirements is a list
            self.assertIsInstance(event_info["requirements"], list,
                                f"Event '{event_name}' requirements should be a list")
            
            # Check that context_fields is a list
            self.assertIsInstance(event_info["context_fields"], list,
                                f"Event '{event_name}' context_fields should be a list")
    
    def test_get_reliability_event_info(self):
        """Test getting reliability event information."""
        # Test known event
        info = get_reliability_event_info("youtubei_captiontracks_shortcircuit")
        self.assertEqual(info["description"], 
                        "Caption tracks extracted directly from ytInitialPlayerResponse without DOM interaction")
        self.assertIn("1.3", info["requirements"])
        self.assertIn("lang", info["context_fields"])
        self.assertIn("asr", info["context_fields"])
        
        # Test unknown event
        info = get_reliability_event_info("unknown_event")
        self.assertEqual(info["description"], "Unknown reliability event")
        self.assertEqual(info["requirements"], [])
        self.assertEqual(info["context_fields"], [])
    
    def test_validate_reliability_event(self):
        """Test reliability event validation."""
        # Test valid event with all required fields
        self.assertTrue(validate_reliability_event(
            "youtubei_captiontracks_shortcircuit",
            lang="en", asr=False, video_id="abc123", job_id="job_456"
        ))
        
        # Test valid event with extra fields (should still be valid)
        self.assertTrue(validate_reliability_event(
            "youtubei_captiontracks_shortcircuit", 
            lang="en", asr=False, video_id="abc123", job_id="job_456", extra_field="value"
        ))
        
        # Test invalid event with missing required fields
        self.assertFalse(validate_reliability_event(
            "youtubei_captiontracks_shortcircuit",
            lang="en"  # Missing asr, video_id, job_id
        ))
        
        # Test unknown event
        self.assertFalse(validate_reliability_event("unknown_event"))
        
        # Test event with no required fields
        self.assertTrue(validate_reliability_event("asr_playback_initiated"))
    
    @patch('log_events.evt')
    def test_log_reliability_event_valid(self, mock_evt):
        """Test logging valid reliability events."""
        # Test valid event
        log_reliability_event("youtubei_captiontracks_shortcircuit",
                            lang="en", asr=False, video_id="abc123", job_id="job_456")
        
        # Should call evt with the event name and fields
        mock_evt.assert_called_with("youtubei_captiontracks_shortcircuit",
                                   lang="en", asr=False, video_id="abc123", job_id="job_456")
    
    @patch('log_events.evt')
    def test_log_reliability_event_invalid(self, mock_evt):
        """Test logging invalid reliability events."""
        # Test invalid event (missing required fields)
        log_reliability_event("youtubei_captiontracks_shortcircuit", lang="en")
        
        # Should call evt twice: once for validation failure, once for the actual event
        self.assertEqual(mock_evt.call_count, 2)
        
        # First call should be validation failure
        first_call = mock_evt.call_args_list[0]
        self.assertEqual(first_call[0][0], "reliability_event_validation_failed")
        
        # Second call should be the actual event
        second_call = mock_evt.call_args_list[1]
        self.assertEqual(second_call[0][0], "youtubei_captiontracks_shortcircuit")
    
    def test_requirement_coverage(self):
        """Test that all requirements from the spec are covered by events."""
        # Requirements from the transcript reliability fix pack
        spec_requirements = {
            "1.3": "youtubei_captiontracks_shortcircuit",
            "2.1": "requests_fallback_blocked", 
            "2.2": "requests_fallback_blocked",
            "3.1": ["timedtext_empty_body", "timedtext_html_or_block", "timedtext_not_xml"],
            "3.2": "timedtext_html_or_block",
            "3.3": ["timedtext_empty_body", "timedtext_html_or_block", "timedtext_not_xml"],
            "3.4": "youtubei_nav_timeout_short_circuit",
            "3.5": "asr_playback_initiated",
            "3.6": "asr_playback_initiated",
            "5.1": "youtubei_nav_timeout_short_circuit"
        }
        
        # Check that each requirement is covered by at least one event
        for req_id, expected_events in spec_requirements.items():
            if isinstance(expected_events, str):
                expected_events = [expected_events]
            
            found_events = []
            for event_name, event_info in RELIABILITY_EVENTS.items():
                if req_id in event_info["requirements"]:
                    found_events.append(event_name)
            
            # Check that at least one expected event covers this requirement
            self.assertTrue(any(event in found_events for event in expected_events),
                           f"Requirement {req_id} not covered by expected events {expected_events}. Found: {found_events}")
    
    def test_event_context_fields_consistency(self):
        """Test that event context fields are consistent with usage in services."""
        # Test specific events that have known context field requirements
        
        # youtubei_captiontracks_shortcircuit should have lang, asr, video_id, job_id
        event_info = RELIABILITY_EVENTS["youtubei_captiontracks_shortcircuit"]
        required_fields = {"lang", "asr", "video_id", "job_id"}
        actual_fields = set(event_info["context_fields"])
        self.assertEqual(actual_fields, required_fields,
                        f"youtubei_captiontracks_shortcircuit context fields mismatch")
        
        # requests_fallback_blocked should have job_id, reason
        event_info = RELIABILITY_EVENTS["requests_fallback_blocked"]
        required_fields = {"job_id", "reason"}
        actual_fields = set(event_info["context_fields"])
        self.assertEqual(actual_fields, required_fields,
                        f"requests_fallback_blocked context fields mismatch")
        
        # asr_playback_initiated should have no required fields
        event_info = RELIABILITY_EVENTS["asr_playback_initiated"]
        self.assertEqual(event_info["context_fields"], [],
                        f"asr_playback_initiated should have no required context fields")
    
    @patch('log_events.evt')
    def test_all_reliability_events_can_be_logged(self, mock_evt):
        """Test that all reliability events can be logged without errors."""
        test_data = {
            "youtubei_captiontracks_shortcircuit": {
                "lang": "en", "asr": False, "video_id": "test123", "job_id": "job_456"
            },
            "youtubei_captiontracks_probe_failed": {
                "err": "Test error", "video_id": "test123", "job_id": "job_456"
            },
            "youtubei_title_menu_open_failed": {
                "err": "Menu not found", "video_id": "test123", "job_id": "job_456"
            },
            "youtubei_direct_missing_ctx": {
                "has_key": True, "has_ctx": False, "has_params": True, 
                "video_id": "test123", "job_id": "job_456"
            },
            "youtubei_nav_timeout_short_circuit": {
                "video_id": "test123", "job_id": "job_456"
            },
            "requests_fallback_blocked": {
                "job_id": "job_456", "reason": "enforce_proxy_no_proxy"
            },
            "ffmpeg_timeout_exceeded": {
                "timeout": 60, "job_id": "job_456"
            },
            "timedtext_empty_body": {
                "status_code": 200, "content_type": "text/xml"
            },
            "timedtext_html_or_block": {
                "context": "test_context", "content_preview": "<html>blocked</html>"
            },
            "timedtext_not_xml": {
                "context": "test_context", "content_preview": "not xml content"
            },
            "asr_playback_initiated": {}
        }
        
        for event_name, fields in test_data.items():
            with self.subTest(event=event_name):
                # Should not raise any exceptions
                log_reliability_event(event_name, **fields)
                
                # Should call evt
                mock_evt.assert_called_with(event_name, **fields)
                mock_evt.reset_mock()


if __name__ == '__main__':
    unittest.main()