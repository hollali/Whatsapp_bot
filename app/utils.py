import hashlib
import re
from datetime import datetime, timezone

from werkzeug.exceptions import BadRequest

PROVIDERS = ("pywhatkit", "twilio", "business_api")
_PHONE_RE = re.compile(r"^\+?[\d\s().-]{3,32}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def parse_utc(value, field="datetime"):
    if not isinstance(value, str) or not value.strip():
        raise BadRequest(f"{field} must be an ISO 8601 string")
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        raise BadRequest(f"invalid {field} (ISO 8601 required)")
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def utc_iso(value):
    return value.isoformat() + "Z" if value else None


def string_field(data, field, max_length=255, required=True):
    value = data.get(field)
    if value is None or value == "":
        if required:
            raise BadRequest(f"{field} required")
        return None
    if not isinstance(value, str) or len(value.strip()) > max_length:
        raise BadRequest(f"invalid {field}")
    return value.strip()


def email_field(data, field="email"):
    value = string_field(data, field, 254).lower()
    if not _EMAIL_RE.fullmatch(value):
        raise BadRequest("invalid email")
    return value


def password_field(data, field="password"):
    value = data.get(field)
    if not isinstance(value, str) or len(value) < 8 or len(value) > 128:
        raise BadRequest("password must be 8-128 characters")
    return value


def phone_field(data, field="phone"):
    value = string_field(data, field, 32)
    if not _PHONE_RE.fullmatch(value):
        raise BadRequest("invalid phone number")
    return value


def provider_field(data, default=None):
    value = data.get("provider", default)
    if value is None or value == "":
        value = "pywhatkit"
    if not isinstance(value, str) or value.lower() not in PROVIDERS:
        raise BadRequest("unknown provider")
    return value.lower()


def api_key_hash(request):
    raw = request.headers.get("X-API-Key") or ""
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        raw = raw or header[7:].strip()
    return hashlib.sha256(raw.encode()).hexdigest() if raw else None


def context_field(data):
    value = data.get("context") or {}
    if not isinstance(value, dict):
        raise BadRequest("context must be an object")
    return value


def phones_list(data):
    value = data.get("phones")
    if not isinstance(value, list) or not value:
        raise BadRequest("phones must be a non-empty list")
    phones = []
    for item in value:
        if not isinstance(item, str) or not _PHONE_RE.fullmatch(item.strip()):
            raise BadRequest("invalid phone number in phones")
        phones.append(item.strip())
    return phones
