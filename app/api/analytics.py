from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required

from app.services.queue import QueueService
from app.models.schedule import DeliveryLog, ScheduledJob
from app.models.campaign import Campaign

analytics_bp = Blueprint("analytics", __name__)
queue = QueueService()


@analytics_bp.route("/summary", methods=["GET"])
@login_required
def summary():
    stats = queue.stats(user_id=current_user.id)
    pending = ScheduledJob.query.filter_by(user_id=current_user.id, status="pending").count()
    running = ScheduledJob.query.filter_by(user_id=current_user.id, status="running").count()
    campaigns = Campaign.query.filter_by(user_id=current_user.id).count()
    return jsonify({
        "delivery": stats,
        "pending_jobs": pending,
        "running_jobs": running,
        "campaigns": campaigns,
    })


@analytics_bp.route("/timeline", methods=["GET"])
@login_required
def timeline():
    days = int(request.args.get("days", 7))
    from datetime import datetime, timedelta
    since = datetime.utcnow() - timedelta(days=days)
    logs = DeliveryLog.query.filter(
        DeliveryLog.user_id == current_user.id, DeliveryLog.created_at >= since
    ).all()
    buckets = {}
    for l in logs:
        key = l.created_at.date().isoformat()
        b = buckets.setdefault(key, {"success": 0, "failed": 0})
        if l.status == "success":
            b["success"] += 1
        else:
            b["failed"] += 1
    return jsonify(buckets)


@analytics_bp.route("/providers", methods=["GET"])
@login_required
def providers_health():
    from app.services.sender import SenderService
    names = ["pywhatkit", "twilio", "business_api"]
    out = []
    for n in names:
        try:
            s = SenderService(n)
            out.append(s.health())
        except Exception as e:
            out.append({"provider": n, "ok": False, "error": str(e)})
    return jsonify(out)
