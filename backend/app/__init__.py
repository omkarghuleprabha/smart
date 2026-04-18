import os
from flask import Flask, jsonify  # ✅ FIXED: Added jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv  # ✅ FIXED: Now works after pip install

# Load environment variables FIRST
load_dotenv()

# Initialize extensions (module-level)
db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
jwt = JWTManager()

def create_app(config_name='default'):
    """
    Factory function to create Flask application
    """
    # Set base directory
    BASE_DIR = r"D:\INTERSHIP\Garbage Management System\Garbage Management System\smart-garbage-management"
    
    # Create app instance
    app = Flask(__name__, 
                template_folder=os.path.join(BASE_DIR, 'backend', 'app', 'templates'),
                static_folder=os.path.join(BASE_DIR, 'backend', 'app', 'static'),
                instance_relative_config=True)
    
    # Load config from config.py
    from .config import config
    app.config.from_object(config[config_name])
    
    # Override with environment variables
    app.config.from_prefixed_env()
    
    # ========================================
    # JWT Configuration (Secure)
    # ========================================
    app.config.setdefault('JWT_SECRET_KEY', os.environ.get('JWT_SECRET_KEY', app.config['SECRET_KEY']))
    app.config.setdefault('JWT_ACCESS_TOKEN_EXPIRES', False)
    app.config.setdefault('JWT_TOKEN_LOCATION', ['cookies', 'headers', 'json'])
    app.config.setdefault('JWT_COOKIE_CSRF_PROTECT', True)
    app.config.setdefault('JWT_COOKIE_SECURE', app.config.get('SESSION_COOKIE_SECURE', False))
    
    # ========================================
    # Initialize Extensions
    # ========================================
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    jwt.init_app(app)
    CORS(app, supports_credentials=True)
    
    # Login Manager Configuration
    login_manager.login_view = 'auth_bp.login'
    login_manager.login_message_category = 'info'
    login_manager.session_protection = 'strong'
    
    # ========================================
    # Register Blueprints (Safe imports)
    # ========================================
    try:
        from .routes.main_routes import main_bp
        from .routes.auth_routes import auth_bp
        from .routes.admin_routes import admin_bp
        from .routes.user_routes import user_bp
        from .routes.api_routes import api_bp
        
        app.register_blueprint(main_bp)
        app.register_blueprint(auth_bp, url_prefix='/auth')
        app.register_blueprint(admin_bp, url_prefix='/admin')
        app.register_blueprint(user_bp, url_prefix='/user')
        app.register_blueprint(api_bp)
        
    except ImportError as e:
        app.logger.warning(f"Blueprint import failed (normal during dev): {e}")
    
    # ========================================
    # Database Setup
    # ========================================
    with app.app_context():
        db.create_all()
        
        @app.route('/health')
        def health_check():
            return jsonify({
                'status': 'healthy',
                'database': db.engine.has_table('users') if hasattr(db, 'engine') else False,
                'timestamp': os.popen('date').read().strip()
            })
    
    # ========================================
    # JWT Error Handlers ✅ FIXED jsonify
    # ========================================
    @app.errorhandler(401)
    def jwt_unauthorized(e):
        return jsonify({'message': 'Missing or invalid token', 'error': 'unauthorized'}), 401
    
    @app.errorhandler(403)
    def jwt_forbidden(e):
        return jsonify({'message': 'Access forbidden', 'error': 'forbidden'}), 403
    
    # Flask-Login unauthorized handler
    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify({'message': 'Login required', 'error': 'unauthorized'}), 401
    
    # ========================================
    # Shell Context Processor
    # ========================================
    @app.shell_context_processor
    def make_shell_context():
        return dict(app=app, db=db, bcrypt=bcrypt)
    
    return app

@login_manager.user_loader
def load_user(user_id):
    """Load user from database for Flask-Login"""
    try:
        from app.models.user_model import DistrictAdmin, TalukaAdmin, VillageWorker, CitizenUser
        
        # Try different user types
        users = [DistrictAdmin, TalukaAdmin, VillageWorker, CitizenUser]
        for UserClass in users:
            if hasattr(UserClass, 'query'):
                user = UserClass.query.get(int(user_id))
                if user:
                    return user
    except ImportError:
        pass
    return None