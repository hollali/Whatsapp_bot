import uuid
from datetime import datetime

from app.extensions import db


class Campaign(db.Model):
    __tablename__ = "campaigns"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    template_id = db.Column(db.String(36), db.ForeignKey("templates.id"), nullable=True)
    message = db.Column(db.Text)
    status = db.Column(db.String(32), default="draft", nullable=False)  # draft/running/paused/completed/failed
    scheduled_at = db.Column(db.DateTime)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    total = db.Column(db.Integer, default=0)
    sent = db.Column(db.Integer, default=0)
    failed = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    template = db.relationship("Template")
    jobs = db.relationship("ScheduledJob", backref="campaign", lazy="dynamic", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "total": self.total,
            "sent": self.sent,
            "failed": self.failed,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
        }
