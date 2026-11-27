from datetime import timedelta

from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required
from werkzeug.exceptions import BadRequest

from app.models.campaign import Campaign
from app.models.schedule import DeliveryLog, ScheduledJob
from app.services.queue import QueueService
from app.utils import utcnow

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
    try:
        days = int(request.args.get("days", 7))
    except ValueError:
        raise BadRequest("days must be an integer")
    if not 1 <= days <= 90:
        raise BadRequest("days must be between 1 and 90")
    since = utcnow() - timedelta(days=days)
    logs = DeliveryLog.query.filter(
        DeliveryLog.user_id == current_user.id, DeliveryLog.created_at >= since
    ).all()
    buckets = {}
    for entry in logs:
        key = entry.created_at.date().isoformat()
        bucket = buckets.setdefault(key, {"success": 0, "failed": 0})
        bucket["success" if entry.status == "success" else "failed"] += 1
    return jsonify({key: buckets[key] for key in sorted(buckets)})


@analytics_bp.route("/providers", methods=["GET"])
@login_required
def providers_health():
    from app.services.sender import SenderService
    results = []
    for name in ("pywhatkit", "twilio", "business_api"):
        try:
            results.append(SenderService(name).health())
        except Exception as exc:
            results.append({"provider": name, "ok": False, "error": str(exc)})
    return jsonify(results)
