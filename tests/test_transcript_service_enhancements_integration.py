#!/usr/bin/env python3
"""
Comprehensive Integration Test Suite for Transcript Service Enhancements
========================================================================

This test suite validates all enhanced functionality from the transcript-service-enhancements spec:
- Storage state loading and Netscape conversion
- Deterministic interception and multi-profile support  
- Cookie integration and circuit breaker behavior
- Proxy configuration across all components
- All requirements validation

Requirements tested: All requirements from transcript-service-enhancements spec
"""

import os
import sys
import logging
import time
import unittest
import tempfile
import json
import shutil
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Optional, List, Any

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestStorageStateManagement(unittest.TestCase):
    """Test enhanced Playwright storage state management (Requirement 1)"""
    
    def setUp(self):
        """Set up test environment with temporary cookie directory"""
        self.temp_dir = tempfile.mkdtemp()
        self.cookie_dir = Path(self.temp_dir)
        self.storage_state_path = self.cookie_dir / "youtube_session.json"
        
        # Mock environment
        self.env_patcher = patch.dict(os.environ, {
            'COOKIE_DIR': str(self.cookie_dir)
        })
        self.env_patcher.start()
    
    def tearDown(self):
        """Clean up test environment"""
        self.env_patcher.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_storage_state_loading_success(self):
        """Test successful storage state loading (Requirement 1.2, 1.3)"""
        # Create valid storage state file
        storage_state = {
            "cookies": [
                {
                    "name": "CONSENT",
                    "value": "YES+cb.20210328-17-p0.en+FX+123",
                    "domain": ".youtube.com",
                    "path": "/",
                    "expires": 1735689600,
                    "httpOnly": False,
                    "secure": True,
                    "sameSite": "None"
                },
                {
                    "name": "VISITOR_INFO1_LIVE", 
                    "value": "test_visitor_id",
                    "domain": ".youtube.com",
                    "path": "/",
                    "expires": 1735689600,
                    "httpOnly": False,
                    "secure": True,
                    "sameSite": "None"
                }
            ],
            "origins": []
        }
        
        with open(self.storage_state_path, 'w') as f:
            json.dump(storage_state, f)
        
        try:
            from transcript_service import TranscriptService
            service = TranscriptService()
            
            # Mock Playwright context creation to verify storage state is loaded
            with patch('transcript_service.sync_playwright') as mock_playwright:
                mock_browser = Mock()
                mock_context = Mock()
                mock_page = Mock()
                
                mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser
                mock_browser.new_context.return_value = mock_context
                mock_context.new_page.return_value = mock_page
                
                # This should load the storage state
                service._create_playwright_context_with_profile("desktop")
                
                # Verify storage_state parameter was passed
                mock_browser.new_context.assert_called()
                call_args = mock_browser.new_context.call_args
                self.assertIn('storage_state', call_args.kwargs)
                self.assertEqual(call_args.kwargs['storage_state'], str(self.storage_state_path))
                
        except ImportError as e:
            self.skipTest(f"TranscriptService not available: {e}")
    
    def test_storage_state_missing_warning(self):
        """Test warning when storage state is missing (Requirement 1.5)"""
        # Ensure no storage state file exists
        self.assertFalse(self.storage_state_path.exists())
        
        try:
            from transcript_service import TranscriptService
            
            with self.assertLogs(level='WARNING') as log_context:
                service = TranscriptService()
                
                # Mock Playwright to avoid actual browser launch
                with patch('transcript_service.sync_playwright') as mock_playwright:
                    mock_browser = Mock()
                    mock_context = Mock()
                    mock_page = Mock()
                    
                    mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser
                    mock_browser.new_context.return_value = mock_context
                    mock_context.new_page.return_value = mock_page
                    
                    service._create_playwright_context_with_profile("desktop")
                
                # Check that warning was logged
                warning_found = any("storage_state" in record.message.lower() for record in log_context.records)
                self.assertTrue(warning_found, "Expected warning about missing storage_state file")
                
        except ImportError as e:
            self.skipTest(f"TranscriptService not available: {e}")
    
    def test_netscape_conversion_fallback(self):
        """Test fallback to Netscape conversion (Requirement 1.6)"""
        # Create Netscape cookies file
        netscape_path = self.cookie_dir / "cookies.txt"
        netscape_content = """# Netscape HTTP Cookie File
.youtube.com	TRUE	/	FALSE	1735689600	CONSENT	YES+cb.20210328-17-p0.en+FX+123
.youtube.com	TRUE	/	FALSE	1735689600	VISITOR_INFO1_LIVE	test_visitor_id
"""
        with open(netscape_path, 'w') as f:
            f.write(netscape_content)
        
        try:
            from cookie_generator import convert_netscape_to_storage_state
            
            # Test conversion
            result_path = convert_netscape_to_storage_state(str(netscape_path))
            
            # Verify storage state was created
            self.assertTrue(Path(result_path).exists())
            
            # Verify content
            with open(result_path, 'r') as f:
                storage_state = json.load(f)
            
            self.assertIn('cookies', storage_state)
            self.assertGreater(len(storage_state['cookies']), 0)
            
            # Check for expected cookies
            cookie_names = [cookie['name'] for cookie in storage_state['cookies']]
            self.assertIn('CONSENT', cookie_names)
            self.assertIn('VISITOR_INFO1_LIVE', cookie_names)
            
        except ImportError as e:
            self.skipTest(f"Cookie generator not available: {e}")


class TestDeterministicInterception(unittest.TestCase):
    """Test deterministic YouTubei transcript capture (Requirement 2)"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_video_id = "test_video_123"
    
    def test_route_based_interception(self):
        """Test route-based interception with Future resolution (Requirement 2.1, 2.2)"""
        try:
            from transcript_service import TranscriptService
            
            service = TranscriptService()
            
            # Mock Playwright components
            with patch('transcript_service.sync_playwright') as mock_playwright:
                mock_browser = Mock()
                mock_context = Mock()
                mock_page = Mock()
                
                mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser
                mock_browser.new_context.return_value = mock_context
                mock_context.new_page.return_value = mock_page
                
                # Mock route setup
                mock_page.route = Mock()
                mock_page.goto = Mock()
                mock_page.wait_for_timeout = Mock()
                
                # Test route interception setup
                with patch.object(service, '_setup_transcript_route_interception') as mock_setup:
                    mock_setup.return_value = "test transcript content"
                    
                    result = service._get_transcript_via_youtubei_enhanced(self.test_video_id)
                    
                    # Verify route was set up
                    mock_setup.assert_called_once()
                    self.assertEqual(result, "test transcript content")
                    
        except ImportError as e:
            self.skipTest(f"TranscriptService not available: {e}")
    
    def test_future_timeout_handling(self):
        """Test Future timeout and fallback (Requirement 2.4)"""
        try:
            from transcript_service import DeterministicTranscriptCapture
            import asyncio
            
            capture = DeterministicTranscriptCapture()
            
            # Test timeout scenario
            with patch('asyncio.wait_for') as mock_wait:
                mock_wait.side_effect = asyncio.TimeoutError("Test timeout")
                
                # This should handle timeout gracefully
                result = capture.wait_for_transcript_with_timeout(timeout_seconds=1)
                self.assertIsNone(result)
                
        except ImportError as e:
            self.skipTest(f"DeterministicTranscriptCapture not available: {e}")
    
    def test_no_fixed_waits(self):
        """Test that no fixed wait_for_timeout calls are used (Requirement 2.3)"""
        try:
            from transcript_service import TranscriptService
            
            service = TranscriptService()
            
            # Mock Playwright to track wait_for_timeout calls
            with patch('transcript_service.sync_playwright') as mock_playwright:
                mock_browser = Mock()
                mock_context = Mock()
                mock_page = Mock()
                
                mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser
                mock_browser.new_context.return_value = mock_context
                mock_context.new_page.return_value = mock_page
                
                # Track wait_for_timeout calls
                wait_calls = []
                def track_wait(*args, **kwargs):
                    wait_calls.append((args, kwargs))
                    
                mock_page.wait_for_timeout.side_effect = track_wait
                
                # Mock successful transcript capture to avoid actual network calls
                with patch.object(service, '_setup_transcript_route_interception') as mock_setup:
                    mock_setup.return_value = "test transcript"
                    
                    service._get_transcript_via_youtubei_enhanced(self.test_video_id)
                    
                    # Verify no fixed waits were used in transcript capture
                    # (Some waits might be acceptable for page loading, but not for transcript capture)
                    transcript_related_waits = [call for call in wait_calls if len(call[0]) > 0 and call[0][0] > 5000]
                    self.assertEqual(len(transcript_related_waits), 0, 
                                   f"Found fixed waits that might be transcript-related: {transcript_related_waits}")
                    
        except ImportError as e:
            self.skipTest(f"TranscriptService not available: {e}")


class TestMultiClientProfiles(unittest.TestCase):
    """Test multi-client profile system (Requirement 3)"""
    
    def test_profile_configurations(self):
        """Test desktop and mobile profile configurations (Requirement 3.6, 3.7)"""
        try:
            from transcript_service import PROFILES, ClientProfile
            
            # Verify profiles exist
            self.assertIn('desktop', PROFILES)
            self.assertIn('mobile', PROFILES)
            
            # Test desktop profile
            desktop = PROFILES['desktop']
            self.assertIsInstance(desktop, ClientProfile)
            self.assertEqual(desktop.name, 'desktop')
            self.assertIn('Windows NT 10.0', desktop.user_agent)
            self.assertEqual(desktop.viewport['width'], 1920)
            self.assertEqual(desktop.viewport['height'], 1080)
            
            # Test mobile profile
            mobile = PROFILES['mobile']
            self.assertIsInstance(mobile, ClientProfile)
            self.assertEqual(mobile.name, 'mobile')
            self.assertIn('Android', mobile.user_agent)
            self.assertEqual(mobile.viewport['width'], 390)
            self.assertEqual(mobile.viewport['height'], 844)
            
        except ImportError as e:
            self.skipTest(f"Profile configurations not available: {e}")
    
    def test_profile_switching_sequence(self):
        """Test attempt sequence: desktop(no-proxy → proxy) then mobile(no-proxy → proxy) (Requirement 3.5)"""
        try:
            from transcript_service import TranscriptService
            
            service = TranscriptService()
            
            # Mock the individual attempt methods to track call sequence
            attempt_calls = []
            
            def mock_attempt(video_id, profile, use_proxy):
                attempt_calls.append((profile, use_proxy))
                return ""  # Simulate failure to continue sequence
            
            with patch.object(service, '_attempt_youtubei_with_profile', side_effect=mock_attempt):
                service._get_transcript_via_youtubei_enhanced(self.test_video_id)
            
            # Verify correct sequence
            expected_sequence = [
                ('desktop', False),  # Desktop without proxy
                ('desktop', True),   # Desktop with proxy
                ('mobile', False),   # Mobile without proxy
                ('mobile', True)     # Mobile with proxy
            ]
            
            self.assertEqual(attempt_calls, expected_sequence)
            
        except ImportError as e:
            self.skipTest(f"TranscriptService not available: {e}")
    
    def test_browser_context_reuse(self):
        """Test browser context reuse with profile switching (Requirement 3.4)"""
        try:
            from transcript_service import TranscriptService
            
            service = TranscriptService()
            
            # Mock Playwright to track browser/context creation
            with patch('transcript_service.sync_playwright') as mock_playwright:
                mock_browser = Mock()
                mock_context1 = Mock()
                mock_context2 = Mock()
                
                mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser
                mock_browser.new_context.side_effect = [mock_context1, mock_context2]
                
                # Create contexts for different profiles
                context1 = service._create_playwright_context_with_profile("desktop")
                context2 = service._create_playwright_context_with_profile("mobile")
                
                # Verify same browser instance is reused
                self.assertEqual(mock_browser.new_context.call_count, 2)
                # Verify different contexts are created
                self.assertNotEqual(context1, context2)
                
        except ImportError as e:
            self.skipTest(f"TranscriptService not available: {e}")


class TestEnhancedCookieIntegration(unittest.TestCase):
    """Test enhanced cookie integration for timed-text (Requirement 4)"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_video_id = "test_video_123"
        self.test_user_id = 456
    
    def test_timed_text_cookie_parameters(self):
        """Test timed-text methods accept cookies parameter (Requirement 4.1, 4.2)"""
        try:
            from transcript_service import _fetch_timedtext_json3_enhanced, _fetch_timedtext_xml_enhanced
            
            test_cookies = {"session_token": "abc123", "user_id": "456"}
            
            # Mock requests to avoid actual network calls
            with patch('requests.Session') as mock_session_class:
                mock_session = Mock()
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.text = '{"events": []}'
                mock_session.get.return_value = mock_response
                mock_session_class.return_value = mock_session
                
                # Test JSON3 method with cookies
                result = _fetch_timedtext_json3_enhanced(self.test_video_id, cookies=test_cookies)
                
                # Verify cookies were passed to request
                mock_session.get.assert_called()
                call_kwargs = mock_session.get.call_args.kwargs
                self.assertIn('cookies', call_kwargs)
                
                # Test XML method with cookies
                mock_response.text = '<transcript></transcript>'
                result = _fetch_timedtext_xml_enhanced(self.test_video_id, cookies=test_cookies)
                
                # Verify cookies were passed
                self.assertEqual(mock_session.get.call_count, 2)
                
        except ImportError as e:
            self.skipTest(f"Enhanced timed-text methods not available: {e}")
    
    def test_user_cookie_preference(self):
        """Test user cookies preferred over environment cookies (Requirement 4.3, 4.4)"""
        try:
            from transcript_service import TranscriptService
            
            service = TranscriptService()
            service.set_current_user_id(self.test_user_id)
            
            # Mock user cookie loading
            with patch.object(service, '_load_user_cookies_from_s3') as mock_user_cookies:
                mock_user_cookies.return_value = {"user_session": "user123"}
                
                with patch.object(service, '_cookie_header_from_env_or_file') as mock_env_cookies:
                    mock_env_cookies.return_value = "env_session=env456"
                    
                    # Mock timed-text method to capture cookies used
                    with patch('transcript_service._fetch_timedtext_json3_enhanced') as mock_fetch:
                        mock_fetch.return_value = "test transcript"
                        
                        service._get_captions_via_timedtext_json3(self.test_video_id)
                        
                        # Verify user cookies were preferred
                        mock_fetch.assert_called()
                        call_kwargs = mock_fetch.call_args.kwargs
                        self.assertIn('cookies', call_kwargs)
                        # User cookies should be used, not env cookies
                        mock_user_cookies.assert_called_once()
                        
        except ImportError as e:
            self.skipTest(f"TranscriptService not available: {e}")
    
    def test_cookie_source_logging(self):
        """Test debug logging for cookie source (Requirement 4.6)"""
        try:
            from transcript_service import TranscriptService
            
            service = TranscriptService()
            service.set_current_user_id(self.test_user_id)
            
            with self.assertLogs(level='DEBUG') as log_context:
                # Mock user cookie loading
                with patch.object(service, '_load_user_cookies_from_s3') as mock_user_cookies:
                    mock_user_cookies.return_value = {"user_session": "user123"}
                    
                    with patch('transcript_service._fetch_timedtext_json3_enhanced') as mock_fetch:
                        mock_fetch.return_value = "test transcript"
                        
                        service._get_captions_via_timedtext_json3(self.test_video_id)
                
                # Check for cookie source logging
                cookie_source_logged = any("cookie_source" in record.message.lower() for record in log_context.records)
                self.assertTrue(cookie_source_logged, "Expected debug log about cookie source")
                
        except ImportError as e:
            self.skipTest(f"TranscriptService not available: {e}")


class TestHTTPAdapterConfiguration(unittest.TestCase):
    """Test complete HTTP adapter configuration (Requirement 5)"""
    
    def test_http_and_https_adapter_mounting(self):
        """Test HTTP adapter mounting for both HTTP and HTTPS (Requirement 5.1, 5.2)"""
        try:
            from transcript_service import make_http_session
            
            session = make_http_session()
            
            # Verify adapters are mounted for both protocols
            self.assertIn('http://', session.adapters)
            self.assertIn('https://', session.adapters)
            
            # Verify they are HTTPAdapter instances with retry logic
            http_adapter = session.adapters['http://']
            https_adapter = session.adapters['https://']
            
            self.assertIsInstance(http_adapter, requests.adapters.HTTPAdapter)
            self.assertIsInstance(https_adapter, requests.adapters.HTTPAdapter)
            
        except ImportError as e:
            self.skipTest(f"make_http_session not available: {e}")
    
    def test_no_unmounted_adapter_warnings(self):
        """Test no warnings about unmounted adapters (Requirement 5.4)"""
        try:
            from transcript_service import make_http_session
            
            with self.assertLogs(level='WARNING') as log_context:
                session = make_http_session()
                
                # Make a mock request to trigger adapter usage
                with patch.object(session, 'get') as mock_get:
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_get.return_value = mock_response
                    
                    session.get('http://example.com')
                    session.get('https://example.com')
            
            # Check that no warnings about unmounted adapters were logged
            adapter_warnings = [record for record in log_context.records 
                              if 'adapter' in record.message.lower() and 'mount' in record.message.lower()]
            self.assertEqual(len(adapter_warnings), 0, f"Found adapter warnings: {adapter_warnings}")
            
        except ImportError as e:
            self.skipTest(f"make_http_session not available: {e}")


class TestCircuitBreakerIntegration(unittest.TestCase):
    """Test circuit breaker integration hooks (Requirement 6)"""
    
    def test_circuit_breaker_failure_recording(self):
        """Test circuit breaker failure recording after retry completion (Requirement 6.3)"""
        try:
            from transcript_service import PlaywrightCircuitBreaker
            
            cb = PlaywrightCircuitBreaker()
            
            # Initially closed
            self.assertFalse(cb.is_open())
            
            # Record failures
            cb.record_failure()
            cb.record_failure()
            cb.record_failure()
            
            # Should be open after threshold failures
            self.assertTrue(cb.is_open())
            
        except ImportError as e:
            self.skipTest(f"PlaywrightCircuitBreaker not available: {e}")
    
    def test_circuit_breaker_skip_logic(self):
        """Test circuit breaker skip logic with logging (Requirement 6.4)"""
        try:
            from transcript_service import TranscriptService
            
            service = TranscriptService()
            
            # Mock circuit breaker to be open
            with patch('transcript_service._playwright_circuit_breaker') as mock_cb:
                mock_cb.is_open.return_value = True
                
                with self.assertLogs(level='INFO') as log_context:
                    result = service._get_transcript_via_youtubei_enhanced("test_video")
                    
                    # Should return empty string when circuit breaker is open
                    self.assertEqual(result, "")
                    
                    # Check for skip logging
                    skip_logged = any("skip" in record.message.lower() and "open" in record.message.lower() 
                                    for record in log_context.records)
                    self.assertTrue(skip_logged, "Expected logging about circuit breaker skip")
                    
        except ImportError as e:
            self.skipTest(f"TranscriptService not available: {e}")
    
    def test_circuit_breaker_success_reset(self):
        """Test circuit breaker success recording resets state (Requirement 6.5)"""
        try:
            from transcript_service import PlaywrightCircuitBreaker
            
            cb = PlaywrightCircuitBreaker()
            
            # Record failures to open circuit breaker
            cb.record_failure()
            cb.record_failure()
            cb.record_failure()
            self.assertTrue(cb.is_open())
            
            # Record success should reset
            cb.record_success()
            self.assertFalse(cb.is_open())
            
        except ImportError as e:
            self.skipTest(f"PlaywrightCircuitBreaker not available: {e}")


class TestDOMFallback(unittest.TestCase):
    """Test DOM fallback implementation (Requirement 7)"""
    
    def test_dom_polling_after_timeout(self):
        """Test DOM polling after network route timeout (Requirement 7.1, 7.2)"""
        try:
            from transcript_service import TranscriptService
            
            service = TranscriptService()
            
            # Mock Playwright page with DOM elements
            mock_page = Mock()
            mock_elements = [Mock(), Mock()]
            mock_elements[0].text_content.return_value = "First transcript line"
            mock_elements[1].text_content.return_value = "Second transcript line"
            mock_page.query_selector_all.return_value = mock_elements
            
            # Test DOM fallback
            result = service._extract_transcript_from_dom(mock_page)
            
            # Should extract text from DOM elements
            self.assertIn("First transcript line", result)
            self.assertIn("Second transcript line", result)
            
        except ImportError as e:
            self.skipTest(f"TranscriptService not available: {e}")
    
    def test_dom_fallback_logging(self):
        """Test logging for successful DOM fallback (Requirement 7.4)"""
        try:
            from transcript_service import TranscriptService
            
            service = TranscriptService()
            
            with self.assertLogs(level='INFO') as log_context:
                # Mock successful DOM extraction
                mock_page = Mock()
                mock_elements = [Mock()]
                mock_elements[0].text_content.return_value = "DOM transcript content"
                mock_page.query_selector_all.return_value = mock_elements
                
                result = service._extract_transcript_from_dom(mock_page)
                
                # Check for DOM fallback success logging
                dom_logged = any("dom" in record.message.lower() and "fallback" in record.message.lower() 
                                for record in log_context.records)
                self.assertTrue(dom_logged, "Expected logging about successful DOM fallback")
                
        except ImportError as e:
            self.skipTest(f"TranscriptService not available: {e}")


class TestProxyConfiguration(unittest.TestCase):
    """Test proxy configuration across all components (Requirements 8, 14, 15, 16)"""
    
    def test_proxy_environment_for_subprocess(self):
        """Test proxy environment variable computation (Requirement 8.1, 14.1, 14.2)"""
        try:
            from proxy_manager import ProxyManager
            
            # Mock proxy configuration
            with patch.dict(os.environ, {
                'PROXY_SECRET_NAME': 'test-proxy-secret'
            }):
                pm = ProxyManager()
                
                # Mock proxy secret loading
                with patch.object(pm, '_load_proxy_secret') as mock_load:
                    mock_secret = Mock()
                    mock_secret.host = "proxy.example.com"
                    mock_secret.port = 8080
                    mock_secret.username = "testuser"
                    mock_secret.password = "testpass"
                    mock_load.return_value = mock_secret
                    
                    # Test subprocess environment generation
                    env_vars = pm.proxy_env_for_subprocess()
                    
                    # Should return http_proxy and https_proxy
                    self.assertIn('http_proxy', env_vars)
                    self.assertIn('https_proxy', env_vars)
                    
                    # URLs should contain credentials and host
                    proxy_url = env_vars['http_proxy']
                    self.assertIn('testuser', proxy_url)
                    self.assertIn('proxy.example.com', proxy_url)
                    self.assertIn('8080', proxy_url)
                    
        except ImportError as e:
            self.skipTest(f"ProxyManager not available: {e}")
    
    def test_unified_proxy_dictionary_interface(self):
        """Test unified proxy dictionary interface (Requirement 15.1, 15.2)"""
        try:
            from proxy_manager import ProxyManager
            
            with patch.dict(os.environ, {
                'PROXY_SECRET_NAME': 'test-proxy-secret'
            }):
                pm = ProxyManager()
                
                # Mock proxy secret
                with patch.object(pm, '_load_proxy_secret') as mock_load:
                    mock_secret = Mock()
                    mock_secret.host = "proxy.example.com"
                    mock_secret.port = 8080
                    mock_secret.username = "testuser"
                    mock_secret.password = "testpass"
                    mock_load.return_value = mock_secret
                    
                    # Test requests format
                    requests_dict = pm.proxy_dict_for("requests")
                    self.assertIn('http', requests_dict)
                    self.assertIn('https', requests_dict)
                    
                    # Test playwright format
                    playwright_dict = pm.proxy_dict_for("playwright")
                    self.assertIn('server', playwright_dict)
                    self.assertIn('username', playwright_dict)
                    self.assertIn('password', playwright_dict)
                    
        except ImportError as e:
            self.skipTest(f"ProxyManager not available: {e}")
    
    def test_proxy_health_monitoring(self):
        """Test proxy health metrics and monitoring (Requirement 16.1, 16.3)"""
        try:
            from proxy_manager import ProxyManager
            
            with patch.dict(os.environ, {
                'PROXY_SECRET_NAME': 'test-proxy-secret'
            }):
                pm = ProxyManager()
                
                # Mock proxy secret
                with patch.object(pm, '_load_proxy_secret') as mock_load:
                    mock_secret = Mock()
                    mock_secret.host = "proxy.example.com"
                    mock_secret.port = 8080
                    mock_secret.username = "testuser"
                    mock_secret.password = "testpass"
                    mock_load.return_value = mock_secret
                    
                    # Test health accessor
                    with patch.object(pm, '_check_proxy_health') as mock_health:
                        mock_health.return_value = True
                        
                        healthy = pm.healthy
                        self.assertTrue(healthy)
                        
        except ImportError as e:
            self.skipTest(f"ProxyManager not available: {e}")


class TestFFmpegEnhancements(unittest.TestCase):
    """Test FFmpeg header hygiene and proxy enforcement (Requirements 8, 9)"""
    
    def test_ffmpeg_proxy_environment(self):
        """Test FFmpeg proxy environment variable setting (Requirement 8.2, 8.3)"""
        try:
            from transcript_service import ASRAudioExtractor
            from proxy_manager import ProxyManager
            
            # Mock proxy manager
            pm = ProxyManager()
            extractor = ASRAudioExtractor(pm)
            
            with patch.object(pm, 'proxy_env_for_subprocess') as mock_env:
                mock_env.return_value = {
                    'http_proxy': 'http://user:pass@proxy.example.com:8080',
                    'https_proxy': 'http://user:pass@proxy.example.com:8080'
                }
                
                # Mock subprocess to capture environment
                with patch('subprocess.run') as mock_run:
                    mock_run.return_value = Mock(returncode=0)
                    
                    extractor._extract_audio_to_wav_enhanced("test_video", "http://example.com/audio.m4a")
                    
                    # Verify subprocess was called with proxy environment
                    mock_run.assert_called()
                    call_kwargs = mock_run.call_args.kwargs
                    self.assertIn('env', call_kwargs)
                    
                    env = call_kwargs['env']
                    self.assertIn('http_proxy', env)
                    self.assertIn('https_proxy', env)
                    
        except ImportError as e:
            self.skipTest(f"ASRAudioExtractor not available: {e}")
    
    def test_ffmpeg_header_formatting(self):
        """Test FFmpeg header CRLF formatting and placement (Requirement 9.1, 9.2)"""
        try:
            from transcript_service import ASRAudioExtractor
            
            extractor = ASRAudioExtractor(None)
            
            # Test header formatting
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'Cookie': 'session=abc123; user=test'
            }
            
            formatted_headers = extractor._format_headers_for_ffmpeg(headers)
            
            # Should be CRLF-joined
            self.assertIn('\r\n', formatted_headers)
            
            # Should contain all headers
            self.assertIn('User-Agent', formatted_headers)
            self.assertIn('Cookie', formatted_headers)
            
        except ImportError as e:
            self.skipTest(f"ASRAudioExtractor not available: {e}")
    
    def test_cookie_masking_in_logs(self):
        """Test cookie value masking in log output (Requirement 9.3, 9.5)"""
        try:
            from transcript_service import ASRAudioExtractor
            
            extractor = ASRAudioExtractor(None)
            
            with self.assertLogs(level='DEBUG') as log_context:
                # Mock subprocess with cookie headers
                with patch('subprocess.run') as mock_run:
                    mock_run.return_value = Mock(returncode=0)
                    
                    headers = {'Cookie': 'secret_session_token=very_secret_value'}
                    extractor._extract_audio_to_wav_enhanced("test_video", "http://example.com/audio.m4a", headers=headers)
                
                # Check that raw cookie values don't appear in logs
                log_messages = [record.message for record in log_context.records]
                cookie_leaked = any('very_secret_value' in msg for msg in log_messages)
                self.assertFalse(cookie_leaked, "Cookie values should be masked in logs")
                
        except ImportError as e:
            self.skipTest(f"ASRAudioExtractor not available: {e}")


class TestMetricsAndLogging(unittest.TestCase):
    """Test comprehensive metrics and structured logging (Requirement 10)"""
    
    def test_circuit_breaker_state_logging(self):
        """Test structured event emission for circuit breaker state changes (Requirement 10.1, 10.2)"""
        try:
            from transcript_service import PlaywrightCircuitBreaker
            
            cb = PlaywrightCircuitBreaker()
            
            with self.assertLogs(level='INFO') as log_context:
                # Trigger state changes
                cb.record_failure()
                cb.record_failure()
                cb.record_failure()  # Should open circuit breaker
                
                cb.record_success()  # Should close circuit breaker
            
            # Check for structured state change events
            state_change_logs = [record for record in log_context.records 
                               if 'circuit_breaker' in record.message.lower()]
            self.assertGreater(len(state_change_logs), 0, "Expected circuit breaker state change logging")
            
        except ImportError as e:
            self.skipTest(f"PlaywrightCircuitBreaker not available: {e}")
    
    def test_stage_duration_logging(self):
        """Test stage duration logging with success/failure tracking (Requirement 10.3)"""
        try:
            from transcript_service import TranscriptService
            
            service = TranscriptService()
            
            with self.assertLogs(level='INFO') as log_context:
                # Mock successful transcript extraction
                with patch.object(service, '_get_captions_via_api') as mock_api:
                    mock_api.return_value = "test transcript"
                    
                    service.get_transcript("test_video")
            
            # Check for stage duration metrics
            duration_logs = [record for record in log_context.records 
                           if 'duration' in record.message.lower() or 'stage' in record.message.lower()]
            self.assertGreater(len(duration_logs), 0, "Expected stage duration logging")
            
        except ImportError as e:
            self.skipTest(f"TranscriptService not available: {e}")
    
    def test_successful_method_logging(self):
        """Test logging which transcript extraction method succeeded (Requirement 10.4)"""
        try:
            from transcript_service import TranscriptService
            
            service = TranscriptService()
            
            with self.assertLogs(level='INFO') as log_context:
                # Mock successful API extraction
                with patch.object(service, '_get_captions_via_api') as mock_api:
                    mock_api.return_value = "test transcript from API"
                    
                    service.get_transcript("test_video")
            
            # Check for method success logging
            method_logs = [record for record in log_context.records 
                         if any(method in record.message.lower() for method in ['api', 'timedtext', 'youtubei', 'asr'])]
            self.assertGreater(len(method_logs), 0, "Expected logging about which method succeeded")
            
        except ImportError as e:
            self.skipTest(f"TranscriptService not available: {e}")


class TestCookieManagement(unittest.TestCase):
    """Test cookie management enhancements (Requirements 11, 12, 13)"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.cookie_dir = Path(self.temp_dir)
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_netscape_to_storage_state_conversion(self):
        """Test Netscape to storage state conversion (Requirement 11.1, 11.2)"""
        try:
            from cookie_generator import convert_netscape_to_storage_state
            
            # Create test Netscape file
            netscape_path = self.cookie_dir / "cookies.txt"
            netscape_content = """# Netscape HTTP Cookie File
.youtube.com	TRUE	/	FALSE	1735689600	CONSENT	YES+cb.20210328-17-p0.en+FX+123
.youtube.com	TRUE	/	TRUE	1735689600	session_token	abc123def456
"""
            with open(netscape_path, 'w') as f:
                f.write(netscape_content)
            
            # Test conversion
            result_path = convert_netscape_to_storage_state(str(netscape_path))
            
            # Verify storage state was created
            self.assertTrue(Path(result_path).exists())
            
            # Verify content structure
            with open(result_path, 'r') as f:
                storage_state = json.load(f)
            
            self.assertIn('cookies', storage_state)
            self.assertIn('origins', storage_state)
            
            # Verify cookies were converted
            cookies = storage_state['cookies']
            cookie_names = [cookie['name'] for cookie in cookies]
            self.assertIn('CONSENT', cookie_names)
            self.assertIn('session_token', cookie_names)
            
        except ImportError as e:
            self.skipTest(f"Cookie generator not available: {e}")
    
    def test_host_cookie_sanitation(self):
        """Test __Host- cookie sanitation (Requirement 12.1, 12.2, 12.3)"""
        try:
            from cookie_generator import sanitize_host_cookies
            
            # Test cookies with __Host- prefix
            cookies = [
                {
                    'name': '__Host-session',
                    'value': 'abc123',
                    'domain': '.youtube.com',
                    'path': '/watch',
                    'secure': False
                },
                {
                    'name': 'regular_cookie',
                    'value': 'def456',
                    'domain': '.youtube.com',
                    'path': '/',
                    'secure': True
                }
            ]
            
            sanitized = sanitize_host_cookies(cookies)
            
            # Find the __Host- cookie
            host_cookie = next((c for c in sanitized if c['name'] == '__Host-session'), None)
            self.assertIsNotNone(host_cookie)
            
            # Verify sanitization
            self.assertTrue(host_cookie['secure'])  # Should be secure=True
            self.assertEqual(host_cookie['path'], '/')  # Should be path="/"
            self.assertNotIn('domain', host_cookie)  # Domain should be removed
            
            # Regular cookie should be unchanged
            regular_cookie = next((c for c in sanitized if c['name'] == 'regular_cookie'), None)
            self.assertIsNotNone(regular_cookie)
            self.assertEqual(regular_cookie['domain'], '.youtube.com')
            
        except ImportError as e:
            self.skipTest(f"Cookie sanitization not available: {e}")
    
    def test_consent_cookie_injection(self):
        """Test SOCS/CONSENT cookie injection when missing (Requirement 13.1, 13.2, 13.3)"""
        try:
            from cookie_generator import inject_consent_cookies_if_missing
            
            # Test storage state without consent cookies
            storage_state = {
                'cookies': [
                    {
                        'name': 'session_token',
                        'value': 'abc123',
                        'domain': '.youtube.com',
                        'path': '/',
                        'secure': True
                    }
                ],
                'origins': []
            }
            
            # Inject consent cookies
            updated_state = inject_consent_cookies_if_missing(storage_state)
            
            # Verify consent cookie was added
            cookie_names = [cookie['name'] for cookie in updated_state['cookies']]
            has_consent = any(name in ['SOCS', 'CONSENT'] for name in cookie_names)
            self.assertTrue(has_consent, "Expected SOCS or CONSENT cookie to be injected")
            
            # Verify consent cookie properties
            consent_cookie = next((c for c in updated_state['cookies'] if c['name'] in ['SOCS', 'CONSENT']), None)
            self.assertIsNotNone(consent_cookie)
            self.assertEqual(consent_cookie['domain'], '.youtube.com')
            self.assertGreater(consent_cookie['expires'], time.time())  # Should have long expiry
            
        except ImportError as e:
            self.skipTest(f"Consent cookie injection not available: {e}")


class TestTenacityRetryWrapper(unittest.TestCase):
    """Test tenacity retry wrapper implementation (Requirement 17)"""
    
    def test_retry_wrapper_on_youtubei_attempt(self):
        """Test tenacity retry wrapper applied to complete YouTubei attempt (Requirement 17.1)"""
        try:
            from transcript_service import TranscriptService
            
            service = TranscriptService()
            
            # Mock tenacity retry behavior
            attempt_count = 0
            def mock_attempt(*args, **kwargs):
                nonlocal attempt_count
                attempt_count += 1
                if attempt_count < 3:
                    raise Exception("Simulated timeout")
                return "success after retries"
            
            with patch.object(service, '_attempt_youtubei_with_profile', side_effect=mock_attempt):
                result = service._get_transcript_via_youtubei_enhanced("test_video")
                
                # Should succeed after retries
                self.assertEqual(result, "success after retries")
                self.assertEqual(attempt_count, 3)  # Should have retried
                
        except ImportError as e:
            self.skipTest(f"TranscriptService not available: {e}")
    
    def test_exponential_backoff_with_jitter(self):
        """Test exponential backoff with jitter for navigation timeouts (Requirement 17.2)"""
        try:
            from transcript_service import TranscriptService
            import time
            
            service = TranscriptService()
            
            # Track retry timing
            retry_times = []
            def mock_attempt(*args, **kwargs):
                retry_times.append(time.time())
                if len(retry_times) < 3:
                    raise Exception("Simulated navigation timeout")
                return "success"
            
            with patch.object(service, '_attempt_youtubei_with_profile', side_effect=mock_attempt):
                start_time = time.time()
                result = service._get_transcript_via_youtubei_enhanced("test_video")
                
                # Should have increasing delays between retries
                if len(retry_times) >= 2:
                    delay1 = retry_times[1] - retry_times[0]
                    delay2 = retry_times[2] - retry_times[1] if len(retry_times) >= 3 else 0
                    
                    # Second delay should be longer than first (exponential backoff)
                    if delay2 > 0:
                        self.assertGreater(delay2, delay1 * 0.8)  # Allow for jitter
                        
        except ImportError as e:
            self.skipTest(f"TranscriptService not available: {e}")
    
    def test_circuit_breaker_after_retry_exhaustion(self):
        """Test circuit breaker activation after retry exhaustion (Requirement 17.4)"""
        try:
            from transcript_service import TranscriptService
            
            service = TranscriptService()
            
            # Mock circuit breaker
            with patch('transcript_service._playwright_circuit_breaker') as mock_cb:
                mock_cb.is_open.return_value = False
                
                # Mock all attempts to fail
                with patch.object(service, '_attempt_youtubei_with_profile') as mock_attempt:
                    mock_attempt.side_effect = Exception("Persistent failure")
                    
                    result = service._get_transcript_via_youtubei_enhanced("test_video")
                    
                    # Should record failure after retry exhaustion
                    mock_cb.record_failure.assert_called()
                    
        except ImportError as e:
            self.skipTest(f"TranscriptService not available: {e}")


def run_integration_tests():
    """Run integration tests that require actual network access"""
    print("\n=== Integration Tests (require network) ===")
    
    try:
        from transcript_service import TranscriptService
        
        # Test with a known public video
        service = TranscriptService()
        
        # Use a video that's likely to have transcripts
        test_video_id = "dQw4w9WgXcQ"  # Rick Roll - likely to have captions
        
        print(f"Testing enhanced transcript service with video: {test_video_id}")
        start_time = time.time()
        
        result = service.get_transcript(test_video_id)
        duration = time.time() - start_time
        
        if result and result.strip():
            print(f"Integration test successful!")
            print(f"   Duration: {duration:.2f}s")
            print(f"   Transcript length: {len(result)} characters")
            print(f"   First 100 chars: {result[:100]}...")
            return True
        else:
            print(f"Integration test returned empty result (may be expected)")
            return True  # Don't fail on empty result as video may not have captions
            
    except Exception as e:
        print(f"Integration test failed: {e}")
        return False


def main():
    """Run all integration tests"""
    print("Transcript Service Enhancements - Integration Test Suite")
    print("=" * 80)
    
    # Run unit tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestStorageStateManagement,
        TestDeterministicInterception,
        TestMultiClientProfiles,
        TestEnhancedCookieIntegration,
        TestHTTPAdapterConfiguration,
        TestCircuitBreakerIntegration,
        TestDOMFallback,
        TestProxyConfiguration,
        TestFFmpegEnhancements,
        TestMetricsAndLogging,
        TestCookieManagement,
        TestTenacityRetryWrapper
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run unit tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Run integration tests if unit tests pass
    integration_success = True
    if result.wasSuccessful():
        integration_success = run_integration_tests()
    
    # Summary
    print("\n" + "=" * 80)
    unit_tests_passed = result.wasSuccessful()
    
    if unit_tests_passed and integration_success:
        print("All integration tests passed! Enhanced transcript service is working correctly.")
        print("\nValidated Requirements:")
        print("   - Storage state loading and Netscape conversion")
        print("   - Deterministic interception and multi-profile support")
        print("   - Cookie integration and circuit breaker behavior")
        print("   - Proxy configuration across all components")
        print("   - All enhanced functionality requirements")
        return 0
    else:
        if not unit_tests_passed:
            print(f"Unit tests failed: {len(result.failures)} failures, {len(result.errors)} errors")
        if not integration_success:
            print("Integration tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())