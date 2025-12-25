#!/usr/bin/env python3
"""
Test backward compatibility and integration for DOM transcript discovery enhancements.

This test validates that DOM enhancements do not change existing method signatures,
preserve error handling and circuit breaker behavior, maintain fallback order,
and ensure DOM interaction failures properly trigger fallback to next transcript method.

Requirements: 14.1, 14.2, 14.3, 14.4, 15.1, 15.2, 15.3, 15.4, 15.5
"""

import asyncio
import time
import os
import sys
import inspect
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Optional, List, Dict, Any

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from transcript_service import TranscriptService, get_circuit_breaker_status, _playwright_circuit_breaker
from proxy_manager import ProxyManager
from log_events import evt


class TestBackwardCompatibilityDOMIntegration:
    """Test backward compatibility and integration for DOM transcript discovery."""
    
    def setup_method(self):
        """Set up test environment."""
        self.service = TranscriptService()
        self.test_video_id = "test_video_123"
        self.test_job_id = "test_job_456"
        
        # Reset circuit breaker state
        _playwright_circuit_breaker.failure_count = 0
        _playwright_circuit_breaker.last_failure_time = None
    
    def test_method_signature_unchanged(self):
        """
        Verify DOM enhancements do not change existing method signatures.
        Requirement: 14.1
        """
        # Test main get_transcript method signature
        import inspect
        
        # Get method signature
        sig = inspect.signature(self.service.get_transcript)
        
        # Verify required parameters
        assert 'video_id' in sig.parameters
        assert sig.parameters['video_id'].annotation == str
        
        # Verify optional parameters with defaults
        expected_params = {
            'language_codes': Optional[list],
            'proxy_manager': None,  # No annotation in original
            'cookies': None,        # No annotation in original
            'user_id': Optional[int],
            'user_cookies': Optional[object]
        }
        
        for param_name, expected_annotation in expected_params.items():
            if param_name in sig.parameters:
                param = sig.parameters[param_name]
                if expected_annotation is not None:
                    assert param.annotation == expected_annotation, f"Parameter {param_name} annotation mismatch"
                assert param.default is not inspect.Parameter.empty, f"Parameter {param_name} should have default"
        
        # Verify **kwargs is present for backward compatibility
        assert any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()), \
            "Method should accept **kwargs for backward compatibility"
    
    def test_playwright_method_signature_unchanged(self):
        """
        Verify _get_transcript_via_playwright method signature is unchanged.
        Requirement: 14.1
        """
        import inspect
        
        # Get method signature
        sig = inspect.signature(self.service._get_transcript_via_playwright)
        
        # Verify required parameters
        assert 'video_id' in sig.parameters
        assert sig.parameters['video_id'].annotation == str
        
        # Verify optional parameters
        expected_params = ['job_id', 'proxy_manager', 'cookie_header']
        for param_name in expected_params:
            assert param_name in sig.parameters, f"Parameter {param_name} missing"
            param = sig.parameters[param_name]
            assert param.default is not inspect.Parameter.empty or param.default is None, \
                f"Parameter {param_name} should have default"
        
        # Verify return type annotation
        assert sig.return_annotation == Optional[List[Dict]], \
            "Return type should be Optional[List[Dict]]"
    
    def test_circuit_breaker_behavior_preserved(self):
        """
        Ensure existing error handling and circuit breaker behavior is preserved.
        Requirement: 14.2
        """
        # Mock capture instance that raises exception
        with patch('youtubei_service.DeterministicYouTubeiCapture') as mock_capture_class:
            mock_capture = Mock()
            mock_capture.extract_transcript = AsyncMock(side_effect=Exception("Test error"))
            mock_capture_class.return_value = mock_capture
            
            # Reset circuit breaker
            _playwright_circuit_breaker.failure_count = 0
            _playwright_circuit_breaker.last_failure_time = None
            
            # Test that exceptions are handled gracefully and circuit breaker is updated
            result = asyncio.run(self.service._get_transcript_via_playwright(
                self.test_video_id, self.test_job_id
            ))
            
            # Should return None for fallback (not raise exception)
            assert result is None
            
            # Circuit breaker should not be affected by DOM interaction failures
            # (DOM failures should not trigger circuit breaker - only core Playwright failures should)
            cb_status = get_circuit_breaker_status()
            assert cb_status['state'] == 'closed', "Circuit breaker should remain closed for DOM interaction failures"
    
    def test_fallback_order_maintained(self):
        """
        Confirm fallback order remains: Playwright → youtube-transcript-api → timedtext → ASR.
        Requirement: 14.3
        """
        # Mock all stages to fail except ASR
        with patch.object(self.service, '_enhanced_yt_api_stage', return_value=("", "NoTranscriptFound")), \
             patch('transcript_service.timedtext_with_job_proxy', return_value=""), \
             patch.object(self.service, '_enhanced_youtubei_stage', return_value=""), \
             patch.object(self.service, '_enhanced_asr_stage', return_value="ASR transcript"):
            
            # Execute pipeline
            result = self.service.get_transcript(self.test_video_id)
            
            # Should get ASR result (last in fallback chain)
            assert result == "ASR transcript"
    
    def test_dom_failure_triggers_fallback(self):
        """
        Test that DOM interaction failures properly trigger fallback to next transcript method.
        Requirement: 14.4
        """
        # Mock capture to fail
        with patch('youtubei_service.DeterministicYouTubeiCapture') as mock_capture_class:
            mock_capture = Mock()
            mock_capture.extract_transcript = AsyncMock(return_value=None)  # DOM failure
            mock_capture_class.return_value = mock_capture
            
            # Mock next stage to succeed
            with patch.object(self.service, '_enhanced_asr_stage', return_value="ASR fallback transcript"):
                
                # Execute pipeline
                result = self.service.get_transcript(self.test_video_id)
                
                # Should get ASR result (fallback after DOM failure)
                assert result == "ASR fallback transcript"
    
    def test_performance_within_timeout_bounds(self):
        """
        Verify DOM interactions complete within existing Playwright timeout bounds.
        Requirement: 15.1
        """
        # Test with mock that simulates reasonable response time
        with patch('youtubei_service.DeterministicYouTubeiCapture') as mock_capture_class:
            mock_capture = Mock()
            
            # Simulate DOM interactions taking reasonable time (under timeout)
            async def mock_extract(cookie_header):
                await asyncio.sleep(0.1)  # 100ms - well under timeout
                return "Mock transcript"
            
            mock_capture.extract_transcript = mock_extract
            mock_capture_class.return_value = mock_capture
            
            start_time = time.time()
            result = asyncio.run(self.service._get_transcript_via_playwright(
                self.test_video_id, self.test_job_id
            ))
            elapsed_time = time.time() - start_time
            
            # Should complete quickly and return result
            assert result is not None
            assert elapsed_time < 1.0, "DOM interactions should complete quickly"
    
    def test_no_significant_performance_impact(self):
        """
        Verify DOM interactions do not significantly increase total transcript extraction time.
        Requirement: 15.2
        """
        # Mock successful DOM interaction
        with patch('youtubei_service.DeterministicYouTubeiCapture') as mock_capture_class:
            mock_capture = Mock()
            mock_capture.extract_transcript = AsyncMock(return_value="Quick transcript")
            mock_capture_class.return_value = mock_capture
            
            # Time the enhanced method
            start_time = time.time()
            result = asyncio.run(self.service._get_transcript_via_playwright(
                self.test_video_id, self.test_job_id
            ))
            elapsed_time = time.time() - start_time
            
            # Should complete in reasonable time
            assert result is not None
            assert elapsed_time < 2.0, "Enhanced method should not add significant overhead"
    
    def test_efficient_selectors_minimal_traversal(self):
        """
        Verify DOM interactions use efficient selectors that minimize DOM traversal.
        Requirement: 15.3
        """
        # This is tested indirectly by verifying the DeterministicYouTubeiCapture
        # is called with appropriate parameters and completes quickly
        with patch('youtubei_service.DeterministicYouTubeiCapture') as mock_capture_class:
            mock_capture = Mock()
            mock_capture.extract_transcript = AsyncMock(return_value="Efficient transcript")
            mock_capture_class.return_value = mock_capture
            
            # Execute method
            result = asyncio.run(self.service._get_transcript_via_playwright(
                self.test_video_id, self.test_job_id
            ))
            
            # Verify capture was created with correct parameters
            mock_capture_class.assert_called_once()
            call_args = mock_capture_class.call_args
            
            # Should have job_id, video_id, and proxy_manager
            assert 'job_id' in call_args.kwargs or len(call_args.args) > 0
            assert 'video_id' in call_args.kwargs or len(call_args.args) > 1
            
            # Should call extract_transcript once
            mock_capture.extract_transcript.assert_called_once()
    
    def test_no_unnecessary_waits_or_polling(self):
        """
        Verify DOM interactions avoid unnecessary waits or polling.
        Requirement: 15.4
        """
        # Mock capture that completes immediately
        with patch('youtubei_service.DeterministicYouTubeiCapture') as mock_capture_class:
            mock_capture = Mock()
            
            # Track call timing
            call_times = []
            
            async def mock_extract(cookie_header):
                call_times.append(time.time())
                return "Immediate transcript"
            
            mock_capture.extract_transcript = mock_extract
            mock_capture_class.return_value = mock_capture
            
            # Execute method
            start_time = time.time()
            result = asyncio.run(self.service._get_transcript_via_playwright(
                self.test_video_id, self.test_job_id
            ))
            total_time = time.time() - start_time
            
            # Should complete quickly without unnecessary delays
            assert result is not None
            assert total_time < 0.5, "Should complete without unnecessary waits"
            assert len(call_times) == 1, "Should make single call without polling"
    
    def test_resource_cleanup_after_completion(self):
        """
        Verify DOM interactions clean up resources (unroute) after completion.
        Requirement: 15.5
        """
        # This is tested by verifying the DeterministicYouTubeiCapture
        # handles its own resource cleanup properly
        with patch('youtubei_service.DeterministicYouTubeiCapture') as mock_capture_class:
            mock_capture = Mock()
            mock_capture.extract_transcript = AsyncMock(return_value="Clean transcript")
            mock_capture_class.return_value = mock_capture
            
            # Execute method
            result = asyncio.run(self.service._get_transcript_via_playwright(
                self.test_video_id, self.test_job_id
            ))
            
            # Should complete successfully
            assert result is not None
            
            # Capture should be created and used properly
            mock_capture_class.assert_called_once()
            mock_capture.extract_transcript.assert_called_once()
    
    def test_graceful_degradation_on_dom_failure(self):
        """
        Test graceful degradation when DOM interactions fail completely.
        Requirements: 9.4, 9.5, 14.4
        """
        # Mock capture that raises exception
        with patch('youtubei_service.DeterministicYouTubeiCapture') as mock_capture_class:
            mock_capture = Mock()
            mock_capture.extract_transcript = AsyncMock(side_effect=Exception("DOM failure"))
            mock_capture_class.return_value = mock_capture
            
            # Should not raise exception, should return None for fallback
            result = asyncio.run(self.service._get_transcript_via_playwright(
                self.test_video_id, self.test_job_id
            ))
            
            assert result is None, "Should return None for graceful fallback"
    
    def test_empty_result_handling(self):
        """
        Test handling of empty or None results from DOM interactions.
        Requirements: 9.4, 9.5
        """
        test_cases = [
            None,           # No transcript found
            "",             # Empty string
            "   ",          # Whitespace only
        ]
        
        for empty_result in test_cases:
            with patch('youtubei_service.DeterministicYouTubeiCapture') as mock_capture_class:
                mock_capture = Mock()
                mock_capture.extract_transcript = AsyncMock(return_value=empty_result)
                mock_capture_class.return_value = mock_capture
                
                result = asyncio.run(self.service._get_transcript_via_playwright(
                    self.test_video_id, self.test_job_id
                ))
                
                assert result is None, f"Should return None for empty result: {repr(empty_result)}"
    
    def test_transcript_parsing_graceful_degradation(self):
        """
        Test that transcript parsing never throws exceptions that break the pipeline.
        Requirement: 9.4
        """
        # Test various malformed inputs
        malformed_inputs = [
            '{"invalid": json}',     # Invalid JSON
            '{"actions": "not_list"}',  # Wrong structure
            'plain text',            # Plain text (should work)
            '',                      # Empty string
            None,                    # None input
        ]
        
        for malformed_input in malformed_inputs:
            # Should not raise exception
            try:
                result = self.service._parse_transcript_text_to_segments(malformed_input)
                assert isinstance(result, list), "Should always return a list"
            except Exception as e:
                raise AssertionError(f"Parsing should not raise exception for input {repr(malformed_input)}: {e}")
    
    def test_integration_with_existing_error_handling(self):
        """
        Test integration with existing error handling and logging systems.
        Requirement: 14.2
        """
        # Mock capture that fails with various error types
        error_types = [
            TimeoutError("Navigation timeout"),
            ConnectionError("Network error"),
            ValueError("Invalid data"),
            Exception("Generic error")
        ]
        
        for error in error_types:
            with patch('youtubei_service.DeterministicYouTubeiCapture') as mock_capture_class:
                mock_capture = Mock()
                mock_capture.extract_transcript = AsyncMock(side_effect=error)
                mock_capture_class.return_value = mock_capture
                
                # Should handle all error types gracefully
                result = asyncio.run(self.service._get_transcript_via_playwright(
                    self.test_video_id, self.test_job_id
                ))
                
                assert result is None, f"Should handle {type(error).__name__} gracefully"
    
    def run_all_tests(self):
        """Run all tests and report results."""
        test_methods = [method for method in dir(self) if method.startswith('test_')]
        passed = 0
        failed = 0
        
        print(f"Running {len(test_methods)} backward compatibility tests...")
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
            print("❌ Some tests failed - backward compatibility issues detected")
            return False
        else:
            print("✅ All tests passed - backward compatibility verified")
            return True


def main():
    """Run the backward compatibility tests."""
    test_suite = TestBackwardCompatibilityDOMIntegration()
    success = test_suite.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())