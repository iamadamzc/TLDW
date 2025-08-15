"""
Test bot-check detection functionality
"""

import unittest
from transcript_service import TranscriptService


class TestBotCheckDetection(unittest.TestCase):
    """Test bot-check detection patterns"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.transcript_service = TranscriptService()
    
    def test_bot_check_detection_patterns(self):
        """Test various bot-check patterns are detected"""
        test_cases = [
            "ERROR: [youtube] 258WHrtM2Bo: Sign in to confirm you're not a bot",
            "Sign in to confirm you're not a bot",
            "sign in to confirm youre not a bot",
            "CONFIRM YOU'RE NOT A BOT",
            "unusual traffic from your computer network",
            "automated requests",
            "captcha required",
            "not a bot verification"
        ]
        
        for test_text in test_cases:
            with self.subTest(text=test_text):
                result = self.transcript_service._detect_bot_check(test_text)
                self.assertTrue(result, f"Should detect bot-check in: {test_text}")
    
    def test_non_bot_check_patterns(self):
        """Test that normal errors are not detected as bot-check"""
        test_cases = [
            "ERROR: [youtube] Video unavailable",
            "ERROR: Network timeout",
            "ERROR: Connection refused",
            "Video is private",
            "This video is not available",
            "Age-restricted video",
            ""
        ]
        
        for test_text in test_cases:
            with self.subTest(text=test_text):
                result = self.transcript_service._detect_bot_check(test_text)
                self.assertFalse(result, f"Should NOT detect bot-check in: {test_text}")
    
    def test_case_insensitive_detection(self):
        """Test that detection is case-insensitive"""
        test_cases = [
            "SIGN IN TO CONFIRM YOU'RE NOT A BOT",
            "Sign In To Confirm You're Not A Bot",
            "sign in to confirm you're not a bot",
            "SiGn In To CoNfIrM yOu'Re NoT a BoT"
        ]
        
        for test_text in test_cases:
            with self.subTest(text=test_text):
                result = self.transcript_service._detect_bot_check(test_text)
                self.assertTrue(result, f"Should detect bot-check (case-insensitive): {test_text}")


if __name__ == '__main__':
    unittest.main()