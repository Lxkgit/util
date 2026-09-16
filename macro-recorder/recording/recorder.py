from __future__ import annotations

import sys
import time
from threading import Lock

from pynput import keyboard, mouse

from core.model import MacroEvent


class MacroRecorder:
    MODES = {"all", "keyboard", "mouse"}

    def __init__(self, on_event=None):
        self.on_event = on_event
        self.recording = False
        self.paused = False
        self.mode = "all"
        self._lock = Lock()
        self._last_time = 0.0
        self._keyboard_listener = None
        self._mouse_listener = None
        self._pressed_keys: set[str] = set()
        self._ignored_keys: set[str] = set()
        self._last_move_time = 0.0
        self._last_move_pos: tuple[int, int] | None = None
        self.move_interval = 0.02
        self.move_distance = 2
        self._windows = sys.platform.startswith("win")

    def set_mode(self, mode: str):
        if mode not in self.MODES:
            raise ValueError(f"不支持的录制模式: {mode}")
        self.mode = mode

    def set_ignored_keys(self, keys: set[str]):
        with self._lock:
            self._ignored_keys = {self._normalize_key_name(key) for key in keys}

    def start(self, mode: str | None = None):
        if mode:
            self.set_mode(mode)
        self.stop()
        with self._lock:
            self.recording = True
            self.paused = False
            self._last_time = time.perf_counter()
            self._last_move_time = self._last_time
            self._last_move_pos = None
            self._pressed_keys.clear()

        if self.mode in {"all", "keyboard"}:
            self._keyboard_listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release,
                suppress=False,
            )
            self._keyboard_listener.daemon = True
            self._keyboard_listener.start()

        if self.mode in {"all", "mouse"}:
            self._mouse_listener = mouse.Listener(
                on_move=self._on_move,
                on_click=self._on_click,
                on_scroll=self._on_scroll,
                suppress=False,
            )
            self._mouse_listener.daemon = True
            self._mouse_listener.start()

    def pause(self):
        with self._lock:
            if not self.recording:
                return False
            self.paused = True
            self._pressed_keys.clear()
        return True

    def resume(self):
        with self._lock:
            if not self.recording:
                return False
            self.paused = False
            self._last_time = time.perf_counter()
            self._last_move_time = self._last_time
            self._last_move_pos = None
            self._pressed_keys.clear()
        return True

    def toggle_pause(self):
        with self._lock:
            if not self.recording:
                return False
            paused = self.paused
        return self.resume() if paused else self.pause()

    def stop(self):
        with self._lock:
            self.recording = False
            self.paused = False
            self._pressed_keys.clear()
            self._last_move_pos = None

        listeners = (self._keyboard_listener, self._mouse_listener)
        self._keyboard_listener = None
        self._mouse_listener = None
        for listener in listeners:
            if not listener:
                continue
            try:
                listener.stop()
                listener.join(timeout=1.0)
            except (RuntimeError, AttributeError):
                pass

    @staticmethod
    def _normalize_key_name(name: str) -> str:
        value = str(name).strip().lower()
        if value.startswith("key."):
            value = value[4:]
        aliases = {
            "control": "ctrl",
            "return": "enter",
            "escape": "esc",
            "capslock": "caps_lock",
            "pageup": "page_up",
            "pagedown": "page_down",
            "windows": "cmd",
            "win": "cmd",
        }
        return aliases.get(value, value)

    @classmethod
    def _key_name(cls, key) -> str:
        if isinstance(key, keyboard.KeyCode):
            if key.char:
                return cls._normalize_key_name(key.char)
            return cls._normalize_key_name(str(key))
        return cls._normalize_key_name(str(key))

    def _add(self, event_type: str, data: dict):
        with self._lock:
            if not self.recording or self.paused:
                return
            now = time.perf_counter()
            event = MacroEvent(event_type, max(0.0, now - self._last_time), data)
            self._last_time = now
        if self.on_event:
            self.on_event(event)

    def _on_key_press(self, key):
        name = self._key_name(key)
        with self._lock:
            if not self.recording or self.paused or name in self._ignored_keys:
                return
            if name in self._pressed_keys:
                return
            self._pressed_keys.add(name)
        self._add("key_down", {"key": name})

    def _on_key_release(self, key):
        name = self._key_name(key)
        with self._lock:
            if not self.recording or self.paused or name in self._ignored_keys:
                return
            self._pressed_keys.discard(name)
        self._add("key_up", {"key": name})

    def _on_move(self, x, y):
        if self.mode not in {"all", "mouse"}:
            return
        now = time.perf_counter()
        with self._lock:
            if not self.recording or self.paused:
                return
            last = self._last_move_pos
            if last is not None:
                dx = x - last[0]
                dy = y - last[1]
                if now - self._last_move_time < self.move_interval and dx * dx + dy * dy < self.move_distance ** 2:
                    return
            self._last_move_time = now
            self._last_move_pos = (x, y)
        self._add("mouse_move", {"x": int(x), "y": int(y)})

    def _on_click(self, x, y, button, pressed):
        if self.mode not in {"all", "mouse"}:
            return
        self._add(
            "mouse_click",
            {
                "x": int(x),
                "y": int(y),
                "button": str(button).replace("Button.", ""),
                "pressed": bool(pressed),
            },
        )

    def _on_scroll(self, x, y, dx, dy):
        if self.mode not in {"all", "mouse"}:
            return
        self._add(
            "mouse_scroll",
            {"x": int(x), "y": int(y), "dx": int(dx), "dy": int(dy)},
        )
