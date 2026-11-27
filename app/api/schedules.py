from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required

from app.extensions import db
from app.models.schedule import DeliveryLog, ScheduledJob

schedules_bp = Blueprint("schedules", __name__)


@schedules_bp.route("", methods=["GET"])
@login_required
def list_schedules():
    status = request.args.get("status")
    q = ScheduledJob.query.filter_by(user_id=current_user.id)
    if status:
        q = q.filter_by(status=status)
    jobs = q.order_by(ScheduledJob.run_at.desc()).limit(500).all()
    return jsonify([job.to_dict() for job in jobs])


@schedules_bp.route("/<jid>", methods=["DELETE"])
@login_required
def delete_schedule(jid):
    job = ScheduledJob.query.filter_by(id=jid, user_id=current_user.id).first_or_404()
    if job.status == "running":
        return jsonify({"error": "cannot delete a running job"}), 409
    DeliveryLog.query.filter_by(job_id=job.id).update({"job_id": None}, synchronize_session=False)
    db.session.delete(job)
    db.session.commit()
    return jsonify({"status": "deleted"})
