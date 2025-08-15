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

with app.app_context():
    # Import models to ensure tables are created
    import models  # noqa: F401
    db.create_all()
    
    # Log dependency status on startup
    _log_startup_dependencies()

# Import and register blueprints
from google_auth import google_auth
from routes import main_routes

app.register_blueprint(google_auth)
app.register_blueprint(main_routes)

# Add health check endpoint for App Runner
@app.route('/health')
def health_check():
    """Enhanced health check with proxy status and dependency verification"""
    health_info = {
        'status': 'healthy', 
        'message': 'TL;DW API is running',
        'proxy_enabled': os.getenv('USE_PROXIES', 'false').lower() == 'true'
    }
    
    # Check critical dependencies
    health_info['dependencies'] = _check_dependencies()
    
    # Add proxy status if enabled
    if health_info['proxy_enabled']:
        try:
            from proxy_manager import ProxyManager
            proxy_manager = ProxyManager()
            proxy_stats = proxy_manager.get_session_stats()
            health_info['proxy_status'] = proxy_stats
        except Exception as e:
            health_info['proxy_status'] = {'error': str(e)}
    
    # Set overall status based on critical dependencies
    if not health_info['dependencies']['ffmpeg']['available'] or not health_info['dependencies']['yt_dlp']['available']:
        health_info['status'] = 'degraded'
        health_info['message'] = 'Some dependencies missing - ASR functionality may be impaired'
    
    return health_info, 200

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
    logging.info("=== TL;DW Startup Dependency Check ===")
    
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
    else:
        logging.info("✅ All critical dependencies available - ASR functionality ready")
    
    logging.info("=== End Dependency Check ===")
    
    return len(critical_missing) == 0
