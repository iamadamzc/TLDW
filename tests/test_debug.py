#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("About to import youtubei_service...")
from youtubei_service import DeterministicYouTubeiCapture
print("Import successful!")

import unittest

class TestDebug(unittest.TestCase):
    def test_simple(self):
        self.assertTrue(True)

print("Class defined!")

if __name__ == "__main__":
    print("Running tests...")
    unittest.main(verbosity=2)