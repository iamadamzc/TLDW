# Transcript Reliability Troubleshooting Guide

## Overview

This guide helps diagnose and resolve issues with the transcript reliability improvements implemented in the TL;DW application. The reliability fix pack addresses critical silent failures, timeout issues, and inefficient processing patterns across the YouTube transcript extraction pipeline.

## New Logging Events

The reliability improvements introduce several new logging events for better observability:

### YouTubei Service Events

```json
{"ts": "2025-08-27T16:24:06.123Z", "lvl": "INFO", "job_id": "j-7f3d", "video_id": "bbz2boNSeL0", "event": "youtubei_captiontracks_shortcircuit", "lang": "en", "asr": false}
{"ts": "2025-08-27T16:24:06.145Z", "lvl": "ERROR", "job_id": "j-7f3d", "video_id": "bbz2boNSeL0", "event": "youtubei_captiontracks_probe_failed", "err": "No ytInitialPlayerResponse found"}
{"ts": "2025-08-27T16:24:06.167Z", "lvl": "ERROR", "job_id": "j-7f3d", "video_id": "bbz2boNSeL0", "event": "youtubei_title_menu_open_failed", "err": "Timeout waiting for menu button"}
{"ts": "2025-08-27T16:24:06.189Z", "lvl": "ERROR", "job_id": "j-7f3d", "video_id": "bbz2boNSeL0", "event": "youtubei_direct_missing_ctx", "has_key": true, "has_ctx": false, "has_params": true}
{"ts": "2025-08-27T16:24:06.211Z", "lvl": "INFO", "job_id": "j-7f3d", "video_id": "bbz2boNSeL0", "event": "youtubei_nav_timeout_short_circuit"}
```

### FFmpeg Service Events

```json
{"ts": "2025-08-27T16:24:06.233Z", "lvl": "WARNING", "job_id": "j-7f3d", "video_id": "bbz2boNSeL0", "event": "requests_fallback_blocked", "reason": "enforce_proxy_no_proxy"}
{"ts": "2025-08-27T16:24:06.255Z", "lvl": "ERROR", "job_id": "j-7f3d", "video_id": "bbz2boNSeL0", "event": "ffmpeg_timeout_exceeded", "timeout": 60}
```

### Transcript Service Events

```json
{"ts": "2025-08-27T16:24:06.277Z", "lvl": "WARNING", "job_id": "j-7f3d", "video_id": "bbz2boNSeL0", "event": "timedtext_empty_body"}
{"ts": "2025-08-27T16:24:06.299Z", "lvl": "WARNING", "job_id": "j-7f3d", "video_id": "bbz2boNSeL0", "event": "timedtext_html_or_block"}
{"ts": "2025-08-27T16:24:06.321Z", "lvl": "WARNING", "job_id": "j-7f3d", "video_id": "bbz2boNSeL0", "event": "timedtext_not_xml"}
{"ts": "2025-08-27T16:24:06.343Z", "lvl": "INFO", "job_id": "j-7f3d", "video_id": "bbz2boNSeL0", "event": "asr_playback_initiated"}
```

## Common Issues and Solutions

### 1. YouTubei Fast-Path Not Working

**Symptoms:**
- No `youtubei_captiontracks_shortcircuit` events in logs
- YouTubei still using DOM interaction for videos with embedded captions
- Slower processing times

**Diagnostic CloudWatch Query:**
```sql
fields @timestamp, job_id, video_id, event, lang, asr
| filter event = "youtubei_captiontracks_shortcircuit"
| stats count() as shortcut_count by bin(1h)
| sort @timestamp desc
```

**Common Causes and Solutions:**

1. **Feature Flag Disabled**
   ```bash
   # Check environment variable
   echo $ENABLE_CAPTION_TRACKS_SHORTCUT
   
   # Enable if disabled
   export ENABLE_CAPTION_TRACKS_SHORTCUT=true
   ```

2. **JavaScript Execution Errors**
   ```sql
   # Check for probe failures
   fields @timestamp, job_id, video_id, err
   | filter event = "youtubei_captiontracks_probe_failed"
   | sort @timestamp desc
   | limit 20
   ```

3. **Page Loading Issues**
   - Verify Playwright navigation is working
   - Check for consent walls or region blocking
   - Review proxy configuration

### 2. Proxy Enforcement Blocking Requests

**Symptoms:**
- `requests_fallback_blocked` events in logs
- FFmpeg failures when `ENFORCE_PROXY_ALL=1`
- Network requests failing unexpectedly

**Diagnostic CloudWatch Query:**
```sql
fields @timestamp, job_id, video_id, reason
| filter event = "requests_fallback_blocked"
| stats count() as blocked_count by reason
| sort blocked_count desc
```

**Solutions:**

1. **Check Proxy Configuration**
   ```bash
   # Verify proxy environment variables
   echo $ENFORCE_PROXY_ALL
   echo $USE_PROXY_FOR_TIMEDTEXT
   
   # Check proxy manager status
   python3 -c "
   from proxy_manager import ProxyManager
   pm = ProxyManager()
   print(f'Proxy available: {pm.is_healthy()}')
   "
   ```

2. **Adjust Proxy Enforcement**
   ```bash
   # Temporarily disable strict enforcement
   export ENFORCE_PROXY_ALL=false
   
   # Or ensure proxy is properly configured
   # Check AWS Secrets Manager for proxy credentials
   ```

### 3. Content Validation Failures

**Symptoms:**
- `timedtext_html_or_block`, `timedtext_not_xml`, `timedtext_empty_body` events
- Transcript extraction failing on valid videos
- Increased fallback to ASR processing

**Diagnostic CloudWatch Query:**
```sql
fields @timestamp, job_id, video_id, event
| filter event in ["timedtext_html_or_block", "timedtext_not_xml", "timedtext_empty_body"]
| stats count() as failure_count by event
| sort failure_count desc
```

**Solutions:**

1. **Check Content Validation Settings**
   ```bash
   # Verify content validation is enabled
   echo $ENABLE_CONTENT_VALIDATION
   
   # Check for consent wall issues
   # Review cookie configuration
   ```

2. **Analyze Response Content**
   ```python
   # Debug content validation
   from transcript_service import TranscriptService
   
   # Check what content is being received
   # Look for HTML responses, consent pages, or captcha
   ```

### 4. FFmpeg Timeout Issues

**Symptoms:**
- `ffmpeg_timeout_exceeded` events
- ASR processing failing due to timeouts
- Audio extraction taking too long

**Diagnostic CloudWatch Query:**
```sql
fields @timestamp, job_id, video_id, timeout, dur_ms
| filter event = "ffmpeg_timeout_exceeded"
| stats avg(timeout) as avg_timeout, count() as timeout_count by bin(1h)
| sort @timestamp desc
```

**Solutions:**

1. **Adjust Timeout Settings**
   ```bash
   # Check current timeout
   echo $FFMPEG_TIMEOUT
   
   # Increase if needed (but be careful of watchdog limits)
   export FFMPEG_TIMEOUT=90
   ```

2. **Check Audio URL Quality**
   - Verify audio URLs are accessible
   - Check for network connectivity issues
   - Review proxy configuration for audio requests

### 5. Deterministic Selectors Failing

**Symptoms:**
- `youtubei_title_menu_open_failed` events
- DOM interaction failures
- Fallback to older selector methods

**Diagnostic CloudWatch Query:**
```sql
fields @timestamp, job_id, video_id, err
| filter event = "youtubei_title_menu_open_failed"
| sort @timestamp desc
| limit 20
```

**Solutions:**

1. **Check Selector Configuration**
   ```bash
   # Verify deterministic selectors are enabled
   echo $ENABLE_DETERMINISTIC_SELECTORS
   ```

2. **YouTube UI Changes**
   - Monitor for YouTube interface updates
   - Check if selectors need updating
   - Review Playwright version compatibility

### 6. ASR Playback Trigger Issues

**Symptoms:**
- Missing `asr_playback_initiated` events
- ASR processing not capturing audio streams
- HLS/MPD manifest requests not triggered

**Diagnostic CloudWatch Query:**
```sql
fields @timestamp, job_id, video_id
| filter event = "asr_playback_initiated"
| stats count() as playback_count by bin(1h)
| sort @timestamp desc
```

**Solutions:**

1. **Check ASR Playback Settings**
   ```bash
   # Verify playback trigger is enabled
   echo $ENABLE_ASR_PLAYBACK_TRIGGER
   ```

2. **Playwright Interaction Issues**
   - Check for video player loading issues
   - Verify keyboard shortcuts are working
   - Review page navigation timing

## Performance Analysis

### Success Rate Monitoring

**Overall Pipeline Success Rate:**
```sql
fields stage, outcome
| filter event = "stage_result"
| stats countif(outcome="success") as success_count,
        count() as total_attempts
  by stage
| eval success_rate = round(success_count * 100.0 / total_attempts, 2)
| sort success_rate asc
```

**Reliability Improvement Impact:**
```sql
fields @timestamp, event, stage, outcome
| filter event = "stage_result"
| filter stage in ["youtubei", "timedtext", "ffmpeg"]
| stats countif(outcome="success") as success_count,
        countif(outcome="error") as error_count,
        countif(outcome="timeout") as timeout_count
  by bin(1h), stage
| sort @timestamp desc
```

### Performance Metrics

**Processing Time Analysis:**
```sql
fields stage, dur_ms, outcome
| filter event = "stage_result" and ispresent(dur_ms) and dur_ms > 0
| filter outcome = "success"
| stats avg(dur_ms) as avg_ms,
        pct(dur_ms, 50) as p50_ms,
        pct(dur_ms, 95) as p95_ms
  by stage
| sort p95_ms desc
```

**Fast-Path Effectiveness:**
```sql
fields @timestamp, event, lang, asr
| filter event = "youtubei_captiontracks_shortcircuit"
| stats count() as shortcut_count,
        countif(asr=false) as human_captions,
        countif(asr=true) as auto_captions
  by bin(1h)
| eval human_caption_rate = round(human_captions * 100.0 / shortcut_count, 2)
| sort @timestamp desc
```

## Configuration Validation

### Environment Variable Checklist

**Core Reliability Settings:**
```bash
# Timeout configuration
echo "FFMPEG_TIMEOUT: $FFMPEG_TIMEOUT"
echo "YOUTUBEI_HARD_TIMEOUT: $YOUTUBEI_HARD_TIMEOUT"
echo "PLAYWRIGHT_NAVIGATION_TIMEOUT: $PLAYWRIGHT_NAVIGATION_TIMEOUT"

# Proxy settings
echo "ENFORCE_PROXY_ALL: $ENFORCE_PROXY_ALL"
echo "USE_PROXY_FOR_TIMEDTEXT: $USE_PROXY_FOR_TIMEDTEXT"

# Feature flags
echo "ENABLE_CAPTION_TRACKS_SHORTCUT: $ENABLE_CAPTION_TRACKS_SHORTCUT"
echo "ENABLE_DETERMINISTIC_SELECTORS: $ENABLE_DETERMINISTIC_SELECTORS"
echo "ENABLE_CONTENT_VALIDATION: $ENABLE_CONTENT_VALIDATION"
echo "ENABLE_FAST_FAIL_YOUTUBEI: $ENABLE_FAST_FAIL_YOUTUBEI"
echo "ENABLE_ASR_PLAYBACK_TRIGGER: $ENABLE_ASR_PLAYBACK_TRIGGER"

# Retry settings
echo "FFMPEG_MAX_RETRIES: $FFMPEG_MAX_RETRIES"
echo "TIMEDTEXT_RETRIES: $TIMEDTEXT_RETRIES"
echo "YOUTUBEI_RETRIES: $YOUTUBEI_RETRIES"
```

**Configuration Validation Script:**
```python
#!/usr/bin/env python3
# validate_reliability_config.py

from reliability_config import validate_reliability_config
import json

def main():
    result = validate_reliability_config()
    print(json.dumps(result, indent=2))
    
    if result["status"] == "valid":
        print("\n✅ Reliability configuration is valid")
        return 0
    else:
        print(f"\n❌ Configuration validation failed: {result['error']}")
        return 1

if __name__ == "__main__":
    exit(main())
```

## Troubleshooting Workflows

### 1. High Error Rate Investigation

```bash
#!/bin/bash
# investigate_high_error_rate.sh

echo "=== Investigating High Error Rate ==="

# Check recent error distribution
aws logs start-query \
  --log-group-name "/aws/apprunner/tldw-transcript-service" \
  --start-time $(date -d '1 hour ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, stage, outcome, detail | filter outcome in ["error", "timeout", "blocked"] | stats count() as error_count by stage, outcome | sort error_count desc'

# Check for specific reliability events
aws logs start-query \
  --log-group-name "/aws/apprunner/tldw-transcript-service" \
  --start-time $(date -d '1 hour ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, event, detail | filter event in ["requests_fallback_blocked", "youtubei_nav_timeout_short_circuit", "ffmpeg_timeout_exceeded"] | stats count() by event'

echo "Check CloudWatch Logs Insights for query results"
```

### 2. Performance Degradation Analysis

```bash
#!/bin/bash
# analyze_performance_degradation.sh

echo "=== Analyzing Performance Degradation ==="

# Check processing time trends
aws logs start-query \
  --log-group-name "/aws/apprunner/tldw-transcript-service" \
  --start-time $(date -d '4 hours ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, stage, dur_ms | filter event = "stage_result" and ispresent(dur_ms) and dur_ms > 0 | stats avg(dur_ms) as avg_ms, pct(dur_ms, 95) as p95_ms by bin(30m), stage | sort @timestamp desc'

# Check fast-path usage
aws logs start-query \
  --log-group-name "/aws/apprunner/tldw-transcript-service" \
  --start-time $(date -d '4 hours ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, event | filter event = "youtubei_captiontracks_shortcircuit" | stats count() as shortcut_count by bin(30m) | sort @timestamp desc'

echo "Check CloudWatch Logs Insights for query results"
```

### 3. Configuration Drift Detection

```python
#!/usr/bin/env python3
# detect_config_drift.py

import os
import json
from reliability_config import get_reliability_config

def detect_config_drift():
    """Detect configuration drift from recommended settings."""
    
    config = get_reliability_config()
    
    # Recommended production settings
    recommended = {
        "ffmpeg_timeout": 60,
        "youtubei_hard_timeout": 45,
        "enforce_proxy_all": False,  # Usually false in production
        "enable_caption_tracks_shortcut": True,
        "enable_deterministic_selectors": True,
        "enable_content_validation": True,
        "enable_fast_fail_youtubei": True,
        "enable_asr_playback_trigger": True,
        "youtubei_retries": 0,  # Fast-fail approach
        "timedtext_retries": 1
    }
    
    drift_detected = False
    
    print("=== Configuration Drift Detection ===")
    
    for key, recommended_value in recommended.items():
        current_value = getattr(config, key, None)
        
        if current_value != recommended_value:
            print(f"⚠️  DRIFT: {key}")
            print(f"   Current: {current_value}")
            print(f"   Recommended: {recommended_value}")
            drift_detected = True
        else:
            print(f"✅ {key}: {current_value}")
    
    if not drift_detected:
        print("\n✅ No configuration drift detected")
    else:
        print(f"\n⚠️  Configuration drift detected - review settings")
    
    return drift_detected

if __name__ == "__main__":
    detect_config_drift()
```

## Emergency Procedures

### 1. Disable Reliability Features

If reliability improvements cause issues:

```bash
#!/bin/bash
# disable_reliability_features.sh

echo "=== DISABLING RELIABILITY FEATURES ==="

# Disable all feature flags
export ENABLE_CAPTION_TRACKS_SHORTCUT=false
export ENABLE_DETERMINISTIC_SELECTORS=false
export ENABLE_CONTENT_VALIDATION=false
export ENABLE_FAST_FAIL_YOUTUBEI=false
export ENABLE_ASR_PLAYBACK_TRIGGER=false

# Revert to conservative timeouts
export FFMPEG_TIMEOUT=120
export YOUTUBEI_HARD_TIMEOUT=60

# Disable proxy enforcement
export ENFORCE_PROXY_ALL=false

echo "Reliability features disabled. Restart application."
```

### 2. Rollback to Previous Behavior

```bash
#!/bin/bash
# rollback_reliability_fixes.sh

echo "=== ROLLING BACK RELIABILITY FIXES ==="

# Set environment variables to mimic pre-fix behavior
export ENABLE_CAPTION_TRACKS_SHORTCUT=false
export ENABLE_DETERMINISTIC_SELECTORS=false
export ENABLE_CONTENT_VALIDATION=false
export ENABLE_FAST_FAIL_YOUTUBEI=false
export ENABLE_ASR_PLAYBACK_TRIGGER=false

# Use original timeout values
export FFMPEG_TIMEOUT=120
export YOUTUBEI_HARD_TIMEOUT=60

# Enable retries (original behavior)
export YOUTUBEI_RETRIES=2
export TIMEDTEXT_RETRIES=2

# Redeploy
./deploy-apprunner.sh --timeout 300

echo "Rollback completed. Monitor application behavior."
```

## Monitoring and Alerting

### Recommended CloudWatch Alarms

```bash
# High error rate alarm
aws cloudwatch put-metric-alarm \
  --alarm-name "TL-DW-High-Transcript-Error-Rate" \
  --alarm-description "Alert on high transcript extraction error rate" \
  --metric-name "TranscriptErrorRate" \
  --namespace "TL-DW/Reliability" \
  --statistic "Average" \
  --period 300 \
  --threshold 15 \
  --comparison-operator "GreaterThanThreshold"

# FFmpeg timeout alarm
aws cloudwatch put-metric-alarm \
  --alarm-name "TL-DW-FFmpeg-Timeout-Rate" \
  --alarm-description "Alert on high FFmpeg timeout rate" \
  --metric-name "FFmpegTimeoutRate" \
  --namespace "TL-DW/Reliability" \
  --statistic "Sum" \
  --period 300 \
  --threshold 5 \
  --comparison-operator "GreaterThanThreshold"

# Proxy enforcement blocks
aws cloudwatch put-metric-alarm \
  --alarm-name "TL-DW-Proxy-Enforcement-Blocks" \
  --alarm-description "Alert on proxy enforcement blocking requests" \
  --metric-name "ProxyEnforcementBlocks" \
  --namespace "TL-DW/Reliability" \
  --statistic "Sum" \
  --period 300 \
  --threshold 10 \
  --comparison-operator "GreaterThanThreshold"
```

### Dashboard Widgets

Create CloudWatch dashboard with these widgets:

1. **Reliability Events Timeline**: Line chart showing reliability event counts over time
2. **Success Rate by Stage**: Bar chart comparing success rates before/after reliability fixes
3. **Fast-Path Usage**: Gauge showing percentage of requests using caption tracks shortcut
4. **Timeout Analysis**: Stacked area chart showing timeout events by service
5. **Configuration Status**: Text widget showing current reliability configuration

## Best Practices

1. **Monitor Gradually**: Deploy reliability fixes to staging first, monitor for 24 hours
2. **Feature Flag Control**: Use feature flags to enable/disable individual improvements
3. **Baseline Metrics**: Establish baseline performance metrics before enabling fixes
4. **Incremental Rollout**: Enable one feature at a time to isolate impact
5. **Rollback Plan**: Always have a rollback plan ready for production deployments
6. **Log Analysis**: Regularly analyze new logging events to identify patterns
7. **Configuration Validation**: Validate configuration after each deployment
8. **Performance Testing**: Test performance impact under load

## Getting Help

### Internal Escalation
1. **Level 1**: Check this troubleshooting guide and CloudWatch logs
2. **Level 2**: Contact development team with specific error patterns
3. **Level 3**: Engage DevOps team for infrastructure-related issues
4. **Level 4**: Emergency rollback if system stability is affected

### Useful Resources
- **CloudWatch Logs Insights**: Use provided query templates
- **Reliability Configuration**: Check `reliability_config.py` for settings
- **Test Scripts**: Use validation scripts in `tests/` directory
- **Deployment Scripts**: Review deployment scripts for environment setup

### Documentation References
- **Design Document**: `.kiro/specs/transcript-reliability-fix-pack/design.md`
- **Requirements**: `.kiro/specs/transcript-reliability-fix-pack/requirements.md`
- **Implementation Tasks**: `.kiro/specs/transcript-reliability-fix-pack/tasks.md`