import os
import logging
import time

from flask import Flask, jsonify
from transcript_metrics import snapshot as transcript_metrics_snapshot
from database import db
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_login import LoginManager

# Import version marker
from transcript_service import APP_VERSION

# Configure minimal JSON logging
from logging_setup import configure_logging
configure_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    use_json=os.getenv("USE_MINIMAL_LOGGING", "true").lower() == "true"
)

# create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# configure the database, relative to the app instance folder
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///tldw.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Disable static file caching to ensure fresh JS/CSS on each deploy
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

# Cache-bust token: set once at app startup so all requests in this
# process lifetime use the same value, but a new deploy gets a new one.
_CACHE_BUST = str(int(time.time()))

@app.context_processor
def inject_cache_bust():
    return {"cache_bust": _CACHE_BUST}

# initialize the app with the extension
db.init_app(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'main_routes.index'  # type: ignore

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

def _check_dependencies():
    """Check availability of critical dependencies for ASR functionality"""
    import subprocess
    import shutil
    
    dependencies = {}
    
    # Check ffmpeg
    try:
        ffmpeg_path = shutil.which('ffmpeg')
        if ffmpeg_path:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
            dependencies['ffmpeg'] = {
                'available': True,
                'path': ffmpeg_path,
                'version': result.stdout.split('\n')[0] if result.stdout else 'unknown'
            }
        else:
            dependencies['ffmpeg'] = {'available': False, 'error': 'ffmpeg not found in PATH'}
    except Exception as e:
        dependencies['ffmpeg'] = {'available': False, 'error': str(e)}
    
    # Check ffprobe
    try:
        ffprobe_path = shutil.which('ffprobe')
        if ffprobe_path:
            result = subprocess.run(['ffprobe', '-version'], capture_output=True, text=True, timeout=5)
            dependencies['ffprobe'] = {
                'available': True,
                'path': ffprobe_path,
                'version': result.stdout.split('\n')[0] if result.stdout else 'unknown'
            }
        else:
            dependencies['ffprobe'] = {'available': False, 'error': 'ffprobe not found in PATH'}
    except Exception as e:
        dependencies['ffprobe'] = {'available': False, 'error': str(e)}
    
    return dependencies

def update_download_metadata(used_cookies=False, client_used="unknown"):
    """Update last download metadata for health endpoint exposure"""
    from datetime import datetime
    
    if hasattr(app, 'last_download_meta'):
        app.last_download_meta.update({
            "used_cookies": used_cookies,
            "client_used": client_used,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    # Also update the comprehensive download attempt tracker
    try:
        from download_attempt_tracker import get_global_tracker
        tracker = get_global_tracker()
        # This is called on success, so we track a successful attempt
        tracker.create_attempt(
            video_id="health_update",  # Placeholder for health updates
            success=True,
            cookies_used=used_cookies,
            client_used=client_used,
            proxy_used=False  # We don't have proxy info in this context
        )
    except ImportError:
        # download_attempt_tracker not available, skip enhanced tracking
        pass
    except Exception:
        # Don't fail on tracking errors
        pass

def _log_startup_dependencies():
    """Log dependency status on application startup for fast failure detection"""
    import shutil
    import subprocess
    
    logging.info("=== TL;DW Startup Dependency Check ===")
    
    # Log basic system info
    logging.info(f"Python executable: {shutil.which('python3')}")
    logging.info(f"Working directory: {os.getcwd()}")
    
    # Quick PATH check for critical binaries
    logging.info(f"ffmpeg: {shutil.which('ffmpeg')}")
    logging.info(f"ffprobe: {shutil.which('ffprobe')}")
    
    # Test ffmpeg/ffprobe execution
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        subprocess.run(["ffprobe", "-version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        logging.info("[OK] ffmpeg/ffprobe execution test passed")
    except Exception as e:
        logging.error(f"[ERROR] FFMPEG_NOT_AVAILABLE: {e}")
    
    dependencies = _check_dependencies()
    
    for dep_name, dep_info in dependencies.items():
        if dep_info['available']:
            version = dep_info.get('version', 'unknown')
            path = dep_info.get('path', 'python module')
            logging.info(f"[OK] {dep_name}: {version} (at {path})")
        else:
            error = dep_info.get('error', 'unknown error')
            logging.error(f"[ERROR] {dep_name}: NOT AVAILABLE - {error}")
    
    # Check if critical dependencies are missing
    critical_missing = []
    if not dependencies.get('ffmpeg', {}).get('available'):
        critical_missing.append('ffmpeg')
    if not dependencies.get('ffprobe', {}).get('available'):
        critical_missing.append('ffprobe')
    
    if critical_missing:
        logging.error(f"[CRITICAL] Missing dependencies {critical_missing} - ASR functionality will fail!")
        logging.error("[CRITICAL] Install missing dependencies or check container build process")
        # Don't fail startup for missing dependencies - let health check handle it
        # This allows the service to start and report issues via /health endpoint
    else:
        logging.info("[OK] All critical dependencies available - ASR functionality ready")
    
    logging.info("=== End Dependency Check ===")
    
    return len(critical_missing) == 0

with app.app_context():
    # Import models to ensure tables are created
    import models  # noqa: F401
    
    # Safe database initialization to prevent race conditions between gunicorn workers
    try:
        db.create_all()
        logging.info("Database tables created successfully")
    except Exception as e:
        error_msg = str(e).lower()
        if "already exists" in error_msg or "duplicate" in error_msg:
            logging.info("Database tables already exist, skipping creation")
        else:
            logging.error(f"Database initialization failed: {e}")
            raise
    
    # Initialize download metadata tracking
    app.last_download_meta = {
        "used_cookies": False,
        "client_used": "unknown",
        "timestamp": None
    }
    
    # Log application version on startup
    logging.info(f"App boot version: {APP_VERSION}")
    
    # Log dependency status on startup
    _log_startup_dependencies()
    
    # Validate configuration on startup
    from config_validator import validate_startup_config
    config_valid = validate_startup_config()
    
    if not config_valid:
        logging.warning("[WARNING] Application starting with configuration issues - some features may not work properly")
    
    # Setup secure logging with credential redaction
    from security_manager import setup_secure_logging
    setup_secure_logging()

# Import and register blueprints
from google_auth import google_auth
from routes import main_routes
from cookies_routes import bp_cookies

# Setup after_request handlers before registering blueprints (Fix F)
@app.after_request
def after_request(response):
    """Global after_request handler setup before blueprint registration."""
    response.headers.add('X-Content-Type-Options', 'nosniff')
    response.headers.add('X-Frame-Options', 'DENY')
    response.headers.add('X-XSS-Protection', '1; mode=block')
    return response

app.register_blueprint(google_auth)
app.register_blueprint(main_routes)
app.register_blueprint(bp_cookies)

# Register dashboard integration with registration guard (Fix F)
_dashboard_registered = False
if not _dashboard_registered:
    try:
        from dashboard_integration import register_dashboard_routes
        register_dashboard_routes(app)
        _dashboard_registered = True
        logging.info("Dashboard integration registered successfully")
    except Exception as e:
        logging.warning(f"Failed to register dashboard integration: {e}")

# Structured logging is now initialized via configure_logging() at startup
# Backward compatibility maintained through feature flag USE_MINIMAL_LOGGING

# Initialize performance monitoring
try:
    from performance_monitor import get_performance_monitor
    performance_monitor = get_performance_monitor()
    logging.info("Performance monitoring initialized")
except Exception as e:
    logging.warning(f"Failed to initialize performance monitoring: {e}")

# Add new health endpoints for proxy monitoring
@app.route('/health/live')
def health_live():
    """Always returns 200 if process is running"""
    from datetime import datetime
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.route('/health/ready')
def health_ready():
    """Returns proxy health status from cache (non-recursive)"""
    from flask import jsonify
    from datetime import datetime
    import uuid
    
    def generate_correlation_id():
        return str(uuid.uuid4())
    
    def get_proxy_manager():
        """Factory for ProxyManager with loaded secret and logger"""
        import json
        import logging
        from proxy_manager import ProxyManager
        
        # Load secret from environment
        raw_config = os.getenv('OXYLABS_PROXY_CONFIG', '').strip()
        if not raw_config:
            raise ValueError("OXYLABS_PROXY_CONFIG environment variable is empty")
        
        # Parse JSON secret
        secret_data = json.loads(raw_config)
        logger = logging.getLogger(__name__)
        return ProxyManager(secret_data, logger)
    
    try:
        pm = get_proxy_manager()
        
        # If no cached result, trigger preflight
        if pm.healthy is None:
            try:
                pm.preflight()
            except Exception as e:
                return jsonify({
                    "status": "not_ready", 
                    "proxy_healthy": False, 
                    "reason": str(e)
                }), 503, {"Retry-After": "30"}
        
        # Return cached result
        if pm.healthy:
            return jsonify({"status": "ready", "proxy_healthy": True})
        else:
            return jsonify({
                "status": "not_ready", 
                "proxy_healthy": False
            }), 503, {"Retry-After": "30"}
            
    except Exception as e:
        return jsonify({
            "status": "error", 
            "proxy_healthy": False, 
            "reason": str(e)
        }), 503, {"Retry-After": "30"}

# Enhanced health check endpoints with gated diagnostics
@app.route('/healthz')
def health_check_apprunner():
    """Enhanced health check with gated diagnostics for App Runner deployment"""
    from datetime import datetime
    import os
    
    # Basic health check always available
    basic_health = {"status": "healthy"}
    
    # Detailed diagnostics only when explicitly enabled (default off for security)
    if os.getenv('EXPOSE_HEALTH_DIAGNOSTICS', 'false').lower() == 'true':
        
        # Check ffmpeg availability (boolean only, no path exposure)
        import shutil
        ffmpeg_available = bool(shutil.which("ffmpeg"))
        
        basic_health.update({
            "ffmpeg_available": ffmpeg_available,
            "transcript_metrics": transcript_metrics_snapshot(),
        })
    
    return jsonify(basic_health), 200


@app.route('/health')
def health_check_detailed():
    """Enhanced health check with proxy status and dependency verification"""
    allow_missing_deps = os.getenv('ALLOW_MISSING_DEPS', 'false').lower() == 'true'
    
    health_info = {
        'status': 'healthy', 
        'message': 'TL;DW API is running',
        'proxy_enabled': os.getenv('USE_PROXIES', 'false').lower() == 'true',
        'allow_missing_deps': allow_missing_deps
    }
    
    # Check critical dependencies
    health_info['dependencies'] = _check_dependencies()
    
    # Add configuration validation status
    try:
        from config_validator import config_validator
        config_summary = config_validator.get_config_summary()
        health_info['configuration'] = config_summary
        
        # Update overall health status based on configuration
        if config_summary['validation_status'] != 'valid':
            health_info['status'] = 'degraded'
            health_info['message'] = f"Configuration issues detected ({config_summary['error_count']} errors, {config_summary['warning_count']} warnings)"
    except Exception as e:
        health_info['configuration'] = {'error': f'Configuration validation failed: {str(e)}'}
        health_info['status'] = 'degraded'
    
    # Add security status
    try:
        from security_manager import get_security_status
        health_info['security'] = get_security_status()
    except Exception as e:
        health_info['security'] = {'error': f'Security status check failed: {str(e)}'}
    
    # Add ffmpeg_location
    health_info['ffmpeg_location'] = os.environ.get('FFMPEG_LOCATION')
    
    # Add proxy status if enabled
    if health_info['proxy_enabled']:
        try:
            # Create new ProxyManager with proper initialization
            import json
            import logging
            from proxy_manager import ProxyManager
            
            # Load secret from environment
            raw_config = os.getenv('OXYLABS_PROXY_CONFIG', '').strip()
            if raw_config:
                secret_data = json.loads(raw_config)
                logger = logging.getLogger(__name__)
                proxy_manager = ProxyManager(secret_data, logger)
                
                # Get basic health info
                proxy_health = {
                    'status': 'configured',
                    'has_username': bool(secret_data.get('username')),
                    'has_password': bool(secret_data.get('password')),
                    'provider': secret_data.get('provider', 'unknown')
                }
                proxy_stats = {'enabled': True}
            else:
                proxy_health = {'status': 'not_configured', 'error': 'OXYLABS_PROXY_CONFIG not set'}
                proxy_stats = {'enabled': False}
            
            # Set proxy_config_readable boolean for deployment validation
            proxy_config_readable = (proxy_health.get('status') == 'configured' and 
                                    proxy_health.get('has_username') and 
                                    proxy_health.get('has_password'))
            
            health_info['proxy_status'] = proxy_stats
            health_info['proxy_config'] = proxy_health
            
            # Test proxy connectivity if configuration is readable
            proxy_config_readable = (proxy_health.get('status') == 'configured' and 
                                    proxy_health.get('has_username') and 
                                    proxy_health.get('has_password'))
            
            if proxy_config_readable and 'proxy_manager' in locals():
                try:
                    # Simple connectivity test using preflight
                    proxy_healthy = proxy_manager.preflight(timeout=5.0)
                    health_info['proxy_connectivity'] = {
                        'test_performed': True,
                        'status': 'success' if proxy_healthy else 'failed',
                        'healthy': proxy_healthy
                    }
                except Exception as e:
                    health_info['proxy_connectivity'] = {
                        'test_performed': True,
                        'status': 'error',
                        'error': str(e)
                    }
                    proxy_config_readable = False
                
            else:
                # Always include proxy_connectivity field for consistency
                health_info['proxy_connectivity'] = {
                    "test_performed": False, 
                    "reason": "proxy_config_not_readable"
                }
            
            health_info['secrets'] = {
                'proxy_config_readable': proxy_config_readable
            }
            
            # Add detailed error info only in debug mode
            debug_health = os.getenv('DEBUG_HEALTHZ', 'false').lower() == 'true'
            if not debug_health and 'error' in str(proxy_health):
                # Redact detailed error in production, keep boolean status
                health_info['proxy_config'] = {
                    'status': proxy_health.get('status', 'error'),
                    'source': proxy_health.get('source', 'unknown'),
                    'readable': proxy_config_readable
                }
                
        except Exception as e:
            # Set proxy_config_readable to false on any error
            health_info['secrets'] = {'proxy_config_readable': False}
            health_info['proxy_status'] = {'error': 'proxy_manager_init_failed'}
            
            # Show detailed error only in debug mode
            debug_health = os.getenv('DEBUG_HEALTHZ', 'false').lower() == 'true'
            if debug_health:
                health_info['proxy_config'] = {'error': str(e)}
            else:
                health_info['proxy_config'] = {'status': 'error', 'readable': False}
            
            # Fail health check when proxy manager cannot be initialized and proxies are enabled
            health_info['status'] = 'unhealthy'
            health_info['message'] = f'Proxy connectivity failed: {str(e)}'
            return health_info, 503
    
    # Add diagnostic information if enabled
    if os.getenv('EXPOSE_HEALTH_DIAGNOSTICS', 'false').lower() == 'true':
        try:
            from transcript_service import TranscriptService
            service = TranscriptService()
            diagnostics = service.get_health_diagnostics()
            health_info['diagnostics'] = diagnostics
        except Exception as e:
            health_info['diagnostics'] = {'error': str(e)}
    
    # Determine status and HTTP code based on critical dependencies
    critical_missing = []
    if not health_info['dependencies']['ffmpeg']['available']:
        critical_missing.append('ffmpeg')
    
    if critical_missing:
        if allow_missing_deps:
            # Return 200 with degraded status when ALLOW_MISSING_DEPS=true
            health_info['status'] = 'degraded'
            health_info['degraded'] = True
            health_info['message'] = f'Critical dependencies missing: {", ".join(critical_missing)} (ALLOW_MISSING_DEPS=true)'
            return health_info, 200
        else:
            # Return 503 when critical deps missing in production
            health_info['status'] = 'unhealthy'
            health_info['message'] = f'Critical dependencies missing: {", ".join(critical_missing)}'
            return health_info, 503
    
    # All dependencies available
    health_info['status'] = 'healthy'
    health_info['message'] = 'All dependencies available - ASR functionality ready'
    return health_info, 200


@app.route('/metrics')
def metrics_endpoint():
    """Comprehensive metrics endpoint with stage durations, percentiles, and circuit breaker events"""
    try:
        from transcript_metrics import get_comprehensive_metrics
        from transcript_service import get_circuit_breaker_status
        
        # Get comprehensive metrics including percentiles and recent events
        metrics = get_comprehensive_metrics()
        
        # Add circuit breaker status
        metrics['circuit_breaker_status'] = get_circuit_breaker_status()
        
        # Add timestamp for metrics collection
        from datetime import datetime
        metrics['timestamp'] = datetime.utcnow().isoformat()
        
        return jsonify(metrics), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Failed to collect metrics',
            'details': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@app.route('/metrics/percentiles')
def metrics_percentiles():
    """Stage duration percentiles for dashboard integration"""
    try:
        from transcript_metrics import get_stage_percentiles
        
        # Calculate percentiles for all known stages
        stages = ["yt_api", "timedtext", "youtubei", "asr"]
        percentiles = {}
        
        for stage in stages:
            percentiles[stage] = get_stage_percentiles(stage)
        
        return jsonify({
            'stage_percentiles': percentiles,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Failed to calculate percentiles',
            'details': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@app.errorhandler(Exception)
def handle_exc(e):
    from flask import jsonify
    code = getattr(e, "code", 500)
    return jsonify({"error": str(e)}), code
