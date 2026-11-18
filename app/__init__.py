import os

from flask import Flask

from app.config import get_config
from app.extensions import init_extensions
from app.models import User  # noqa: F401
from app.services.scheduler import Scheduler


def create_app(config=None):
    app = Flask(__name__, template_folder="web/templates", static_folder="web/static")
    cfg = config or get_config()
    app.config.from_object(cfg)

    init_extensions(app)

    # register blueprints
    from app.api import api_bp
    from app.web import web_bp

    app.register_blueprint(api_bp, url_prefix="/api/v1")
    app.register_blueprint(web_bp)

    # login manager
    from app.extensions import login_manager

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(user_id)

    # ensure upload folder
    os.makedirs(app.config.get("UPLOAD_FOLDER", "uploads"), exist_ok=True)

    # create tables if missing (dev convenience)
    with app.app_context():
        from app.extensions import db
        db.create_all()

    # scheduler (after tables exist)
    scheduler = Scheduler(app, interval=app.config.get("SCHEDULER_INTERVAL", 10))
    app.scheduler = scheduler
    if not app.config.get("TESTING"):
        scheduler.start()

    @app.teardown_appcontext
    def shutdown_scheduler(exception=None):
        pass

    return app
