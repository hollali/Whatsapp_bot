import uuid

from app.extensions import db
from app.utils import utc_iso, utcnow


class ScheduledJob(db.Model):
    __tablename__ = "scheduled_jobs"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    campaign_id = db.Column(db.String(36), db.ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True)
    contact_id = db.Column(db.String(36), db.ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True)
    phone = db.Column(db.String(32), nullable=False)
    message = db.Column(db.Text, nullable=False)
    provider = db.Column(db.String(32), default="pywhatkit")
    run_at = db.Column(db.DateTime, nullable=False, index=True)
    status = db.Column(db.String(32), default="pending", nullable=False, index=True)  # pending/running/success/failed/cancelled
    attempts = db.Column(db.Integer, default=0, nullable=False)
    max_attempts = db.Column(db.Integer, default=3, nullable=False)
    last_error = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)

    contact = db.relationship("Contact")

    def to_dict(self):
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "phone": self.phone,
            "message": self.message,
            "status": self.status,
            "provider": self.provider,
            "run_at": utc_iso(self.run_at),
            "finished_at": utc_iso(self.finished_at),
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "last_error": self.last_error,
        }


class DeliveryLog(db.Model):
    __tablename__ = "delivery_logs"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    job_id = db.Column(db.String(36), db.ForeignKey("scheduled_jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    campaign_id = db.Column(db.String(36), db.ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True)
    phone = db.Column(db.String(32), nullable=False)
    status = db.Column(db.String(32), nullable=False)  # success/failed
    error = db.Column(db.Text)
    provider = db.Column(db.String(32))
    duration_ms = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
