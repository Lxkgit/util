from __future__ import annotations

import ctypes
import sys
import time
from threading import Event, Lock, Thread

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
        self._keyboard_thread = None
        self._keyboard_stop = None
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
            if self._windows:
                self._start_windows_keyboard_poll()
            else:
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

        stop = self._keyboard_stop
        thread = self._keyboard_thread
        self._keyboard_stop = None
        self._keyboard_thread = None
        if stop:
            stop.set()
        if thread:
            try:
                thread.join(timeout=1.0)
            except RuntimeError:
                pass

        for attr in ("_keyboard_listener", "_mouse_listener"):
            listener = getattr(self, attr)
            setattr(self, attr, None)
            if listener:
                try:
                    listener.stop()
                    listener.join(timeout=1.0)
                except (RuntimeError, AttributeError):
                    pass

    def _start_windows_keyboard_poll(self):
        stop = Event()
        self._keyboard_stop = stop
        self._keyboard_thread = Thread(target=self._windows_keyboard_poll, args=(stop,), daemon=True, name="windows-keyboard-recorder")
        self._keyboard_thread.start()

    def _windows_keyboard_poll(self, stop: Event):
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        get_state = user32.GetAsyncKeyState
        get_state.argtypes = [ctypes.c_int]
        get_state.restype = ctypes.c_short
        key_map = self._windows_key_map()
        previous = {vk: False for vk in key_map}
        while not stop.is_set():
            for vk, name in key_map.items():
                pressed = bool(get_state(vk) & 0x8000)
                if pressed != previous[vk]:
                    if pressed:
                        self._on_key_press_name(name)
                    else:
                        self._on_key_release_name(name)
                    previous[vk] = pressed
            stop.wait(0.005)

    @staticmethod
    def _windows_key_map() -> dict[int, str]:
        m = {vk: chr(vk).lower() for vk in range(0x41, 0x5B)}
        m.update({vk: chr(vk) for vk in range(0x30, 0x3A)})
        m.update({vk: f"f{vk - 0x6F}" for vk in range(0x70, 0x7C)})
        m.update({
            0x08:"backspace",0x09:"tab",0x0D:"enter",0x1B:"esc",0x20:"space",
            0x21:"page_up",0x22:"page_down",0x23:"end",0x24:"home",0x25:"left",
            0x26:"up",0x27:"right",0x28:"down",0x2D:"insert",0x2E:"delete",
            0x5B:"cmd_l",0x5C:"cmd_r",0x5D:"menu",0x90:"num_lock",0x91:"scroll_lock",
            0x14:"caps_lock",0x2C:"print_screen",0x13:"pause",
            0xA0:"shift_l",0xA1:"shift_r",0xA2:"ctrl_l",0xA3:"ctrl_r",0xA4:"alt_l",0xA5:"alt_r",
            0x60:"num0",0x61:"num1",0x62:"num2",0x63:"num3",0x64:"num4",0x65:"num5",
            0x66:"num6",0x67:"num7",0x68:"num8",0x69:"num9",0x6A:"num_multiply",
            0x6B:"num_add",0x6D:"num_subtract",0x6E:"num_decimal",0x6F:"num_divide",
            0xBA:";",0xBB:"=",0xBC:",",0xBD:"-",0xBE:".",0xBF:"/",0xC0:"`",
            0xDB:"[",0xDC:"\\",0xDD:"]",0xDE:"'",
        })
        return m

    @staticmethod
    def _normalize_key_name(name: str) -> str:
        value = str(name).strip().lower()
        if value.startswith("key."):
            value = value[4:]
        return {
            "control":"ctrl", "return":"enter", "escape":"esc", "capslock":"caps_lock",
            "pageup":"page_up", "pagedown":"page_down", "windows":"cmd", "win":"cmd",
        }.get(value, value)

    @classmethod
    def _key_name(cls, key) -> str:
        if isinstance(key, keyboard.KeyCode):
            return cls._normalize_key_name(key.char if key.char else str(key))
        return cls._normalize_key_name(str(key))

    def _on_key_press_name(self, name: str):
        with self._lock:
            if not self.recording or self.paused or name in self._ignored_keys or name in self._pressed_keys:
                return
            self._pressed_keys.add(name)
        self._add("key_down", {"key": name})

    def _on_key_release_name(self, name: str):
        with self._lock:
            if not self.recording or self.paused or name in self._ignored_keys:
                return
            self._pressed_keys.discard(name)
        self._add("key_up", {"key": name})

    def _on_key_press(self, key):
        self._on_key_press_name(self._key_name(key))

    def _on_key_release(self, key):
        self._on_key_release_name(self._key_name(key))

    def _add(self, event_type: str, data: dict):
        with self._lock:
            if not self.recording or self.paused:
                return
            now = time.perf_counter()
            event = MacroEvent(event_type, max(0.0, now - self._last_time), data)
            self._last_time = now
        if self.on_event:
            self.on_event(event)

    def _on_move(self, x, y):
        if self.mode not in {"all", "mouse"}:
            return
        now = time.perf_counter()
        with self._lock:
            if not self.recording or self.paused:
                return
            last = self._last_move_pos
            if last is not None:
                dx, dy = x - last[0], y - last[1]
                if now - self._last_move_time < self.move_interval and dx * dx + dy * dy < self.move_distance ** 2:
                    return
            self._last_move_time = now
            self._last_move_pos = (x, y)
        self._add("mouse_move", {"x": int(x), "y": int(y)})

    def _on_click(self, x, y, button, pressed):
        if self.mode not in {"all", "mouse"}:
            return
        self._add("mouse_click", {"x": int(x), "y": int(y), "button": str(button).replace("Button.", ""), "pressed": bool(pressed)})

    def _on_scroll(self, x, y, dx, dy):
        if self.mode not in {"all", "mouse"}:
            return
        self._add("mouse_scroll", {"x": int(x), "y": int(y), "dx": int(dx), "dy": int(dy)})
