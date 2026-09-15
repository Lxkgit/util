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

    def start(self):
        self.stop()
        with self._lock:
            self.events.clear()
            self.recording = True
            self._last_time = time.perf_counter()

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
        for listener in (self._keyboard_listener, self._mouse_listener):
            if listener:
                listener.stop()
        self._keyboard_listener = None
        self._mouse_listener = None
        self._pressed_keys.clear()

    def _add(self, event_type: str, data: dict):
        with self._lock:
            if not self.recording:
                return
            now = time.perf_counter()
            delay = max(0.0, now - self._last_time)
            self._last_time = now
            event = MacroEvent(event_type, delay, data)
            self.events.append(event)
        if self.on_event:
            self.on_event(event)

    @staticmethod
    def _key_name(key) -> str:
        if isinstance(key, keyboard.KeyCode):
            return key.char or str(key)
        return str(key).replace("Key.", "")

    def _on_key_press(self, key):
        name = self._key_name(key)
        if name in self._pressed_keys:
            return
        self._pressed_keys.add(name)
        self._add("key_down", {"key": name})

    def _on_key_release(self, key):
        name = self._key_name(key)
        self._pressed_keys.discard(name)
        self._add("key_up", {"key": name})

    def _on_move(self, x, y):
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
