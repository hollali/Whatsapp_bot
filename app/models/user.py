import uuid
from datetime import datetime

from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120))
    role = db.Column(db.String(32), default="user", nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contacts = db.relationship("Contact", backref="owner", lazy="dynamic", cascade="all, delete-orphan")
    templates = db.relationship("Template", backref="owner", lazy="dynamic", cascade="all, delete-orphan")
    campaigns = db.relationship("Campaign", backref="owner", lazy="dynamic", cascade="all, delete-orphan")
    api_keys = db.relationship("ApiKey", backref="owner", lazy="dynamic", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {"id": self.id, "email": self.email, "name": self.name, "role": self.role}
