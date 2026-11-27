from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required
from werkzeug.exceptions import BadRequest

from app.extensions import db
from app.models.campaign import Campaign
from app.models.contact import Contact
from app.models.schedule import DeliveryLog, ScheduledJob
from app.models.template import Template
from app.services.queue import QueueService
from app.services.template_engine import TemplateEngine
from app.utils import parse_utc, phones_list, string_field, utcnow

campaigns_bp = Blueprint("campaigns", __name__)
queue = QueueService()


def _campaign(cid):
    return Campaign.query.filter_by(id=cid, user_id=current_user.id).first_or_404()


def _validate_template(template_id):
    if not template_id:
        return None
    template = Template.query.filter_by(id=template_id, user_id=current_user.id).first()
    if not template:
        raise BadRequest("template not found")
    return template


@campaigns_bp.route("", methods=["GET"])
@login_required
def list_campaigns():
    campaigns = Campaign.query.filter_by(user_id=current_user.id).order_by(Campaign.created_at.desc()).all()
    return jsonify([c.to_dict() for c in campaigns])


@campaigns_bp.route("", methods=["POST"])
@login_required
def create_campaign():
    data = request.get_json() or {}
    template = _validate_template(data.get("template_id"))
    name = string_field(data, "name", 120, required=False) or "Untitled"
    message = string_field(data, "message", 10000, required=False)
    scheduled_at = parse_utc(data["scheduled_at"], "scheduled_at") if data.get("scheduled_at") else None
    if not message and not template:
        raise BadRequest("message or template_id required")
    campaign = Campaign(user_id=current_user.id, name=name, template_id=template.id if template else None,
                        message=message, scheduled_at=scheduled_at)
    db.session.add(campaign)
    db.session.commit()
    return jsonify(campaign.to_dict()), 201


@campaigns_bp.route("/<cid>", methods=["GET"])
@login_required
def get_campaign(cid):
    return jsonify(_campaign(cid).to_dict())


@campaigns_bp.route("/<cid>/launch", methods=["POST"])
@login_required
def launch_campaign(cid):
    campaign = _campaign(cid)
    if campaign.status not in ("draft", "failed"):
        return jsonify({"error": "campaign cannot be launched in its current state"}), 409
    data = request.get_json() or {}
    group_id = data.get("group_id")
    if group_id:
        group = Contact.query.filter_by(user_id=current_user.id, group_id=group_id).first()
        if not group:
            return jsonify({"error": "group not found"}), 404
    if data.get("phones") is not None:
        phones = phones_list(data)
    else:
        q = Contact.query.filter_by(user_id=current_user.id, opted_out=False)
        if group_id:
            q = q.filter_by(group_id=group_id)
        phones = [ct.phone for ct in q.all()]
    contacts = Contact.query.filter(
        Contact.user_id == current_user.id, Contact.phone.in_(phones)
    ).all()
    opted_out = {ct.phone for ct in contacts if ct.opted_out}
    phones = list(dict.fromkeys(p for p in phones if p not in opted_out))
    names = {ct.phone: ct.name for ct in contacts}
    contact_ids = {ct.phone: ct.id for ct in contacts}

    template = _validate_template(campaign.template_id)
    message = template.body if template else campaign.message
    if not phones or not message:
        return jsonify({"error": "no recipients or message"}), 400

    run_at = campaign.scheduled_at or utcnow()
    jobs = []
    for phone in phones:
        try:
            rendered = TemplateEngine.render(message, {"name": names.get(phone) or phone, "phone": phone})
        except ValueError:
            rendered = message
        jobs.append(queue.enqueue(current_user.id, phone, rendered, run_at=run_at,
                                  campaign_id=campaign.id, contact_id=contact_ids.get(phone)))
    campaign.total = len(jobs)
    campaign.sent = 0
    campaign.failed = 0
    campaign.status = "scheduled" if campaign.scheduled_at and campaign.scheduled_at > utcnow() else "running"
    campaign.started_at = utcnow()
    db.session.commit()
    return jsonify({"enqueued": len(jobs), "campaign": campaign.to_dict()}), 202


@campaigns_bp.route("/<cid>/pause", methods=["POST"])
@login_required
def pause_campaign(cid):
    campaign = _campaign(cid)
    if campaign.status not in ("running", "scheduled"):
        return jsonify({"error": "campaign is not running"}), 409
    ScheduledJob.query.filter_by(campaign_id=campaign.id, user_id=current_user.id, status="pending").update(
        {"status": "cancelled"}
    )
    campaign.status = "paused"
    db.session.commit()
    return jsonify(campaign.to_dict())


@campaigns_bp.route("/<cid>/resume", methods=["POST"])
@login_required
def resume_campaign(cid):
    campaign = _campaign(cid)
    if campaign.status != "paused":
        return jsonify({"error": "campaign is not paused"}), 409
    ScheduledJob.query.filter_by(campaign_id=campaign.id, user_id=current_user.id, status="cancelled").update(
        {"status": "pending"}
    )
    campaign.status = "running"
    db.session.commit()
    return jsonify(campaign.to_dict())


@campaigns_bp.route("/<cid>", methods=["DELETE"])
@login_required
def delete_campaign(cid):
    campaign = _campaign(cid)
    job_ids = [j.id for j in ScheduledJob.query.filter_by(campaign_id=campaign.id).all()]
    if job_ids:
        DeliveryLog.query.filter(DeliveryLog.job_id.in_(job_ids)).update({"job_id": None}, synchronize_session=False)
    DeliveryLog.query.filter_by(campaign_id=campaign.id).update({"campaign_id": None}, synchronize_session=False)
    ScheduledJob.query.filter_by(campaign_id=campaign.id).delete(synchronize_session=False)
    db.session.delete(campaign)
    db.session.commit()
    return jsonify({"status": "deleted"})
