from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from flask_socketio import SocketIO

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
mail = Mail()
csrf = CSRFProtect()
socketio = SocketIO(async_mode="threading")


def init_extensions(app: Flask):
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "web.login"
    mail.init_app(app)
    csrf.init_app(app)
    socketio.init_app(app, cors_allowed_origins=app.config.get("SOCKETIO_CORS_ORIGINS"))
