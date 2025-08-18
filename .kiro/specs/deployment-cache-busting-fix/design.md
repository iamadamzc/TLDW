# Design Document

## Overview

This design implements a comprehensive solution to resolve Docker caching issues that cause silent deployment failures in AWS App Runner. The solution consists of three coordinated components: cache-busting in the deployment script, Dockerfile modifications to use cache-busting arguments, and enhanced health checks that validate proxy connectivity.

## Architecture

The fix operates at three levels of the deployment pipeline:

1. **Build-time Cache Invalidation**: The deploy.sh script passes unique identifiers to Docker builds
2. **Container-level Cache Busting**: The Dockerfile uses build arguments to ensure dependency update commands are never cached
3. **Runtime Health Validation**: The application health check validates critical dependencies like proxy connectivity

## Components and Interfaces

### Deploy Script Enhancement

**File**: `deploy.sh`
**Location**: Line ~282 (docker build command)

The deployment script will be modified to pass a `CACHE_BUSTER` build argument containing the unique git commit hash (`${IMAGE_TAG}`). This ensures every build has a unique identifier that propagates through the Docker build process.

**Interface**:
```bash
docker build \
  --build-arg YT_DLP_AUTO_UPDATE=true \
  --build-arg CACHE_BUSTER=${IMAGE_TAG} \
  -t ${ECR_REPOSITORY}:${IMAGE_TAG} .
```

### Dockerfile Cache-Busting Integration

**File**: `Dockerfile`
**Integration Point**: After existing `ARG YT_DLP_AUTO_UPDATE=false` line

The Dockerfile will accept the cache-busting argument and incorporate it into the yt-dlp update RUN command. By echoing the unique hash, the command string becomes different for every build, reliably breaking Docker's layer cache.

**Interface**:
```dockerfile
ARG YT_DLP_AUTO_UPDATE=false
ARG CACHE_BUSTER

RUN if [ "$YT_DLP_AUTO_UPDATE" = "true" ]; then \
    echo "Cache Buster: $CACHE_BUSTER" && \
    echo "Auto-updating yt-dlp to latest version..." && \
    pip install --no-cache-dir -U yt-dlp; \
  else \
    echo "Using yt-dlp version from requirements.txt"; \
  fi
```

### Enhanced Health Check System

**File**: `app.py`
**Function**: `/healthz` endpoint

The health check will be enhanced to validate proxy connectivity when proxies are enabled. This creates an explicit failure path that prevents silent deployment issues.

**Interface**:
```python
@app.route('/healthz')
def health_check():
    # Existing health check logic preserved
    health_info = {
        'status': 'healthy',
        'message': 'TL;DW API is running',
        'proxy_enabled': os.getenv('USE_PROXIES', 'false').lower() == 'true',
    }
    
    # Add proxy connectivity validation
    if health_info['proxy_enabled']:
        proxy_test_result = _test_proxy_connectivity()
        if proxy_test_result['status'] != 'success':
            health_info['status'] = 'unhealthy'
            health_info['message'] = f'Proxy connectivity failed: {proxy_test_result["error"]}'
            return health_info, 503
    
    return health_info, 200
```

## Data Models

### Health Check Response Model

```python
{
    "status": "healthy" | "unhealthy",
    "message": str,
    "proxy_enabled": bool,
    "proxy_connectivity": {
        "status": "success" | "error",
        "error": str | null
    },
    "dependencies": dict  # Existing dependency checks
}
```

### Cache-Busting Build Arguments

```dockerfile
CACHE_BUSTER: string  # Git commit hash from ${IMAGE_TAG}
YT_DLP_AUTO_UPDATE: "true" | "false"  # Existing argument
```

## Error Handling

### Docker Build Failures

- If cache-busting arguments are missing, the build will proceed but may use cached layers
- Build argument validation occurs at Docker build time
- Failed builds will be caught by the deployment script's error handling

### Proxy Connectivity Failures

- Proxy test failures result in HTTP 503 responses from health checks
- App Runner will reject deployments that fail health checks
- Error messages include specific failure reasons for debugging
- Fallback behavior maintains previous stable deployment

### Health Check Exceptions

- Proxy manager import failures are caught and treated as connectivity failures
- Exception details are logged in health check responses
- System remains responsive even when proxy tests fail

## Testing Strategy

### Unit Testing

- Test cache-busting argument integration in Docker builds
- Validate health check proxy connectivity logic
- Mock proxy manager responses for various failure scenarios

### Integration Testing

- End-to-end deployment testing with cache-busting enabled
- Health check validation with real proxy configurations
- Deployment rollback testing when health checks fail

### Deployment Validation

- Verify unique Docker layers are created for each deployment
- Confirm App Runner properly rejects unhealthy deployments
- Validate that dependency updates are applied in new containers

## Implementation Sequence

1. **Deploy Script Modification**: Add cache-busting build argument
2. **Dockerfile Enhancement**: Accept and use cache-busting argument
3. **Health Check Enhancement**: Add proxy connectivity validation
4. **Integration Testing**: Validate end-to-end deployment pipeline
5. **Production Deployment**: Apply fixes and monitor deployment success

This design ensures that Docker caching issues are eliminated while providing explicit feedback when deployments encounter problems, replacing silent failures with actionable error reporting.