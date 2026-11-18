from datetime import datetime

from app.extensions import db
from app.models.schedule import ScheduledJob, DeliveryLog


class QueueService:
    def enqueue(self, user_id, phone, message, run_at=None, campaign_id=None, contact_id=None,
                provider="pywhatkit", max_attempts=3):
        job = ScheduledJob(
            user_id=user_id,
            phone=phone,
            message=message,
            run_at=run_at or datetime.utcnow(),
            campaign_id=campaign_id,
            contact_id=contact_id,
            provider=provider,
            max_attempts=max_attempts,
        )
        db.session.add(job)
        db.session.commit()
        return job

    def cancel(self, job_id, user_id=None):
        q = ScheduledJob.query.filter_by(id=job_id)
        if user_id:
            q = q.filter_by(user_id=user_id)
        job = q.first()
        if not job:
            return False
        if job.status in ("success", "failed", "cancelled"):
            return False
        job.status = "cancelled"
        db.session.commit()
        return True

    def retry(self, job_id):
        job = ScheduledJob.query.get(job_id)
        if not job:
            return None
        job.status = "pending"
        job.attempts = 0
        job.last_error = None
        job.run_at = datetime.utcnow()
        db.session.commit()
        return job

    def due_jobs(self, limit=50):
        now = datetime.utcnow()
        return (
            ScheduledJob.query
            .filter(ScheduledJob.status == "pending", ScheduledJob.run_at <= now)
            .order_by(ScheduledJob.run_at.asc())
            .limit(limit)
            .all()
        )

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
