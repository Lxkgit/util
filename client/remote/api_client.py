import json
import requests


class RemoteApiError(RuntimeError):
    """远程设备服务接口异常。"""


class RemoteApiClient:
    def __init__(self, base_url="http://124.221.195.130", timeout=8):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def _request(self, method, path, **kwargs):
        url = f"{self.base_url}{path}"
        try:
            response = self.session.request(
                method,
                url,
                timeout=self.timeout,
                **kwargs
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise RemoteApiError(f"请求服务端失败：{exc}") from exc
        except ValueError as exc:
            raise RemoteApiError("服务端返回的内容不是有效 JSON") from exc

        if isinstance(data, dict) and data.get("success") is False:
            raise RemoteApiError(
                data.get("message") or data.get("msg") or "服务端操作失败"
            )
        return data

    def register(self, device_info):
        if not isinstance(device_info, dict) or not device_info.get("key"):
            raise ValueError("注册信息必须包含 key")

        return self._request(
            "POST",
            "/api/file/client/register",
            json=device_info
        )

    def heartbeat(self, device_key):
        if not device_key:
            raise ValueError("设备 key 不能为空")

        return self._request(
            "GET",
            "/api/file/client/heartBeat",
            params={"key": device_key}
        )

    def list_clients(self):
        data = self._request("GET", "/api/file/client/list")
        if not isinstance(data, dict):
            raise RemoteApiError("设备列表响应格式不正确")

        result = data.get("result", [])
        if result is None:
            return []
        if not isinstance(result, list):
            raise RemoteApiError("设备列表 result 不是数组")

        devices = []
        for item in result:
            try:
                device = json.loads(item) if isinstance(item, str) else item
            except (TypeError, ValueError):
                continue

            if isinstance(device, dict) and device.get("key"):
                devices.append(device)

        return devices
