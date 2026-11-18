from abc import ABC, abstractmethod


class ProviderError(Exception):
    pass


class BaseProvider(ABC):
    name = "base"

    @abstractmethod
    def send(self, phone: str, message: str, **kwargs) -> dict:
        """Send a message. Return dict with status info. Raise ProviderError on failure."""
        raise NotImplementedError

    def health(self) -> dict:
        return {"provider": self.name, "ok": True}
