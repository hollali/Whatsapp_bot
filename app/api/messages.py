from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required

from app.extensions import db
from app.services.queue import QueueService
from app.services.template_engine import TemplateEngine
from app.models.template import Template

messages_bp = Blueprint("messages", __name__)
queue = QueueService()


@messages_bp.route("/send", methods=["POST"])
@login_required
def send_now():
    data = request.get_json() or {}
    phone = data.get("phone")
    message = data.get("message")
    template_id = data.get("template_id")
    context = data.get("context", {})
    if template_id:
        t = Template.query.filter_by(id=template_id, user_id=current_user.id).first()
        if not t:
            return jsonify({"error": "template not found"}), 404
        try:
            message = TemplateEngine.render(t.body, context)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    if not phone or not message:
        return jsonify({"error": "phone and message required"}), 400
    job = queue.enqueue(current_user.id, phone, message, run_at=datetime.utcnow(),
                        provider=data.get("provider", "pywhatkit"))
    return jsonify(job.to_dict()), 202


@messages_bp.route("/schedule", methods=["POST"])
@login_required
def schedule():
    data = request.get_json() or {}
    phone = data.get("phone")
    message = data.get("message")
    template_id = data.get("template_id")
    context = data.get("context", {})
    run_at = data.get("run_at")
    if template_id:
        t = Template.query.filter_by(id=template_id, user_id=current_user.id).first()
        if not t:
            return jsonify({"error": "template not found"}), 404
        try:
            message = TemplateEngine.render(t.body, context)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    if not phone or not message:
        return jsonify({"error": "phone and message required"}), 400
    if run_at:
        try:
            run_at = datetime.fromisoformat(run_at)
        except ValueError:
            return jsonify({"error": "invalid run_at (ISO format)"}), 400
    else:
        run_at = datetime.utcnow()
    job = queue.enqueue(current_user.id, phone, message, run_at=run_at,
                        provider=data.get("provider", "pywhatkit"))
    return jsonify(job.to_dict()), 202


@messages_bp.route("/jobs", methods=["GET"])
@login_required
def list_jobs():
    status = request.args.get("status")
    from app.models.schedule import ScheduledJob
    q = ScheduledJob.query.filter_by(user_id=current_user.id)
    if status:
        q = q.filter_by(status=status)
    jobs = q.order_by(ScheduledJob.created_at.desc()).limit(200).all()
    return jsonify([j.to_dict() for j in jobs])


@messages_bp.route("/jobs/<jid>", methods=["GET"])
@login_required
def get_job(jid):
    from app.models.schedule import ScheduledJob
    j = ScheduledJob.query.filter_by(id=jid, user_id=current_user.id).first()
    if not j:
        return jsonify({"error": "not found"}), 404
    return jsonify(j.to_dict())


@messages_bp.route("/jobs/<jid>/cancel", methods=["POST"])
@login_required
def cancel_job(jid):
    ok = queue.cancel(jid, user_id=current_user.id)
    if not ok:
        return jsonify({"error": "cannot cancel"}), 400
    return jsonify({"status": "cancelled"})


@messages_bp.route("/jobs/<jid>/retry", methods=["POST"])
@login_required
def retry_job(jid):
    j = queue.retry(jid)
    if not j or j.user_id != current_user.id:
        return jsonify({"error": "not found"}), 404
    return jsonify(j.to_dict())


@messages_bp.route("/bulk", methods=["POST"])
@login_required
def bulk_send():
    data = request.get_json() or {}
    phones = data.get("phones", [])
    message = data.get("message")
    template_id = data.get("template_id")
    context = data.get("context", {})
    run_at = data.get("run_at")
    if template_id:
        t = Template.query.filter_by(id=template_id, user_id=current_user.id).first()
        if not t:
            return jsonify({"error": "template not found"}), 404
        try:
            message = TemplateEngine.render(t.body, context)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    if not phones or not message:
        return jsonify({"error": "phones and message required"}), 400
    if run_at:
        try:
            run_at = datetime.fromisoformat(run_at)
        except ValueError:
            return jsonify({"error": "invalid run_at"}), 400
    else:
        run_at = datetime.utcnow()
    jobs = []
    for p in phones:
        j = queue.enqueue(current_user.id, p, message, run_at=run_at,
                          provider=data.get("provider", "pywhatkit"))
        jobs.append(j.to_dict())
    return jsonify({"enqueued": len(jobs), "jobs": jobs}), 202
