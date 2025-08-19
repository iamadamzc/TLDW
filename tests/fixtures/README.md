# Test Fixtures for CI Smoke Tests

This directory contains test fixtures for comprehensive CI smoke testing without relying on live YouTube videos.

## Fixture Types

### Caption Fixtures
- `sample_captions.json` - Mock YouTube transcript API response
- `sample_captions_multilang.json` - Multi-language caption response

### Audio Fixtures  
- `tiny_test.mp4` - Minimal MP4 file for ASR path testing
- `tiny_test.m4a` - Minimal M4A file for step1 testing
- `tiny_test.mp3` - Minimal MP3 file for step2 testing

### Cookie Fixtures
- `sample_cookies.txt` - Mock cookie file for authenticated scenarios
- `expired_cookies.txt` - Expired cookie file for testing fallback behavior

### Deepgram Response Fixtures
- `deepgram_success.json` - Mock successful Deepgram API response
- `deepgram_error.json` - Mock Deepgram API error response

## Usage

These fixtures are used by the CI smoke test suite to test the complete pipeline without external dependencies:

1. **Transcript Path**: Uses caption fixtures to mock YouTube Transcript API
2. **ASR Path**: Uses audio fixtures with mocked Deepgram responses
3. **Cookie Scenarios**: Tests both authenticated and fallback scenarios
4. **Error Handling**: Tests various failure modes with controlled inputs

## Benefits

- **Reliable**: No dependency on external services or network conditions
- **Fast**: Local fixtures execute quickly in CI
- **Comprehensive**: Covers all major code paths and scenarios
- **Deterministic**: Same results every time, enabling reliable regression detection