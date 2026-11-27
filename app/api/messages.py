from flask import Blueprint, current_app, request, jsonify
from flask_login import current_user, login_required
from werkzeug.exceptions import BadRequest

from app.extensions import db
from app.models.schedule import ScheduledJob
from app.models.template import Template
from app.services.queue import QueueService
from app.services.template_engine import TemplateEngine
from app.utils import context_field, parse_utc, phone_field, phones_list, provider_field, string_field, utcnow

messages_bp = Blueprint("messages", __name__)
queue = QueueService()


def _render_message(data):
    template_id = data.get("template_id")
    context = context_field(data)
    if template_id:
        template = Template.query.filter_by(id=template_id, user_id=current_user.id).first_or_404()
        try:
            return TemplateEngine.render(template.body, context)
        except ValueError as exc:
            raise BadRequest(str(exc))
    message = string_field(data, "message", 10000)
    if not message:
        raise BadRequest("message or template_id required")
    return message


def _run_at(data):
    return parse_utc(data["run_at"], "run_at") if data.get("run_at") else utcnow()


@messages_bp.route("/send", methods=["POST"])
@login_required
def send_now():
    data = request.get_json() or {}
    phone = phone_field(data)
    message = _render_message(data)
    job = queue.enqueue(current_user.id, phone, message, run_at=utcnow(),
                        provider=provider_field(data))
    return jsonify(job.to_dict()), 202


@messages_bp.route("/schedule", methods=["POST"])
@login_required
def schedule():
    data = request.get_json() or {}
    phone = phone_field(data)
    message = _render_message(data)
    job = queue.enqueue(current_user.id, phone, message, run_at=_run_at(data),
                        provider=provider_field(data))
    return jsonify(job.to_dict()), 202


@messages_bp.route("/jobs", methods=["GET"])
@login_required
def list_jobs():
    status = request.args.get("status")
    q = ScheduledJob.query.filter_by(user_id=current_user.id)
    if status:
        q = q.filter_by(status=status)
    jobs = q.order_by(ScheduledJob.created_at.desc()).limit(200).all()
    return jsonify([job.to_dict() for job in jobs])


@messages_bp.route("/jobs/<jid>", methods=["GET"])
@login_required
def get_job(jid):
    job = ScheduledJob.query.filter_by(id=jid, user_id=current_user.id).first_or_404()
    return jsonify(job.to_dict())


@messages_bp.route("/jobs/<jid>/cancel", methods=["POST"])
@login_required
def cancel_job(jid):
    if not queue.cancel(jid, user_id=current_user.id):
        return jsonify({"error": "cannot cancel"}), 400
    return jsonify({"status": "cancelled"})


@messages_bp.route("/jobs/<jid>/retry", methods=["POST"])
@login_required
def retry_job(jid):
    job = queue.retry(jid, user_id=current_user.id)
    if not job:
        return jsonify({"error": "not found"}), 404
    return jsonify(job.to_dict())


@messages_bp.route("/bulk", methods=["POST"])
@login_required
def bulk_send():
    data = request.get_json() or {}
    phones = phones_list(data)
    limit = current_app.config.get("MAX_BULK_JOBS", 500)
    if len(phones) > limit:
        raise BadRequest(f"too many recipients (max {limit})")
    message = _render_message(data)
    run_at = _run_at(data)
    provider = provider_field(data)
    jobs = [queue.enqueue(current_user.id, phone, message, run_at=run_at, provider=provider)
            for phone in phones]
    return jsonify({"enqueued": len(jobs), "jobs": [job.to_dict() for job in jobs]}), 202
