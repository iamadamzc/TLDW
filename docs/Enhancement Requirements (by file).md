Enhancement Requirements (by file)
A) transcript_service.py (enhance only)

Load storage_state when launching Playwright

Why: You already generate COOKIE_DIR/youtube_session.json with the generator; currently the Playwright context here doesn’t explicitly load a storage state.

Add: When creating the PW context, if ${COOKIE_DIR}/youtube_session.json exists, call browser.new_context(storage_state=path, locale="en-US").

Acceptance: For a logged-in session, document.cookie on YouTube has CONSENT/VISITOR cookies without re-consenting; first navigation does not show GDPR wall.

Deterministic YouTubei capture via page.route + Future (no sleeps)

Why: Current interception relies on response listeners/timing; make it deterministic.

Add: Intercept **/youtubei/v1/get_transcript*, route.continue_() and resolve an asyncio.Future from the response body, with a 20-25s timeout. Fall back only if Future isn’t resolved.

Acceptance: For a video with transcripts, the handler returns non-empty text without any fixed wait_for_timeout calls.

Client profile switching (desktop → mobile)

Why: Some transcripts are only exposed for one client profile.

Add: A client_profile param driving UA/viewport; attempt order: desktop(no-proxy → proxy) then mobile(no-proxy → proxy). Reuse one browser; create new contexts per profile to keep clean UA.

Acceptance: Logs show attempts across profiles; at least one profile returns a transcript on known edge cases.

Timed-text: prefer per-user cookies over env fallback

Why: Today _fetch_timedtext* mostly relies on env/file cookies. You already have S3/user cookies plumbing; thread that through and prefer it.

Add: Functions _fetch_timedtext_json3/_fetch_timedtext_xml/_fetch_timedtext accept a cookies header string or dict and use it over env/file. Keep env/file as fallback.

Acceptance: For a member-only or region-gated track, timed-text requests include the user’s cookies (verified in debug logs).

HTTP adapter mount (in addition to HTTPS)

Why: Your requests.Session mounts a retry adapter only for https://. Some redirects/probes may hit http://.

Add: session.mount("http://", HTTPAdapter(max_retries=retry)) in make_http_session.

Acceptance: No warnings about unmounted adapters; retries apply equally to HTTP/HTTPS.

Playwright-layer retry + integrate your circuit breaker

What you already have: A Playwright circuit breaker class and timeout handling (nice!).

Add: Wrap the entire YouTubei attempt in 2–3 tenacity retries (timeout/blocked errors), and call record_failure/record_success on the breaker. If breaker is open, skip the stage and log “open → skip”.

Acceptance: After N consecutive PW timeouts, further calls skip PW for the recovery period; one successful run resets the breaker.

DOM fallback after route timeout

Why: Occasionally the network call is blocked but transcript text nodes render in the DOM.

Add: If the Future times out, poll a small set of selectors for transcript lines for ~3–5s; if found, extract text.

Acceptance: Edge cases where network is blocked still yield text via DOM.

ffmpeg: force HTTPS through the proxy (env)

Why: Even if you add -http_proxy, HTTPS can leak; ensure env proxies are set for the subprocess.

Add: In ASRAudioExtractor._extract_audio_to_wav, compute proxy URL via your proxy manager and pass env={**os.environ, "http_proxy":url,"https_proxy":url} to subprocess.run.

Acceptance: With a broken proxy, extraction fails immediately; with a working proxy, succeeds. External IP observed by httpbin/ip changes when env proxy is set.

ffmpeg header hygiene (verify placement, CRLF)

What you likely already do: Build a CRLF-joined header string and include -headers in the command.

Add/Verify: Ensure -headers "<CRLF string>" appears before -i and that Cookie: … remains masked in logs.

Acceptance: ffmpeg runs without “No trailing CRLF”/header parsing errors; logs never contain raw cookie values.

Metrics & structured logs for PW breaker + stage timings

What you already log: Various warnings and errors.

Add: Emit structured events for breaker_state (open/closed/half-open), stage durations, and which attempt found the transcript (timedtext/YouTubei/ASR).

Acceptance: Logs/metrics dashboards show counts and latencies per stage and breaker state transitions.

B) cookie_generator.py (enhance only)

Netscape cookies.txt → storage_state converter

Why: You already generate youtube_session.json by warming a session. Add a converter for users who provide a Netscape file so Playwright can still use storage_state.

Add: A CLI flag --from-netscape cookies.txt that produces ${COOKIE_DIR}/youtube_session.json with sanitized cookies and minimal origins structure.

Acceptance: Running the converter yields a valid storage_state file that Playwright can load.

__Host- cookie sanitation on import

Why: Playwright rejects __Host- cookies unless secure=True, path="/", and no domain (use url field).

Add: On conversion, normalize all __Host-* cookies accordingly.

Acceptance: No Playwright errors about invalid __Host- cookies; cookies appear in context.

Explicit SOCS/CONSENT injection (only if missing)

Why: Your generator currently clicks consent (great), but in some regions it won’t surface.

Add: If neither SOCS nor CONSENT present at the end of warm-up/conversion, synthesize safe “accepted” values scoped to .youtube.com with long expiry.

Acceptance: After generation/conversion, storage_state always includes one of SOCS/CONSENT.

C) proxy_manager.py (enhance only)

Convenience env builder for subprocesses

Why: You already build proxies for requests/Playwright and validate secrets extensively. Provide a tiny utility for ffmpeg/env.

Add: def proxy_env_for_subprocess(self) -> dict: returning {"http_proxy": url, "https_proxy": url} (computed from your existing secret/session builder).

Acceptance: transcript_service.ASRAudioExtractor can call pm.proxy_env_for_subprocess() and pass directly to subprocess.run.

Expose a single proxy_dict_for(kind) (if not already public)

Why: Call-sites sometimes need "requests" vs "playwright". If this is already implemented, no change; if not, add it.

Add (only if missing): proxy_dict_for("requests") -> {"http":..., "https":...}, proxy_dict_for("playwright") -> {"server":..., "username":..., "password":...} using current ProxySecret and session token generator.

Acceptance: Transcript service can obtain proxies with one method for each consumer.

Breaker/preflight metrics surface

What you have: Rich preflight with httpbin + generate_204 and thorough secret validation (nice).

Add: Log counters for preflight hits/misses and masked username tail; retain current masking. Provide a healthy boolean accessor (already present) in structured logs periodically.

Acceptance: Periodic logs/metrics show proxy health and preflight rates without leaking secrets.

D) Cross-cutting Enhancements

Retries with jitter for Playwright steps

Why: You already do HTTP retries; add PW-layer retries for navigation/interception timeouts.

Add: tenacity (or your existing retry util) with exponential backoff + jitter on the entire YouTubei attempt function (2–3 tries).

Acceptance: Transient PW timeouts recover on second/third try; breaker kicks in only on sustained failures.

Stage-order & early-exit remain unchanged

Keep your existing order (yt-api → timedtext → YouTubei → ASR). The items above only make each stage more reliable; they do not reorder.