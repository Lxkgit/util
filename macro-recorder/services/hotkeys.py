from __future__ import annotations

from pynput import keyboard


class HotkeyService:
    def __init__(self, on_action):
        self.on_action = on_action
        self.listener = None

    @staticmethod
    def normalize(value: str) -> str:
        mapping = {
            "escape": "esc",
            "return": "enter",
            "control": "ctrl",
            "windows": "cmd",
            "win": "cmd",
            "meta": "cmd",
            "pageup": "page_up",
            "pagedown": "page_down",
            "capslock": "caps_lock",
        }
        parts = []
        for part in value.split("+"):
            part = part.strip().lower()
            if part:
                parts.append(mapping.get(part, part))
        return "+".join(parts)

    @classmethod
    def to_pynput(cls, value: str) -> str:
        normalized = cls.normalize(value)
        parts = normalized.split("+")
        special = {
            "ctrl", "shift", "alt", "cmd", "enter", "esc", "space", "tab",
            "backspace", "delete", "insert", "home", "end", "page_up", "page_down",
            "up", "down", "left", "right",
        }
        if len(parts) == 1:
            return f"<{parts[0]}>" if parts[0] in special or parts[0].startswith("f") else parts[0]
        return "+".join(
            f"<{part}>" if part in special or part.startswith("f") else part
            for part in parts
        )

    def install(self, record_start: str, record_stop: str, record_shared: bool, play_pause: str, stop_playback: str):
        self.stop()
        hotkeys = {
            self._spec(record_start): lambda: self.on_action("record_toggle"),
            self._spec(record_stop): lambda: self.on_action("record_stop"),
            self._spec(play_pause): lambda: self.on_action("play_pause"),
            self._spec(stop_playback): lambda: self.on_action("stop_playback"),
        }

        # 只监听，不拦截系统输入。
        # 截图、游戏等其他软件的组合快捷键必须能够正常到达系统。
        self.listener = keyboard.GlobalHotKeys(hotkeys, suppress=False)
        self.listener.start()

    def stop(self):
        listener = self.listener
        self.listener = None
        if not listener:
            return
        listener.stop()
        try:
            listener.join(timeout=1.0)
        except RuntimeError:
            pass

    def ignored_keys(self, *shortcuts: str) -> set[str]:
        """
        返回需要从录制内容中排除的控制键。

        只有单键控制快捷键才排除，例如 F8/F9/F10/F11。
        组合快捷键不能简单排除其中的每一个按键，否则像 Alt+A、Ctrl+Shift+S
        这样的正常系统快捷键会被误认为控制键，导致截图等操作无法被录制。
        组合控制快捷键仍由 GlobalHotKeys 负责触发控制动作，但其按键本身允许
        进入录制数据，从而保证屏幕级宏可以完整记录真实键盘操作。
        """
        keys = set()
        for shortcut in shortcuts:
            parts = [part for part in self.normalize(shortcut).split("+") if part]
            if len(parts) == 1:
                keys.add(parts[0])
        return keys

    def _spec(self, value: str) -> str:
        return self.to_pynput(value)
