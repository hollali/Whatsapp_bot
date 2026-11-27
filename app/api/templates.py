from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required
from werkzeug.exceptions import BadRequest

from app.extensions import db
from app.models.campaign import Campaign
from app.models.template import Template
from app.services.template_engine import TemplateEngine
from app.utils import context_field, string_field

templates_bp = Blueprint("templates", __name__)


def _template(tid):
    return Template.query.filter_by(id=tid, user_id=current_user.id).first_or_404()


def _variables(body):
    return ",".join(TemplateEngine.extract_variables(body))


@templates_bp.route("", methods=["GET"])
@login_required
def list_templates():
    templates = Template.query.filter_by(user_id=current_user.id).all()
    return jsonify([template.to_dict() for template in templates])


@templates_bp.route("", methods=["POST"])
@login_required
def create_template():
    data = request.get_json() or {}
    name = string_field(data, "name", 120)
    body = string_field(data, "body", 10000)
    template = Template(user_id=current_user.id, name=name, body=body, variables=_variables(body))
    db.session.add(template)
    db.session.commit()
    return jsonify(template.to_dict()), 201


@templates_bp.route("/<tid>", methods=["GET"])
@login_required
def get_template(tid):
    return jsonify(_template(tid).to_dict())


@templates_bp.route("/<tid>", methods=["PUT", "PATCH"])
@login_required
def update_template(tid):
    template = _template(tid)
    data = request.get_json() or {}
    if "name" in data:
        template.name = string_field(data, "name", 120)
    if "body" in data:
        template.body = string_field(data, "body", 10000)
        template.variables = _variables(template.body)
    db.session.commit()
    return jsonify(template.to_dict())


@templates_bp.route("/<tid>", methods=["DELETE"])
@login_required
def delete_template(tid):
    template = _template(tid)
    Campaign.query.filter_by(template_id=template.id, user_id=current_user.id).update(
        {"template_id": None}, synchronize_session=False
    )
    db.session.delete(template)
    db.session.commit()
    return jsonify({"status": "deleted"})


@templates_bp.route("/<tid>/render", methods=["POST"])
@login_required
def render_template(tid):
    template = _template(tid)
    data = request.get_json() or {}
    try:
        rendered = TemplateEngine.render(template.body, context_field(data))
    except ValueError as exc:
        raise BadRequest(str(exc))
    return jsonify({"rendered": rendered})
