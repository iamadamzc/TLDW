#!/usr/bin/env python3
"""
Demonstration of reliability logging events.

This script shows how the comprehensive reliability logging system works
for the transcript reliability fix pack.
"""

import sys
import os
import logging

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from log_events import (
    evt, 
    RELIABILITY_EVENTS, 
    get_reliability_event_info, 
    validate_reliability_event,
    log_reliability_event
)
from logging_setup import configure_logging


def demo_reliability_events():
    """Demonstrate reliability logging events."""
    print("=== Reliability Logging Events Demo ===\n")
    
    # Configure JSON logging
    configure_logging(log_level="INFO", use_json=True)
    
    print("1. Available Reliability Events:")
    print("-" * 40)
    for event_name, event_info in RELIABILITY_EVENTS.items():
        print(f"• {event_name}")
        print(f"  Description: {event_info['description']}")
        print(f"  Requirements: {', '.join(event_info['requirements'])}")
        print(f"  Context Fields: {', '.join(event_info['context_fields']) or 'None'}")
        print()
    
    print("\n2. Event Information Lookup:")
    print("-" * 40)
    event_name = "youtubei_captiontracks_shortcircuit"
    info = get_reliability_event_info(event_name)
    print(f"Event: {event_name}")
    print(f"Info: {info}")
    print()
    
    print("3. Event Validation:")
    print("-" * 40)
    # Valid event
    is_valid = validate_reliability_event(
        "youtubei_captiontracks_shortcircuit",
        lang="en", asr=False, video_id="abc123", job_id="job_456"
    )
    print(f"Valid event with all fields: {is_valid}")
    
    # Invalid event (missing fields)
    is_valid = validate_reliability_event(
        "youtubei_captiontracks_shortcircuit",
        lang="en"  # Missing required fields
    )
    print(f"Invalid event with missing fields: {is_valid}")
    print()
    
    print("4. Sample Reliability Events (JSON output):")
    print("-" * 40)
    
    # YouTubei caption tracks shortcircuit (Requirement 1.3)
    print("YouTubei caption tracks shortcircuit:")
    log_reliability_event("youtubei_captiontracks_shortcircuit",
                         lang="en", asr=False, video_id="dQw4w9WgXcQ", job_id="job_123")
    
    # Proxy enforcement block (Requirement 2.1)
    print("\nProxy enforcement block:")
    log_reliability_event("requests_fallback_blocked",
                         job_id="job_123", reason="enforce_proxy_no_proxy")
    
    # Content validation failure (Requirement 3.3)
    print("\nContent validation failure:")
    log_reliability_event("timedtext_html_or_block",
                         context="timedtext_fetch", content_preview="<html><title>Consent</title>")
    
    # ASR playback initiation (Requirement 3.6)
    print("\nASR playback initiation:")
    log_reliability_event("asr_playback_initiated")
    
    # FFmpeg timeout (Requirement 2.3)
    print("\nFFmpeg timeout:")
    log_reliability_event("ffmpeg_timeout_exceeded",
                         timeout=60, job_id="job_123")
    
    print("\n5. Event with validation failure:")
    print("-" * 40)
    # This will log a validation failure event first, then the actual event
    log_reliability_event("youtubei_captiontracks_shortcircuit", lang="en")  # Missing required fields
    
    print("\n=== Demo Complete ===")


def demo_requirement_coverage():
    """Show which requirements are covered by reliability events."""
    print("\n=== Requirement Coverage Analysis ===\n")
    
    # Group events by requirements
    req_to_events = {}
    for event_name, event_info in RELIABILITY_EVENTS.items():
        for req in event_info["requirements"]:
            if req not in req_to_events:
                req_to_events[req] = []
            req_to_events[req].append(event_name)
    
    print("Requirements covered by reliability events:")
    print("-" * 50)
    for req in sorted(req_to_events.keys()):
        events = req_to_events[req]
        print(f"Requirement {req}:")
        for event in events:
            description = RELIABILITY_EVENTS[event]["description"]
            print(f"  • {event}: {description}")
        print()


if __name__ == "__main__":
    demo_reliability_events()
    demo_requirement_coverage()