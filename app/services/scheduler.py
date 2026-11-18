import threading
import time
from datetime import datetime, timedelta

from app.extensions import db
from app.services.queue import QueueService
from app.services.sender import SenderService


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
        jobs = self.queue.due_jobs()
        for job in jobs:
            self._process(job)

    def _process(self, job):
        job.status = "running"
        job.started_at = datetime.utcnow()
        job.attempts += 1
        db.session.commit()

        sender = SenderService(job.provider)
        start = time.time()
        try:
            res = sender.send(job.phone, job.message)
            duration = res.get("duration_ms", int((time.time() - start) * 1000))
            job.status = "success"
            job.finished_at = datetime.utcnow()
            db.session.commit()
            self.queue.log_delivery(job, "success", duration_ms=duration)

            if job.campaign_id:
                from app.models.campaign import Campaign
                c = Campaign.query.get(job.campaign_id)
                if c:
                    c.sent += 1
                    db.session.commit()
            try:
                from app.extensions import socketio
                socketio.emit("job_update", job.to_dict())
            except Exception:
                pass
        except Exception as e:
            err = str(e)
            job.last_error = err
            if job.attempts < job.max_attempts:
                job.status = "pending"
                job.run_at = datetime.utcnow() + timedelta(seconds=60 * job.attempts)
            else:
                job.status = "failed"
                job.finished_at = datetime.utcnow()
            db.session.commit()
            self.queue.log_delivery(job, "failed", error=err, duration_ms=int((time.time() - start) * 1000))
            if job.campaign_id and job.status == "failed":
                from app.models.campaign import Campaign
                c = Campaign.query.get(job.campaign_id)
                if c:
                    c.failed += 1
                    db.session.commit()
            try:
                from app.extensions import socketio
                socketio.emit("job_update", job.to_dict())
            except Exception:
                pass
