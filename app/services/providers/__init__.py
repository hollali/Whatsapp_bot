from app.services.providers.base import BaseProvider, ProviderError
from app.services.providers.pywhatkit_provider import PyWhatKitProvider
from app.services.providers.twilio_provider import TwilioProvider, BusinessApiProvider


def get_provider(name="pywhatkit", **kwargs):
    name = (name or "pywhatkit").lower()
    if name == "pywhatkit":
        return PyWhatKitProvider(**kwargs)
    if name == "twilio":
        return TwilioProvider(**kwargs)
    if name in ("business", "business_api", "whatsapp_business"):
        return BusinessApiProvider(**kwargs)
    raise ProviderError(f"Unknown provider: {name}")


__all__ = ["BaseProvider", "ProviderError", "get_provider"]
