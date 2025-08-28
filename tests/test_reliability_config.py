#!/usr/bin/env python3
"""
Tests for reliability configuration management.
"""

import os
import unittest
from unittest.mock import patch

from reliability_config import ReliabilityConfig, get_reliability_config, reload_reliability_config


class TestReliabilityConfig(unittest.TestCase):
    """Test reliability configuration loading and validation."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ReliabilityConfig()
        
        # Test timeout defaults
        self.assertEqual(config.ffmpeg_timeout, 60)
        self.assertEqual(config.youtubei_hard_timeout, 45)
        self.assertEqual(config.playwright_navigation_timeout, 60)
        
        # Test proxy defaults
        self.assertFalse(config.enforce_proxy_all)
        self.assertTrue(config.use_proxy_for_timedtext)
        
        # Test feature flag defaults
        self.assertTrue(config.enable_caption_tracks_shortcut)
        self.assertTrue(config.enable_deterministic_selectors)
        self.assertTrue(config.enable_content_validation)
        self.assertTrue(config.enable_fast_fail_youtubei)
        self.assertTrue(config.enable_asr_playback_trigger)
        
        # Test retry defaults
        self.assertEqual(config.ffmpeg_max_retries, 2)
        self.assertEqual(config.timedtext_retries, 1)
        self.assertEqual(config.youtubei_retries, 0)
        
    @patch.dict(os.environ, {
        'FFMPEG_TIMEOUT': '90',
        'YOUTUBEI_HARD_TIMEOUT': '30',
        'ENFORCE_PROXY_ALL': '1',
        'ENABLE_CAPTION_TRACKS_SHORTCUT': '0'
    })
    def test_env_var_loading(self):
        """Test loading configuration from environment variables."""
        config = ReliabilityConfig.from_env()
        
        self.assertEqual(config.ffmpeg_timeout, 90)
        self.assertEqual(config.youtubei_hard_timeout, 30)
        self.assertTrue(config.enforce_proxy_all)
        self.assertFalse(config.enable_caption_tracks_shortcut)
        
    @patch.dict(os.environ, {
        'FFMPEG_TIMEOUT': '10',  # Below minimum
        'YOUTUBEI_HARD_TIMEOUT': '200'  # Above maximum
    })
    def test_validation_bounds(self):
        """Test that configuration values are bounded to valid ranges."""
        config = ReliabilityConfig.from_env()
        
        # Should be clamped to minimum/maximum
        self.assertEqual(config.ffmpeg_timeout, 30)  # Minimum
        self.assertEqual(config.youtubei_hard_timeout, 120)  # Maximum
        
    @patch.dict(os.environ, {
        'FFMPEG_TIMEOUT': 'invalid',
        'ENFORCE_PROXY_ALL': 'maybe'
    })
    def test_invalid_values(self):
        """Test handling of invalid environment variable values."""
        config = ReliabilityConfig.from_env()
        
        # Should fall back to defaults
        self.assertEqual(config.ffmpeg_timeout, 60)
        self.assertFalse(config.enforce_proxy_all)  # Invalid bool becomes False
        
    def test_config_to_dict(self):
        """Test configuration serialization to dictionary."""
        config = ReliabilityConfig()
        config_dict = config.to_dict()
        
        # Check structure
        self.assertIn('timeouts', config_dict)
        self.assertIn('proxy', config_dict)
        self.assertIn('features', config_dict)
        self.assertIn('retries', config_dict)
        self.assertIn('asr', config_dict)
        
        # Check values
        self.assertEqual(config_dict['timeouts']['ffmpeg_timeout'], 60)
        self.assertEqual(config_dict['proxy']['enforce_proxy_all'], False)
        self.assertEqual(config_dict['features']['enable_caption_tracks_shortcut'], True)
        
    def test_health_check_info(self):
        """Test health check information generation."""
        config = ReliabilityConfig()
        health_info = config.get_health_check_info()
        
        self.assertTrue(health_info['reliability_config_loaded'])
        self.assertFalse(health_info['proxy_enforcement'])
        self.assertEqual(health_info['feature_flags_enabled'], 5)  # All 5 features enabled by default
        self.assertIn('timeout_config', health_info)
        
    def test_global_config_instance(self):
        """Test global configuration instance management."""
        # Get config twice - should be same instance
        config1 = get_reliability_config()
        config2 = get_reliability_config()
        self.assertIs(config1, config2)
        
        # Reload should create new instance
        config3 = reload_reliability_config()
        self.assertIsNot(config1, config3)
        
    @patch.dict(os.environ, {
        'YOUTUBEI_HARD_TIMEOUT': '70',
        'FFMPEG_TIMEOUT': '60'
    })
    def test_timeout_validation_warning(self):
        """Test that configuration validation warns about problematic timeout relationships."""
        # This should trigger a warning since YouTubei timeout >= FFmpeg timeout
        with patch('reliability_config.logger') as mock_logger:
            ReliabilityConfig.from_env()
            
            # Check that a warning was logged
            mock_logger.warning.assert_called()
            warning_calls = [call for call in mock_logger.warning.call_args_list 
                           if 'YouTubei timeout' in str(call)]
            self.assertTrue(len(warning_calls) > 0)


class TestServiceIntegration(unittest.TestCase):
    """Test that services correctly use the centralized configuration."""
    
    def test_ffmpeg_service_uses_config(self):
        """Test that FFmpeg service uses centralized configuration."""
        from ffmpeg_service import FFMPEG_TIMEOUT, FFMPEG_MAX_RETRIES
        from reliability_config import get_reliability_config
        
        config = get_reliability_config()
        self.assertEqual(FFMPEG_TIMEOUT, config.ffmpeg_timeout)
        self.assertEqual(FFMPEG_MAX_RETRIES, config.ffmpeg_max_retries)
        
    def test_transcript_service_uses_config(self):
        """Test that transcript service uses centralized configuration."""
        from transcript_service import YOUTUBEI_HARD_TIMEOUT, ENFORCE_PROXY_ALL, USE_PROXY_FOR_TIMEDTEXT
        from reliability_config import get_reliability_config
        
        config = get_reliability_config()
        self.assertEqual(YOUTUBEI_HARD_TIMEOUT, config.youtubei_hard_timeout)
        self.assertEqual(ENFORCE_PROXY_ALL, config.enforce_proxy_all)
        self.assertEqual(USE_PROXY_FOR_TIMEDTEXT, config.use_proxy_for_timedtext)


if __name__ == '__main__':
    unittest.main()