from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, current_user
from werkzeug.security import check_password_hash

from app.extensions import db
from app.models.user import User
from app.models.apikey import ApiKey
import secrets
import hashlib

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")
    name = data.get("name")
    if not email or not password:
        return jsonify({"error": "email and password required"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "email already registered"}), 409
    u = User(email=email, name=name)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    return jsonify(u.to_dict()), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    user = User.query.filter_by(email=data.get("email")).first()
    if not user or not user.check_password(data.get("password", "")):
        return jsonify({"error": "invalid credentials"}), 401
    login_user(user)
    return jsonify(user.to_dict())


@auth_bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    return jsonify({"status": "ok"})


@auth_bp.route("/me", methods=["GET"])
def me():
    if not current_user.is_authenticated:
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(current_user.to_dict())


@auth_bp.route("/api-keys", methods=["GET"])
def list_keys():
    if not current_user.is_authenticated:
        return jsonify({"error": "unauthorized"}), 401
    keys = ApiKey.query.filter_by(user_id=current_user.id, revoked=False).all()
    return jsonify([k.to_dict() for k in keys])


@auth_bp.route("/api-keys", methods=["POST"])
def create_key():
    if not current_user.is_authenticated:
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json() or {}
    name = data.get("name", "default")
    raw = secrets.token_urlsafe(32)
    prefix = raw[:8]
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    k = ApiKey(user_id=current_user.id, name=name, key_hash=key_hash, prefix=prefix)
    db.session.add(k)
    db.session.commit()
    return jsonify({"key": raw, "prefix": prefix, "id": k.id}), 201


@auth_bp.route("/api-keys/<key_id>", methods=["DELETE"])
def revoke_key(key_id):
    if not current_user.is_authenticated:
        return jsonify({"error": "unauthorized"}), 401
    k = ApiKey.query.filter_by(id=key_id, user_id=current_user.id).first()
    if not k:
        return jsonify({"error": "not found"}), 404
    k.revoked = True
    db.session.commit()
    return jsonify({"status": "revoked"})
