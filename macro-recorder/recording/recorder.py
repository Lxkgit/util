from __future__ import annotations

import time
from threading import Lock
from pynput import keyboard, mouse

from core.model import MacroEvent


class MacroRecorder:
    MODES = {"all", "keyboard", "mouse"}

    def __init__(self, on_event=None):
        self.on_event = on_event
        self.recording = False
        self.mode = "all"
        self._lock = Lock()
        self._last_time = 0.0
        self._keyboard_listener = None
        self._mouse_listener = None
        self._pressed_keys: set[str] = set()
        self._ignored_keys: set[str] = set()
        self._last_move_time = 0.0
        self._last_move_pos: tuple[int, int] | None = None
        self.move_interval = 0.03
        self.move_distance = 3

    def set_mode(self, mode: str):
        if mode not in self.MODES:
            raise ValueError(f"不支持的录制模式: {mode}")
        self.mode = mode

    def set_ignored_keys(self, keys: set[str]):
        with self._lock:
            self._ignored_keys = set(keys)

    def start(self, mode: str | None = None):
        if mode:
            self.set_mode(mode)
        self.stop()
        with self._lock:
            self.recording = True
            self._last_time = time.perf_counter()
            self._last_move_time = self._last_time
            self._last_move_pos = None
            self._pressed_keys.clear()
        if self.mode in {"all", "keyboard"}:
            self._keyboard_listener = keyboard.Listener(on_press=self._on_key_press, on_release=self._on_key_release)
            self._keyboard_listener.start()
        if self.mode in {"all", "mouse"}:
            self._mouse_listener = mouse.Listener(on_move=self._on_move, on_click=self._on_click, on_scroll=self._on_scroll)
            self._mouse_listener.start()

    def stop(self):
        with self._lock:
            self.recording = False
            self._pressed_keys.clear()
            self._last_move_pos = None
        listeners = (self._keyboard_listener, self._mouse_listener)
        self._keyboard_listener = None
        self._mouse_listener = None
        for listener in listeners:
            if listener:
                listener.stop()

    def _add(self, event_type: str, data: dict):
        with self._lock:
            if not self.recording:
                return
            now = time.perf_counter()
            event = MacroEvent(event_type, max(0.0, now - self._last_time), data)
            self._last_time = now
        if self.on_event:
            self.on_event(event)

    @staticmethod
    def _key_name(key) -> str:
        if isinstance(key, keyboard.KeyCode):
            return key.char or str(key)
        return str(key).replace("Key.", "")

    def _on_key_press(self, key):
        name = self._key_name(key)
        with self._lock:
            if not self.recording or name in self._ignored_keys or name in self._pressed_keys:
                return
            self._pressed_keys.add(name)
        self._add("key_down", {"key": name})

    def _on_key_release(self, key):
        name = self._key_name(key)
        with self._lock:
            if not self.recording or name in self._ignored_keys:
                return
            self._pressed_keys.discard(name)
        self._add("key_up", {"key": name})

    def _on_move(self, x, y):
        now = time.perf_counter()
        with self._lock:
            if not self.recording:
                return
            last = self._last_move_pos
            if last is not None:
                dx, dy = x - last[0], y - last[1]
                if now - self._last_move_time < self.move_interval and dx * dx + dy * dy < self.move_distance ** 2:
                    return
            self._last_move_time = now
            self._last_move_pos = (x, y)
        self._add("mouse_move", {"x": x, "y": y})

    def _on_click(self, x, y, button, pressed):
        self._add("mouse_click", {"x": x, "y": y, "button": str(button).replace("Button.", ""), "pressed": pressed})

    def _on_scroll(self, x, y, dx, dy):
        self._add("mouse_scroll", {"x": x, "y": y, "dx": dx, "dy": dy})
