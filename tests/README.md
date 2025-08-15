# TLDW Test Suite

This directory contains comprehensive tests for the TLDW proxy and user agent sticky session functionality.

## Test Structure

### Unit Tests
- `test_proxy_session.py` - ProxySession sticky session functionality
- `test_user_agent_manager.py` - UserAgentManager header consistency
- `test_discovery_gate_simple.py` - Discovery gate logic validation

### Integration Tests
- `test_integration_mvp.py` - End-to-end workflow testing
- `test_smoke_and_acceptance.py` - Smoke tests and acceptance criteria

### Legacy Tests (in `legacy/` directory)
- `legacy/test_proxy_config.py` - Original proxy configuration tests
- `legacy/test_token_manager.py` - Token management tests  
- `legacy/test_youtube_service.py` - YouTube API service tests

*Note: Legacy tests have circular import issues and are kept separate*

## Running Tests

### Run All Tests
```bash
python tests/run_all_tests.py
```

### Run Individual Test Files
```bash
python -m unittest tests.test_proxy_session -v
python -m unittest tests.test_user_agent_manager -v
python -m unittest tests.test_integration_mvp -v
```

### Run Specific Test Categories
```bash
# Unit tests only
python -m unittest tests.test_proxy_session tests.test_user_agent_manager tests.test_discovery_gate_simple -v

# Integration tests only
python -m unittest tests.test_integration_mvp -v

# Acceptance tests only
python -m unittest tests.test_smoke_and_acceptance -v
```

## Test Coverage

The test suite validates:

✅ **Sticky Session Functionality**
- Deterministic session ID generation from video_id
- Sticky username format with geo-enabled toggle
- URL encoding of credentials
- Session rotation and consistency

✅ **User Agent Management**
- Consistent headers for transcript and yt-dlp
- Accept-Language header inclusion
- Error handling and fallback behavior

✅ **Discovery Gate Logic**
- Caption availability checking
- Transcript scraping bypass when no captions
- Proper fallback to ASR workflow

✅ **Integration Workflows**
- End-to-end transcript → yt-dlp with same session
- Bot detection retry with session rotation
- 407 error fail-fast behavior

✅ **Acceptance Criteria**
- Zero 407 Proxy Authentication errors
- Session consistency across operations
- Structured logging with credential redaction
- User-Agent parity between transcript and yt-dlp

## Definition of Done Validation

The test suite validates all acceptance criteria:
- 0 occurrences of proxy_407 across test scenarios
- Bot detection recovery with session rotation
- Identical session IDs for transcript + yt-dlp per video
- All logs include ua_applied=true and latency_ms
- No passwords or full proxy URLs in logs