#!/usr/bin/env python3
"""
MVP Testing for Container Deployment
Tests the four critical areas for container-based App Runner deployment.
"""

import os
import sys
import subprocess
import tempfile
import logging
import requests
import time
from unittest.mock import patch, MagicMock

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ContainerDeploymentTests:
    """MVP test suite for container deployment verification"""
    
    def __init__(self):
        self.test_results = []
        self.failed_tests = []
    
    def log_test_result(self, test_name, passed, message=""):
        """Log test result and track failures"""
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status}: {test_name} - {message}")
        self.test_results.append((test_name, passed, message))
        if not passed:
            self.failed_tests.append(test_name)
    
    def test_docker_build_smoke(self):
        """Test 1: Docker build smoke test (verify ffmpeg present in container)"""
        logger.info("=== Test 1: Docker Build Smoke Test ===")
        
        try:
            # Build the Docker image
            logger.info("Building Docker image...")
            build_result = subprocess.run(
                ["docker", "build", "-t", "tldw-test", "."],
                capture_output=True, text=True, timeout=300
            )
            
            if build_result.returncode != 0:
                self.log_test_result("Docker Build", False, f"Build failed: {build_result.stderr}")
                return False
            
            # Test ffmpeg availability in container
            logger.info("Testing ffmpeg availability in container...")
            ffmpeg_test = subprocess.run([
                "docker", "run", "--rm", "tldw-test",
                "sh", "-c", "which ffmpeg && ffmpeg -version | head -1"
            ], capture_output=True, text=True, timeout=30)
            
            if ffmpeg_test.returncode != 0:
                self.log_test_result("FFmpeg in Container", False, "ffmpeg not found or failed")
                return False
            
            # Test ffprobe availability
            ffprobe_test = subprocess.run([
                "docker", "run", "--rm", "tldw-test",
                "sh", "-c", "which ffprobe && ffprobe -version | head -1"
            ], capture_output=True, text=True, timeout=30)
            
            if ffprobe_test.returncode != 0:
                self.log_test_result("FFprobe in Container", False, "ffprobe not found or failed")
                return False
            
            # Test yt-dlp import
            ytdlp_test = subprocess.run([
                "docker", "run", "--rm", "tldw-test",
                "python", "-c", "import yt_dlp; print(f'yt-dlp {yt_dlp.version.__version__}')"
            ], capture_output=True, text=True, timeout=30)
            
            if ytdlp_test.returncode != 0:
                self.log_test_result("yt-dlp in Container", False, "yt-dlp import failed")
                return False
            
            self.log_test_result("Docker Build Smoke Test", True, "All dependencies verified in container")
            return True
            
        except subprocess.TimeoutExpired:
            self.log_test_result("Docker Build Smoke Test", False, "Test timed out")
            return False
        except Exception as e:
            self.log_test_result("Docker Build Smoke Test", False, f"Unexpected error: {e}")
            return False
    
    def test_wsgi_dependency_check(self):
        """Test 2: wsgi.py dependency check (passes/fails with ALLOW_MISSING_DEPS scenarios)"""
        logger.info("=== Test 2: WSGI Dependency Check ===")
        
        try:
            # Test with ALLOW_MISSING_DEPS=false (should fail if deps missing)
            logger.info("Testing ALLOW_MISSING_DEPS=false scenario...")
            
            # Mock missing ffmpeg
            with patch('shutil.which') as mock_which:
                mock_which.return_value = None  # Simulate missing binary
                
                # Set environment
                os.environ['ALLOW_MISSING_DEPS'] = 'false'
                
                # Import and test wsgi module
                try:
                    # This should raise RuntimeError due to missing deps
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("wsgi_test", "wsgi.py")
                    wsgi_module = importlib.util.module_from_spec(spec)
                    
                    # This should fail
                    spec.loader.exec_module(wsgi_module)
                    self.log_test_result("WSGI Strict Mode", False, "Should have failed with missing deps")
                    return False
                    
                except RuntimeError as e:
                    if "missing from PATH" in str(e):
                        self.log_test_result("WSGI Strict Mode", True, "Correctly failed with missing deps")
                    else:
                        self.log_test_result("WSGI Strict Mode", False, f"Wrong error: {e}")
                        return False
            
            # Test with ALLOW_MISSING_DEPS=true (should pass with warnings)
            logger.info("Testing ALLOW_MISSING_DEPS=true scenario...")
            
            with patch('shutil.which') as mock_which:
                mock_which.return_value = None  # Simulate missing binary
                
                # Set environment
                os.environ['ALLOW_MISSING_DEPS'] = 'true'
                
                try:
                    # This should pass with warnings
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("wsgi_test2", "wsgi.py")
                    wsgi_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(wsgi_module)
                    
                    self.log_test_result("WSGI Permissive Mode", True, "Correctly passed with missing deps")
                    
                except Exception as e:
                    self.log_test_result("WSGI Permissive Mode", False, f"Should not have failed: {e}")
                    return False
            
            return True
            
        except Exception as e:
            self.log_test_result("WSGI Dependency Check", False, f"Test error: {e}")
            return False
        finally:
            # Clean up environment
            os.environ.pop('ALLOW_MISSING_DEPS', None)
    
    def test_ytdlp_ffmpeg_integration(self):
        """Test 3: yt-dlp integration with --ffmpeg-location parameter"""
        logger.info("=== Test 3: yt-dlp FFmpeg Integration ===")
        
        try:
            # Set up test environment
            os.environ['FFMPEG_LOCATION'] = '/usr/bin'
            
            # Import transcript service
            from transcript_service import TranscriptService
            
            # Create service instance
            service = TranscriptService()
            
            # Mock the yt-dlp download to test configuration
            with patch('yt_dlp.YoutubeDL') as mock_ytdl:
                mock_instance = MagicMock()
                mock_ytdl.return_value.__enter__.return_value = mock_instance
                
                # Mock session for testing
                mock_session = MagicMock()
                mock_session.proxy_url = "http://test-proxy:8080"
                mock_session.session_id = "test-session-123"
                
                try:
                    # This should configure yt-dlp with ffmpeg_location
                    service._attempt_ytdlp_download("test_video_id", mock_session, attempt=1)
                except Exception:
                    pass  # We expect this to fail, we're just testing configuration
                
                # Verify yt-dlp was called with correct configuration
                if mock_ytdl.called:
                    call_args = mock_ytdl.call_args[0][0]  # First positional argument (ydl_opts)
                    
                    if 'ffmpeg_location' in call_args:
                        ffmpeg_location = call_args['ffmpeg_location']
                        if ffmpeg_location == '/usr/bin':
                            self.log_test_result("yt-dlp FFmpeg Location", True, f"Correct ffmpeg_location: {ffmpeg_location}")
                        else:
                            self.log_test_result("yt-dlp FFmpeg Location", False, f"Wrong ffmpeg_location: {ffmpeg_location}")
                            return False
                    else:
                        self.log_test_result("yt-dlp FFmpeg Location", False, "ffmpeg_location not set in ydl_opts")
                        return False
                    
                    # Check socket timeout
                    if call_args.get('socket_timeout') == 15:
                        self.log_test_result("yt-dlp Socket Timeout", True, "Correct socket_timeout: 15")
                    else:
                        self.log_test_result("yt-dlp Socket Timeout", False, f"Wrong socket_timeout: {call_args.get('socket_timeout')}")
                        return False
                    
                else:
                    self.log_test_result("yt-dlp Integration", False, "yt-dlp was not called")
                    return False
            
            return True
            
        except Exception as e:
            self.log_test_result("yt-dlp FFmpeg Integration", False, f"Test error: {e}")
            return False
        finally:
            # Clean up environment
            os.environ.pop('FFMPEG_LOCATION', None)
    
    def test_health_endpoints(self):
        """Test 4: /health and /healthz endpoints returning 200 with dependency status"""
        logger.info("=== Test 4: Health Endpoints Test ===")
        
        try:
            # Start the Flask app in test mode
            from app import app
            app.config['TESTING'] = True
            
            with app.test_client() as client:
                # Test /health endpoint
                logger.info("Testing /health endpoint...")
                health_response = client.get('/health')
                
                if health_response.status_code != 200:
                    self.log_test_result("Health Endpoint Status", False, f"Status: {health_response.status_code}")
                    return False
                
                # Parse response
                health_data = health_response.get_json()
                if not health_data:
                    self.log_test_result("Health Endpoint Data", False, "No JSON response")
                    return False
                
                # Check required fields
                required_fields = ['status', 'dependencies']
                for field in required_fields:
                    if field not in health_data:
                        self.log_test_result("Health Endpoint Fields", False, f"Missing field: {field}")
                        return False
                
                # Check dependencies structure
                deps = health_data.get('dependencies', {})
                required_deps = ['ffmpeg', 'ffprobe', 'yt_dlp']
                for dep in required_deps:
                    if dep not in deps:
                        self.log_test_result("Health Dependencies", False, f"Missing dependency: {dep}")
                        return False
                
                self.log_test_result("Health Endpoint", True, "All checks passed")
                
                # Test /healthz endpoint
                logger.info("Testing /healthz endpoint...")
                healthz_response = client.get('/healthz')
                
                if healthz_response.status_code != 200:
                    self.log_test_result("Healthz Endpoint", False, f"Status: {healthz_response.status_code}")
                    return False
                
                self.log_test_result("Healthz Endpoint", True, "Returns 200")
                
            return True
            
        except Exception as e:
            self.log_test_result("Health Endpoints Test", False, f"Test error: {e}")
            return False
    
    def run_all_tests(self):
        """Run all MVP tests and return overall result"""
        logger.info("🚀 Starting Container Deployment MVP Tests")
        logger.info("=" * 60)
        
        tests = [
            self.test_docker_build_smoke,
            self.test_wsgi_dependency_check,
            self.test_ytdlp_ffmpeg_integration,
            self.test_health_endpoints
        ]
        
        passed_tests = 0
        total_tests = len(tests)
        
        for test_func in tests:
            try:
                if test_func():
                    passed_tests += 1
            except Exception as e:
                logger.error(f"Test {test_func.__name__} crashed: {e}")
        
        # Summary
        logger.info("=" * 60)
        logger.info(f"🏁 Test Summary: {passed_tests}/{total_tests} tests passed")
        
        if self.failed_tests:
            logger.error(f"❌ Failed tests: {', '.join(self.failed_tests)}")
            return False
        else:
            logger.info("✅ All MVP tests passed!")
            return True

def main():
    """Main test runner"""
    tester = ContainerDeploymentTests()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()