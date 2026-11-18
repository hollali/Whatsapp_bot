from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required

from app.extensions import db
from app.models.schedule import ScheduledJob

schedules_bp = Blueprint("schedules", __name__)


@schedules_bp.route("", methods=["GET"])
@login_required
def list_schedules():
    jobs = ScheduledJob.query.filter_by(user_id=current_user.id).order_by(ScheduledJob.run_at.desc()).limit(500).all()
    return jsonify([j.to_dict() for j in jobs])


@schedules_bp.route("/<jid>", methods=["DELETE"])
@login_required
def delete_schedule(jid):
    j = ScheduledJob.query.filter_by(id=jid, user_id=current_user.id).first()
    if not j:
        return jsonify({"error": "not found"}), 404
    db.session.delete(j)
    db.session.commit()
    return jsonify({"status": "deleted"})
