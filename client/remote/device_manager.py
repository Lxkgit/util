import platform
import socket
import uuid

from features.settings import load_config, save_config


APP_VERSION = "1.0.0"


class DeviceManager:
    def __init__(self):
        self.device_key = self._load_or_create_key()

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

    def build_registration(self):
        return {
            "key": self.device_key,
            "deviceName": socket.gethostname(),
            "platform": platform.platform(),
            "version": APP_VERSION,
            "signals": []
        }
