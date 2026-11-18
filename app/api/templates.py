from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required

from app.extensions import db
from app.models.template import Template
from app.services.template_engine import TemplateEngine

templates_bp = Blueprint("templates", __name__)


@templates_bp.route("", methods=["GET"])
@login_required
def list_templates():
    ts = Template.query.filter_by(user_id=current_user.id).all()
    return jsonify([t.to_dict() for t in ts])


@templates_bp.route("", methods=["POST"])
@login_required
def create_template():
    data = request.get_json() or {}
    if not data.get("name") or not data.get("body"):
        return jsonify({"error": "name and body required"}), 400
    t = Template(user_id=current_user.id, name=data["name"], body=data["body"],
                 variables=",".join(TemplateEngine.extract_variables(data["body"])))
    db.session.add(t)
    db.session.commit()
    return jsonify(t.to_dict()), 201


@templates_bp.route("/<tid>", methods=["GET"])
@login_required
def get_template(tid):
    t = Template.query.filter_by(id=tid, user_id=current_user.id).first()
    if not t:
        return jsonify({"error": "not found"}), 404
    return jsonify(t.to_dict())


@templates_bp.route("/<tid>", methods=["PUT", "PATCH"])
@login_required
def update_template(tid):
    t = Template.query.filter_by(id=tid, user_id=current_user.id).first()
    if not t:
        return jsonify({"error": "not found"}), 404
    data = request.get_json() or {}
    if "name" in data:
        t.name = data["name"]
    if "body" in data:
        t.body = data["body"]
        t.variables = ",".join(TemplateEngine.extract_variables(data["body"]))
    db.session.commit()
    return jsonify(t.to_dict())


@templates_bp.route("/<tid>", methods=["DELETE"])
@login_required
def delete_template(tid):
    t = Template.query.filter_by(id=tid, user_id=current_user.id).first()
    if not t:
        return jsonify({"error": "not found"}), 404
    db.session.delete(t)
    db.session.commit()
    return jsonify({"status": "deleted"})


@templates_bp.route("/<tid>/render", methods=["POST"])
@login_required
def render_template(tid):
    t = Template.query.filter_by(id=tid, user_id=current_user.id).first()
    if not t:
        return jsonify({"error": "not found"}), 404
    data = request.get_json() or {}
    try:
        rendered = TemplateEngine.render(t.body, data.get("context", {}))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"rendered": rendered})
