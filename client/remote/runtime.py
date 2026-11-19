import time

from PySide6.QtCore import QThread, Signal

from remote.api_client import RemoteApiClient, RemoteApiError
from remote.device_manager import DeviceManager


class RemoteWorker(QThread):
    devices_updated = Signal(list)
    status_updated = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.device_manager = DeviceManager()
        self.api = RemoteApiClient()
        self._heartbeat_interval = 60
        self._list_interval = 5
        self._register_retry_interval = 15

    def run(self):
        registered = False
        last_heartbeat = 0.0
        next_register_attempt = 0.0
        last_list_attempt = 0.0
        last_enabled = None

        while not self.isInterruptionRequested():
            now = time.monotonic()
            enabled = self.device_manager.is_enabled()

            if enabled != last_enabled:
                if enabled:
                    self.status_updated.emit("正在注册本机设备……")
                else:
                    self.status_updated.emit(
                        "本机对外注册已关闭，仍可查询其他在线设备"
                    )
                last_enabled = enabled

            if enabled and not registered and now >= next_register_attempt:
                try:
                    self.api.register(self.device_manager.build_registration())
                    registered = True
                    last_heartbeat = time.monotonic()
                    self.status_updated.emit("本机已注册，正在维持在线状态")
                except (RemoteApiError, ValueError) as exc:
                    self.error_occurred.emit(f"设备注册失败：{exc}")
                    next_register_attempt = time.monotonic() + self._register_retry_interval

            now = time.monotonic()
            if enabled and registered and now - last_heartbeat >= self._heartbeat_interval:
                try:
                    self.api.heartbeat(self.device_manager.device_key)
                    last_heartbeat = time.monotonic()
                except (RemoteApiError, ValueError) as exc:
                    self.error_occurred.emit(f"设备心跳失败：{exc}")
                    registered = False
                    next_register_attempt = time.monotonic() + self._register_retry_interval

            now = time.monotonic()
            if now - last_list_attempt >= self._list_interval:
                try:
                    devices = self.api.list_clients()
                    self.devices_updated.emit(devices)
                except RemoteApiError as exc:
                    self.error_occurred.emit(f"获取设备列表失败：{exc}")
                last_list_attempt = time.monotonic()

            self.msleep(1000)

    def stop(self):
        self.requestInterruption()
        self.wait(10000)
