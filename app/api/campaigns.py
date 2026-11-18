from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required

from app.extensions import db
from app.models.campaign import Campaign
from app.models.contact import Contact
from app.services.queue import QueueService

campaigns_bp = Blueprint("campaigns", __name__)
queue = QueueService()


@campaigns_bp.route("", methods=["GET"])
@login_required
def list_campaigns():
    cs = Campaign.query.filter_by(user_id=current_user.id).order_by(Campaign.created_at.desc()).all()
    return jsonify([c.to_dict() for c in cs])


@campaigns_bp.route("", methods=["POST"])
@login_required
def create_campaign():
    data = request.get_json() or {}
    c = Campaign(
        user_id=current_user.id,
        name=data.get("name", "Untitled"),
        template_id=data.get("template_id"),
        message=data.get("message"),
        scheduled_at=datetime.fromisoformat(data["scheduled_at"]) if data.get("scheduled_at") else None,
    )
    db.session.add(c)
    db.session.commit()
    return jsonify(c.to_dict()), 201


@campaigns_bp.route("/<cid>", methods=["GET"])
@login_required
def get_campaign(cid):
    c = Campaign.query.filter_by(id=cid, user_id=current_user.id).first()
    if not c:
        return jsonify({"error": "not found"}), 404
    return jsonify(c.to_dict())


@campaigns_bp.route("/<cid>/launch", methods=["POST"])
@login_required
def launch_campaign(cid):
    c = Campaign.query.filter_by(id=cid, user_id=current_user.id).first()
    if not c:
        return jsonify({"error": "not found"}), 404
    data = request.get_json() or {}
    group_id = data.get("group_id")
    phones = data.get("phones")
    if phones is None:
        q = Contact.query.filter_by(user_id=current_user.id, opted_out=False)
        if group_id:
            q = q.filter_by(group_id=group_id)
        contacts = q.all()
        phones = [ct.phone for ct in contacts]
    message = c.message
    if c.template_id:
        from app.models.template import Template
        from app.services.template_engine import TemplateEngine
        t = Template.query.get(c.template_id)
        if t:
            message = t.body
    if not phones or not message:
        return jsonify({"error": "no recipients or message"}), 400
    run_at = c.scheduled_at or datetime.utcnow()
    jobs = []
    for p in phones:
        rendered = message
        if c.template_id:
            from app.services.template_engine import TemplateEngine
            rendered = TemplateEngine.render(message, {"name": p, "phone": p})
        j = queue.enqueue(current_user.id, p, rendered, run_at=run_at, campaign_id=c.id)
        jobs.append(j)
    c.total = len(jobs)
    c.status = "running"
    c.started_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"enqueued": len(jobs), "campaign": c.to_dict()}), 202


@campaigns_bp.route("/<cid>/pause", methods=["POST"])
@login_required
def pause_campaign(cid):
    c = Campaign.query.filter_by(id=cid, user_id=current_user.id).first()
    if not c:
        return jsonify({"error": "not found"}), 404
    c.status = "paused"
    db.session.commit()
    return jsonify(c.to_dict())


@campaigns_bp.route("/<cid>", methods=["DELETE"])
@login_required
def delete_campaign(cid):
    c = Campaign.query.filter_by(id=cid, user_id=current_user.id).first()
    if not c:
        return jsonify({"error": "not found"}), 404
    db.session.delete(c)
    db.session.commit()
    return jsonify({"status": "deleted"})
