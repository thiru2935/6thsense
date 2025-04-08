import os
import logging
import json

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_login import LoginManager

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)
# create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # needed for url_for to generate with https

# configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize database
db.init_app(app)

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

with app.app_context():
    # Import models
    import models
    db.create_all()
    
    # Import routes
    from routes.auth import auth_bp
    from routes.patient import patient_bp
    from routes.provider import provider_bp
    from routes.api import api_bp
    from routes.chatbot import chatbot_bp
    from routes.emr_integration import emr_bp
    
    # Initialize default data
    from services.questionnaire import create_default_questions
    try:
        create_default_questions()
    except Exception as e:
        app.logger.error(f"Error creating default questions: {e}")
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(patient_bp)
    app.register_blueprint(provider_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(chatbot_bp)
    app.register_blueprint(emr_bp)
    
    # Load user for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        return models.User.query.get(int(user_id))
    
    # Context processor to add date to all templates
    @app.context_processor
    def inject_now():
        from datetime import datetime
        return {'now': datetime.utcnow()}
    
    # Template filters
    @app.template_filter('from_json')
    def from_json(value):
        if not value:
            return []
        try:
            return json.loads(value)
        except Exception as e:
            app.logger.error(f"Error parsing JSON: {e}")
            return []
        
    # Main route
    @app.route('/')
    def index():
        from flask import render_template
        return render_template('index.html')
