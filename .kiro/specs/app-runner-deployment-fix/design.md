# Design Document

## Overview

This design addresses the App Runner deployment failures by providing two corrected configuration approaches: a fixed Docker runtime configuration and a recommended Python runtime configuration. Additionally, it includes cleanup of unused files and troubleshooting artifacts that are cluttering the codebase. The current issue stems from mixing Docker and Python runtime syntax in the `apprunner.yaml` file, which causes App Runner to fail during service creation.

## Architecture

### Current Problem Analysis

The existing `apprunner.yaml` contains several configuration errors:
1. Uses `runtime: docker` but includes Python runtime-style build commands
2. Includes unnecessary `run` section when using Docker (CMD in Dockerfile should handle this)
3. Port configuration conflicts between Docker (8000) and App Runner Python convention (8080)
4. Missing proper Docker-specific syntax for image specification

### Solution Architecture

We will provide two distinct deployment paths and clean up the codebase:

**Path A: Fixed Docker Runtime**
- Correct `apprunner.yaml` syntax for Docker runtime
- Leverage existing Dockerfile
- Maintain current port 8000 configuration
- Remove conflicting Python runtime syntax

**Path B: Python Runtime (Recommended)**
- Switch to App Runner's managed Python runtime
- Eliminate Dockerfile dependency
- Use App Runner's port 8080 convention
- Simplified configuration and faster deployments

**Codebase Cleanup**
- Remove unused test files and troubleshooting artifacts
- Clean up duplicate or obsolete configuration files
- Organize remaining files with clear purpose documentation

## Components and Interfaces

### File Cleanup Strategy

#### Files to Remove
- `test-app.py` - Troubleshooting artifact, conflicts with main app
- Any duplicate or test configuration files
- Temporary files created during debugging
- Unused deployment scripts or configurations

#### Files to Keep
- `app.py` - Main Flask application
- `main.py` - Application entry point
- `requirements.txt` - Dependencies (needs fixing)
- `Dockerfile` - For Docker runtime approach
- `apprunner.yaml` - Deployment configuration (needs fixing)

### Configuration Files

#### Docker Runtime Configuration
```yaml
version: 1.0
runtime: docker
build:
  dockerfile: Dockerfile
```

#### Python Runtime Configuration
```yaml
version: 1.0
runtime: python3
build:
  commands:
    build:
      - pip install -r requirements.txt
run:
  command: gunicorn --bind 0.0.0.0:8080 --workers 1 app:app
  network:
    port: 8080
```

### Application Components

#### Flask Application Structure
- Main application: `app.py` (Flask app instance)
- Entry point: `main.py` (imports from app.py)
- Health check endpoint: `/health` (already implemented)
- Dependencies: Defined in `requirements.txt`

#### Port Configuration Strategy
- Docker approach: Maintain port 8000 (matches existing Dockerfile)
- Python approach: Use port 8080 (App Runner convention)
- Health check endpoint works on both ports

## Data Models

### Configuration Models

#### Docker Runtime Model
```yaml
version: string (1.0)
runtime: string (docker)
build:
  dockerfile: string (path to Dockerfile)
```

#### Python Runtime Model
```yaml
version: string (1.0)
runtime: string (python3)
build:
  commands:
    build: array of strings
run:
  command: string
  network:
    port: integer
```

### Dependency Model
The `requirements.txt` file needs correction - currently has a malformed entry:
```
psycopg2-binaryguni
corn==21.2.0
```
Should be:
```
psycopg2-binary==2.9.9
gunicorn==21.2.0
```

## Error Handling

### Deployment Failure Scenarios

1. **Invalid apprunner.yaml syntax**
   - Detection: App Runner CREATE_FAILED status
   - Resolution: Validate YAML syntax and runtime-specific requirements

2. **Port binding conflicts**
   - Detection: Service starts but health checks fail
   - Resolution: Ensure application port matches apprunner.yaml configuration

3. **Missing dependencies**
   - Detection: Build failures during pip install
   - Resolution: Fix requirements.txt syntax errors

4. **Dockerfile conflicts (Python runtime)**
   - Detection: Unexpected build behavior
   - Resolution: Remove or rename Dockerfile when using Python runtime

### Health Check Strategy

The existing `/health` endpoint provides:
```python
@app.route('/health')
def health_check():
    return {'status': 'healthy', 'message': 'TL;DW API is running'}, 200
```

This endpoint will work for both Docker and Python runtime approaches.

## Testing Strategy

### Configuration Validation
1. **YAML Syntax Testing**
   - Validate apprunner.yaml against App Runner schema
   - Test both Docker and Python runtime configurations

2. **Local Testing**
   - Docker approach: Test with `docker build` and `docker run`
   - Python approach: Test with local gunicorn command

3. **Deployment Testing**
   - Create test App Runner services with each configuration
   - Verify successful deployment and health check responses

### Integration Testing
1. **End-to-End Deployment**
   - Test complete GitHub → App Runner deployment pipeline
   - Verify service accessibility and functionality

2. **Health Check Validation**
   - Confirm `/health` endpoint responds correctly
   - Test App Runner service health monitoring

### Rollback Strategy
1. **Configuration Backup**
   - Preserve current apprunner.yaml as backup
   - Document rollback steps if new configuration fails

2. **Incremental Deployment**
   - Test Docker runtime fix first (minimal changes)
   - If successful, optionally migrate to Python runtime

## Implementation Approach

### Phase 1: Codebase Cleanup
- Identify and remove unused/troubleshooting files
- Clean up duplicate configurations
- Organize remaining files with clear documentation

### Phase 2: Fix Docker Runtime (Low Risk)
- Correct existing apprunner.yaml for proper Docker syntax
- Fix requirements.txt syntax errors
- Update Dockerfile if needed
- Test deployment with minimal changes

### Phase 3: Python Runtime Option (Recommended)
- Create alternative Python runtime configuration
- Update documentation with both approaches
- Provide migration guide

This design ensures both immediate problem resolution, codebase organization, and long-term deployment optimization.