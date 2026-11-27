from flask import current_app
from sqlalchemy import or_, update

from app.extensions import db
from app.models.campaign import Campaign
from app.models.schedule import DeliveryLog, ScheduledJob
from app.utils import utcnow


class QueueService:
    def enqueue(self, user_id, phone, message, run_at=None, campaign_id=None, contact_id=None,
                provider="pywhatkit", max_attempts=None):
        if max_attempts is None:
            max_attempts = current_app.config.get("MAX_RETRIES", 3)
        job = ScheduledJob(
            user_id=user_id,
            phone=phone,
            message=message,
            run_at=run_at or utcnow(),
            campaign_id=campaign_id,
            contact_id=contact_id,
            provider=provider,
            max_attempts=max_attempts,
        )
        db.session.add(job)
        db.session.commit()
        return job

    def cancel(self, job_id, user_id=None):
        q = ScheduledJob.query.filter_by(id=job_id, status="pending")
        if user_id:
            q = q.filter_by(user_id=user_id)
        job = q.first()
        if not job:
            return False
        job.status = "cancelled"
        db.session.commit()
        return True

    def retry(self, job_id, user_id=None):
        q = ScheduledJob.query.filter_by(id=job_id)
        if user_id:
            q = q.filter_by(user_id=user_id)
        job = q.first()
        if not job or job.status not in ("failed", "cancelled"):
            return None
        job.status = "pending"
        job.attempts = 0
        job.last_error = None
        job.run_at = utcnow()
        db.session.commit()
        return job

    def claim(self, job_id):
        result = db.session.execute(
            update(ScheduledJob)
            .where(ScheduledJob.id == job_id, ScheduledJob.status == "pending")
            .values(status="running", started_at=utcnow(), attempts=ScheduledJob.attempts + 1)
        )
        db.session.commit()
        return result.rowcount == 1

    def due_jobs(self, limit=50):
        now = utcnow()
        q = ScheduledJob.query.filter(
            ScheduledJob.status == "pending", ScheduledJob.run_at <= now
        )
        paused = [c.id for c in Campaign.query.filter_by(status="paused").all()]
        if paused:
            q = q.filter(or_(ScheduledJob.campaign_id.is_(None), ScheduledJob.campaign_id.notin_(paused)))
        return q.order_by(ScheduledJob.run_at.asc()).limit(limit).all()

    def log_delivery(self, job, status, error=None, duration_ms=None):
        entry = DeliveryLog(
            user_id=job.user_id,
            job_id=job.id,
            campaign_id=job.campaign_id,
            phone=job.phone,
            status=status,
            error=error,
            provider=job.provider,
            duration_ms=duration_ms,
        )
        db.session.add(entry)
        db.session.commit()
        return entry

    def stats(self, user_id=None):
        q = DeliveryLog.query
        if user_id:
            q = q.filter_by(user_id=user_id)
        total = q.count()
        success = q.filter_by(status="success").count()
        failed = q.filter_by(status="failed").count()
        return {"total": total, "success": success, "failed": failed}
