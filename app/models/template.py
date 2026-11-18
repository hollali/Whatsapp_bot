import uuid
from datetime import datetime

from app.extensions import db


class Template(db.Model):
    __tablename__ = "templates"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    body = db.Column(db.Text, nullable=False)
    variables = db.Column(db.String(255))  # comma-separated hint
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "body": self.body, "variables": self.variables}
