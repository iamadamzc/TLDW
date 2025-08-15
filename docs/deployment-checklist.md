# Container App Runner Deployment Checklist

## Pre-Deployment Verification

### Local Testing
- [ ] Docker build completes successfully
- [ ] Container starts without errors
- [ ] Health check endpoint returns 200
- [ ] ffmpeg/ffprobe available in container
- [ ] yt-dlp import works correctly

### Code Verification
- [ ] Dockerfile uses non-root user
- [ ] wsgi.py has ALLOW_MISSING_DEPS=false default
- [ ] yt-dlp calls include explicit ffmpeg_location
- [ ] No apprunner.yaml file in repository
- [ ] All secrets properly referenced

## Deployment Process

### ECR Setup
- [ ] ECR repository created
- [ ] AWS CLI configured with correct permissions
- [ ] Docker logged into ECR
- [ ] Image built and tagged correctly
- [ ] Image pushed to ECR successfully

### App Runner Configuration
- [ ] Service source set to "Container registry"
- [ ] Image URI points to correct ECR image
- [ ] Port set to 8080
- [ ] Health check path set to /healthz
- [ ] Start command left empty (uses Dockerfile CMD)
- [ ] All required secrets configured

## Post-Deployment Verification

### Service Health
- [ ] App Runner service status is "Running"
- [ ] Health check endpoint returns 200
- [ ] Service URL accessible
- [ ] No error logs in App Runner console

### Dependency Verification
- [ ] Startup logs show ffmpeg at /usr/bin/ffmpeg
- [ ] Startup logs show ffprobe at /usr/bin/ffprobe
- [ ] Startup logs show yt-dlp version 2024.8.6
- [ ] FFMPEG_LOCATION environment variable set
- [ ] No "missing dependency" errors

### Functional Testing
- [ ] Application loads successfully
- [ ] User authentication works
- [ ] Video URL submission accepted
- [ ] Transcript fetching works
- [ ] Audio download via yt-dlp succeeds
- [ ] No "ffmpeg not found" errors
- [ ] ASR processing completes
- [ ] Email notifications sent
- [ ] No "407 Proxy Authentication Required" errors

### Performance Verification
- [ ] Container startup time < 30 seconds
- [ ] Health check response time < 5 seconds
- [ ] Memory usage reasonable (< 1GB)
- [ ] CPU usage stable under load

## Rollback Plan

If deployment fails:

1. **Immediate Rollback**
   - [ ] Revert to previous App Runner service version
   - [ ] Restore apprunner.source.yaml.backup if needed
   - [ ] Verify service returns to working state

2. **Investigation**
   - [ ] Check App Runner logs for errors
   - [ ] Verify ECR image integrity
   - [ ] Test container locally
   - [ ] Review configuration changes

3. **Fix and Redeploy**
   - [ ] Address identified issues
   - [ ] Test fixes locally
   - [ ] Rebuild and push corrected image
   - [ ] Redeploy with verification

## Success Criteria

### Technical Metrics
- [ ] Service uptime > 99%
- [ ] Health check success rate > 99%
- [ ] Average response time < 2 seconds
- [ ] Error rate < 1%

### Functional Metrics
- [ ] Video processing success rate > 90%
- [ ] Proxy rotation working on bot-check
- [ ] Email delivery success rate > 95%
- [ ] No critical dependency failures

### Operational Metrics
- [ ] Deployment time < 10 minutes
- [ ] Zero downtime during deployment
- [ ] Monitoring and alerting functional
- [ ] Documentation updated and accurate

## Sign-off

- [ ] Development Team Lead: _________________ Date: _______
- [ ] DevOps Engineer: _________________ Date: _______
- [ ] QA Lead: _________________ Date: _______
- [ ] Product Owner: _________________ Date: _______

## Notes

_Use this section to document any issues encountered, workarounds applied, or lessons learned during deployment._

---

**Deployment Date:** _______________
**Deployed By:** _______________
**App Runner Service:** _______________
**ECR Image URI:** _______________