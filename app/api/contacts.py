from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required

from app.extensions import db
from app.models.contact import Contact, ContactGroup

contacts_bp = Blueprint("contacts", __name__)


def _auth():
    if not current_user.is_authenticated:
        return jsonify({"error": "unauthorized"}), 401
    return None


@contacts_bp.route("", methods=["GET"])
@login_required
def list_contacts():
    group_id = request.args.get("group_id")
    q = Contact.query.filter_by(user_id=current_user.id)
    if group_id:
        q = q.filter_by(group_id=group_id)
    return jsonify([c.to_dict() for c in q.all()])


@contacts_bp.route("", methods=["POST"])
@login_required
def create_contact():
    data = request.get_json() or {}
    phone = data.get("phone")
    if not phone:
        return jsonify({"error": "phone required"}), 400
    c = Contact(
        user_id=current_user.id,
        name=data.get("name"),
        phone=phone,
        email=data.get("email"),
        tags=data.get("tags"),
        group_id=data.get("group_id"),
    )
    db.session.add(c)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    return jsonify(c.to_dict()), 201


@contacts_bp.route("/<cid>", methods=["GET"])
@login_required
def get_contact(cid):
    c = Contact.query.filter_by(id=cid, user_id=current_user.id).first()
    if not c:
        return jsonify({"error": "not found"}), 404
    return jsonify(c.to_dict())


@contacts_bp.route("/<cid>", methods=["PUT", "PATCH"])
@login_required
def update_contact(cid):
    c = Contact.query.filter_by(id=cid, user_id=current_user.id).first()
    if not c:
        return jsonify({"error": "not found"}), 404
    data = request.get_json() or {}
    for field in ("name", "phone", "email", "tags", "group_id", "opted_out"):
        if field in data:
            setattr(c, field, data[field])
    db.session.commit()
    return jsonify(c.to_dict())


@contacts_bp.route("/<cid>", methods=["DELETE"])
@login_required
def delete_contact(cid):
    c = Contact.query.filter_by(id=cid, user_id=current_user.id).first()
    if not c:
        return jsonify({"error": "not found"}), 404
    db.session.delete(c)
    db.session.commit()
    return jsonify({"status": "deleted"})


@contacts_bp.route("/import", methods=["POST"])
@login_required
def import_contacts():
    data = request.get_json() or {}
    items = data.get("contacts", [])
    created = 0
    for it in items:
        if not it.get("phone"):
            continue
        c = Contact(user_id=current_user.id, name=it.get("name"), phone=it.get("phone"),
                    email=it.get("email"), tags=it.get("tags"))
        db.session.add(c)
        created += 1
    db.session.commit()
    return jsonify({"created": created})


@contacts_bp.route("/groups", methods=["GET"])
@login_required
def list_groups():
    groups = ContactGroup.query.filter_by(user_id=current_user.id).all()
    return jsonify([{"id": g.id, "name": g.name, "description": g.description} for g in groups])


@contacts_bp.route("/groups", methods=["POST"])
@login_required
def create_group():
    data = request.get_json() or {}
    g = ContactGroup(user_id=current_user.id, name=data.get("name"), description=data.get("description"))
    db.session.add(g)
    db.session.commit()
    return jsonify({"id": g.id, "name": g.name}), 201
