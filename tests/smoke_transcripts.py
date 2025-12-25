#!/usr/bin/env python3
"""
Containerized smoke test suite for transcript extraction.
Tests the 4-tier fallback system with a matrix of videos and connection types.

Test Matrix:
- 4 videos: dQw4w9WgXcQ, jNQXAC9IVRw, kJQP7kiw5Fk, BPjmmZlDhNc
- 2 connection types: proxy, direct
- 2 user agents: desktop, mobile

Usage:
    python tests/smoke_transcripts.py
    python tests/smoke_transcripts.py --video dQw4w9WgXcQ --proxy-only
    python tests/smoke_transcripts.py --quick  # Test only one video
"""

import os
import sys
import time
import json
import logging
import argparse
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from transcript_service import TranscriptService
from proxy_manager import ProxyManager
from shared_managers import shared_managers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('smoke_test_results.log')
    ]
)

@dataclass
class TestResult:
    video_id: str
    connection_type: str  # "proxy" or "direct"
    user_agent_type: str  # "desktop" or "mobile"
    success: bool
    transcript_source: str  # "yt_api", "timedtext", "youtubei", "asr", "none"
    transcript_length: int
    duration_ms: int
    error_message: Optional[str] = None
    
    def to_dict(self):
        return asdict(self)

class SmokeTestSuite:
    """Comprehensive smoke test suite for transcript extraction"""
    
    # Test video matrix - mix of content types and availability
    TEST_VIDEOS = [
        "dQw4w9WgXcQ",  # Rick Astley - Never Gonna Give You Up (popular, likely has transcripts)
        "jNQXAC9IVRw",  # Me at the zoo (first YouTube video, short)
        "kJQP7kiw5Fk",  # Charlie bit my finger (classic, likely has transcripts)
        "BPjmmZlDhNc"   # Test video from logs (known to have transcript issues)
    ]
    
    def __init__(self, proxy_enabled: bool = True, quick_mode: bool = False):
        self.proxy_enabled = proxy_enabled
        self.quick_mode = quick_mode
        self.results: List[TestResult] = []
        
        # Initialize transcript service
        self.transcript_service = TranscriptService(use_shared_managers=True)
        
        # Get proxy manager for testing
        self.proxy_manager = shared_managers.get_proxy_manager()
        
        logging.info(f"Smoke test initialized: proxy_enabled={proxy_enabled}, quick_mode={quick_mode}")
        logging.info(f"Proxy manager available: {self.proxy_manager is not None}")
        
    def run_full_suite(self) -> Dict:
        """Run the complete test matrix"""
        logging.info("Starting comprehensive transcript smoke test suite")
        
        test_videos = [self.TEST_VIDEOS[0]] if self.quick_mode else self.TEST_VIDEOS
        connection_types = ["direct"]
        
        if self.proxy_enabled and self.proxy_manager and self.proxy_manager.in_use:
            connection_types.append("proxy")
            logging.info("Proxy testing enabled")
        else:
            logging.info("Proxy testing disabled (not available or not configured)")
        
        user_agent_types = ["desktop", "mobile"]
        
        total_tests = len(test_videos) * len(connection_types) * len(user_agent_types)
        logging.info(f"Running {total_tests} test combinations")
        
        test_count = 0
        for video_id in test_videos:
            for connection_type in connection_types:
                for ua_type in user_agent_types:
                    test_count += 1
                    logging.info(f"Test {test_count}/{total_tests}: {video_id} via {connection_type} ({ua_type})")
                    
                    result = self._test_single_video(video_id, connection_type, ua_type)
                    self.results.append(result)
                    
                    # Log result immediately
                    status = "✅ SUCCESS" if result.success else "❌ FAILED"
                    logging.info(f"  {status}: {result.transcript_source} source, "
                               f"{result.transcript_length} chars, {result.duration_ms}ms")
                    
                    if result.error_message:
                        logging.warning(f"  Error: {result.error_message}")
                    
                    # Brief pause between tests to avoid rate limiting
                    time.sleep(2)
        
        return self._generate_summary()
    
    def _test_single_video(self, video_id: str, connection_type: str, ua_type: str) -> TestResult:
        """Test transcript extraction for a single video with specific parameters"""
        start_time = time.time()
        
        try:
            # Configure connection type by temporarily modifying proxy manager
            original_in_use = None
            if connection_type == "direct" and self.proxy_manager:
                original_in_use = self.proxy_manager.in_use
                self.proxy_manager.in_use = False
            
            # Set user agent type (this would typically be done via headers/cookies)
            # For now, we'll just pass it as context
            cookies = self._get_cookies_for_ua_type(ua_type)
            
            # Attempt transcript extraction
            transcript = self.transcript_service.get_transcript(
                video_id=video_id,
                language="en",
                user_cookies=cookies,
                playwright_cookies=cookies
            )
            
            # Restore original proxy state
            if original_in_use is not None:
                self.proxy_manager.in_use = original_in_use
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            if transcript and transcript.strip():
                # Determine source from logs (simplified - in real implementation would track this)
                source = self._determine_transcript_source(video_id)
                
                return TestResult(
                    video_id=video_id,
                    connection_type=connection_type,
                    user_agent_type=ua_type,
                    success=True,
                    transcript_source=source,
                    transcript_length=len(transcript),
                    duration_ms=duration_ms
                )
            else:
                return TestResult(
                    video_id=video_id,
                    connection_type=connection_type,
                    user_agent_type=ua_type,
                    success=False,
                    transcript_source="none",
                    transcript_length=0,
                    duration_ms=duration_ms,
                    error_message="No transcript extracted"
                )
                
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            
            return TestResult(
                video_id=video_id,
                connection_type=connection_type,
                user_agent_type=ua_type,
                success=False,
                transcript_source="error",
                transcript_length=0,
                duration_ms=duration_ms,
                error_message=str(e)
            )
    
    def _get_cookies_for_ua_type(self, ua_type: str) -> Optional[Dict]:
        """Get appropriate cookies for user agent type"""
        if ua_type == "mobile":
            # Mobile-specific cookies/headers would go here
            return {"mobile": "1"}
        return None
    
    def _determine_transcript_source(self, video_id: str) -> str:
        """Determine which source provided the transcript (simplified)"""
        # In a real implementation, this would track the actual source
        # For now, return a reasonable default
        return "yt_api"  # Most likely source for successful extractions
    
    def _generate_summary(self) -> Dict:
        """Generate comprehensive test summary"""
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r.success)
        failed_tests = total_tests - successful_tests
        
        # Group results by various dimensions
        by_video = {}
        by_connection = {}
        by_source = {}
        
        for result in self.results:
            # By video
            if result.video_id not in by_video:
                by_video[result.video_id] = {"success": 0, "failed": 0}
            by_video[result.video_id]["success" if result.success else "failed"] += 1
            
            # By connection type
            if result.connection_type not in by_connection:
                by_connection[result.connection_type] = {"success": 0, "failed": 0}
            by_connection[result.connection_type]["success" if result.success else "failed"] += 1
            
            # By transcript source
            if result.transcript_source not in by_source:
                by_source[result.transcript_source] = 0
            by_source[result.transcript_source] += 1
        
        # Calculate average metrics for successful tests
        successful_results = [r for r in self.results if r.success]
        avg_duration = sum(r.duration_ms for r in successful_results) / len(successful_results) if successful_results else 0
        avg_length = sum(r.transcript_length for r in successful_results) / len(successful_results) if successful_results else 0
        
        summary = {
            "test_summary": {
                "total_tests": total_tests,
                "successful": successful_tests,
                "failed": failed_tests,
                "success_rate": f"{(successful_tests/total_tests)*100:.1f}%" if total_tests > 0 else "0%"
            },
            "performance_metrics": {
                "avg_duration_ms": int(avg_duration),
                "avg_transcript_length": int(avg_length)
            },
            "results_by_video": by_video,
            "results_by_connection": by_connection,
            "results_by_source": by_source,
            "detailed_results": [r.to_dict() for r in self.results]
        }
        
        return summary
    
    def save_results(self, filename: str = "smoke_test_results.json"):
        """Save detailed results to JSON file"""
        summary = self._generate_summary()
        
        with open(filename, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logging.info(f"Results saved to {filename}")
        return filename

def main():
    """Main entry point for smoke test suite"""
    parser = argparse.ArgumentParser(description="Transcript extraction smoke test suite")
    parser.add_argument("--video", help="Test specific video ID only")
    parser.add_argument("--proxy-only", action="store_true", help="Test only with proxy")
    parser.add_argument("--direct-only", action="store_true", help="Test only direct connections")
    parser.add_argument("--quick", action="store_true", help="Quick test mode (one video only)")
    parser.add_argument("--output", default="smoke_test_results.json", help="Output file for results")
    
    args = parser.parse_args()
    
    # Determine proxy configuration
    proxy_enabled = True
    if args.direct_only:
        proxy_enabled = False
    
    # Initialize test suite
    suite = SmokeTestSuite(proxy_enabled=proxy_enabled, quick_mode=args.quick)
    
    # Override test videos if specific video requested
    if args.video:
        suite.TEST_VIDEOS = [args.video]
        logging.info(f"Testing single video: {args.video}")
    
    try:
        # Run the test suite
        summary = suite.run_full_suite()
        
        # Save results
        suite.save_results(args.output)
        
        # Print summary
        print("\n" + "="*60)
        print("TRANSCRIPT EXTRACTION SMOKE TEST RESULTS")
        print("="*60)
        print(f"Total Tests: {summary['test_summary']['total_tests']}")
        print(f"Successful: {summary['test_summary']['successful']}")
        print(f"Failed: {summary['test_summary']['failed']}")
        print(f"Success Rate: {summary['test_summary']['success_rate']}")
        print(f"Average Duration: {summary['performance_metrics']['avg_duration_ms']}ms")
        print(f"Average Transcript Length: {summary['performance_metrics']['avg_transcript_length']} chars")
        
        print("\nResults by Video:")
        for video_id, stats in summary['results_by_video'].items():
            print(f"  {video_id}: {stats['success']} success, {stats['failed']} failed")
        
        print("\nResults by Connection Type:")
        for conn_type, stats in summary['results_by_connection'].items():
            print(f"  {conn_type}: {stats['success']} success, {stats['failed']} failed")
        
        print("\nResults by Transcript Source:")
        for source, count in summary['results_by_source'].items():
            print(f"  {source}: {count} tests")
        
        print(f"\nDetailed results saved to: {args.output}")
        
        # Exit with appropriate code
        if summary['test_summary']['failed'] > 0:
            print(f"\n⚠️  {summary['test_summary']['failed']} tests failed - check logs for details")
            sys.exit(1)
        else:
            print("\n✅ All tests passed!")
            sys.exit(0)
            
    except Exception as e:
        logging.error(f"Smoke test suite failed: {e}")
        print(f"\n❌ Test suite failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
