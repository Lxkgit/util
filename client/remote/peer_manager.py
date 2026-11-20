import asyncio
import json


class PeerManager:
    def __init__(self, publish_signal, event_callback):
        self.publish_signal = publish_signal
        self.event_callback = event_callback
        self.peers = {}
        self.channels = {}
        self.pending_offers = {}
        self.screenshot_buffers = {}

        try:
            from aiortc import (
                RTCPeerConnection,
                RTCSessionDescription,
                RTCConfiguration,
                RTCIceServer
            )
            self.RTCPeerConnection = RTCPeerConnection
            self.RTCSessionDescription = RTCSessionDescription
            self.RTCConfiguration = RTCConfiguration
            self.RTCIceServer = RTCIceServer
            self.aiortc_error = None
        except Exception as exc:
            self.aiortc_error = exc

    def _new_peer(self, peer_key):
        if self.aiortc_error:
            raise RuntimeError(
                "缺少 WebRTC 依赖，请执行 pip install -r requirements-remote.txt"
            ) from self.aiortc_error

        configuration = self.RTCConfiguration(
            iceServers=[
                self.RTCIceServer(urls=["stun:stun.l.google.com:19302"])
            ]
        )
        pc = self.RTCPeerConnection(configuration=configuration)
        self.peers[peer_key] = pc

        @pc.on("connectionstatechange")
        def on_connection_state_change():
            state = pc.connectionState
            self.event_callback("connection_state", peer_key, state)
            if state in ("failed", "closed"):
                self.channels.pop(peer_key, None)

        @pc.on("iceconnectionstatechange")
        def on_ice_connection_state_change():
            self.event_callback(
                "connection_state",
                peer_key,
                f"ICE：{pc.iceConnectionState}"
            )

        @pc.on("icegatheringstatechange")
        def on_ice_gathering_state_change():
            self.event_callback(
                "connection_state",
                peer_key,
                f"ICE候选收集：{pc.iceGatheringState}"
            )

        @pc.on("signalingstatechange")
        def on_signaling_state_change():
            self.event_callback(
                "connection_state",
                peer_key,
                f"信令状态：{pc.signalingState}"
            )

        @pc.on("datachannel")
        def on_datachannel(channel):
            self._bind_channel(peer_key, channel)

        return pc

    def _bind_channel(self, peer_key, channel):
        self.channels[peer_key] = channel

        @channel.on("open")
        def on_open():
            self.event_callback("connection_state", peer_key, "connected")

        @channel.on("close")
        def on_close():
            self.event_callback("connection_state", peer_key, "disconnected")

        @channel.on("message")
        def on_message(message):
            asyncio.create_task(
                self._handle_message(peer_key, channel, message)
            )

    async def connect(self, peer_key):
        await self.close(peer_key)
        pc = self._new_peer(peer_key)
        channel = pc.createDataChannel("remote-control")
        self._bind_channel(peer_key, channel)

        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)

        await self.publish_signal(
            peer_key,
            "offer",
            {
                "type": pc.localDescription.type,
                "sdp": pc.localDescription.sdp
            }
        )
        self.event_callback("connection_state", peer_key, "signaling")

    async def handle_signal(self, signal):
        peer_key = signal.get("from")
        signal_type = signal.get("type")
        payload = signal.get("payload") or {}

        if not peer_key or not isinstance(payload, dict):
            return

        if signal_type == "offer":
            if peer_key in self.pending_offers:
                return

            await self.close(peer_key)
            pc = self._new_peer(peer_key)
            description = self.RTCSessionDescription(
                sdp=payload.get("sdp", ""),
                type=payload.get("type", "offer")
            )
            await pc.setRemoteDescription(description)
            self.pending_offers[peer_key] = pc
            self.event_callback("incoming_connection", peer_key, "")
            return

        if signal_type == "answer":
            pc = self.peers.get(peer_key)
            if not pc or pc.remoteDescription:
                return

            description = self.RTCSessionDescription(
                sdp=payload.get("sdp", ""),
                type=payload.get("type", "answer")
            )
            await pc.setRemoteDescription(description)
            self.event_callback("connection_state", peer_key, "已收到 Answer")

    async def approve_offer(self, peer_key, approved):
        pc = self.pending_offers.pop(peer_key, None)
        if not pc:
            return

        if not approved:
            await pc.close()
            self.peers.pop(peer_key, None)
            self.event_callback("connection_state", peer_key, "rejected")
            return

        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        await self.publish_signal(
            peer_key,
            "answer",
            {
                "type": pc.localDescription.type,
                "sdp": pc.localDescription.sdp
            }
        )
        self.event_callback("connection_state", peer_key, "answer_sent")

    async def request_software(self, peer_key):
        self._send_json(peer_key, {
            "type": "get_software_list",
            "requestId": self._request_id()
        })

    async def request_screenshot(self, peer_key):
        self._send_json(peer_key, {
            "type": "capture_screen",
            "requestId": self._request_id(),
            "format": "jpeg",
            "quality": 78
        })

    def _send_json(self, peer_key, message):
        channel = self.channels.get(peer_key)
        if not channel or channel.readyState != "open":
            raise RuntimeError("尚未与该设备建立 P2P 连接")
        channel.send(json.dumps(message, ensure_ascii=False))

    async def _handle_message(self, peer_key, channel, message):
        if isinstance(message, bytes):
            state = self.screenshot_buffers.get(peer_key)
            if not state:
                return

            state["data"].extend(message)
            if len(state["data"]) >= state["size"]:
                payload = bytes(state["data"][:state["size"]])
                transfer_kind = state["kind"]
                self.screenshot_buffers.pop(peer_key, None)

                if transfer_kind == "screenshot":
                    self.event_callback("screenshot_received", peer_key, payload)
                elif transfer_kind == "software":
                    try:
                        software = json.loads(payload.decode("utf-8"))
                        self.event_callback(
                            "software_list_received", peer_key, software
                        )
                    except (UnicodeDecodeError, ValueError):
                        self.event_callback(
                            "peer_error", peer_key, "软件列表数据解析失败"
                        )
            return

        try:
            data = json.loads(message)
        except (TypeError, ValueError):
            return

        message_type = data.get("type")
        if message_type == "get_software_list":
            await self._send_software_list(peer_key, channel, data)
        elif message_type == "capture_screen":
            await self._send_screenshot(peer_key, channel, data)
        elif message_type == "transfer_begin":
            try:
                size = int(data.get("size", 0))
            except (TypeError, ValueError):
                return
            transfer_kind = data.get("kind")
            if transfer_kind in ("screenshot", "software") and 0 < size <= 20 * 1024 * 1024:
                self.screenshot_buffers[peer_key] = {
                    "kind": transfer_kind,
                    "size": size,
                    "data": bytearray()
                }
        elif message_type == "operation_error":
            self.event_callback(
                "peer_error",
                peer_key,
                data.get("message", "远端操作失败")
            )

    async def _send_software_list(self, peer_key, channel, request):
        try:
            from remote.software_manager import get_installed_software

            software = await asyncio.to_thread(get_installed_software)
            payload = json.dumps(
                software, ensure_ascii=False
            ).encode("utf-8")
        except Exception as exc:
            if channel.readyState == "open":
                channel.send(json.dumps({
                    "type": "operation_error",
                    "requestId": request.get("requestId"),
                    "message": f"读取软件列表失败：{exc}"
                }, ensure_ascii=False))
            return

        await self._send_binary_payload(
            channel, "software", payload, "application/json",
            request.get("requestId")
        )

    async def _send_screenshot(self, peer_key, channel, request):
        try:
            from remote.screenshot_manager import capture_primary_screen_jpeg

            image_data = await asyncio.to_thread(
                capture_primary_screen_jpeg,
                int(request.get("quality", 78))
            )
            if channel.readyState != "open":
                return

            await self._send_binary_payload(
                channel, "screenshot", image_data, "image/jpeg",
                request.get("requestId")
            )
        except Exception as exc:
            if channel.readyState == "open":
                channel.send(json.dumps({
                    "type": "operation_error",
                    "requestId": request.get("requestId"),
                    "message": f"远程截图失败：{exc}"
                }, ensure_ascii=False))

    async def _send_binary_payload(
        self, channel, transfer_kind, payload, mime_type, request_id
    ):
        if len(payload) > 20 * 1024 * 1024:
            raise ValueError("传输数据超过 20 MB 限制")
        if channel.readyState != "open":
            return

        channel.send(json.dumps({
            "type": "transfer_begin",
            "kind": transfer_kind,
            "requestId": request_id,
            "mime": mime_type,
            "size": len(payload)
        }))
        chunk_size = 16 * 1024
        for offset in range(0, len(payload), chunk_size):
            if channel.readyState != "open":
                break
            channel.send(payload[offset:offset + chunk_size])

    async def close(self, peer_key):
        pc = self.peers.pop(peer_key, None)
        self.pending_offers.pop(peer_key, None)
        self.channels.pop(peer_key, None)
        self.screenshot_buffers.pop(peer_key, None)
        if pc:
            await pc.close()

    async def close_all(self):
        for peer_key in list(self.peers):
            await self.close(peer_key)

    @staticmethod
    def _request_id():
        import uuid
        return uuid.uuid4().hex
