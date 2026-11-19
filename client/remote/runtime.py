import asyncio
import queue
import time

from PySide6.QtCore import QThread, Signal

from remote.api_client import RemoteApiClient, RemoteApiError
from remote.device_manager import DeviceManager
from remote.peer_manager import PeerManager
from remote.signal_manager import create_signal, get_pending_signals


class RemoteWorker(QThread):
    devices_updated = Signal(list)
    status_updated = Signal(str)
    error_occurred = Signal(str)
    incoming_connection = Signal(str, str)
    connection_state = Signal(str, str)
    software_list_received = Signal(str, list)
    screenshot_received = Signal(str, bytes)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.device_manager = DeviceManager()
        self.api = RemoteApiClient()
        self.commands = queue.Queue()
        self._seen_signals = set()
        self.peer_manager = None

    def request_connect(self, peer_key):
        self.commands.put(("connect", peer_key, None))

    def approve_connection(self, peer_key, approved):
        self.commands.put(("approve", peer_key, approved))

    def request_software(self, peer_key):
        self.commands.put(("software", peer_key, None))

    def request_screenshot(self, peer_key):
        self.commands.put(("screenshot", peer_key, None))

    def disconnect(self, peer_key):
        self.commands.put(("disconnect", peer_key, None))

    def _peer_event(self, event, peer_key, value):
        if event == "incoming_connection":
            self.incoming_connection.emit(peer_key, str(value))
        elif event == "connection_state":
            self.connection_state.emit(peer_key, str(value))
        elif event == "software_list_received":
            self.software_list_received.emit(peer_key, value or [])
        elif event == "screenshot_received":
            self.screenshot_received.emit(peer_key, value)
        elif event == "peer_error":
            self.error_occurred.emit(str(value))

    async def _publish_signal(self, receiver, signal_type, payload):
        signal = create_signal(
            self.device_manager.device_key,
            receiver,
            signal_type,
            payload
        )
        self.device_manager.add_signal(signal)

        # 注册接口会覆盖本设备 JSON，因此每次发布信令都提交完整设备信息。
        await asyncio.to_thread(
            self.api.register,
            self.device_manager.build_registration()
        )

    async def _process_devices(self, devices):
        local_key = self.device_manager.device_key
        now = int(time.time())

        for device in devices:
            for signal in get_pending_signals(device, local_key):
                message_id = signal.get("messageId")
                if not message_id or message_id in self._seen_signals:
                    continue

                if int(signal.get("expiresAt", 0) or 0) < now:
                    continue

                self._seen_signals.add(message_id)
                try:
                    await self.peer_manager.handle_signal(signal)
                except Exception as exc:
                    self.error_occurred.emit(f"处理连接信令失败：{exc}")

        if len(self._seen_signals) > 2000:
            self._seen_signals.clear()

    async def _handle_command(self, command):
        action, peer_key, value = command

        try:
            if action == "connect":
                await self.peer_manager.connect(peer_key)
            elif action == "approve":
                await self.peer_manager.approve_offer(peer_key, value)
            elif action == "software":
                await self.peer_manager.request_software(peer_key)
            elif action == "screenshot":
                await self.peer_manager.request_screenshot(peer_key)
            elif action == "disconnect":
                await self.peer_manager.close(peer_key)
        except Exception as exc:
            self.error_occurred.emit(str(exc))

    async def _run_async(self):
        self.peer_manager = PeerManager(
            self._publish_signal,
            self._peer_event
        )

        registered = False
        last_heartbeat = 0.0
        next_register_attempt = 0.0
        last_list_attempt = 0.0
        last_enabled = None

        while not self.isInterruptionRequested():
            enabled = self.device_manager.is_enabled()
            now = time.monotonic()

            if enabled != last_enabled:
                if enabled:
                    registered = False
                    next_register_attempt = 0.0
                    self.status_updated.emit("正在注册本机设备……")
                else:
                    registered = False
                    self.status_updated.emit(
                        "本机对外注册已关闭，仍可查询其他在线设备"
                    )
                last_enabled = enabled

            if enabled and not registered and now >= next_register_attempt:
                try:
                    await asyncio.to_thread(
                        self.api.register,
                        self.device_manager.build_registration()
                    )
                    registered = True
                    last_heartbeat = time.monotonic()
                    self.status_updated.emit("本机已注册，正在维持在线状态")
                except Exception as exc:
                    self.error_occurred.emit(f"设备注册失败：{exc}")
                    next_register_attempt = time.monotonic() + 15

            now = time.monotonic()
            if enabled and registered and now - last_heartbeat >= 60:
                try:
                    await asyncio.to_thread(
                        self.api.heartbeat,
                        self.device_manager.device_key
                    )
                    last_heartbeat = time.monotonic()
                except RemoteApiError as exc:
                    self.error_occurred.emit(f"设备心跳失败：{exc}")
                    registered = False
                    next_register_attempt = time.monotonic() + 5

            now = time.monotonic()
            if now - last_list_attempt >= 5:
                try:
                    devices = await asyncio.to_thread(self.api.list_clients)
                    self.devices_updated.emit(devices)
                    await self._process_devices(devices)
                except RemoteApiError as exc:
                    self.error_occurred.emit(f"获取设备列表失败：{exc}")
                last_list_attempt = time.monotonic()

            while True:
                try:
                    command = self.commands.get_nowait()
                except queue.Empty:
                    break
                await self._handle_command(command)

            await asyncio.sleep(0.2)

        await self.peer_manager.close_all()

    def run(self):
        try:
            asyncio.run(self._run_async())
        except Exception as exc:
            self.error_occurred.emit(f"远程通信模块启动失败：{exc}")

    def stop(self):
        self.requestInterruption()
        self.wait(15000)
