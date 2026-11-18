import time

from app.services.providers.base import BaseProvider, ProviderError


class PyWhatKitProvider(BaseProvider):
    name = "pywhatkit"

    def __init__(self, wait_time=15, close_tab=True, close_time=3):
        self.wait_time = wait_time
        self.close_tab = close_tab
        self.close_time = close_time

    def send(self, phone, message, **kwargs):
        try:
            import pywhatkit as kit
        except ImportError as e:
            raise ProviderError("pywhatkit not installed") from e

        hour = kwargs.get("hour")
        minute = kwargs.get("minute")
        instant = kwargs.get("instant", hour is None or minute is None)
        start = time.time()
        try:
            if instant:
                kit.sendwhatmsg_instantly(
                    phone, message, wait_time=self.wait_time, tab_close=self.close_tab, close_time=self.close_time
                )
            else:
                kit.sendwhatmsg(
                    phone, message, hour, minute, wait_time=self.wait_time, tab_close=self.close_tab, close_time=self.close_time
                )
        except Exception as e:
            raise ProviderError(str(e)) from e
        return {"provider": self.name, "duration_ms": int((time.time() - start) * 1000)}

    def health(self):
        try:
            import pywhatkit  # noqa
            return {"provider": self.name, "ok": True}
        except Exception as e:
            return {"provider": self.name, "ok": False, "error": str(e)}
