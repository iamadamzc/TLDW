# Implementation Plan - MVP Baseline

## P0 Essentials (MVP Scope)

- [x] 1. Create Oxylabs proxy credentials secret in AWS Secrets Manager


  - Create new secret named `tldw-oxylabs-proxy-config` in AWS Secrets Manager
  - Store simple JSON with Oxylabs proxy configuration (host, port, username, password)
  - Test secret retrieval and validate proxy credentials format
  - _Requirements: 3.1, 3.2_

- [x] 2. Implement sticky session ProxyManager (no round-robin)


  - Create proxy_manager.py with simple ProxyManager class
  - Implement sticky sessions keyed by video_id with 10-minute TTL
  - Load proxy configuration from AWS Secrets Manager
  - Add basic session rotation (one retry per video_id)
  - _Requirements: 2.1, 2.2_

- [x] 3. Add proxy-aware HTTP requests with simple retry logic


  - Create proxy HTTP request wrapper with Oxylabs integration
  - Implement 403/429/"not a bot" detection for YouTube blocking
  - Add simple pacing: ≤2 req/sec with ±250ms jitter per session
  - Add basic backoff and single session rotation on blocks
  - _Requirements: 1.1, 1.2, 2.3_

- [x] 4. Integrate proxy system with TranscriptService


  - Modify transcript_service.py to use sticky proxy sessions
  - Add USE_PROXIES environment variable to enable/disable proxy usage
  - Implement fallback to ASR when transcript blocked after one rotation
  - Add caption check: if contentDetails.caption != "true" → skip to ASR
  - _Requirements: 4.1, 4.2, 2.4_

- [x] 5. Add basic caching and structured logging


  - Implement transcript caching by (video_id, lang) for 7-30 days
  - Add structured logging: video_id, step (transcript|ytdlp), status, attempt, latency_ms
  - Create simple success rate counter/metric for % blocked
  - Log proxy session usage and rotation events
  - _Requirements: 1.3, 2.3, 3.3_

- [x] 6. Update App Runner configuration for proxy support






  - Add OXYLABS_PROXY_CONFIG environment variable reference to proxy secret
  - Add USE_PROXIES=true environment variable
  - Update App Runner IAM role permissions to access new proxy secret
  - Test proxy secret injection in App Runner environment
  - _Requirements: 3.1, 3.2_

- [x] 7. Test MVP proxy integration end-to-end


  - Test Oxylabs proxy connectivity and sticky sessions
  - Verify transcript fetching works through proxy with session reuse
  - Test single rotation on 403/429 blocks then fallback to ASR
  - Validate ≥95% success rate on first/second attempt across 20-50 videos
  - _Requirements: 1.1, 1.4_

## MVP Exit Criteria
- ≥95% success on first/second attempt across 20-50 varied videos
- <2% persistent blocks after one rotation
- End-to-end time per video <2-3 minutes (discover → transcript/ASR → summary email)
- Concurrency limit: ≤5 concurrent videos per worker

## Deferred for Post-MVP (Future Iterations)
- Advanced round-robin across proxy pools
- Proxy health scoring, cooldowns, circuit breakers  
- Comprehensive dashboards and statistics
- App Runner health endpoints and extensive tooling
- Geographic proxy pools and per-user geo policies
- Complex error taxonomy beyond 403/429/timeout