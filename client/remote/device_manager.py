import platform
import socket
import time
import uuid

from features.settings import load_config, save_config


APP_VERSION = "1.0.0"


class DeviceManager:
    def __init__(self):
        self.device_key = self._load_or_create_key()
        self._signals = []

    @staticmethod
    def _load_or_create_key():
        config = load_config()
        device_key = config["DEFAULT"].get("DeviceKey", "").strip()
        if not device_key:
            device_key = uuid.uuid4().hex
            save_config("DeviceKey", device_key)
        return device_key

    @staticmethod
    def is_enabled():
        config = load_config()
        return config["DEFAULT"].getboolean("RemoteEnabled", fallback=True)

    @staticmethod
    def set_enabled(enabled):
        save_config("RemoteEnabled", "true" if enabled else "false")

    def add_signal(self, signal):
        now = int(time.time())
        active = []
        for item in self._signals:
            try:
                if int(item.get("expiresAt", 0) or 0) >= now:
                    active.append(item)
            except (TypeError, ValueError):
                continue
        active.append(signal)
        self._signals = active

    def build_registration(self):
        now = int(time.time())
        active = []
        for item in self._signals:
            try:
                if int(item.get("expiresAt", 0) or 0) >= now:
                    active.append(item)
            except (TypeError, ValueError):
                continue
        self._signals = active

        return {
            "key": self.device_key,
            "deviceName": socket.gethostname(),
            "platform": platform.platform(),
            "version": APP_VERSION,
            "signals": list(self._signals)
        }
