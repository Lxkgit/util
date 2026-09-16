from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes
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
        self._windows_thread = None
        self._windows_stop = None
        self._keyboard_hook = None
        self._mouse_hook = None
        self._keyboard_proc = None
        self._mouse_proc = None
        self._pressed_keys: set[str] = set()
        self._ignored_keys: set[str] = set()
        self._last_move_time = 0.0
        self._last_move_pos: tuple[int, int] | None = None
        self.move_interval = 0.03
        self.move_distance = 3
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

        if self._windows:
            self._start_windows_hooks()
            return

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

        if self._windows:
            self._stop_windows_hooks()
            return

        listeners = (self._keyboard_listener, self._mouse_listener)
        self._keyboard_listener = None
        self._mouse_listener = None
        for listener in listeners:
            if not listener:
                continue
            listener.stop()
            try:
                listener.join(timeout=1.0)
            except RuntimeError:
                pass

    def _start_windows_hooks(self):
        self._windows_stop = Event()
        self._windows_thread = Thread(target=self._windows_hook_thread, daemon=True)
        self._windows_thread.start()

    def _windows_hook_thread(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        WH_KEYBOARD_LL = 13
        WH_MOUSE_LL = 14
        WM_QUIT = 0x0012
        LRESULT = ctypes.c_ssize_t

        LowLevelKeyboardProc = ctypes.WINFUNCTYPE(
            LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
        )
        LowLevelMouseProc = ctypes.WINFUNCTYPE(
            LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
        )

        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("vkCode", wintypes.DWORD),
                ("scanCode", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t),
            ]

        class POINT(ctypes.Structure):
            _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

        class MSLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("pt", POINT),
                ("mouseData", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t),
            ]

        def keyboard_proc(n_code, w_param, l_param):
            if n_code >= 0 and self._windows_stop and not self._windows_stop.is_set():
                info = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                vk = int(info.vkCode)
                is_up = int(w_param) in (0x0101, 0x0105)
                name = self._windows_vk_name(vk, int(info.scanCode), int(info.flags))
                if name:
                    if is_up:
                        self._on_key_release_name(name)
                    else:
                        self._on_key_press_name(name)
            return user32.CallNextHookEx(None, n_code, w_param, l_param)

        def mouse_proc(n_code, w_param, l_param):
            if n_code >= 0 and self._windows_stop and not self._windows_stop.is_set():
                info = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                x, y = int(info.pt.x), int(info.pt.y)
                msg = int(w_param)
                if msg == 0x0200:
                    if self.mode in {"all", "mouse"}:
                        self._on_move(x, y)
                elif msg in (0x0201, 0x0202, 0x0204, 0x0205, 0x0207, 0x0208):
                    if self.mode in {"all", "mouse"}:
                        button = {0x0201: "left", 0x0202: "left", 0x0204: "right", 0x0205: "right", 0x0207: "middle", 0x0208: "middle"}[msg]
                        self._add("mouse_click", {"x": x, "y": y, "button": button, "pressed": msg in (0x0201, 0x0204, 0x0207)})
                elif msg == 0x020A:
                    if self.mode in {"all", "mouse"}:
                        delta = ctypes.c_short((int(info.mouseData) >> 16) & 0xFFFF).value
                        self._add("mouse_scroll", {"x": x, "y": y, "dx": 0, "dy": int(delta / 120)})
            return user32.CallNextHookEx(None, n_code, w_param, l_param)

        self._keyboard_proc = LowLevelKeyboardProc(keyboard_proc)
        self._mouse_proc = LowLevelMouseProc(mouse_proc)

        if self.mode in {"all", "keyboard"}:
            self._keyboard_hook = user32.SetWindowsHookExW(
                WH_KEYBOARD_LL, self._keyboard_proc, kernel32.GetModuleHandleW(None), 0
            )
        if self.mode in {"all", "mouse"}:
            self._mouse_hook = user32.SetWindowsHookExW(
                WH_MOUSE_LL, self._mouse_proc, kernel32.GetModuleHandleW(None), 0
            )

        if (self.mode in {"all", "keyboard"} and not self._keyboard_hook) or (self.mode in {"all", "mouse"} and not self._mouse_hook):
            raise ctypes.WinError()

        msg = wintypes.MSG()
        while self._windows_stop and not self._windows_stop.is_set():
            result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result <= 0:
                break

        if self._keyboard_hook:
            user32.UnhookWindowsHookEx(self._keyboard_hook)
            self._keyboard_hook = None
        if self._mouse_hook:
            user32.UnhookWindowsHookEx(self._mouse_hook)
            self._mouse_hook = None

    def _stop_windows_hooks(self):
        stop = self._windows_stop
        thread = self._windows_thread
        self._windows_stop = None
        self._windows_thread = None
        if not stop:
            return
        stop.set()
        if thread and thread.is_alive():
            try:
                ctypes.windll.user32.PostThreadMessageW(thread.ident, 0x0012, 0, 0)
            except Exception:
                pass
            thread.join(timeout=1.5)

    def _windows_vk_name(self, vk: int, scan_code: int, flags: int) -> str:
        mapping = {
            0x08: "backspace", 0x09: "tab", 0x0D: "enter", 0x10: "shift",
            0x11: "ctrl", 0x12: "alt", 0x13: "pause", 0x14: "caps_lock",
            0x1B: "esc", 0x20: "space", 0x21: "page_up", 0x22: "page_down",
            0x23: "end", 0x24: "home", 0x25: "left", 0x26: "up", 0x27: "right",
            0x28: "down", 0x2D: "insert", 0x2E: "delete", 0x5B: "cmd_l", 0x5C: "cmd_r",
            0x5D: "menu", 0x70: "f1", 0x71: "f2", 0x72: "f3", 0x73: "f4",
            0x74: "f5", 0x75: "f6", 0x76: "f7", 0x77: "f8", 0x78: "f9",
            0x79: "f10", 0x7A: "f11", 0x7B: "f12", 0x90: "num_lock", 0x91: "scroll_lock",
            0xA0: "shift_l", 0xA1: "shift_r", 0xA2: "ctrl_l", 0xA3: "ctrl_r",
            0xA4: "alt_l", 0xA5: "alt_r", 0x2C: "print_screen",
        }
        if vk in mapping:
            return mapping[vk]
        if 0x41 <= vk <= 0x5A:
            return chr(vk).lower()
        if 0x30 <= vk <= 0x39:
            return chr(vk)
        if 0x60 <= vk <= 0x69:
            return f"num{vk - 0x60}"
        return ""

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

    @staticmethod
    def _normalize_key_name(name: str) -> str:
        value = str(name).strip().lower()
        if value.startswith("key."):
            value = value[4:]
        aliases = {
            "control": "ctrl", "return": "enter", "escape": "esc", "capslock": "caps_lock",
            "pageup": "page_up", "pagedown": "page_down", "windows": "cmd", "win": "cmd",
        }
        return aliases.get(value, value)

    @classmethod
    def _key_name(cls, key) -> str:
        if isinstance(key, keyboard.KeyCode):
            return cls._normalize_key_name(key.char or str(key))
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
            if not self.recording or self.paused or name in self._ignored_keys or name in self._pressed_keys:
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
        self._add("mouse_move", {"x": x, "y": y})

    def _on_click(self, x, y, button, pressed):
        self._add("mouse_click", {"x": x, "y": y, "button": str(button).replace("Button.", ""), "pressed": pressed})

    def _on_scroll(self, x, y, dx, dy):
        self._add("mouse_scroll", {"x": x, "y": y, "dx": dx, "dy": dy})
