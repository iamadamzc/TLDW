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

# Import and register blueprints
from google_auth import google_auth
from routes import main_routes

app.register_blueprint(google_auth)
app.register_blueprint(main_routes)

# Add health check endpoint for App Runner
@app.route('/health')
def health_check():
    """Enhanced health check with proxy status information"""
    health_info = {
        'status': 'healthy', 
        'message': 'TL;DW API is running',
        'proxy_enabled': os.getenv('USE_PROXIES', 'false').lower() == 'true'
    }
    
    # Add proxy status if enabled
    if health_info['proxy_enabled']:
        try:
            from proxy_manager import ProxyManager
            proxy_manager = ProxyManager()
            proxy_stats = proxy_manager.get_session_stats()
            health_info['proxy_status'] = proxy_stats
        except Exception as e:
            health_info['proxy_status'] = {'error': str(e)}
    
    return health_info, 200
