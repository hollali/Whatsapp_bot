import os

from flask import Flask, jsonify, redirect, request, url_for
from flask_login import current_user

from app.config import get_config
from app.extensions import db, init_extensions
from app.models import User  # noqa: F401
from app.models.apikey import ApiKey
from app.services.scheduler import Scheduler
from app.utils import api_key_hash, utcnow


def create_app(config=None):
    app = Flask(__name__, template_folder="web/templates", static_folder="web/static")
    cfg = config or get_config()
    app.config.from_object(cfg)

    init_extensions(app)

    from app.api import api_bp, rate_limit_request, register_api_errors
    from app.web import web_bp

    register_api_errors(app)
    app.register_blueprint(api_bp, url_prefix="/api/v1")
    app.register_blueprint(web_bp)

    from app.extensions import login_manager, socketio

    login_manager.login_view = "web.login"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, user_id)

    @login_manager.request_loader
    def load_user_from_request(incoming_request):
        digest = api_key_hash(incoming_request)
        if not digest:
            return None
        key = ApiKey.query.filter_by(key_hash=digest, revoked=False).first()
        if not key:
            return None
        user = db.session.get(User, key.user_id)
        if not user:
            return None
        key.last_used_at = utcnow()
        db.session.commit()
        return user

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith("/api/v1"):
            return jsonify({"error": "unauthorized"}), 401
        return redirect(url_for("web.login"))

    @socketio.on("connect")
    def on_connect(auth=None):
        if current_user.is_authenticated:
            from flask_socketio import join_room
            join_room("user:" + current_user.id)

    @app.before_request
    def apply_rate_limit():
        return rate_limit_request()

    os.makedirs(app.config.get("UPLOAD_FOLDER", "uploads"), exist_ok=True)

    if app.config.get("AUTO_CREATE_TABLES", True):
        with app.app_context():
            db.create_all()

    if not app.config.get("TESTING") and app.config.get("ENABLE_SCHEDULER", True):
        scheduler = Scheduler(app, interval=app.config.get("SCHEDULER_INTERVAL", 10))
        scheduler.start()
        app.scheduler = scheduler

    return app
