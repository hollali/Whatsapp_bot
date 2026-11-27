import hashlib
import secrets


from flask import Blueprint, request, jsonify
from flask_login import current_user, login_user, logout_user
from werkzeug.exceptions import BadRequest
from werkzeug.security import check_password_hash

from app.extensions import db
from app.models.apikey import ApiKey
from app.models.user import User
from app.utils import email_field, password_field, string_field

auth_bp = Blueprint("auth", __name__)


def _require_user():
    if not current_user.is_authenticated:
        raise BadRequest("unauthorized")
    return current_user


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    email = email_field(data)
    password = password_field(data)
    name = string_field(data, "name", 120, required=False) or email.split("@")[0]
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "email already registered"}), 409
    user = User(email=email, name=name)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password", "")
    user = User.query.filter_by(email=email.lower() if isinstance(email, str) else email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "invalid credentials"}), 401
    login_user(user)
    return jsonify(user.to_dict())


@auth_bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    return jsonify({"status": "ok"})


@auth_bp.route("/me", methods=["GET"])
def me():
    return jsonify(_require_user().to_dict())


@auth_bp.route("/api-keys", methods=["GET"])
def list_keys():
    user = _require_user()
    keys = ApiKey.query.filter_by(user_id=user.id, revoked=False).all()
    return jsonify([key.to_dict() for key in keys])


@auth_bp.route("/api-keys", methods=["POST"])
def create_key():
    user = _require_user()
    name = string_field(request.get_json() or {}, "name", 120, required=False) or "default"
    raw = secrets.token_urlsafe(32)
    key = ApiKey(user_id=user.id, name=name, key_hash=hashlib.sha256(raw.encode()).hexdigest(),
                 prefix=raw[:8])
    db.session.add(key)
    db.session.commit()
    return jsonify({"key": raw, "prefix": key.prefix, "id": key.id}), 201


@auth_bp.route("/api-keys/<key_id>", methods=["DELETE"])
def revoke_key(key_id):
    user = _require_user()
    key = ApiKey.query.filter_by(id=key_id, user_id=user.id).first_or_404()
    key.revoked = True
    db.session.commit()
    return jsonify({"status": "revoked"})
