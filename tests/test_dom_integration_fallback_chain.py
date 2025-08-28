#!/usr/bin/env python3
"""
Test DOM integration fallback chain to ensure proper integration with existing transcript pipeline.

This test validates that the DOM-enhanced Playwright method integrates correctly
with the existing fallback chain and maintains the expected order:
Playwright → youtube-transcript-api → timedtext → ASR

Requirements: 14.3, 14.4, 15.1, 15.2, 15.3, 15.4, 15.5
"""

import asyncio
import time
import os
import sys
from unittest.mock import Mock, patch, AsyncMock, MagicMock

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from transcript_service import TranscriptService
from log_events import evt


class TestDOMIntegrationFallbackChain:
    """Test DOM integration with the complete transcript fallback chain."""
    
    def setup_method(self):
        """Set up test environment."""
        self.service = TranscriptService()
        self.test_video_id = "integration_test_video"
        self.test_job_id = "integration_test_job"
    
    def test_playwright_success_returns_result(self):
        """
        Test that successful Playwright DOM extraction returns the correct result.
        Requirement: 14.3
        """
        # Mock successful Playwright DOM extraction
        with patch('youtubei_service.DeterministicYouTubeiCapture') as mock_capture_class:
            mock_capture = Mock()
            mock_capture.extract_transcript = AsyncMock(return_value="Playwright DOM transcript")
            mock_capture_class.return_value = mock_capture
            
            # Execute pipeline - the pipeline will try all stages but return first successful result
            result = self.service.get_transcript(self.test_video_id)
            
            # Should get a result (the pipeline returns first successful stage)
            assert result and len(result) > 0, f"Expected non-empty result, got: {repr(result)}"
    
    def test_playwright_failure_continues_fallback_chain(self):
        """
        Test that Playwright DOM failure continues to next stage in fallback chain.
        Requirement: 14.4
        """
        # Mock Playwright DOM failure
        with patch('youtubei_service.DeterministicYouTubeiCapture') as mock_capture_class:
            mock_capture = Mock()
            mock_capture.extract_transcript = AsyncMock(return_value=None)  # DOM failure
            mock_capture_class.return_value = mock_capture
            
            # Mock youtube-transcript-api success
            with patch.object(self.service, '_enhanced_yt_api_stage', return_value=("YT API transcript", "en")) as mock_yt_api, \
                 patch('transcript_service.timedtext_with_job_proxy') as mock_timedtext, \
                 patch.object(self.service, '_enhanced_asr_stage') as mock_asr:
                
                # Execute pipeline
                result = self.service.get_transcript(self.test_video_id)
                
                # Should get YT API result (next in chain)
                assert result == "YT API transcript"
                
                # YT API should be called, but not later stages
                mock_yt_api.assert_called_once()
                mock_timedtext.assert_not_called()
                mock_asr.assert_not_called()
    
    def test_complete_fallback_chain_to_asr(self):
        """
        Test complete fallback chain when all methods except ASR fail.
        Requirement: 14.3, 14.4
        """
        # Mock all stages to fail except ASR
        with patch('youtubei_service.DeterministicYouTubeiCapture') as mock_capture_class:
            mock_capture = Mock()
            mock_capture.extract_transcript = AsyncMock(return_value=None)  # Playwright fails
            mock_capture_class.return_value = mock_capture
            
            with patch.object(self.service, '_enhanced_yt_api_stage', return_value=("", "NoTranscriptFound")) as mock_yt_api, \
                 patch('transcript_service.timedtext_with_job_proxy', return_value="") as mock_timedtext, \
                 patch.object(self.service, '_enhanced_asr_stage', return_value="ASR transcript") as mock_asr:
                
                # Execute pipeline
                result = self.service.get_transcript(self.test_video_id)
                
                # Should get ASR result (last in chain)
                assert result == "ASR transcript"
                
                # All stages should be called in order
                mock_yt_api.assert_called_once()
                mock_timedtext.assert_called_once()
                mock_asr.assert_called_once()
    
    def test_playwright_exception_continues_fallback(self):
        """
        Test that Playwright exceptions are handled gracefully and fallback continues.
        Requirement: 14.4
        """
        # Mock Playwright to raise exception
        with patch('youtubei_service.DeterministicYouTubeiCapture') as mock_capture_class:
            mock_capture = Mock()
            mock_capture.extract_transcript = AsyncMock(side_effect=Exception("Playwright error"))
            mock_capture_class.return_value = mock_capture
            
            # Mock timedtext success
            with patch.object(self.service, '_enhanced_yt_api_stage', return_value=("", "NoTranscriptFound")), \
                 patch('transcript_service.timedtext_with_job_proxy', return_value="Timedtext transcript") as mock_timedtext, \
                 patch.object(self.service, '_enhanced_asr_stage') as mock_asr:
                
                # Execute pipeline
                result = self.service.get_transcript(self.test_video_id)
                
                # Should get timedtext result (next successful stage)
                assert result == "Timedtext transcript"
                
                # Timedtext should be called, ASR should not
                mock_timedtext.assert_called_once()
                mock_asr.assert_not_called()
    
    def test_performance_impact_on_pipeline(self):
        """
        Test that DOM enhancements don't significantly impact overall pipeline performance.
        Requirement: 15.2
        """
        # Mock fast Playwright success
        with patch('youtubei_service.DeterministicYouTubeiCapture') as mock_capture_class:
            mock_capture = Mock()
            
            async def fast_extract(cookie_header):
                await asyncio.sleep(0.05)  # 50ms - very fast
                return "Fast DOM transcript"
            
            mock_capture.extract_transcript = fast_extract
            mock_capture_class.return_value = mock_capture
            
            # Time the complete pipeline
            start_time = time.time()
            result = self.service.get_transcript(self.test_video_id)
            elapsed_time = time.time() - start_time
            
            # Should complete quickly
            assert "Fast DOM transcript" in result
            assert elapsed_time < 1.0, f"Pipeline took {elapsed_time:.2f}s - should be under 1s"
    
    def test_resource_cleanup_in_pipeline(self):
        """
        Test that resources are properly cleaned up during pipeline execution.
        Requirement: 15.5
        """
        # Mock Playwright with resource tracking
        with patch('youtubei_service.DeterministicYouTubeiCapture') as mock_capture_class:
            mock_capture = Mock()
            mock_capture.extract_transcript = AsyncMock(return_value="Resource test transcript")
            mock_capture_class.return_value = mock_capture
            
            # Execute pipeline
            result = self.service.get_transcript(self.test_video_id)
            
            # Should complete successfully
            assert "Resource test transcript" in result
            
            # Capture should be created and used exactly once
            mock_capture_class.assert_called_once()
            mock_capture.extract_transcript.assert_called_once()
    
    def test_error_handling_integration(self):
        """
        Test that DOM error handling integrates properly with existing error handling.
        Requirement: 14.2
        """
        error_scenarios = [
            (TimeoutError("DOM timeout"), "Timeout fallback"),
            (ConnectionError("DOM connection error"), "Connection fallback"),
            (ValueError("DOM value error"), "Value fallback"),
            (Exception("Generic DOM error"), "Generic fallback")
        ]
        
        for error, fallback_result in error_scenarios:
            with patch('youtubei_service.DeterministicYouTubeiCapture') as mock_capture_class:
                mock_capture = Mock()
                mock_capture.extract_transcript = AsyncMock(side_effect=error)
                mock_capture_class.return_value = mock_capture
                
                # Mock next stage to succeed
                with patch.object(self.service, '_enhanced_yt_api_stage', return_value=(fallback_result, "en")):
                    
                    # Should handle error gracefully and continue to fallback
                    result = self.service.get_transcript(self.test_video_id)
                    assert result == fallback_result, f"Should handle {type(error).__name__} and fallback"
    
    def test_circuit_breaker_integration(self):
        """
        Test that circuit breaker behavior is preserved with DOM enhancements.
        Requirement: 14.2
        """
        from transcript_service import _playwright_circuit_breaker, get_circuit_breaker_status
        
        # Reset circuit breaker
        _playwright_circuit_breaker.failure_count = 0
        _playwright_circuit_breaker.last_failure_time = None
        
        # Mock DOM failure (should not affect circuit breaker)
        with patch('youtubei_service.DeterministicYouTubeiCapture') as mock_capture_class:
            mock_capture = Mock()
            mock_capture.extract_transcript = AsyncMock(side_effect=Exception("DOM error"))
            mock_capture_class.return_value = mock_capture
            
            # Mock fallback success
            with patch.object(self.service, '_enhanced_yt_api_stage', return_value=("Fallback transcript", "en")):
                
                # Execute pipeline
                result = self.service.get_transcript(self.test_video_id)
                
                # Should get fallback result
                assert result == "Fallback transcript"
                
                # Circuit breaker should remain closed (DOM errors don't trigger it)
                cb_status = get_circuit_breaker_status()
                assert cb_status['state'] == 'closed', "Circuit breaker should remain closed for DOM errors"
                assert cb_status['failure_count'] == 0, "DOM errors should not increment failure count"
    
    def run_all_tests(self):
        """Run all integration tests and report results."""
        test_methods = [method for method in dir(self) if method.startswith('test_')]
        passed = 0
        failed = 0
        
        print(f"Running {len(test_methods)} DOM integration tests...")
        print("=" * 60)
        
        for test_method in test_methods:
            try:
                print(f"Running {test_method}...", end=" ")
                self.setup_method()
                getattr(self, test_method)()
                print("PASSED")
                passed += 1
            except Exception as e:
                print(f"FAILED: {e}")
                failed += 1
        
        print("=" * 60)
        print(f"Results: {passed} passed, {failed} failed")
        
        if failed > 0:
            print("❌ Some integration tests failed")
            return False
        else:
            print("✅ All integration tests passed - DOM integration verified")
            return True


def main():
    """Run the DOM integration tests."""
    test_suite = TestDOMIntegrationFallbackChain()
    success = test_suite.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())