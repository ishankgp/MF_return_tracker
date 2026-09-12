import os
import logging
from datetime import timedelta
from flask import Flask, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

try:
    from flask_session import Session
except Exception:  # pragma: no cover
    Session = None

from config import get_config
from mf_tracker.core.extensions import login_manager, oauth, cors, init_caches

def create_app(config_object=None):
    load_dotenv()
    
    app = Flask(__name__)
    if config_object:
        app.config.from_object(config_object)
    else:
        app.config.from_object(get_config())
        
    secret_key = app.config.get("SECRET_KEY")
    if not secret_key and app.config.get("FLASK_ENV", "development") == "production":
        raise ValueError("SECRET_KEY must be set in production")
    app.secret_key = secret_key or "dev-secret-key"

    # Setup Logging
    IS_VERCEL = os.environ.get("VERCEL") == "1"
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.getenv("DATA_DIR", BASE_DIR)
    logs_dir = os.path.join(DATA_DIR, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    log_handlers = [logging.StreamHandler()]
    if not IS_VERCEL:
        log_handlers.append(logging.FileHandler(os.path.join(logs_dir, "app.log"), encoding="utf-8"))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=log_handlers,
    )

    # Init extensions
    cors.init_app(app)
    login_manager.init_app(app)
    
    oauth.init_app(app)
    oauth.register(
        name="google",
        client_id=app.config.get("GOOGLE_CLIENT_ID"),
        client_secret=app.config.get("GOOGLE_CLIENT_SECRET"),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

    redis_client = init_caches(app)

    if redis_client and Session is not None:
        app.config["SESSION_TYPE"] = "redis"
        app.config["SESSION_REDIS"] = redis_client
        app.config["SESSION_PERMANENT"] = True
        app.config["SESSION_USE_SIGNER"] = True
        app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
        Session(app)
        app.logger.info("Redis-based sessions enabled")
    else:
        app.logger.info("Using default cookie-based sessions")

    # Import and register blueprints
    from mf_tracker.api.auth import auth_bp
    from mf_tracker.api.funds import funds_bp, research_bp, refresh_bp
    from mf_tracker.api.notes import notes_bp
    from mf_tracker.web.views import web_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(funds_bp)
    app.register_blueprint(research_bp)
    app.register_blueprint(refresh_bp)
    app.register_blueprint(notes_bp)
    app.register_blueprint(web_bp)

    @app.route("/favicon.ico")
    def favicon():
        return send_from_directory(os.path.join(app.root_path, "static"), "favicon.ico", mimetype="image/vnd.microsoft.icon")

    return app

if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", 5000))
    app.run(host="127.0.0.1", port=port)
