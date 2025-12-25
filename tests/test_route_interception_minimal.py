#!/usr/bin/env python3
import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from youtubei_service import DeterministicYouTubeiCapture

class TestRouteInterceptionMinimal(unittest.TestCase):
    def setUp(self):
        self.capture = DeterministicYouTubeiCapture(
            job_id="test_job_id",
            video_id="test_video_id"
        )

    def test_basic_functionality(self):
        """Test basic functionality"""
        self.assertIsNotNone(self.capture)

if __name__ == "__main__":
    unittest.main(verbosity=2)