#!/usr/bin/env python3
"""
Test script for yt-dlp hardening with multi-client support and network resilience
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock, call
import tempfile

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TestYtDlpHardening(unittest.TestCase):
    """Test yt-dlp hardening features"""
    
    def test_multi_client_configuration(self):
        """Test that yt-dlp uses multiple player clients for resilience"""
        from yt_download_helper import download_audio_with_fallback
        
        # Mock YoutubeDL to capture configuration
        with patch('yt_download_helper.YoutubeDL') as mock_ydl_class:
            mock_ydl = MagicMock()
            mock_ydl_class.return_value.__enter__.return_value = mock_ydl
            mock_ydl.download.side_effect = Exception("Test exception to prevent actual download")
            
            try:
                download_audio_with_fallback(
                    "https://www.youtube.com/watch?v=test",
                    "Mozilla/5.0 Test Agent",
                    None,  # No proxy
                    "/usr/bin"
                )
            except:
                pass  # Expected to fail, we just want to check configuration
            
            # Verify YoutubeDL was called with multi-client configuration
            self.assertTrue(mock_ydl_class.called)
            call_args = mock_ydl_class.call_args[0][0]  # First positional argument (config dict)
            
            # Check that extractor_args contains multiple player clients
            self.assertIn("extractor_args", call_args)
            self.assertIn("youtube", call_args["extractor_args"])
            self.assertIn("player_client", call_args["extractor_args"]["youtube"])
            
            player_clients = call_args["extractor_args"]["youtube"]["player_client"]
            expected_clients = ["android", "web", "web_safari"]
            self.assertEqual(player_clients, expected_clients)
    
    def test_network_resilience_settings(self):
        """Test that network resilience settings are properly configured"""
        from yt_download_helper import download_audio_with_fallback
        
        # Mock YoutubeDL to capture configuration
        with patch('yt_download_helper.YoutubeDL') as mock_ydl_class:
            mock_ydl = MagicMock()
            mock_ydl_class.return_value.__enter__.return_value = mock_ydl
            mock_ydl.download.side_effect = Exception("Test exception")
            
            try:
                download_audio_with_fallback(
                    "https://www.youtube.com/watch?v=test",
                    "Mozilla/5.0 Test Agent",
                    None,
                    "/usr/bin"
                )
            except:
                pass
            
            # Get the configuration passed to YoutubeDL
            call_args = mock_ydl_class.call_args[0][0]
            
            # Verify network resilience settings
            self.assertEqual(call_args["retries"], 2, "Should have retries=2")
            self.assertEqual(call_args["socket_timeout"], 10, "Should have socket_timeout=10")
            self.assertTrue(call_args["nocheckcertificate"], "Should have nocheckcertificate=True")
            self.assertEqual(call_args["fragment_retries"], 2, "Should have fragment_retries=2")
    
    def test_enhanced_http_headers(self):
        """Test that enhanced HTTP headers are configured for bot detection avoidance"""
        from yt_download_helper import download_audio_with_fallback
        
        test_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        
        with patch('yt_download_helper.YoutubeDL') as mock_ydl_class:
            mock_ydl = MagicMock()
            mock_ydl_class.return_value.__enter__.return_value = mock_ydl
            mock_ydl.download.side_effect = Exception("Test exception")
            
            try:
                download_audio_with_fallback(
                    "https://www.youtube.com/watch?v=test",
                    test_ua,
                    None,
                    "/usr/bin"
                )
            except:
                pass
            
            call_args = mock_ydl_class.call_args[0][0]
            headers = call_args["http_headers"]
            
            # Verify enhanced headers
            self.assertEqual(headers["User-Agent"], test_ua)
            self.assertIn("Accept-Language", headers)
            self.assertIn("en-US,en;q=0.9", headers["Accept-Language"])
            self.assertIn("Sec-Ch-Ua", headers)
            self.assertIn("Origin", headers)
            self.assertEqual(headers["Origin"], "https://www.youtube.com")
            self.assertIn("DNT", headers)
            self.assertEqual(headers["DNT"], "1")
    
    def test_identical_configuration_both_steps(self):
        """Test that both step1 and step2 use identical base configuration"""
        from yt_download_helper import download_audio_with_fallback
        
        configurations = []
        
        def capture_config(*args, **kwargs):
            configurations.append(args[0])  # Capture the config dict
            mock_ydl = MagicMock()
            mock_ydl.download.side_effect = Exception("Force step2")
            return mock_ydl
        
        with patch('yt_download_helper.YoutubeDL') as mock_ydl_class:
            mock_ydl_class.side_effect = capture_config
            
            try:
                download_audio_with_fallback(
                    "https://www.youtube.com/watch?v=test",
                    "Mozilla/5.0 Test Agent",
                    None,
                    "/usr/bin"
                )
            except:
                pass
            
            # Should have captured configurations for both step1 and step2
            self.assertGreaterEqual(len(configurations), 2, "Should capture both step1 and step2 configs")
            
            step1_config = configurations[0]
            step2_config = configurations[1]
            
            # Compare key configuration elements (excluding step-specific ones)
            shared_keys = ["retries", "socket_timeout", "nocheckcertificate", "extractor_args", "http_headers"]
            
            for key in shared_keys:
                self.assertEqual(
                    step1_config.get(key), 
                    step2_config.get(key),
                    f"Configuration key '{key}' should be identical in both steps"
                )
    
    def test_error_detection_functions(self):
        """Test error detection functions work correctly"""
        from yt_download_helper import _detect_extraction_failure, _combine_error_messages
        
        # Test extraction failure detection
        self.assertTrue(_detect_extraction_failure("Failed to extract any player response"))
        self.assertTrue(_detect_extraction_failure("Unable to extract player response"))
        self.assertTrue(_detect_extraction_failure("unable to extract yt initial data"))
        self.assertTrue(_detect_extraction_failure("failed to parse json"))
        self.assertFalse(_detect_extraction_failure("Network timeout"))
        self.assertFalse(_detect_extraction_failure(""))
        
        # Test error message combination
        combined = _combine_error_messages("Step1 error", "Step2 error")
        self.assertEqual(combined, "Step1 error || Step2 error")
        
        combined = _combine_error_messages("Step1 error", None)
        self.assertEqual(combined, "Step1 error")
        
        combined = _combine_error_messages(None, "Step2 error")
        self.assertEqual(combined, "Step2 error")
        
        # Test error length capping
        long_error1 = "A" * 6000
        long_error2 = "B" * 6000
        combined = _combine_error_messages(long_error1, long_error2)
        self.assertLess(len(combined), 10100, "Combined error should be capped")
        self.assertIn("truncated", combined, "Should indicate truncation")

class TestYtDlpConfiguration(unittest.TestCase):
    """Test specific yt-dlp configuration elements"""
    
    def test_player_client_order(self):
        """Test that player clients are in the correct order for maximum compatibility"""
        from yt_download_helper import download_audio_with_fallback
        
        with patch('yt_download_helper.YoutubeDL') as mock_ydl_class:
            mock_ydl = MagicMock()
            mock_ydl_class.return_value.__enter__.return_value = mock_ydl
            mock_ydl.download.side_effect = Exception("Test")
            
            try:
                download_audio_with_fallback(
                    "https://www.youtube.com/watch?v=test",
                    "Test UA",
                    None,
                    "/usr/bin"
                )
            except:
                pass
            
            config = mock_ydl_class.call_args[0][0]
            clients = config["extractor_args"]["youtube"]["player_client"]
            
            # Verify order: android first (most reliable), then web variants
            self.assertEqual(clients[0], "android", "Android client should be first for reliability")
            self.assertIn("web", clients, "Should include web client")
            self.assertIn("web_safari", clients, "Should include web_safari client")
    
    def test_proxy_configuration_preserved(self):
        """Test that proxy configuration is properly preserved in both steps"""
        from yt_download_helper import download_audio_with_fallback
        
        test_proxy = "http://user:pass@proxy.example.com:8080"
        
        with patch('yt_download_helper.YoutubeDL') as mock_ydl_class:
            mock_ydl = MagicMock()
            mock_ydl_class.return_value.__enter__.return_value = mock_ydl
            mock_ydl.download.side_effect = Exception("Test")
            
            try:
                download_audio_with_fallback(
                    "https://www.youtube.com/watch?v=test",
                    "Test UA",
                    test_proxy,
                    "/usr/bin"
                )
            except:
                pass
            
            config = mock_ydl_class.call_args[0][0]
            self.assertEqual(config["proxy"], test_proxy, "Proxy should be preserved in configuration")

def run_tests():
    """Run all yt-dlp hardening tests"""
    print("🧪 Running yt-dlp Hardening Tests")
    print("=" * 40)
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestYtDlpHardening))
    suite.addTests(loader.loadTestsFromTestCase(TestYtDlpConfiguration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print()
    if result.wasSuccessful():
        print("✅ All yt-dlp hardening tests passed!")
        print()
        print("📋 Verified features:")
        print("   - Multi-client support: ✅ ['android', 'web', 'web_safari']")
        print("   - Network resilience: ✅ retries=2, socket_timeout=10, nocheckcertificate=True")
        print("   - Enhanced HTTP headers: ✅ User-Agent, Accept-Language, Sec-Ch-Ua, etc.")
        print("   - Identical configuration: ✅ Both step1 and step2 use same base_opts")
        print("   - Error detection: ✅ Extraction failure and error combination")
        return True
    else:
        print("❌ Some yt-dlp hardening tests failed!")
        print(f"   Failures: {len(result.failures)}")
        print(f"   Errors: {len(result.errors)}")
        return False

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)