from __future__ import annotations

import ctypes
import queue
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

        self._windows_hook_thread = None
        self._windows_hook_thread_id = 0
        self._windows_keyboard_hook = None
        self._windows_mouse_hook = None
        self._windows_hook_error = None
        self._windows_hook_ready = Event()

        self._input_queue: queue.Queue[tuple[float, str, tuple]] = queue.Queue()
        self._input_worker = None
        self._input_worker_stop = Event()

        self._pressed_keys: set[str] = set()
        self._ignored_keys: set[str] = set()
        self._last_move_time = 0.0
        self._last_move_pos: tuple[int, int] | None = None
        self.move_interval = 0.02
        self.move_distance = 2
        self._windows = sys.platform.startswith("win")

        self._diagnostics = {
            "keyboard_hook": 0,
            "mouse_hook": 0,
            "queue": 0,
            "saved": 0,
        }

    def set_mode(self, mode: str):
        if mode not in self.MODES:
            raise ValueError(f"不支持的录制模式: {mode}")
        self.mode = mode

    def set_ignored_keys(self, keys: set[str]):
        with self._lock:
            self._ignored_keys = {self._normalize_key_name(key) for key in keys}

    def get_diagnostics(self) -> dict:
        with self._lock:
            result = dict(self._diagnostics)
            result["queue_pending"] = self._input_queue.qsize()
            result["hook_ready"] = self._windows_hook_ready.is_set()
            result["hook_error"] = self._windows_hook_error
            return result

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
            self._windows_hook_error = None
            for key in self._diagnostics:
                self._diagnostics[key] = 0

        self._input_queue = queue.Queue()
        self._input_worker_stop.clear()
        self._input_worker = Thread(
            target=self._input_worker_main,
            daemon=True,
            name="macro-input-worker",
        )
        self._input_worker.start()

        if self._windows:
            self._start_windows_hook()
        elif self.mode in {"all", "keyboard"}:
            self._keyboard_listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release,
                suppress=False,
            )
            self._keyboard_listener.daemon = True
            self._keyboard_listener.start()

        if not self._windows and self.mode in {"all", "mouse"}:
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

        if self._windows_hook_thread:
            try:
                user32 = ctypes.WinDLL("user32", use_last_error=True)
                if self._windows_hook_thread_id:
                    post_thread_message = user32.PostThreadMessageW
                    post_thread_message.argtypes = [
                        ctypes.c_uint32,
                        ctypes.c_uint32,
                        ctypes.c_size_t,
                        ctypes.c_ssize_t,
                    ]
                    post_thread_message.restype = ctypes.c_bool
                    post_thread_message(self._windows_hook_thread_id, 0x0012, 0, 0)
            except Exception as exc:
                self._windows_hook_error = f"停止 Windows Hook 失败: {exc}"

            try:
                self._windows_hook_thread.join(timeout=1.5)
            except RuntimeError:
                pass
            self._windows_hook_thread = None
            self._windows_hook_thread_id = 0
            self._windows_keyboard_hook = None
            self._windows_mouse_hook = None
            self._windows_hook_ready.clear()

        for attr in ("_keyboard_listener", "_mouse_listener"):
            listener = getattr(self, attr)
            setattr(self, attr, None)
            if listener:
                try:
                    listener.stop()
                    listener.join(timeout=1.0)
                except (RuntimeError, AttributeError):
                    pass

        self._input_worker_stop.set()
        worker = self._input_worker
        self._input_worker = None
        if worker:
            try:
                worker.join(timeout=1.5)
            except RuntimeError:
                pass

    def _start_windows_hook(self):
        if self._windows_hook_thread is not None:
            return
        self._windows_hook_ready.clear()
        self._windows_hook_thread = Thread(
            target=self._windows_hook_thread_main,
            daemon=True,
            name="windows-input-hook",
        )
        self._windows_hook_thread.start()

    def _queue_input(self, event_type: str, *data):
        timestamp = time.perf_counter()
        self._input_queue.put((timestamp, event_type, data))
        with self._lock:
            self._diagnostics["queue"] += 1

    def _input_worker_main(self):
        while not self._input_worker_stop.is_set() or not self._input_queue.empty():
            try:
                timestamp, event_type, data = self._input_queue.get(timeout=0.05)
            except queue.Empty:
                continue

            if event_type == "key_down":
                self._process_key(timestamp, data[0], True)
            elif event_type == "key_up":
                self._process_key(timestamp, data[0], False)
            elif event_type == "mouse_move":
                self._process_move(timestamp, data[0], data[1])
            elif event_type == "mouse_button":
                self._process_mouse_button(timestamp, data[0], data[1], data[2], data[3])
            elif event_type == "mouse_scroll":
                self._process_scroll(timestamp, data[0], data[1], data[2], data[3])

    def _windows_hook_thread_main(self):
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        thread_id = kernel32.GetCurrentThreadId
        thread_id.argtypes = []
        thread_id.restype = ctypes.c_uint32
        self._windows_hook_thread_id = int(thread_id())

        peek_message = user32.PeekMessageW
        peek_message.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_uint32,
        ]
        peek_message.restype = ctypes.c_bool
        peek_message(None, None, 0, 0, 0)

        LRESULT = ctypes.c_ssize_t
        HOOKPROC = ctypes.WINFUNCTYPE(
            LRESULT,
            ctypes.c_int,
            ctypes.c_size_t,
            ctypes.c_void_p,
        )

        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("vkCode", ctypes.c_uint32),
                ("scanCode", ctypes.c_uint32),
                ("flags", ctypes.c_uint32),
                ("time", ctypes.c_uint32),
                ("dwExtraInfo", ctypes.c_size_t),
            ]

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        class MSLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("pt", POINT),
                ("mouseData", ctypes.c_uint32),
                ("flags", ctypes.c_uint32),
                ("time", ctypes.c_uint32),
                ("dwExtraInfo", ctypes.c_size_t),
            ]

        keyboard_hook = None
        mouse_hook = None

        user32.CallNextHookEx.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_size_t,
            ctypes.c_void_p,
        ]
        user32.CallNextHookEx.restype = LRESULT
        user32.SetWindowsHookExW.argtypes = [
            ctypes.c_int,
            HOOKPROC,
            ctypes.c_void_p,
            ctypes.c_uint32,
        ]
        user32.SetWindowsHookExW.restype = ctypes.c_void_p
        user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
        user32.UnhookWindowsHookEx.restype = ctypes.c_bool
        user32.GetMessageW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
        ]
        user32.GetMessageW.restype = ctypes.c_int
        user32.TranslateMessage.argtypes = [ctypes.c_void_p]
        user32.TranslateMessage.restype = ctypes.c_bool
        user32.DispatchMessageW.argtypes = [ctypes.c_void_p]
        user32.DispatchMessageW.restype = LRESULT

        @HOOKPROC
        def keyboard_proc(n_code, w_param, l_param):
            try:
                if n_code >= 0 and l_param:
                    data = ctypes.cast(
                        l_param,
                        ctypes.POINTER(KBDLLHOOKSTRUCT),
                    ).contents
                    msg = int(w_param)
                    if msg in (0x0100, 0x0104):
                        with self._lock:
                            self._diagnostics["keyboard_hook"] += 1
                        self._queue_input("key_down", int(data.vkCode))
                    elif msg in (0x0101, 0x0105):
                        with self._lock:
                            self._diagnostics["keyboard_hook"] += 1
                        self._queue_input("key_up", int(data.vkCode))
            except Exception:
                pass

            # Hook 回调必须尽快返回；系统输入永远不在这里做业务处理。
            return user32.CallNextHookEx(
                keyboard_hook or 0,
                n_code,
                w_param,
                l_param,
            )

        @HOOKPROC
        def mouse_proc(n_code, w_param, l_param):
            try:
                if n_code >= 0 and l_param:
                    data = ctypes.cast(
                        l_param,
                        ctypes.POINTER(MSLLHOOKSTRUCT),
                    ).contents
                    msg = int(w_param)
                    x, y = int(data.pt.x), int(data.pt.y)
                    if msg == 0x0200:
                        with self._lock:
                            self._diagnostics["mouse_hook"] += 1
                        self._queue_input("mouse_move", x, y)
                    elif msg == 0x0201:
                        with self._lock:
                            self._diagnostics["mouse_hook"] += 1
                        self._queue_input("mouse_button", x, y, "left", True)
                    elif msg == 0x0202:
                        with self._lock:
                            self._diagnostics["mouse_hook"] += 1
                        self._queue_input("mouse_button", x, y, "left", False)
                    elif msg == 0x0204:
                        with self._lock:
                            self._diagnostics["mouse_hook"] += 1
                        self._queue_input("mouse_button", x, y, "right", True)
                    elif msg == 0x0205:
                        with self._lock:
                            self._diagnostics["mouse_hook"] += 1
                        self._queue_input("mouse_button", x, y, "right", False)
                    elif msg == 0x0207:
                        with self._lock:
                            self._diagnostics["mouse_hook"] += 1
                        self._queue_input("mouse_button", x, y, "middle", True)
                    elif msg == 0x0208:
                        with self._lock:
                            self._diagnostics["mouse_hook"] += 1
                        self._queue_input("mouse_button", x, y, "middle", False)
                    elif msg == 0x020A:
                        with self._lock:
                            self._diagnostics["mouse_hook"] += 1
                        delta = ctypes.c_short((data.mouseData >> 16) & 0xFFFF).value
                        self._queue_input(
                            "mouse_scroll",
                            x,
                            y,
                            0,
                            delta // 120 if delta else 0,
                        )
                    elif msg == 0x020E:
                        with self._lock:
                            self._diagnostics["mouse_hook"] += 1
                        delta = ctypes.c_short((data.mouseData >> 16) & 0xFFFF).value
                        self._queue_input(
                            "mouse_scroll",
                            x,
                            y,
                            delta // 120 if delta else 0,
                            0,
                        )
            except Exception:
                pass

            return user32.CallNextHookEx(
                mouse_hook or 0,
                n_code,
                w_param,
                l_param,
            )

        try:
            user32.PostThreadMessageW.argtypes = [
                ctypes.c_uint32,
                ctypes.c_uint32,
                ctypes.c_size_t,
                ctypes.c_ssize_t,
            ]
            user32.PostThreadMessageW.restype = ctypes.c_bool
            kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
            kernel32.GetModuleHandleW.restype = ctypes.c_void_p
            hinst = kernel32.GetModuleHandleW(None)

            if self.mode in {"all", "keyboard"}:
                keyboard_hook = user32.SetWindowsHookExW(
                    13,
                    keyboard_proc,
                    hinst,
                    0,
                )
                if not keyboard_hook:
                    raise ctypes.WinError(ctypes.get_last_error())
                self._windows_keyboard_hook = keyboard_hook

            if self.mode in {"all", "mouse"}:
                mouse_hook = user32.SetWindowsHookExW(
                    14,
                    mouse_proc,
                    hinst,
                    0,
                )
                if not mouse_hook:
                    raise ctypes.WinError(ctypes.get_last_error())
                self._windows_mouse_hook = mouse_hook

            self._windows_hook_ready.set()
            msg = ctypes.create_string_buffer(48)
            while True:
                result = user32.GetMessageW(msg, None, 0, 0)
                if result <= 0:
                    break
                user32.TranslateMessage(msg)
                user32.DispatchMessageW(msg)
        except Exception as exc:
            self._windows_hook_error = f"Windows Hook 初始化失败: {exc}"
            print(self._windows_hook_error, file=sys.stderr)
        finally:
            if keyboard_hook:
                user32.UnhookWindowsHookEx(keyboard_hook)
            if mouse_hook:
                user32.UnhookWindowsHookEx(mouse_hook)
            self._windows_hook_ready.clear()

    def _process_key(self, timestamp: float, vk: int, pressed: bool):
        name = self._windows_vk_name(vk) if self._windows else None
        if name is None:
            return
        if pressed:
            self._process_key_press(timestamp, name)
        else:
            self._process_key_release(timestamp, name)

    def _process_key_press(self, timestamp: float, name: str):
        with self._lock:
            if not self.recording or self.paused or name in self._ignored_keys or name in self._pressed_keys:
                return
            self._pressed_keys.add(name)
        self._add_at(timestamp, "key_down", {"key": name})

    def _process_key_release(self, timestamp: float, name: str):
        with self._lock:
            if not self.recording or self.paused or name in self._ignored_keys:
                return
            self._pressed_keys.discard(name)
        self._add_at(timestamp, "key_up", {"key": name})

    def _on_windows_vk(self, vk: int, pressed: bool):
        if pressed:
            self._on_key_press_name(self._windows_vk_name(vk))
        else:
            self._on_key_release_name(self._windows_vk_name(vk))

    def _on_key_press_name(self, name: str | None):
        if name is None:
            return
        self._queue_input("key_down", name)

    def _on_key_release_name(self, name: str | None):
        if name is None:
            return
        self._queue_input("key_up", name)

    def _on_key_press(self, key):
        self._queue_input("key_down", self._key_name(key))

    def _on_key_release(self, key):
        self._queue_input("key_up", self._key_name(key))

    def _process_move(self, timestamp: float, x: int, y: int):
        if self.mode not in {"all", "mouse"}:
            return
        with self._lock:
            if not self.recording or self.paused:
                return
            last = self._last_move_pos
            if last is not None:
                dx, dy = x - last[0], y - last[1]
                if (
                    timestamp - self._last_move_time < self.move_interval
                    and dx * dx + dy * dy < self.move_distance ** 2
                ):
                    return
            self._last_move_time = timestamp
            self._last_move_pos = (x, y)
        self._add_at(timestamp, "mouse_move", {"x": int(x), "y": int(y)})

    def _process_mouse_button(self, timestamp: float, x: int, y: int, button: str, pressed: bool):
        if self.mode not in {"all", "mouse"}:
            return
        self._add_at(
            timestamp,
            "mouse_click",
            {
                "x": int(x),
                "y": int(y),
                "button": button,
                "pressed": bool(pressed),
            },
        )

    def _process_scroll(self, timestamp: float, x: int, y: int, dx: int, dy: int):
        if self.mode not in {"all", "mouse"}:
            return
        self._add_at(
            timestamp,
            "mouse_scroll",
            {
                "x": int(x),
                "y": int(y),
                "dx": int(dx),
                "dy": int(dy),
            },
        )

    def _add_at(self, timestamp: float, event_type: str, data: dict):
        with self._lock:
            if not self.recording or self.paused:
                return
            event = MacroEvent(
                event_type,
                max(0.0, timestamp - self._last_time),
                data,
            )
            self._last_time = timestamp
            self._diagnostics["saved"] += 1
        if self.on_event:
            self.on_event(event)

    def _add(self, event_type: str, data: dict):
        self._add_at(time.perf_counter(), event_type, data)

    def _on_move(self, x, y):
        self._queue_input("mouse_move", int(x), int(y))

    def _on_mouse_button(self, x, y, button, pressed):
        self._queue_input(
            "mouse_button",
            int(x),
            int(y),
            str(button).replace("Button.", ""),
            bool(pressed),
        )

    def _on_click(self, x, y, button, pressed):
        self._on_mouse_button(x, y, button, pressed)

    def _on_scroll(self, x, y, dx, dy):
        self._queue_input("mouse_scroll", int(x), int(y), int(dx), int(dy))

    @staticmethod
    def _windows_vk_name(vk: int) -> str | None:
        if 0x41 <= vk <= 0x5A:
            return chr(vk).lower()
        if 0x30 <= vk <= 0x39:
            return chr(vk)
        if 0x70 <= vk <= 0x7B:
            return f"f{vk - 0x6F}"
        return {
            0x08: "backspace", 0x09: "tab", 0x0D: "enter", 0x1B: "esc", 0x20: "space",
            0x21: "page_up", 0x22: "page_down", 0x23: "end", 0x24: "home", 0x25: "left",
            0x26: "up", 0x27: "right", 0x28: "down", 0x2D: "insert", 0x2E: "delete",
            0x5B: "cmd_l", 0x5C: "cmd_r", 0x5D: "menu", 0x14: "caps_lock", 0x2C: "print_screen",
            0xA0: "shift_l", 0xA1: "shift_r", 0xA2: "ctrl_l", 0xA3: "ctrl_r", 0xA4: "alt_l", 0xA5: "alt_r",
            0x60: "num0", 0x61: "num1", 0x62: "num2", 0x63: "num3", 0x64: "num4", 0x65: "num5",
            0x66: "num6", 0x67: "num7", 0x68: "num8", 0x69: "num9", 0x6A: "num_multiply",
            0x6B: "num_add", 0x6D: "num_subtract", 0x6E: "num_decimal", 0x6F: "num_divide",
            0xBA: ";", 0xBB: "=", 0xBC: ",", 0xBD: "-", 0xBE: ".", 0xBF: "/", 0xC0: "`",
            0xDB: "[", 0xDC: "\\", 0xDD: "]", 0xDE: "'",
        }.get(vk)

    @staticmethod
    def _normalize_key_name(name: str) -> str:
        value = str(name).strip().lower()
        if value.startswith("key."):
            value = value[4:]
        return {
            "control": "ctrl", "return": "enter", "escape": "esc", "capslock": "caps_lock",
            "pageup": "page_up", "pagedown": "page_down", "windows": "cmd", "win": "cmd",
        }.get(value, value)

    @classmethod
    def _key_name(cls, key) -> str:
        if isinstance(key, keyboard.KeyCode):
            return cls._normalize_key_name(key.char if key.char else str(key))
        return cls._normalize_key_name(str(key))
