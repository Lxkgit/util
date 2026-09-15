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
        hotkeys = {}

        if record_shared:
            hotkeys[self._spec(record_start)] = lambda: self.on_action("record_toggle")
        else:
            hotkeys[self._spec(record_start)] = lambda: self.on_action("record_start")
            hotkeys[self._spec(record_stop)] = lambda: self.on_action("record_stop")

        hotkeys[self._spec(play_pause)] = lambda: self.on_action("play_pause")
        hotkeys[self._spec(stop_playback)] = lambda: self.on_action("stop_playback")

        self.listener = keyboard.GlobalHotKeys(hotkeys)
        self.listener.start()

    def stop(self):
        if self.listener:
            self.listener.stop()
            self.listener = None

    def ignored_keys(self, *shortcuts: str) -> set[str]:
        keys = set()
        for shortcut in shortcuts:
            for part in self.normalize(shortcut).split("+"):
                if part:
                    keys.add(part)
        return keys

    def _spec(self, value: str) -> str:
        return self.to_pynput(value)
