from __future__ import annotations

import ctypes
import sys
import time
from threading import Lock, Thread

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
        self._windows_hook_thread = None
        self._windows_hook_thread_id = 0
        self._windows_keyboard_hook = None
        self._windows_mouse_hook = None
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

        if self._windows and self.mode in {"all", "keyboard"}:
            self._start_windows_keyboard_hook()
        elif self.mode in {"all", "keyboard"}:
            self._keyboard_listener = keyboard.Listener(on_press=self._on_key_press, on_release=self._on_key_release, suppress=False)
            self._keyboard_listener.daemon = True
            self._keyboard_listener.start()

        if self._windows and self.mode in {"all", "mouse"}:
            self._start_windows_mouse_hook()
        elif self.mode in {"all", "mouse"}:
            self._mouse_listener = mouse.Listener(on_move=self._on_move, on_click=self._on_click, on_scroll=self._on_scroll, suppress=False)
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

        if self._windows_hook_thread:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            if self._windows_hook_thread_id:
                kernel32.PostThreadMessageW(self._windows_hook_thread_id, 0x0012, 0, 0)
            try:
                self._windows_hook_thread.join(timeout=1.5)
            except RuntimeError:
                pass
            self._windows_hook_thread = None
            self._windows_hook_thread_id = 0
            self._windows_keyboard_hook = None
            self._windows_mouse_hook = None

        for attr in ("_keyboard_listener", "_mouse_listener"):
            listener = getattr(self, attr)
            setattr(self, attr, None)
            if listener:
                try:
                    listener.stop()
                    listener.join(timeout=1.0)
                except (RuntimeError, AttributeError):
                    pass

    def _start_windows_keyboard_hook(self):
        self._start_windows_hook(mouse_hook=False)

    def _start_windows_mouse_hook(self):
        if self._windows_hook_thread is None:
            self._start_windows_hook(mouse_hook=True)
        else:
            # 同一个 Windows Hook 线程同时安装键盘和鼠标 Hook。
            return

    def _start_windows_hook(self, mouse_hook=False):
        # 第一次启动时，线程根据当前录制模式安装需要的两个 Hook。
        if self._windows_hook_thread is not None:
            return
        self._windows_hook_thread = Thread(target=self._windows_hook_thread_main, daemon=True, name="windows-input-hook")
        self._windows_hook_thread.start()

    def _windows_hook_thread_main(self):
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        thread_id = kernel32.GetCurrentThreadId()
        self._windows_hook_thread_id = int(thread_id)

        LRESULT = ctypes.c_ssize_t
        HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, ctypes.c_size_t, ctypes.c_void_p)

        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [("vkCode", ctypes.c_uint32), ("scanCode", ctypes.c_uint32), ("flags", ctypes.c_uint32), ("time", ctypes.c_uint32), ("dwExtraInfo", ctypes.c_size_t)]

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        class MSLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [("pt", POINT), ("mouseData", ctypes.c_uint32), ("flags", ctypes.c_uint32), ("time", ctypes.c_uint32), ("dwExtraInfo", ctypes.c_size_t)]

        keyboard_hook = None
        mouse_hook = None

        @HOOKPROC
        def keyboard_proc(n_code, w_param, l_param):
            if n_code >= 0 and l_param:
                data = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                msg = int(w_param)
                if msg == 0x0100 or msg == 0x0104:
                    self._on_windows_vk(data.vkCode, True)
                elif msg == 0x0101 or msg == 0x0105:
                    self._on_windows_vk(data.vkCode, False)
            return user32.CallNextHookEx(keyboard_hook or 0, n_code, w_param, l_param)

        @HOOKPROC
        def mouse_proc(n_code, w_param, l_param):
            if n_code >= 0 and l_param:
                data = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                msg = int(w_param)
                x, y = int(data.pt.x), int(data.pt.y)
                if msg == 0x0200:
                    self._on_move(x, y)
                elif msg == 0x0201:
                    self._on_mouse_button(x, y, "left", True)
                elif msg == 0x0202:
                    self._on_mouse_button(x, y, "left", False)
                elif msg == 0x0204:
                    self._on_mouse_button(x, y, "right", True)
                elif msg == 0x0205:
                    self._on_mouse_button(x, y, "right", False)
                elif msg == 0x0207:
                    self._on_mouse_button(x, y, "middle", True)
                elif msg == 0x0208:
                    self._on_mouse_button(x, y, "middle", False)
                elif msg == 0x020A:
                    delta = ctypes.c_short((data.mouseData >> 16) & 0xFFFF).value
                    self._add("mouse_scroll", {"x": x, "y": y, "dx": 0, "dy": delta // 120 if delta else 0})
                elif msg == 0x020E:
                    delta = ctypes.c_short((data.mouseData >> 16) & 0xFFFF).value
                    self._add("mouse_scroll", {"x": x, "y": y, "dx": delta // 120 if delta else 0, "dy": 0})
            return user32.CallNextHookEx(mouse_hook or 0, n_code, w_param, l_param)

        try:
            user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, ctypes.c_void_p, ctypes.c_uint32]
            user32.SetWindowsHookExW.restype = ctypes.c_void_p
            user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.c_void_p]
            user32.CallNextHookEx.restype = LRESULT
            user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
            user32.UnhookWindowsHookEx.restype = ctypes.c_bool
            user32.GetMessageW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32]
            user32.GetMessageW.restype = ctypes.c_int

            hinst = kernel32.GetModuleHandleW(None)
            if self.mode in {"all", "keyboard"}:
                keyboard_hook = user32.SetWindowsHookExW(13, keyboard_proc, hinst, 0)
                if not keyboard_hook:
                    raise ctypes.WinError(ctypes.get_last_error())
                self._windows_keyboard_hook = keyboard_hook
            if self.mode in {"all", "mouse"}:
                mouse_hook = user32.SetWindowsHookExW(14, mouse_proc, hinst, 0)
                if not mouse_hook:
                    raise ctypes.WinError(ctypes.get_last_error())
                self._windows_mouse_hook = mouse_hook

            msg = ctypes.create_string_buffer(48)
            while True:
                result = user32.GetMessageW(msg, None, 0, 0)
                if result <= 0:
                    break
                user32.TranslateMessage(msg)
                user32.DispatchMessageW(msg)
        except Exception:
            # Hook 线程异常不能静默破坏录制状态。
            self._windows_keyboard_hook = None
            self._windows_mouse_hook = None
        finally:
            if keyboard_hook:
                user32.UnhookWindowsHookEx(keyboard_hook)
            if mouse_hook:
                user32.UnhookWindowsHookEx(mouse_hook)

    def _on_windows_vk(self, vk: int, pressed: bool):
        name = self._windows_vk_name(vk)
        if name is None:
            return
        if pressed:
            self._on_key_press_name(name)
        else:
            self._on_key_release_name(name)

    @staticmethod
    def _windows_vk_name(vk: int) -> str | None:
        if 0x41 <= vk <= 0x5A:
            return chr(vk).lower()
        if 0x30 <= vk <= 0x39:
            return chr(vk)
        if 0x70 <= vk <= 0x7B:
            return f"f{vk - 0x6F}"
        return {
            0x08:"backspace",0x09:"tab",0x0D:"enter",0x1B:"esc",0x20:"space",
            0x21:"page_up",0x22:"page_down",0x23:"end",0x24:"home",0x25:"left",
            0x26:"up",0x27:"right",0x28:"down",0x2D:"insert",0x2E:"delete",
            0x5B:"cmd_l",0x5C:"cmd_r",0x5D:"menu",0x14:"caps_lock",0x2C:"print_screen",
            0xA0:"shift_l",0xA1:"shift_r",0xA2:"ctrl_l",0xA3:"ctrl_r",0xA4:"alt_l",0xA5:"alt_r",
            0x60:"num0",0x61:"num1",0x62:"num2",0x63:"num3",0x64:"num4",0x65:"num5",
            0x66:"num6",0x67:"num7",0x68:"num8",0x69:"num9",0x6A:"num_multiply",
            0x6B:"num_add",0x6D:"num_subtract",0x6E:"num_decimal",0x6F:"num_divide",
            0xBA:";",0xBB:"=",0xBC:",",0xBD:"-",0xBE:".",0xBF:"/",0xC0:"`",
            0xDB:"[",0xDC:"\\",0xDD:"]",0xDE:"'",
        }.get(vk)

    @staticmethod
    def _normalize_key_name(name: str) -> str:
        value = str(name).strip().lower()
        if value.startswith("key."):
            value = value[4:]
        return {"control":"ctrl","return":"enter","escape":"esc","capslock":"caps_lock","pageup":"page_up","pagedown":"page_down","windows":"cmd","win":"cmd"}.get(value, value)

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

    def _on_mouse_button(self, x, y, button, pressed):
        self._add("mouse_click", {"x": int(x), "y": int(y), "button": button, "pressed": bool(pressed)})

    def _on_click(self, x, y, button, pressed):
        if self.mode not in {"all", "mouse"}:
            return
        self._on_mouse_button(x, y, str(button).replace("Button.", ""), pressed)

    def _on_scroll(self, x, y, dx, dy):
        if self.mode not in {"all", "mouse"}:
            return
        self._add("mouse_scroll", {"x": int(x), "y": int(y), "dx": int(dx), "dy": int(dy)})
