# Live Testing Guide - Transcript Extraction Fixes

## Prerequisites

Make sure you're on the correct branch:
```bash
git branch  # Should show: fix/postdeploy-transcripts-asr-headers
git status  # Should be clean or show only test_fixes.py
```

---

## Test Scenarios

### Scenario 1: Quick API Test (What We Just Did)

**Purpose:** Verify youtube-transcript-api stage works  
**Expected:** Fast extraction via API, no DOM interaction needed

```bash
python test_fixes.py
```

**Expected output:**
```
✅ SUCCESS: Got 121 transcript segments
```

---

### Scenario 2: Test YouTubei DOM Sequence

**Purpose:** Verify the deterministic DOM sequence with kebab → menu → panel clicks  
**Video:** Use a video where API fails but transcript exists

```python
# Save as test_youtubei_dom.py
from youtubei_service import DeterministicYouTubeiCapture
from storage_state_manager import StorageStateManager
import asyncio

async def test_youtubei_dom():
    print("="*60)
    print("Testing YouTubei DOM Sequence")
    print("="*60)
    
    # Initialize with test video
    video_id = "dQw4w9WgXcQ"  # Rick Astley - alternative video
    job_id = "test_job_youtubei_dom"
    
    storage_manager = StorageStateManager()
    
    # Create capture service
    capture = DeterministicYouTubeiCapture(
        video_id=video_id,
        job_id=job_id,
        proxy_manager=None,  # No proxy for local test
        storage_manager=storage_manager
    )
    
    try:
        transcript = await capture.extract_transcript(cookies=None)
        
        if transcript:
            print(f"\n✅ SUCCESS: Got transcript ({len(transcript)} chars)")
            print(f"Preview: {transcript[:200]}...")
            
            # Check logs for breadcrumbs
            print("\nCheck logs above for these breadcrumbs:")
            print("  - youtubei_kebab_clicked")
            print("  - youtubei_transcript_menu_clicked")
            print("  - youtubei_panel_opened")
            
            return True
        else:
            print("\n❌ FAILED: No transcript returned")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_youtubei_dom())
    exit(0 if success else 1)
```

**Run it:**
```bash
python test_youtubei_dom.py
```

**What to look for in logs:**
- `youtubei_navigation_complete` with `strategy=networkidle` or `strategy=domcontentloaded`
- `youtubei_dom_hydration_complete`
- `youtubei_kebab_clicked` ← **KEY breadcrumb**
- `youtubei_transcript_menu_clicked` ← **KEY breadcrumb**
- `youtubei_panel_opened` ← **KEY breadcrumb**

---

### Scenario 3: Test via Flask API (Production-like)

**Purpose:** Test the full pipeline via HTTP API as it runs in production

**Start the Flask app:**
```bash
# In terminal 1
python app.py
# Or if you have a run script:
python run.py
```

**Make test request:**
```bash
# In terminal 2
curl -X POST http://localhost:5000/api/summarize \
  -H "Content-Type: application/json" \
  -d '{
    "video_ids": ["rNxC16mlO60"],
    "user_email": "test@example.com"
  }'
```

**Expected response:**
```json
{
  "job_id": "some-uuid",
  "status": "queued",
  "video_count": 1
}
```

**Check job status:**
```bash
curl http://localhost:5000/api/jobs/<job_id>
```

**What to verify:**
- Job completes successfully
- Transcript extracted for video
- No errors in Flask logs
- Check logs for breadcrumbs

---

### Scenario 4: Test Timedtext TypeError Protection

**Purpose:** Verify timedtext doesn't crash on malformed responses

```python
# Save as test_timedtext_robustness.py
from timedtext_service import timedtext_attempt
import logging

logging.basicConfig(level=logging.INFO)

def test_timedtext_robustness():
    print("="*60)
    print("Testing Timedtext Robustness")
    print("="*60)
    
    test_videos = [
        ("rNxC16mlO60", "Should succeed"),
        ("invalid_video_id", "Should fail gracefully"),
        ("dQw4w9WgXcQ", "Alternative video"),
    ]
    
    for video_id, description in test_videos:
        print(f"\nTesting: {video_id} - {description}")
        try:
            result = timedtext_attempt(video_id, language_codes=["en"])
            if result:
                print(f"  ✅ Got transcript: {len(result)} chars")
            else:
                print(f"  ℹ️  No transcript (expected for invalid IDs)")
        except Exception as e:
            print(f"  ❌ ERROR: {type(e).__name__}: {str(e)}")
            return False
    
    print("\n✅ All tests completed without crashes")
    return True

if __name__ == "__main__":
    success = test_timedtext_robustness()
    exit(0 if success else 1)
```

**Run it:**
```bash
python test_timedtext_robustness.py
```

**Expected:** No TypeErrors, graceful handling of all responses

---

## Production Deployment Testing

### Step 1: Deploy to Staging/Dev Environment

**If using Docker:**
```bash
# Build new image with fixes
docker build -t tldw:fix-transcripts .

# Run container
docker run -p 5000:5000 \
  -e DEEPGRAM_API_KEY=your_key \
  -e ENABLE_ASR_FALLBACK=1 \
  tldw:fix-transcripts
```

**If using AWS App Runner:**
```bash
# Push to your deployment branch
git push origin fix/postdeploy-transcripts-asr-headers

# Trigger App Runner deployment via your CI/CD pipeline
# Or manually deploy via AWS Console
```

### Step 2: Monitor Logs in Production

**Key events to monitor:**
```
# Good signs:
✅ youtubei_kebab_clicked
✅ youtubei_transcript_menu_clicked  
✅ youtubei_panel_opened
✅ youtubei_navigation_complete (strategy=domcontentloaded or networkidle)
✅ timedtext_response_received (with diagnostics)

# No longer should see:
❌ TypeError: string indices must be integers
❌ youtubei_dom_no_expander
❌ transcript button not found (should be rare now)
```

### Step 3: Test Error Cases

**Videos to test:**
1. **Age-restricted video** - Should handle gracefully
2. **Private video** - Should fail cleanly
3. **Video with no captions** - Should fall back to ASR (if enabled)
4. **Long video (>2hr)** - Test ASR duration limits

---

## Recommended Test Sequence

### For Local Development:
1. ✅ Run `python test_fixes.py` - Verify basic extraction works
2. Run `python test_youtubei_dom.py` - Verify DOM sequence (if you create it)
3. Run via Flask API - Test full integration

### For Staging/Production:
1. Deploy to staging environment
2. Monitor logs for 1-2 hours
3. Test with known-problematic videos (e.g., `rNxC16mlO60`)
4. Verify no `TypeError` in timedtext
5. Check that total extraction time is < 150s for most videos

---

## Rollback Plan

If issues are found:

```bash
# Revert commits
git revert 81cae10  # Cache fix
git revert 26bdded  # Main fixes

# Or hard reset (if not pushed)
git reset --hard HEAD~2

# Push rollback
git push origin fix/postdeploy-transcripts-asr-headers --force
```

---

## Success Metrics

Track these in production logs:

1. **YouTubei DOM success rate** - Should increase
   - Look for `youtubei_panel_opened` events
   
2. **Timedtext TypeError rate** - Should drop to 0
   - Monitor for `timedtext_validation_error` vs success

3. **Average extraction time** - Should improve
   - Track time from start to completion

4. **Stage timeout rate** - Should be low
   - Monitor navigation timeouts vs successes

---

## Getting Help

If you see unexpected errors:

1. **Check logs** for breadcrumbs and error events
2. **Capture full log output** for a failing video
3. **Note the video_id** that failed
4. **Check YouTube directly** - Does the video have captions?

The deterministic DOM sequence is designed to be robust, but YouTube can always change their UI!
