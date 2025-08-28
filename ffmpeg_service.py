"""
Enhanced FFmpeg service with hardening and requests streaming fallback.

This module provides:
- CRLF-formatted headers for FFmpeg
- Both environment proxy variables and -http_proxy usage
- Comprehensive reconnect flags for network resilience
- WAV output configuration (mono 16kHz)
- Stderr capture and masking
- Requests streaming fallback for persistent FFmpeg failures
"""

import os
import subprocess
import tempfile
import time
import logging
import json
from typing import Optional, Dict, List, Tuple
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from logging_setup import get_logger
from log_events import evt

logger = get_logger(__name__)

# FFmpeg configuration
FFMPEG_TIMEOUT = 120  # seconds
FFMPEG_MAX_RETRIES = 2
REQUESTS_CHUNK_SIZE = 8192  # bytes
REQUESTS_TIMEOUT = 180  # seconds

# User agent for requests
FFMPEG_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)


def _mask_url_for_logging(url: str) -> str:
    """
    Mask sensitive query parameters in URLs for logging.
    
    Args:
        url: URL to mask
        
    Returns:
        URL with sensitive parameters masked
    """
    try:
        parsed = urlparse(url)
        if not parsed.query:
            return url
        
        # Mask the entire query string for googlevideo URLs
        if 'googlevideo.com' in parsed.netloc.lower():
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?***MASKED_GOOGLEVIDEO_PARAMS***"
        
        # For other URLs, mask specific sensitive parameters
        from urllib.parse import parse_qs, urlencode, urlunparse
        params = parse_qs(parsed.query, keep_blank_values=True)
        
        sensitive_params = {'key', 'token', 'auth', 'session', 'sig', 'signature', 'expire', 'id'}
        masked_params = {}
        
        for key, values in params.items():
            if key.lower() in sensitive_params:
                masked_params[key] = ['***MASKED***'] * len(values)
            else:
                masked_params[key] = values
        
        masked_query = urlencode(masked_params, doseq=True)
        masked_parsed = parsed._replace(query=masked_query)
        
        return urlunparse(masked_parsed)
        
    except Exception:
        # Fallback: mask everything after the domain
        try:
            parsed = urlparse(url)
            return f"{parsed.scheme}://{parsed.netloc}/***MASKED_PATH_AND_PARAMS***"
        except:
            return "***MASKED_URL***"


def _mask_cookie_header(cookie_header: str) -> str:
    """
    Mask cookie values for logging while preserving structure.
    
    Args:
        cookie_header: Cookie header string
        
    Returns:
        Cookie header with values masked
    """
    if not cookie_header:
        return ""
    
    try:
        masked_pairs = []
        for pair in cookie_header.split("; "):
            if "=" in pair:
                name, _ = pair.split("=", 1)
                masked_pairs.append(f"{name}=***MASKED***")
            else:
                masked_pairs.append(pair)
        
        return "; ".join(masked_pairs)
        
    except Exception:
        return "***MASKED_COOKIES***"


def _build_ffmpeg_headers(cookies: Optional[str] = None) -> str:
    """
    Build FFmpeg headers string with proper CRLF formatting.
    
    Args:
        cookies: Cookie header string (optional)
        
    Returns:
        CRLF-joined header string with trailing CRLF
    """
    headers = [
        f"User-Agent: {FFMPEG_USER_AGENT}",
        "Accept: */*",
        "Accept-Language: en-US,en;q=0.9",
        "Origin: https://www.youtube.com",
        "Referer: https://www.youtube.com/"
    ]
    
    if cookies:
        headers.append(f"Cookie: {cookies}")
    
    # Join with CRLF and ensure trailing CRLF
    headers_str = "\r\n".join(headers) + "\r\n"
    
    return headers_str


def _extract_stderr_lines(stderr_bytes: Optional[bytes], max_lines: int = 2) -> str:
    """
    Extract first N lines from stderr output for logging.
    
    Args:
        stderr_bytes: Raw stderr bytes from subprocess
        max_lines: Maximum number of lines to extract
        
    Returns:
        String containing first N lines of stderr, masked for security
    """
    if not stderr_bytes:
        return ""
    
    try:
        stderr_text = stderr_bytes.decode('utf-8', errors='replace')
        lines = stderr_text.strip().split('\n')
        
        # Take first N lines
        head_lines = lines[:max_lines] if len(lines) > max_lines else lines
        
        # Mask URLs and sensitive information in each line
        masked_lines = []
        for line in head_lines:
            # Mask URLs
            if 'http' in line.lower():
                # Simple URL masking - replace anything that looks like a URL
                import re
                line = re.sub(r'https?://[^\s]+', '***MASKED_URL***', line)
            
            # Mask cookie-like patterns
            if 'cookie' in line.lower():
                line = re.sub(r'cookie[=:][^\s;]+', 'cookie=***MASKED***', line, flags=re.IGNORECASE)
            
            masked_lines.append(line)
        
        return '\n'.join(masked_lines)
        
    except Exception as e:
        return f"stderr_decode_error: {str(e)}"


def _classify_ffmpeg_error(stderr_text: str, returncode: int) -> str:
    """
    Classify FFmpeg error for better diagnostics.
    
    Args:
        stderr_text: FFmpeg stderr output
        returncode: Process return code
        
    Returns:
        Error classification string
    """
    if not stderr_text:
        return f"exit_code_{returncode}"
    
    stderr_lower = stderr_text.lower()
    
    # Network/HTTP errors
    if any(pattern in stderr_lower for pattern in [
        'http error 403', '403 forbidden', 'server returned 403',
        'http error 404', '404 not found', 'server returned 404',
        'http error 429', '429 too many requests', 'server returned 429',
        'connection refused', 'connection reset', 'connection timeout',
        'network is unreachable', 'no route to host'
    ]):
        return "network_error"
    
    # TLS/SSL errors
    if any(pattern in stderr_lower for pattern in [
        'ssl', 'tls', 'certificate', 'handshake', 'protocol error'
    ]):
        return "tls_error"
    
    # Format/codec errors
    if any(pattern in stderr_lower for pattern in [
        'invalid data found', 'could not find codec', 'unknown format',
        'invalid argument', 'not supported'
    ]):
        return "format_error"
    
    # EOF/truncation errors
    if any(pattern in stderr_lower for pattern in [
        'premature eof', 'end of file', 'truncated', 'incomplete'
    ]):
        return "eof_error"
    
    # Generic error with return code
    return f"ffmpeg_error_{returncode}"


class FFmpegService:
    """
    Enhanced FFmpeg service with hardening and fallback capabilities.
    """
    
    def __init__(self, job_id: str, proxy_manager=None):
        """
        Initialize FFmpeg service.
        
        Args:
            job_id: Job identifier for sticky proxy session
            proxy_manager: ProxyManager instance for job-scoped sessions
        """
        self.job_id = job_id
        self.proxy_manager = proxy_manager
        
        # Get job-scoped proxy configuration
        self.proxy_env = {}
        self.proxy_url = None
        
        if proxy_manager and proxy_manager.in_use:
            try:
                self.proxy_env = proxy_manager.proxy_env_for_job(job_id)
                # Also get proxy URL for -http_proxy flag
                proxy_dict = proxy_manager.proxy_dict_for_job(job_id, "requests")
                if proxy_dict:
                    self.proxy_url = proxy_dict.get("https") or proxy_dict.get("http")
            except Exception as e:
                logger.warning(f"Failed to get job proxy for FFmpeg: {e}")
        
        # Check ENFORCE_PROXY_ALL compliance
        self.enforce_proxy = os.getenv("ENFORCE_PROXY_ALL", "0") in ("1", "true", "yes")
        if self.enforce_proxy and not (self.proxy_env or self.proxy_url):
            logger.error(f"ENFORCE_PROXY_ALL=1 but no proxy available for FFmpeg job {job_id}")
    
    def extract_audio_to_wav(
        self,
        audio_url: str,
        output_path: str,
        cookies: Optional[str] = None
    ) -> Tuple[bool, int, str]:
        """
        Extract audio from URL to WAV file using FFmpeg with comprehensive hardening.
        
        Args:
            audio_url: URL of audio stream
            output_path: Path where WAV file should be saved
            cookies: Cookie header string (optional)
            
        Returns:
            Tuple of (success, returncode, error_classification)
        """
        # Check proxy enforcement
        if self.enforce_proxy and not (self.proxy_env or self.proxy_url):
            evt("ffmpeg_blocked", reason="enforce_proxy_no_proxy", job_id=self.job_id)
            return False, -1, "proxy_enforcement_error"
        
        # Log attempt start
        masked_url = _mask_url_for_logging(audio_url)
        masked_cookies = _mask_cookie_header(cookies) if cookies else None
        
        evt("ffmpeg_attempt",
            job_id=self.job_id,
            url=masked_url,
            has_cookies=bool(cookies),
            has_proxy=bool(self.proxy_env or self.proxy_url))
        
        # Try FFmpeg extraction with retries
        for attempt in range(1, FFMPEG_MAX_RETRIES + 1):
            success, returncode, error_classification = self._ffmpeg_extract_attempt(
                audio_url, output_path, cookies, attempt
            )
            
            if success:
                return True, returncode, "success"
            
            # Log failed attempt
            evt("ffmpeg_attempt_failed",
                job_id=self.job_id,
                attempt=attempt,
                returncode=returncode,
                error_classification=error_classification)
            
            # Don't retry on certain error types
            if error_classification in ["format_error", "proxy_enforcement_error"]:
                break
            
            # Short delay before retry
            if attempt < FFMPEG_MAX_RETRIES:
                time.sleep(1)
        
        # All FFmpeg attempts failed - try requests streaming fallback
        evt("ffmpeg_exhausted", job_id=self.job_id, attempts=FFMPEG_MAX_RETRIES)
        
        try:
            if self._requests_streaming_fallback(audio_url, output_path, cookies):
                evt("requests_fallback_success", job_id=self.job_id)
                return True, 0, "requests_fallback_success"
            else:
                evt("requests_fallback_failed", job_id=self.job_id)
                return False, -1, "all_methods_failed"
        except Exception as e:
            evt("requests_fallback_error", job_id=self.job_id, error=str(e))
            return False, -1, "requests_fallback_error"
    
    def _ffmpeg_extract_attempt(
        self,
        audio_url: str,
        output_path: str,
        cookies: Optional[str],
        attempt: int
    ) -> Tuple[bool, int, str]:
        """
        Single FFmpeg extraction attempt.
        
        Args:
            audio_url: URL of audio stream
            output_path: Path where WAV file should be saved
            cookies: Cookie header string (optional)
            attempt: Attempt number (for logging)
            
        Returns:
            Tuple of (success, returncode, error_classification)
        """
        start_time = time.time()
        
        try:
            # Build headers with proper CRLF formatting
            headers_str = _build_ffmpeg_headers(cookies)
            
            # Build FFmpeg command
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output file
                "-loglevel", "error",  # Only show errors
                "-headers", headers_str,  # CRLF-formatted headers
                # Network resilience flags
                "-rw_timeout", "60000000",  # 60 second read/write timeout (microseconds)
                "-reconnect", "1",
                "-reconnect_streamed", "1", 
                "-reconnect_on_network_error", "1",
                "-reconnect_at_eof", "1",
                "-max_reload", "10",
                # Input format tolerance
                "-analyzeduration", "10M",
                "-probesize", "50M",
                "-i", audio_url,
                # WAV output configuration (mono 16kHz)
                "-vn",  # No video
                "-ac", "1",  # Mono
                "-ar", "16000",  # 16kHz sample rate
                "-acodec", "pcm_s16le",  # PCM 16-bit little-endian
                "-f", "wav",  # WAV format
                # Error resilience
                "-err_detect", "ignore_err",
                "-fflags", "+genpts",
                output_path
            ]
            
            # Add proxy flag if available
            if self.proxy_url:
                cmd.insert(-1, "-http_proxy")  # Insert before output path
                cmd.insert(-1, self.proxy_url)
            
            # Prepare environment
            env = os.environ.copy()
            if self.proxy_env:
                env.update(self.proxy_env)
            
            # Log command (masked)
            masked_cmd = self._mask_ffmpeg_command(cmd)
            evt("ffmpeg_command",
                job_id=self.job_id,
                attempt=attempt,
                command_preview=masked_cmd[:5],  # First 5 args only
                has_proxy_flag=bool(self.proxy_url),
                has_proxy_env=bool(self.proxy_env))
            
            # Execute FFmpeg
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=FFMPEG_TIMEOUT,
                env=env,
                check=False  # Don't raise on non-zero exit
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Extract stderr for logging
            stderr_head = _extract_stderr_lines(result.stderr, max_lines=2)
            error_classification = _classify_ffmpeg_error(stderr_head, result.returncode)
            
            # Log result
            evt("ffmpeg_result",
                job_id=self.job_id,
                attempt=attempt,
                returncode=result.returncode,
                duration_ms=duration_ms,
                stderr_head=stderr_head,
                error_classification=error_classification)
            
            # Check if output file was created successfully
            if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                file_size = os.path.getsize(output_path)
                
                # Reject tiny downloads (< 1MB) as they're likely corrupted or HTML error pages
                MIN_FILE_SIZE = 1024 * 1024  # 1MB
                if file_size < MIN_FILE_SIZE:
                    evt("ffmpeg_tiny_file_rejected",
                        job_id=self.job_id,
                        attempt=attempt,
                        file_size=file_size,
                        min_size=MIN_FILE_SIZE)
                    
                    # Clean up the tiny file
                    try:
                        os.unlink(output_path)
                    except:
                        pass
                    
                    return False, result.returncode, "tiny_file_rejected"
                
                # Validate audio file with ffprobe before declaring success
                if self._validate_audio_with_ffprobe(output_path):
                    evt("ffmpeg_success",
                        job_id=self.job_id,
                        attempt=attempt,
                        duration_ms=duration_ms,
                        output_size=file_size)
                    return True, result.returncode, "success"
                else:
                    evt("ffmpeg_invalid_audio",
                        job_id=self.job_id,
                        attempt=attempt,
                        file_size=file_size)
                    
                    # Clean up the invalid file
                    try:
                        os.unlink(output_path)
                    except:
                        pass
                    
                    return False, result.returncode, "invalid_audio_format"
            else:
                return False, result.returncode, error_classification
                
        except subprocess.TimeoutExpired as e:
            duration_ms = int((time.time() - start_time) * 1000)
            stderr_head = _extract_stderr_lines(e.stderr, max_lines=2) if e.stderr else ""
            
            evt("ffmpeg_timeout",
                job_id=self.job_id,
                attempt=attempt,
                duration_ms=duration_ms,
                timeout_seconds=FFMPEG_TIMEOUT,
                stderr_head=stderr_head)
            
            return False, -1, "timeout"
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            
            evt("ffmpeg_exception",
                job_id=self.job_id,
                attempt=attempt,
                duration_ms=duration_ms,
                error_type=type(e).__name__,
                error_detail=str(e))
            
            return False, -1, f"exception_{type(e).__name__}"
    
    def _validate_audio_with_ffprobe(self, audio_path: str) -> bool:
        """
        Validate audio file with ffprobe before sending to Deepgram.
        
        Args:
            audio_path: Path to audio file to validate
            
        Returns:
            True if audio file is valid, False otherwise
        """
        try:
            # Use ffprobe to validate the audio file
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                audio_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=10,
                check=False
            )
            
            if result.returncode != 0:
                evt("ffprobe_validation_failed",
                    job_id=self.job_id,
                    returncode=result.returncode,
                    stderr=result.stderr.decode('utf-8', errors='replace')[:200] if result.stderr else "")
                return False
            
            # Parse ffprobe output
            try:
                probe_data = json.loads(result.stdout.decode('utf-8'))
                
                # Check if we have format information
                format_info = probe_data.get('format', {})
                if not format_info:
                    evt("ffprobe_no_format_info", job_id=self.job_id)
                    return False
                
                # Check duration - should be > 0
                duration = float(format_info.get('duration', 0))
                if duration <= 0:
                    evt("ffprobe_zero_duration", job_id=self.job_id, duration=duration)
                    return False
                
                # Check if we have audio streams
                streams = probe_data.get('streams', [])
                audio_streams = [s for s in streams if s.get('codec_type') == 'audio']
                
                if not audio_streams:
                    evt("ffprobe_no_audio_streams", job_id=self.job_id, total_streams=len(streams))
                    return False
                
                # Validate first audio stream
                audio_stream = audio_streams[0]
                codec_name = audio_stream.get('codec_name', '')
                sample_rate = audio_stream.get('sample_rate', '')
                channels = audio_stream.get('channels', 0)
                
                # For WAV files, expect PCM codec
                if codec_name not in ['pcm_s16le', 'pcm_s16be', 'pcm_s24le', 'pcm_s24be', 'pcm_s32le', 'pcm_s32be']:
                    evt("ffprobe_unexpected_codec",
                        job_id=self.job_id,
                        codec_name=codec_name,
                        expected="pcm_*")
                    return False
                
                # Check sample rate (should be 16000 for our use case)
                if sample_rate != '16000':
                    evt("ffprobe_unexpected_sample_rate",
                        job_id=self.job_id,
                        sample_rate=sample_rate,
                        expected="16000")
                    # Don't fail on sample rate mismatch, just log it
                
                # Check channels (should be 1 for mono)
                if channels != 1:
                    evt("ffprobe_unexpected_channels",
                        job_id=self.job_id,
                        channels=channels,
                        expected=1)
                    # Don't fail on channel mismatch, just log it
                
                evt("ffprobe_validation_success",
                    job_id=self.job_id,
                    duration=duration,
                    codec_name=codec_name,
                    sample_rate=sample_rate,
                    channels=channels)
                
                return True
                
            except (json.JSONDecodeError, KeyError, ValueError) as parse_error:
                evt("ffprobe_parse_error",
                    job_id=self.job_id,
                    error=str(parse_error)[:200],
                    stdout_preview=result.stdout.decode('utf-8', errors='replace')[:200] if result.stdout else "")
                return False
                
        except subprocess.TimeoutExpired:
            evt("ffprobe_timeout", job_id=self.job_id, timeout_seconds=10)
            return False
            
        except Exception as e:
            evt("ffprobe_exception",
                job_id=self.job_id,
                error_type=type(e).__name__,
                error_detail=str(e)[:200])
            return False
    
    def _mask_ffmpeg_command(self, cmd: List[str]) -> List[str]:
        """
        Create masked version of FFmpeg command for logging.
        
        Args:
            cmd: FFmpeg command list
            
        Returns:
            Masked command list
        """
        masked_cmd = []
        
        for i, arg in enumerate(cmd):
            if isinstance(arg, str):
                # Mask URLs
                if arg.startswith('http'):
                    masked_cmd.append(_mask_url_for_logging(arg))
                # Mask headers containing cookies
                elif 'Cookie:' in arg:
                    masked_cmd.append("[HEADERS_WITH_MASKED_COOKIES]")
                # Mask proxy URLs
                elif i > 0 and cmd[i-1] == '-http_proxy':
                    masked_cmd.append("***MASKED_PROXY_URL***")
                else:
                    masked_cmd.append(arg)
            else:
                masked_cmd.append(str(arg))
        
        return masked_cmd
    
    def _requests_streaming_fallback(
        self,
        audio_url: str,
        output_path: str,
        cookies: Optional[str]
    ) -> bool:
        """
        Fallback method using requests streaming to download audio.
        
        Args:
            audio_url: URL of audio stream
            output_path: Path where file should be saved
            cookies: Cookie header string (optional)
            
        Returns:
            True if successful, False otherwise
        """
        start_time = time.time()
        
        try:
            # Create session with retry strategy
            session = requests.Session()
            
            retry_strategy = Retry(
                total=2,
                connect=1,
                read=2,
                backoff_factor=0.5,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET"],
            )
            
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("https://", adapter)
            session.mount("http://", adapter)
            
            # Set headers
            headers = {
                "User-Agent": FFMPEG_USER_AGENT,
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Origin": "https://www.youtube.com",
                "Referer": "https://www.youtube.com/"
            }
            
            if cookies:
                headers["Cookie"] = cookies
            
            # Configure proxy
            proxies = None
            if self.proxy_manager and self.proxy_manager.in_use:
                try:
                    proxies = self.proxy_manager.proxy_dict_for_job(self.job_id, "requests")
                except Exception as e:
                    logger.warning(f"Failed to get proxy for requests fallback: {e}")
            
            # Make streaming request
            evt("requests_fallback_start",
                job_id=self.job_id,
                url=_mask_url_for_logging(audio_url),
                has_cookies=bool(cookies),
                has_proxy=bool(proxies))
            
            response = session.get(
                audio_url,
                headers=headers,
                proxies=proxies,
                stream=True,
                timeout=(10, REQUESTS_TIMEOUT)
            )
            
            response.raise_for_status()
            
            # Stream to temporary file first
            temp_path = output_path + ".tmp"
            bytes_downloaded = 0
            
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=REQUESTS_CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Verify file was downloaded
            if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                # Move to final location
                os.rename(temp_path, output_path)
                
                evt("requests_fallback_complete",
                    job_id=self.job_id,
                    duration_ms=duration_ms,
                    bytes_downloaded=bytes_downloaded,
                    status_code=response.status_code)
                
                return True
            else:
                evt("requests_fallback_empty",
                    job_id=self.job_id,
                    duration_ms=duration_ms)
                return False
                
        except requests.exceptions.RequestException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            
            evt("requests_fallback_network_error",
                job_id=self.job_id,
                duration_ms=duration_ms,
                error_type=type(e).__name__,
                error_detail=str(e)[:200])
            
            return False
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            
            evt("requests_fallback_exception",
                job_id=self.job_id,
                duration_ms=duration_ms,
                error_type=type(e).__name__,
                error_detail=str(e)[:200])
            
            return False
        
        finally:
            # Clean up temp file if it exists
            temp_path = output_path + ".tmp"
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except:
                    pass


def extract_audio_with_job_proxy(
    audio_url: str,
    output_path: str,
    job_id: str,
    proxy_manager,
    cookies: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Extract audio using FFmpeg with job-scoped proxy session and fallback.
    
    Args:
        audio_url: URL of audio stream
        output_path: Path where WAV file should be saved
        job_id: Job identifier for sticky proxy session
        proxy_manager: ProxyManager instance
        cookies: Optional[str] = None
        
    Returns:
        Tuple of (success, error_classification)
    """
    service = FFmpegService(job_id, proxy_manager)
    success, returncode, error_classification = service.extract_audio_to_wav(
        audio_url, output_path, cookies
    )
    
    if not success:
        return success, error_classification
    
    # 1) Reject trivially small outputs (likely HTML or truncated)
    try:
        size = os.path.getsize(output_path)
    except FileNotFoundError:
        evt("asr_audio_missing_output")
        return False, "audio-missing"
    if size < 1_000_000:  # ~1MB
        evt("asr_audio_rejected_too_small", size=size)
        return False, "audio-too-small"

    # 2) ffprobe validation before handing to Deepgram
    import json, subprocess
    probe = subprocess.run(
        ["ffprobe","-v","error","-show_streams","-show_format","-print_format","json", output_path],
        capture_output=True, text=True, timeout=10
    )
    meta = json.loads(probe.stdout or "{}")
    streams = meta.get("streams") or []
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    if not has_audio:
        evt("asr_audio_probe_failed", meta=meta if len(json.dumps(meta)) < 800 else {"note":"omitted"})
        return False, "audio-invalid"

    return success, error_classification
