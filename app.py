import os
import logging

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_login import LoginManager

# Set up logging for debugging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

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
    
    # Check yt-dlp
    try:
        import yt_dlp
        dependencies['yt_dlp'] = {
            'available': True,
            'version': yt_dlp.version.__version__
        }
    except Exception as e:
        dependencies['yt_dlp'] = {'available': False, 'error': str(e)}
    
    return dependencies

def _log_startup_dependencies():
    """Log dependency status on application startup for fast failure detection"""
    import shutil
    import subprocess
    
    logging.info("=== TL;DW Startup Dependency Check ===")
    
    # Log basic system info
    logging.info(f"Python executable: {shutil.which('python3')}")
    logging.info(f"Working directory: {os.getcwd()}")
    
    # Quick PATH check for critical binaries
    logging.info(f"yt-dlp: {shutil.which('yt-dlp')}")
    logging.info(f"ffmpeg: {shutil.which('ffmpeg')}")
    logging.info(f"ffprobe: {shutil.which('ffprobe')}")
    
    # Test ffmpeg/ffprobe execution
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        subprocess.run(["ffprobe", "-version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        logging.info("✅ ffmpeg/ffprobe execution test passed")
    except Exception as e:
        logging.error(f"❌ FFMPEG_NOT_AVAILABLE: {e}")
    
    dependencies = _check_dependencies()
    
    for dep_name, dep_info in dependencies.items():
        if dep_info['available']:
            version = dep_info.get('version', 'unknown')
            path = dep_info.get('path', 'python module')
            logging.info(f"✅ {dep_name}: {version} (at {path})")
        else:
            error = dep_info.get('error', 'unknown error')
            logging.error(f"❌ {dep_name}: NOT AVAILABLE - {error}")
    
    # Check if critical dependencies are missing
    critical_missing = []
    if not dependencies.get('ffmpeg', {}).get('available'):
        critical_missing.append('ffmpeg')
    if not dependencies.get('ffprobe', {}).get('available'):
        critical_missing.append('ffprobe')
    if not dependencies.get('yt_dlp', {}).get('available'):
        critical_missing.append('yt-dlp')
    
    if critical_missing:
        logging.error(f"🚨 CRITICAL: Missing dependencies {critical_missing} - ASR functionality will fail!")
        logging.error("🔧 Install missing dependencies or check container build process")
        # Don't fail startup for missing dependencies - let health check handle it
        # This allows the service to start and report issues via /health endpoint
    else:
        logging.info("✅ All critical dependencies available - ASR functionality ready")
    
    logging.info("=== End Dependency Check ===")
    
    return len(critical_missing) == 0

with app.app_context():
    # Import models to ensure tables are created
    import models  # noqa: F401
    db.create_all()
    
    # Log dependency status on startup
    _log_startup_dependencies()

# Import and register blueprints
from google_auth import google_auth
from routes import main_routes
from cookies_routes import bp_cookies

app.register_blueprint(google_auth)
app.register_blueprint(main_routes)
app.register_blueprint(bp_cookies)

# Add health check endpoints for App Runner
@app.route('/health')
@app.route('/healthz')
def health_check():
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
    
    # Add ffmpeg_location and yt_dlp_version fields
    health_info['ffmpeg_location'] = os.environ.get('FFMPEG_LOCATION')
    
    # Extract yt-dlp version from dependencies
    yt_dlp_dep = health_info['dependencies'].get('yt_dlp', {})
    if yt_dlp_dep.get('available'):
        health_info['yt_dlp_version'] = yt_dlp_dep.get('version', 'unknown')
    else:
        health_info['yt_dlp_version'] = None
    
    # Add proxy status if enabled
    if health_info['proxy_enabled']:
        try:
            from proxy_manager import ProxyManager
            proxy_manager = ProxyManager()
            proxy_stats = proxy_manager.get_session_stats()
            proxy_health = proxy_manager.get_proxy_health_info()
            
            # Set proxy_config_readable boolean for deployment validation
            proxy_config_readable = (proxy_health.get('status') == 'configured' and 
                                    proxy_health.get('has_username') and 
                                    proxy_health.get('has_password'))
            
            health_info['proxy_status'] = proxy_stats
            health_info['proxy_config'] = proxy_health
            
            # Test proxy connectivity if configuration is readable
            if proxy_config_readable:
                proxy_test = proxy_manager.test_proxy_connectivity()
                health_info['proxy_connectivity'] = proxy_test
                
                # Update proxy_config_readable based on actual connectivity
                if proxy_test.get('status') == 'success':
                    proxy_config_readable = True
                elif proxy_test.get('status') in ['failed', 'error']:
                    proxy_config_readable = False
                    # Log the connectivity issue for debugging
                    logging.warning(f"Proxy connectivity test failed: {proxy_test}")
            
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
    if not health_info['dependencies']['yt_dlp']['available']:
        critical_missing.append('yt-dlp')
    
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
