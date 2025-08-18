# Implementation Plan

- [x] 1. Modify deploy.sh script to add cache-busting build argument


  - Locate the docker build command around line 282 in deploy.sh
  - Add --build-arg CACHE_BUSTER=${IMAGE_TAG} to the existing docker build command
  - Ensure the argument is passed alongside the existing YT_DLP_AUTO_UPDATE argument
  - _Requirements: 1.1, 1.2_

- [x] 2. Update Dockerfile to accept and use cache-busting argument


  - Add ARG CACHE_BUSTER declaration after the existing ARG YT_DLP_AUTO_UPDATE=false line
  - Modify the yt-dlp update RUN command to echo the CACHE_BUSTER value
  - Ensure the cache-busting echo statement makes each build command unique
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 3. Enhance health check endpoint with proxy connectivity validation


  - Locate the /healthz endpoint function in app.py
  - Add proxy connectivity testing logic when USE_PROXIES environment variable is enabled
  - Import and use ProxyManager.test_proxy_connectivity() method
  - Return HTTP 503 status code when proxy connectivity fails
  - Include proxy status information in health check response
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 4. Implement robust error handling for health check proxy testing


  - Add try-catch blocks around proxy manager imports and connectivity tests
  - Handle ProxyManager import failures gracefully
  - Provide descriptive error messages in health check responses
  - Ensure health check remains functional even when proxy testing fails
  - _Requirements: 3.4, 4.3_

- [ ] 5. Validate integration between all deployment hardening components



  - Test that cache-busting arguments flow correctly from deploy.sh to Dockerfile
  - Verify that Docker builds create unique layers for dependency updates
  - Confirm health check properly validates proxy connectivity
  - Ensure deployment failures are explicit rather than silent
  - _Requirements: 4.1, 4.2, 4.4_