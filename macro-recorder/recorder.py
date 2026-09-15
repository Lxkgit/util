from __future__ import annotations

import time
from threading import Lock
from pynput import keyboard, mouse

from model import MacroEvent


class MacroRecorder:
    def __init__(self, on_event=None):
        self.on_event = on_event
        self.events: list[MacroEvent] = []
        self.recording = False
        self._last_time = 0.0
        self._keyboard_listener = None
        self._mouse_listener = None
        self._lock = Lock()
        self._pressed_keys: set[str] = set()
        self._ignored_keys: set[str] = set()
        self._last_move_time = 0.0
        self._last_move_pos: tuple[int, int] | None = None
        self.move_interval = 0.03
        self.move_distance = 3

    def set_ignored_keys(self, keys: set[str]):
        with self._lock:
            self._ignored_keys = set(keys)

    def start(self):
        self.stop()
        with self._lock:
            self.events.clear()
            self.recording = True
            now = time.perf_counter()
            self._last_time = now
            self._last_move_time = now
            self._last_move_pos = None

        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self._mouse_listener = mouse.Listener(
            on_move=self._on_move,
            on_click=self._on_click,
            on_scroll=self._on_scroll,
        )
        self._keyboard_listener.start()
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
        callback = None
        event = None
        with self._lock:
            if not self.recording:
                return
            now = time.perf_counter()
            delay = max(0.0, now - self._last_time)
            self._last_time = now
            event = MacroEvent(event_type, delay, data)
            self.events.append(event)
            callback = self.on_event
        if callback:
            callback(event)

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
            if name in self._ignored_keys:
                return
            if not self.recording:
                return
            self._pressed_keys.discard(name)
        self._add("key_up", {"key": name})

    def _on_move(self, x, y):
        now = time.perf_counter()
        with self._lock:
            if not self.recording:
                return
            last_pos = self._last_move_pos
            if last_pos is not None:
                dx = x - last_pos[0]
                dy = y - last_pos[1]
                if now - self._last_move_time < self.move_interval and dx * dx + dy * dy < self.move_distance * self.move_distance:
                    return
            self._last_move_time = now
            self._last_move_pos = (x, y)
        self._add("mouse_move", {"x": x, "y": y})

    def _on_click(self, x, y, button, pressed):
        self._add("mouse_click", {
            "x": x,
            "y": y,
            "button": str(button).replace("Button.", ""),
            "pressed": pressed,
        })

    def _on_scroll(self, x, y, dx, dy):
        self._add("mouse_scroll", {"x": x, "y": y, "dx": dx, "dy": dy})
