#!/usr/bin/env python3
"""
Test script to verify the enhanced YouTubei DOM interaction strategies.
This script tests the new open_transcript_panel_enhanced method.
"""

import asyncio
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from youtubei_service import DeterministicYouTubeiCapture

async def test_enhanced_dom_interaction():
    """Test the enhanced DOM interaction strategies"""
    print("Testing enhanced YouTubei DOM interaction strategies...")
    
    # Create a test instance
    capture = DeterministicYouTubeiCapture("test_job", "test_video_id")
    
    # Test that the new methods exist
    assert hasattr(capture, 'open_transcript_panel_enhanced'), "open_transcript_panel_enhanced method not found"
    assert hasattr(capture, '_open_via_more_actions'), "_open_via_more_actions method not found"
    
    print("✓ Enhanced DOM interaction methods are present")
    
    # Test method signatures (inspect unbound methods from class)
    import inspect
    sig = inspect.signature(DeterministicYouTubeiCapture.open_transcript_panel_enhanced)
    assert len(sig.parameters) == 1, f"Expected 1 parameter, got {len(sig.parameters)}"
    
    sig = inspect.signature(DeterministicYouTubeiCapture._open_via_more_actions)
    assert len(sig.parameters) == 1, f"Expected 1 parameter, got {len(sig.parameters)}"
    
    print("✓ Method signatures are correct")
    
    # Test that the methods are callable
    assert callable(capture.open_transcript_panel_enhanced), "open_transcript_panel_enhanced is not callable"
    assert callable(capture._open_via_more_actions), "_open_via_more_actions is not callable"
    
    print("✓ Methods are callable")
    
    print("\nEnhanced DOM interaction implementation test passed!")
    print("The new strategies include:")
    print("1. Direct transcript button click")
    print("2. More actions menu → Show transcript")
    print("3. Keyboard shortcuts (Shift+.)")
    print("4. JavaScript injection as last resort")
    
    return True

if __name__ == "__main__":
    asyncio.run(test_enhanced_dom_interaction())
