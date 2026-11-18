import uuid
from datetime import datetime

from app.extensions import db


class ApiKey(db.Model):
    __tablename__ = "api_keys"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    key_hash = db.Column(db.String(255), nullable=False, unique=True)
    prefix = db.Column(db.String(12), nullable=False)
    last_used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    revoked = db.Column(db.Boolean, default=False, nullable=False)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "prefix": self.prefix, "revoked": self.revoked}
