import threading
import time
from datetime import timedelta

from flask import current_app

from app.extensions import db
from app.services.queue import QueueService
from app.services.sender import SenderService
from app.utils import utcnow


class Scheduler:
    def __init__(self, app, interval=10):
        self.app = app
        self.interval = interval
        self.queue = QueueService()
        self._thread = None
        self._stop = threading.Event()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="wa-scheduler")
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self):
        while not self._stop.is_set():
            try:
                with self.app.app_context():
                    self._tick()
            except Exception as e:
                self.app.logger.exception("Scheduler tick failed: %s", e)
            self._stop.wait(self.interval)

    def _tick(self):
        for job in self.queue.due_jobs():
            self._process(job)

    def _emit(self, job, status):
        try:
            from app.extensions import socketio
            socketio.emit("job_update", {
                "id": job.id,
                "status": status,
                "phone": job.phone,
                "campaign_id": job.campaign_id,
            }, to="user:" + job.user_id)
        except Exception:
            pass

    def _finalize_campaign(self, campaign_id):
        if not campaign_id:
            return
        from app.models.campaign import Campaign
        from app.models.schedule import ScheduledJob
        campaign = Campaign.query.get(campaign_id)
        if not campaign or campaign.status not in ("running", "scheduled"):
            return
        pending = ScheduledJob.query.filter_by(campaign_id=campaign_id).filter(
            ScheduledJob.status.in_(("pending", "running"))
        ).count()
        if pending == 0:
            campaign.status = "completed"
            campaign.completed_at = utcnow()
            db.session.commit()

    def _process(self, job):
        if not self.queue.claim(job.id):
            return
        db.session.refresh(job)

        sender = SenderService(job.provider)
        start = time.time()
        try:
            res = sender.send(job.phone, job.message)
            duration = res.get("duration_ms", int((time.time() - start) * 1000))
            job.status = "success"
            job.finished_at = utcnow()
            db.session.commit()
            self.queue.log_delivery(job, "success", duration_ms=duration)

            if job.campaign_id:
                from app.models.campaign import Campaign
                campaign = Campaign.query.get(job.campaign_id)
                if campaign:
                    campaign.sent = Campaign.sent + 1
                    db.session.commit()
            self._finalize_campaign(job.campaign_id)
            self._emit(job, "success")
        except Exception as e:
            err = str(e)
            job.last_error = err
            terminal = job.attempts >= job.max_attempts
            if terminal:
                job.status = "failed"
                job.finished_at = utcnow()
            else:
                job.status = "pending"
                backoff = current_app.config.get("RETRY_BACKOFF", 60)
                job.run_at = utcnow() + timedelta(seconds=backoff * job.attempts)
            db.session.commit()
            if terminal:
                self.queue.log_delivery(job, "failed", error=err,
                                        duration_ms=int((time.time() - start) * 1000))
                if job.campaign_id:
                    from app.models.campaign import Campaign
                    campaign = Campaign.query.get(job.campaign_id)
                    if campaign:
                        campaign.failed = Campaign.failed + 1
                        db.session.commit()
                self._finalize_campaign(job.campaign_id)
            self._emit(job, job.status)
