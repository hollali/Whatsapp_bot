from collections import defaultdict, deque
from time import time

from flask import Blueprint, current_app, jsonify, request
from werkzeug.exceptions import BadRequest, MethodNotAllowed, NotFound

from app.extensions import csrf

api_bp = Blueprint("api", __name__)

csrf.exempt(api_bp)

_minute = 60
_rate_windows = defaultdict(deque)
_RATE_LIMITS = {"/api/v1/auth/login": 20, "/api/v1/auth/register": 10}
_DEFAULT_RATE_LIMIT = 120


def rate_limit_request():
    if not request.path.startswith("/api/v1") or not current_app.config.get("RATE_LIMIT_ENABLED", True):
        return None
    now = time()
    key = (request.remote_addr or "unknown", request.path)
    window = _rate_windows[key]
    while window and now - window[0] > _minute:
        window.popleft()
    limit = _RATE_LIMITS.get(request.path, _DEFAULT_RATE_LIMIT)
    if len(window) >= limit:
        return jsonify({"error": "rate limit exceeded"}), 429
    window.append(now)
    return None


def register_api_errors(app):
    def bad_request(error):
        if request.path.startswith("/api/v1"):
            return jsonify({"error": getattr(error, "description", str(error))}), 400
        return error

    def not_found(error):
        if request.path.startswith("/api/v1"):
            return jsonify({"error": "not found"}), 404
        return error

    def method_not_allowed(error):
        if request.path.startswith("/api/v1"):
            return jsonify({"error": "method not allowed"}), 405
        return error

    app.register_error_handler(BadRequest, bad_request)
    app.register_error_handler(NotFound, not_found)
    app.register_error_handler(MethodNotAllowed, method_not_allowed)


@api_bp.route("/health", methods=["GET"])
def health():
    from app.services.sender import SenderService
    return jsonify({"status": "ok", "provider": SenderService().health()})


from app.api import auth, contacts, messages, campaigns, schedules, templates, analytics  # noqa: E402,F401

for blueprint in (auth.auth_bp, contacts.contacts_bp, messages.messages_bp,
                  campaigns.campaigns_bp, schedules.schedules_bp, templates.templates_bp,
                  analytics.analytics_bp):
    csrf.exempt(blueprint)
    api_bp.register_blueprint(blueprint, url_prefix="/" + blueprint.name)
