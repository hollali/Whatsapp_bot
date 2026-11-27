import os
from datetime import timedelta

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(path):
        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip().strip('"\''))


BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_SAMESITE = "Lax"
    RATE_LIMIT_ENABLED = os.environ.get("RATE_LIMIT_ENABLED", "true").lower() == "true"
    MAX_BULK_JOBS = int(os.environ.get("MAX_BULK_JOBS", 500))
    SOCKETIO_CORS_ORIGINS = [origin for origin in os.environ.get("SOCKETIO_CORS_ORIGINS", "").split(",") if origin] or None
    ENABLE_SCHEDULER = os.environ.get("ENABLE_SCHEDULER", "true").lower() == "true"
    AUTO_CREATE_TABLES = os.environ.get("AUTO_CREATE_TABLES", "true").lower() == "true"
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'whatsapp_bot.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAIL_SERVER = os.environ.get("MAIL_SERVER")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@whatsapp-bot.local")
    SCHEDULER_INTERVAL = int(os.environ.get("SCHEDULER_INTERVAL", 10))
    MAX_RETRIES = int(os.environ.get("MAX_RETRIES", 3))
    RETRY_BACKOFF = int(os.environ.get("RETRY_BACKOFF", 60))
    WHATSAPP_PROVIDER = os.environ.get("WHATSAPP_PROVIDER", "pywhatkit")
    API_RATE_LIMIT = os.environ.get("API_RATE_LIMIT", "100 per minute")
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    RATE_LIMIT_ENABLED = False


CONFIGS = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config():
    env = os.environ.get("APP_ENV", "development")
    cfg = CONFIGS.get(env, DevelopmentConfig)
    if env == "production" and cfg.SECRET_KEY == "dev-secret-change-me":
        raise RuntimeError("SECRET_KEY must be set in production")
    return cfg
