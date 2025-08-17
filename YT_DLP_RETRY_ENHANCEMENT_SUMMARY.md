# yt-dlp Retry Logic and Cookie Handling Enhancement Summary

## Overview

This document summarizes the comprehensive enhancements made to the TL;DW application's yt-dlp integration to address YouTube extraction errors, cookie invalidation, and improve overall reliability.

## Problem Statement

**Initial State:**
- ✅ 407 Proxy Authentication errors resolved (geo targeting disabled)
- ✅ Proxy connectivity working (`proxy_connectivity.status = success`)
- ❌ yt-dlp failing with YouTube extraction errors, not proxy errors
- ❌ Cookie invalidation causing failures without proper retry logic
- ❌ No cookie freshness detection
- ❌ Limited visibility into yt-dlp version and update status

**Error Signatures Observed:**
```
WARNING: [youtube] … The provided YouTube account cookies are no longer valid…
ERROR: Unable to extract player response
```

## Solution Architecture

### 1. **Centralized Retry Logic** ✅
**Location:** `yt_download_helper.py`
**New Function:** `download_audio_with_retry()`

**Strategy:**
- **Attempt 1:** Use cookies if provided and fresh
- **Retry 1:** Skip cookies if cookie invalidation or extraction failure detected  
- **Retry 2:** Fail gracefully with "consider updating yt-dlp" message
- **No runtime `pip install`** - updates handled at container build time

### 2. **Cookie Freshness Detection** ✅
**Function:** `_check_cookie_freshness()`

**Features:**
- Checks if cookiefile is older than 12 hours
- Logs warning: `⚠️ Cookiefile is older than 12 hours and may be invalid. Please refresh.`
- Automatically skips stale cookies in retry logic
- Still attempts to use stale cookies but enables fallback

### 3. **Cookie Invalidation Detection** ✅
**Function:** `_detect_cookie_invalidation()`

**Patterns Detected:**
- "cookies are no longer valid"
- "provided youtube account cookies are no longer valid"
- "cookie has expired"
- "invalid cookies"

**Behavior:**
- Logs at WARN level with user ID: `⚠️ YouTube cookies invalid for user {user_id}, retrying without cookies`
- Explicitly sets `use_cookies=False` in retry (not silent skip)

### 4. **Extraction Failure Detection** ✅
**Function:** `_detect_extraction_failure()`

**Patterns Detected:**
- "unable to extract player response"
- "unable to extract video data"
- "video unavailable"
- "extraction failed"

**Behavior:**
- Triggers retry without cookies
- Distinguishes from network/proxy errors

### 5. **Structured JSON Startup Logging** ✅
**Location:** `app.py` in `_check_dependencies()`

**Format:**
```json
{"component": "yt_dlp", "version": "2025.08.12", "status": "loaded"}
```

**Benefits:**
- Easy to grep in App Runner logs
- Structured for log aggregation tools
- Consistent with existing logging patterns

### 6. **Container Build-Time Auto-Update** ✅
**Location:** `Dockerfile`

**Implementation:**
```dockerfile
ARG YT_DLP_AUTO_UPDATE=false
RUN if [ "$YT_DLP_AUTO_UPDATE" = "true" ]; then \
        echo "Auto-updating yt-dlp to latest version..." && \
        pip install --no-cache-dir -U yt-dlp; \
    else \
        echo "Using yt-dlp version from requirements.txt"; \
    fi
```

**Usage:**
```bash
docker build --build-arg YT_DLP_AUTO_UPDATE=true -t tldw .
```

## Implementation Details

### Key Files Modified

1. **`yt_download_helper.py`**
   - Added `_check_cookie_freshness()`
   - Added `_detect_cookie_invalidation()`
   - Added `_detect_extraction_failure()`
   - Added `download_audio_with_retry()` with comprehensive retry logic

2. **`transcript_service.py`**
   - Updated to use `download_audio_with_retry()` instead of `download_audio_with_fallback()`
   - Simplified retry logic (delegated to helper)
   - Enhanced user_id passing for better logging

3. **`app.py`**
   - Added structured JSON logging for yt-dlp version at startup
   - Enhanced dependency checking with version logging

4. **`Dockerfile`**
   - Added optional build-time yt-dlp auto-update mechanism

### Integration Points

- **Cookie freshness** integrates with existing `_maybe_cookie()` function
- **Retry logic** builds on existing `_attempt_ytdlp_download()` method  
- **Error detection** enhances existing `_detect_bot_check()` function
- **Logging** integrates with existing structured logging system

## Testing and Validation

### Test Coverage ✅
**Test File:** `test_yt_dlp_retry_logic.py`

**Scenarios Tested:**
1. ✅ Cookie freshness detection (12-hour threshold)
2. ✅ Cookie invalidation pattern detection
3. ✅ Extraction failure pattern detection
4. ✅ Success on first attempt with cookies
5. ✅ Cookie invalidation → retry without cookies → success
6. ✅ Extraction failure → retry without cookies → success
7. ✅ Both attempts fail → proper combined error message
8. ✅ Stale cookies automatically skipped

**Test Results:**
```
🎉 All tests passed! Retry logic implementation is working correctly.

Key features verified:
✅ Cookie freshness checking (12-hour threshold)
✅ Cookie invalidation detection from yt-dlp errors
✅ Extraction failure detection
✅ Automatic retry without cookies on failure
✅ Proper error logging and user feedback
✅ Stale cookie automatic skipping
```

## Acceptance Criteria Status

### ✅ **Already Achieved (Pre-Implementation)**
- No more 407s in logs (proxy authentication fixed)
- Proxy usernames log without `-cc-` when geo disabled
- Proxy connectivity shows `proxy_connectivity.status = success`

### ✅ **Newly Implemented**
- yt-dlp extraction errors automatically retried with cookie fallback
- Cookie invalidation detected and logged at WARN level with `use_cookies=False`
- Cookie freshness warning for files older than 12 hours
- Structured JSON logging for yt-dlp version at startup
- Clear distinction between proxy errors (407) and extractor errors
- Graceful failure with "consider updating yt-dlp" message
- Container build-time yt-dlp auto-update capability

## Operational Benefits

### **For Operations Teams:**
1. **Clear Error Classification:** Proxy errors (407) vs extraction errors clearly distinguished
2. **Proactive Cookie Management:** 12-hour freshness warnings help prevent stale cookie issues
3. **Version Visibility:** Structured yt-dlp version logging for update tracking
4. **Automated Fallbacks:** Reduces manual intervention for cookie-related failures

### **For Users:**
1. **Improved Success Rate:** Automatic retry without cookies when invalidation detected
2. **Better Error Messages:** Clear guidance when yt-dlp needs updating
3. **Transparent Cookie Status:** Clear warnings when cookies need refreshing

### **For Developers:**
1. **Centralized Logic:** All retry logic in one place (`yt_download_helper.py`)
2. **Comprehensive Testing:** Full test coverage for retry scenarios
3. **Deployment Flexibility:** Optional build-time yt-dlp updates

## Deployment Instructions

### **Standard Deployment:**
```bash
docker build -t tldw .
```

### **With yt-dlp Auto-Update:**
```bash
docker build --build-arg YT_DLP_AUTO_UPDATE=true -t tldw .
```

### **Environment Variables:**
- `OXY_DISABLE_GEO=true` (already configured - keeps geo targeting disabled)
- `DISABLE_COOKIES=false` (default - enables cookie functionality)

## Monitoring and Alerting

### **Key Log Patterns to Monitor:**

**Success Indicators:**
```
{"component": "yt_dlp", "version": "X.Y.Z", "status": "loaded"}
yt_dlp_attempt=1 use_cookies=true
```

**Warning Indicators:**
```
⚠️ Cookiefile is older than 12 hours and may be invalid. Please refresh.
⚠️ YouTube cookies invalid for user {user_id}, retrying without cookies
```

**Error Indicators:**
```
yt-dlp extraction failed after retry for {video_url}. Consider updating yt-dlp, may be outdated extractor.
```

## Future Enhancements

### **Potential Improvements:**
1. **Automatic Cookie Refresh:** Integration with cookie management system
2. **Dynamic yt-dlp Updates:** Runtime update mechanism with safety checks
3. **Enhanced Metrics:** Success/failure rate tracking per retry type
4. **User Notification:** Proactive cookie refresh reminders

## Conclusion

The yt-dlp retry logic and cookie handling enhancements provide a robust, production-ready solution for handling YouTube extraction errors. The implementation follows best practices with:

- **Deployment-time updates** (not runtime)
- **Centralized retry logic** (no duplication)
- **Explicit error handling** (clear logging)
- **Comprehensive testing** (all scenarios covered)
- **Operational visibility** (structured logging)

The system now gracefully handles cookie invalidation, provides clear error classification, and maintains high availability through intelligent retry mechanisms.
