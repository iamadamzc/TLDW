# TL;DW YouTube Transcript Service - Critical Fixes Required

## Context
You are working on a YouTube transcript extraction service that uses a multi-stage fallback pipeline. The primary issue has been identified: the youtube-transcript-api library cannot accept cookies in the `fetch()` method, causing empty XML responses from YouTube's anti-bot protection.

## Current Architecture
- **Pipeline stages**: youtube-transcript-api → timedtext → YouTubei → ASR fallback  
- **Runtime**: Python + Flask, Docker container on AWS App Runner
- **Tools**: Playwright, ffmpeg, Deepgram ASR
- **Networking**: Oxylabs residential proxy + user cookies

## Log Evidence of Issues
Recent logs show:
1. **Transcript listing works** but fetch fails: `Transcript.fetch() got an unexpected keyword argument 'cookies'`
2. **Empty XML responses**: `no element found: line 1, column 0` 
3. **FFmpeg failures**: `Invalid data found when processing input` on WebM/Opus streams (itag=251)
4. **YouTubei timeouts**: Multiple 60s+ timeouts on page loads
5. **ASR Playwright timeouts**: `Page.goto: Timeout 60000ms exceeded`

## Your Tasks

### TASK 1: Integrate Direct HTTP Transcript Fetching ⭐ **HIGHEST PRIORITY**
Replace the problematic `transcript_obj.fetch(cookies=cookies)` calls in the transcript service with the provided direct HTTP implementation. 

**Requirements:**
- Use the provided `get_transcript_with_cookies()` function 
- Maintain the same function signatures and return formats
- Add proper error handling and logging
- Test with the existing cookie loading mechanism
- Ensure it works with the current pipeline fallback logic

### TASK 2: Harden FFmpeg Command for WebM/Opus Handling
The current ffmpeg command fails on `itag=251` (WebM/Opus audio streams) with "Invalid data found when processing input".

**Fix Required:**
```bash
ffmpeg -headers "Cookie: {cookies}\r\nUser-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\nReferer: https://www.youtube.com/\r\n" -i "{url}" -f wav -acodec pcm_s16le -ar 16000 -ac 1 -y output.wav
```

**Additional Requirements:**
- Add input format tolerance: `-f webm` or `-analyzeduration 10M -probesize 50M`
- Include proper error handling for different audio formats
- Add retry logic for network issues
- Log the exact ffmpeg command being executed for debugging

### TASK 3: Optimize YouTubei Timeout Handling
Current YouTubei stage is timing out after 60s+ on both desktop and mobile URLs.

**Core Improvements:**
- Increase timeout to 120s as recommended
- Implement exponential backoff between retries
- Add circuit breaker pattern: skip YouTubei for 1 hour after 3 consecutive failures

**Advanced YouTubei Reliability Strategies:**

**A) Session "Warming" - Anti-Detection Strategy**
Before navigating to the target video, have Playwright visit YouTube homepage or trending videos to establish realistic browsing patterns:
```python
# Before target video:
await page.goto("https://www.youtube.com")
await page.wait_for_timeout(random.randint(2000, 5000))  # Human-like pause
await page.goto("https://www.youtube.com/trending") 
await page.wait_for_timeout(random.randint(1000, 3000))
# Then navigate to target video
```
This mimics human behavior and helps establish a "cleaner" session fingerprint.

**B) Smart Player Response Interception - PRIORITY UPGRADE**
Instead of just waiting for `/get_transcript` XHR, intercept the initial player response containing transcript URLs directly:
- Listen for `player_response` object in network requests
- Extract `captions.playerCaptionsTracklistRenderer.captionTracks[]` 
- Get direct transcript URLs with authentication tokens
- This bypasses UI interaction entirely (like yt-dlp does)
- **Could make YouTubei the PRIMARY method instead of fallback**

**C) Explicit Consent Dialog Handling - Critical Fix**
Add immediate consent banner detection and handling:
```python
# Check for consent dialog immediately after page load
try:
    consent_button = await page.wait_for_selector('button:has-text("Accept all")', timeout=5000)
    if consent_button:
        await consent_button.click()
        await page.wait_for_timeout(2000)
except:
    pass  # No consent dialog found
```
Handle common patterns:
- `"Before you continue to YouTube"`
- `"Accept all"` / `"Reject all"` buttons  
- Age verification dialogs
- Regional compliance notices

**Implementation Priority:**
1. Consent handling (immediate timeout reduction)
2. Player response interception (could revolutionize success rate)
3. Session warming (reduces detection probability)

### TASK 4: Improve ASR Playwright Reliability  
ASR stage is failing with page load timeouts.

**Fixes Required:**
- Add retry logic with exponential backoff for page loads
- Implement chunked downloading for large audio files
- Save failed audio streams to S3 for debugging (optional but recommended)
- Add better error handling for different page load failure scenarios
- Consider using direct audio URL extraction without full page loads

### TASK 5: Proxy Strategy Optimization
Optimize when and how proxies are used in the pipeline.

**Strategy Changes:**
- **youtube-transcript-api**: Usually works better WITHOUT proxy - try direct first
- **timedtext**: Always use proxy if available  
- **YouTubei**: Always use proxy if available
- **ASR**: Start without proxy, use proxy only if direct fails

## Implementation Guidelines

### Error Handling Standards
- Log all failures with specific error codes and video IDs
- Include performance metrics for each stage (duration_ms, success/failure)
- Maintain breadcrumb logging for debugging
- Never fail silently - always log what went wrong

### Testing Requirements  
- Test with the video ID from logs: `n60NTrKs-wc`
- Verify cookie propagation works correctly
- Test proxy vs no-proxy scenarios
- Validate that fallback pipeline continues properly after failures

### Success Metrics
After implementing these fixes, you should see:
- **Primary**: Transcript extraction success rate >80% (currently failing due to cookie issue)
- **Secondary**: FFmpeg audio extraction success on WebM/Opus streams
- **Tertiary**: Reduced timeout failures in YouTubei and ASR stages

## Files to Modify
Focus on these files based on the current architecture:
- `transcript_service.py` - Main transcript pipeline logic
- `youtube_service.py` - ASR and audio extraction  
- `proxy_manager.py` - Proxy routing logic
- Any FFmpeg command execution code

## Critical Notes
- **The cookie propagation fix (Task 1) should resolve ~80% of current failures**
- **Do NOT modify the overall pipeline architecture - it's well designed**
- **Maintain backward compatibility with existing API endpoints**
- **Keep the async job processing pattern intact**

## Expected Outcome
These fixes should dramatically improve the transcript extraction success rate by addressing the core cookie authentication issue and hardening the fallback stages. The advanced YouTubei improvements (especially player response interception) could potentially make YouTubei the primary transcript source instead of a fallback method, significantly reducing reliance on the ASR pipeline.

**Success Metrics After Implementation:**
- **Primary**: Transcript extraction success rate >80% (currently failing due to cookie issue)
- **Secondary**: YouTubei becomes reliable primary method via player response interception
- **Tertiary**: Reduced timeout failures through consent handling and session warming