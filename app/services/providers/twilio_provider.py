from app.services.providers.base import BaseProvider, ProviderError


class TwilioProvider(BaseProvider):
    name = "twilio"

    def __init__(self, account_sid=None, auth_token=None, from_number=None):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number

    def send(self, phone, message, **kwargs):
        # Stub: implement with twilio SDK when available
        raise ProviderError("Twilio provider not configured/implemented")

    def health(self):
        return {"provider": self.name, "ok": False, "error": "not configured"}


class BusinessApiProvider(BaseProvider):
    name = "business_api"

    def __init__(self, token=None, phone_number_id=None):
        self.token = token
        self.phone_number_id = phone_number_id

    def send(self, phone, message, **kwargs):
        raise ProviderError("WhatsApp Business API provider not configured/implemented")

    def health(self):
        return {"provider": self.name, "ok": False, "error": "not configured"}
