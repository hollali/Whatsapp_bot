from app.services.providers import get_provider, ProviderError


class SenderService:
    def __init__(self, provider_name="pywhatkit", provider_kwargs=None):
        self.provider_name = provider_name
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
