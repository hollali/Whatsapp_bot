from flask import Blueprint, current_app, request, jsonify
from flask_login import current_user, login_required
from werkzeug.exceptions import BadRequest

from app.extensions import db
from app.models.contact import Contact, ContactGroup
from app.utils import phone_field, string_field

contacts_bp = Blueprint("contacts", __name__)


def _group(group_id, required=False):
    if not group_id:
        if required:
            raise BadRequest("group_id required")
        return None
    group = ContactGroup.query.filter_by(id=group_id, user_id=current_user.id).first()
    if not group:
        raise BadRequest("group not found")
    return group


def _contact(cid):
    return Contact.query.filter_by(id=cid, user_id=current_user.id).first_or_404()


def _contact_data(data, partial=False):
    values = {}
    if not partial or "phone" in data:
        values["phone"] = phone_field(data)
    if "name" in data:
        values["name"] = string_field(data, "name", 120, required=False)
    if "email" in data:
        email = string_field(data, "email", 254, required=False)
        if email:
            values["email"] = email.lower()
    if "tags" in data:
        tags = data["tags"]
        if isinstance(tags, list):
            tags = ",".join(str(tag) for tag in tags)
        values["tags"] = string_field({"tags": tags}, "tags", 255, required=False)
    if "group_id" in data:
        _group(data["group_id"])
        values["group_id"] = data["group_id"] or None
    if "opted_out" in data:
        if not isinstance(data["opted_out"], bool):
            raise BadRequest("opted_out must be a boolean")
        values["opted_out"] = data["opted_out"]
    return values


@contacts_bp.route("", methods=["GET"])
@login_required
def list_contacts():
    group_id = request.args.get("group_id")
    q = Contact.query.filter_by(user_id=current_user.id)
    if group_id:
        q = q.filter_by(group_id=group_id)
    return jsonify([contact.to_dict() for contact in q.order_by(Contact.created_at.desc()).all()])


@contacts_bp.route("", methods=["POST"])
@login_required
def create_contact():
    data = request.get_json() or {}
    values = _contact_data(data)
    contact = Contact(user_id=current_user.id, **values)
    db.session.add(contact)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "phone already exists"}), 409
    return jsonify(contact.to_dict()), 201


@contacts_bp.route("/<cid>", methods=["GET"])
@login_required
def get_contact(cid):
    return jsonify(_contact(cid).to_dict())


@contacts_bp.route("/<cid>", methods=["PUT", "PATCH"])
@login_required
def update_contact(cid):
    contact = _contact(cid)
    data = request.get_json() or {}
    for field, value in _contact_data(data, partial=True).items():
        setattr(contact, field, value)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "phone already exists"}), 409
    return jsonify(contact.to_dict())


@contacts_bp.route("/<cid>", methods=["DELETE"])
@login_required
def delete_contact(cid):
    contact = _contact(cid)
    from app.models.schedule import DeliveryLog, ScheduledJob
    job_ids = [job.id for job in ScheduledJob.query.filter_by(contact_id=contact.id).all()]
    if job_ids:
        DeliveryLog.query.filter(DeliveryLog.job_id.in_(job_ids)).update({"job_id": None}, synchronize_session=False)
    ScheduledJob.query.filter_by(contact_id=contact.id).update({"contact_id": None}, synchronize_session=False)
    db.session.delete(contact)
    db.session.commit()
    return jsonify({"status": "deleted"})


@contacts_bp.route("/import", methods=["POST"])
@login_required
def import_contacts():
    items = (request.get_json() or {}).get("contacts", [])
    limit = current_app.config.get("MAX_BULK_JOBS", 500)
    if not isinstance(items, list) or len(items) > limit:
        raise BadRequest(f"contacts must be a list of at most {limit} items")
    existing = {row.phone for row in Contact.query.filter_by(user_id=current_user.id).all()}
    created = skipped = 0
    for item in items:
        if not isinstance(item, dict):
            skipped += 1
            continue
        try:
            values = _contact_data(item)
        except BadRequest:
            skipped += 1
            continue
        if values["phone"] in existing:
            skipped += 1
            continue
        db.session.add(Contact(user_id=current_user.id, **values))
        existing.add(values["phone"])
        created += 1
    db.session.commit()
    return jsonify({"created": created, "skipped": skipped})


@contacts_bp.route("/groups", methods=["GET"])
@login_required
def list_groups():
    groups = ContactGroup.query.filter_by(user_id=current_user.id).all()
    return jsonify([group.to_dict() if hasattr(group, "to_dict") else
                    {"id": group.id, "name": group.name, "description": group.description}
                    for group in groups])


@contacts_bp.route("/groups", methods=["POST"])
@login_required
def create_group():
    data = request.get_json() or {}
    name = string_field(data, "name", 120)
    description = string_field(data, "description", 500, required=False)
    group = ContactGroup(user_id=current_user.id, name=name, description=description)
    db.session.add(group)
    db.session.commit()
    return jsonify({"id": group.id, "name": group.name, "description": group.description}), 201


@contacts_bp.route("/groups/<gid>", methods=["PUT", "PATCH"])
@login_required
def update_group(gid):
    group = ContactGroup.query.filter_by(id=gid, user_id=current_user.id).first_or_404()
    data = request.get_json() or {}
    if "name" in data:
        group.name = string_field(data, "name", 120)
    if "description" in data:
        group.description = string_field(data, "description", 500, required=False)
    db.session.commit()
    return jsonify({"id": group.id, "name": group.name, "description": group.description})


@contacts_bp.route("/groups/<gid>", methods=["DELETE"])
@login_required
def delete_group(gid):
    group = ContactGroup.query.filter_by(id=gid, user_id=current_user.id).first_or_404()
    Contact.query.filter_by(group_id=group.id).update({"group_id": None}, synchronize_session=False)
    db.session.delete(group)
    db.session.commit()
    return jsonify({"status": "deleted"})
