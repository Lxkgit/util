from __future__ import annotations

from pynput import keyboard


class HotkeyService:
    def __init__(self, on_action):
        self.on_action = on_action
        self.listener = None

    @staticmethod
    def to_pynput(value: str) -> str:
        mapping = {"escape":"esc","return":"enter","control":"ctrl","win":"cmd","meta":"cmd","pageup":"page_up","pagedown":"page_down"}
        parts = [mapping.get(p.strip().lower(), p.strip().lower()) for p in value.split("+") if p.strip()]
        if len(parts) == 1: return parts[0]
        special = {"ctrl","shift","alt","cmd","enter","esc","space","tab"}
        return "+".join(f"<{p}>" if p in special else p for p in parts)

    def install(self, start: str, stop: str, shared: bool):
        self.stop()
        start_spec = self._spec(start); stop_spec = self._spec(stop)
        hotkeys = {}
        if shared: hotkeys[start_spec] = lambda: self.on_action("record_toggle")
        else:
            hotkeys[start_spec] = lambda: self.on_action("record_start")
            hotkeys[stop_spec] = lambda: self.on_action("record_stop")
        hotkeys["<f9>"] = lambda: self.on_action("f9")
        hotkeys["<f10>"] = lambda: self.on_action("f10")
        self.listener = keyboard.GlobalHotKeys(hotkeys)
        self.listener.start()

    def stop(self):
        if self.listener:
            self.listener.stop(); self.listener = None

    def ignored_keys(self, start: str, stop: str) -> set[str]:
        keys = {"f9", "f10"}
        for shortcut in (start, stop):
            for part in shortcut.lower().split("+"):
                part = part.strip()
                if part: keys.add(self.to_pynput(part).replace("<", "").replace(">", ""))
        return keys

    def _spec(self, value: str) -> str:
        converted = self.to_pynput(value)
        return converted if "+" in converted or converted.startswith("<") else f"<{converted}>"
