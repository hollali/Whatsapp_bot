from flask import Blueprint, jsonify

from app.extensions import csrf

api_bp = Blueprint("api", __name__)

# disable csrf for api (token/api key based)
csrf.exempt(api_bp)


@api_bp.route("/health", methods=["GET"])
def health():
    from app.services.sender import SenderService
    s = SenderService()
    return jsonify({"status": "ok", "provider": s.health()})


from app.api import auth, contacts, messages, campaigns, schedules, templates, analytics  # noqa: E402,F401

api_bp.register_blueprint(auth.auth_bp, url_prefix="/auth")
api_bp.register_blueprint(contacts.contacts_bp, url_prefix="/contacts")
api_bp.register_blueprint(messages.messages_bp, url_prefix="/messages")
api_bp.register_blueprint(campaigns.campaigns_bp, url_prefix="/campaigns")
api_bp.register_blueprint(schedules.schedules_bp, url_prefix="/schedules")
api_bp.register_blueprint(templates.templates_bp, url_prefix="/templates")
api_bp.register_blueprint(analytics.analytics_bp, url_prefix="/analytics")
