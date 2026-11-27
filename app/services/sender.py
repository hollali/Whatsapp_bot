from flask import current_app, has_app_context

from app.services.providers import get_provider


class SenderService:
    def __init__(self, provider_name=None, provider_kwargs=None):
        default = current_app.config.get("WHATSAPP_PROVIDER", "pywhatkit") if has_app_context() else "pywhatkit"
        self.provider_name = provider_name or default
        self.provider_kwargs = provider_kwargs or {}
        self._provider = None

    @property
    def provider(self):
        if self._provider is None:
            self._provider = get_provider(self.provider_name, **self.provider_kwargs)
        return self._provider

    def send(self, phone, message, **kwargs):
        return self.provider.send(phone, message, **kwargs)

    def health(self):
        return self.provider.health()
