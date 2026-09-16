from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from threading import Event, Thread

from pynput import keyboard, mouse

from core.model import MacroEvent


class MacroPlayer:
    """屏幕级宏播放器。

    Windows 下优先使用系统 SendInput 注入键鼠事件，使系统截图层、UAC 外的普通桌面 UI
    也能接收到鼠标移动和键盘组合键；其他系统继续使用 pynput。
    """

    def __init__(self, on_progress=None, on_state=None):
        self.on_progress = on_progress
        self.on_state = on_state
        self.mouse = mouse.Controller()
        self.keyboard = keyboard.Controller()
        self._stop = Event()
        self._pause = Event()
        self.running = False
        self.paused = False
        self._pressed_keys = set()
        self._pressed_buttons = set()
        self._windows = __import__("sys").platform.startswith("win")

        if self._windows:
            self._setup_windows_input()

    def _setup_windows_input(self):
        self._user32 = ctypes.windll.user32
        self._INPUT_MOUSE = 0
        self._INPUT_KEYBOARD = 1
        self._KEYEVENTF_KEYUP = 0x0002
        self._KEYEVENTF_SCANCODE = 0x0008
        self._MOUSEEVENTF_MOVE = 0x0001
        self._MOUSEEVENTF_LEFTDOWN = 0x0002
        self._MOUSEEVENTF_LEFTUP = 0x0004
        self._MOUSEEVENTF_RIGHTDOWN = 0x0008
        self._MOUSEEVENTF_RIGHTUP = 0x0010
        self._MOUSEEVENTF_MIDDLEDOWN = 0x0020
        self._MOUSEEVENTF_MIDDLEUP = 0x0040
        self._MOUSEEVENTF_WHEEL = 0x0800
        self._MOUSEEVENTF_ABSOLUTE = 0x8000
        self._MOUSEEVENTF_VIRTUALDESK = 0x4000

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
            ]

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [
                ("dx", wintypes.LONG),
                ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
            ]

        class HARDWAREINPUT(ctypes.Structure):
            _fields_ = [
                ("uMsg", wintypes.DWORD),
                ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD),
            ]

        class INPUT_UNION(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]

        class INPUT(ctypes.Structure):
            _anonymous_ = ("u",)
            _fields_ = [("type", wintypes.DWORD), ("u", INPUT_UNION)]

        self._INPUT = INPUT
        self._KEYBDINPUT = KEYBDINPUT
        self._MOUSEINPUT = MOUSEINPUT
        self._user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
        self._user32.SendInput.restype = wintypes.UINT

    def play(self, events: list[MacroEvent], repeat: int = 1) -> bool:
        if self.running or not events:
            return False

        self._stop.clear()
        self._pause.clear()
        self._pressed_keys.clear()
        self._pressed_buttons.clear()
        self.running = True
        self.paused = False
        Thread(target=self._run, args=(list(events), repeat), daemon=True).start()
        return True

    def toggle_pause(self):
        if not self.running:
            return

        if self._pause.is_set():
            self._pause.clear()
            self.paused = False
            self._state("播放中")
        else:
            self._pause.set()
            self.paused = True
            self._state("已暂停")

    def stop(self):
        self._stop.set()
        self._pause.clear()

    def _run(self, events, repeat):
        try:
            total = len(events) * repeat if repeat > 0 else 0
            completed = 0
            cycle = 0

            while not self._stop.is_set() and (repeat <= 0 or cycle < repeat):
                for event in events:
                    if self._wait(event.delay):
                        return
                    self._execute(event)
                    completed += 1
                    if self.on_progress and total:
                        self.on_progress(completed, total)
                cycle += 1

            if self.on_progress:
                self.on_progress(total if total else completed, total)
        except Exception as exc:
            self._state(f"播放异常：{exc}")
        finally:
            self._release_all_inputs()
            self.running = False
            self.paused = False
            if not self._stop.is_set():
                self._state("播放完成")
            else:
                self._state("已停止")

    def _wait(self, seconds: float) -> bool:
        end = time.perf_counter() + seconds
        while time.perf_counter() < end:
            if self._stop.is_set():
                return True

            while self._pause.is_set() and not self._stop.is_set():
                time.sleep(0.05)
                end += 0.05

            time.sleep(min(0.005, max(0, end - time.perf_counter())))

        return False

    def _execute(self, event: MacroEvent):
        data = event.data

        if event.type == "delay":
            return
        if event.type == "key_down":
            key = self._key(data["key"])
            if self._windows:
                self._send_key(key, True)
            else:
                self.keyboard.press(key)
            self._pressed_keys.add(key)
        elif event.type == "key_up":
            key = self._key(data["key"])
            if self._windows:
                self._send_key(key, False)
            else:
                self.keyboard.release(key)
            self._pressed_keys.discard(key)
        elif event.type == "mouse_move":
            x, y = int(data["x"]), int(data["y"])
            if self._windows:
                self._send_mouse_move(x, y)
            else:
                self.mouse.position = (x, y)
        elif event.type == "mouse_click":
            x, y = int(data["x"]), int(data["y"])
            button = getattr(mouse.Button, data["button"])
            if self._windows:
                self._send_mouse_move(x, y)
                self._send_mouse_button(button, bool(data["pressed"]))
            else:
                self.mouse.position = (x, y)
                if data["pressed"]:
                    self.mouse.press(button)
                else:
                    self.mouse.release(button)
            if data["pressed"]:
                self._pressed_buttons.add(button)
            else:
                self._pressed_buttons.discard(button)
        elif event.type == "mouse_scroll":
            x, y = int(data["x"]), int(data["y"])
            if self._windows:
                self._send_mouse_move(x, y)
                self._send_mouse_wheel(int(data["dy"]))
            else:
                self.mouse.position = (x, y)
                self.mouse.scroll(int(data["dx"]), int(data["dy"]))

    def _send_key(self, key, pressed: bool):
        vk = self._key_to_vk(key)
        if not vk:
            raise ValueError(f"Windows 无法发送按键：{key}")
        flags = 0 if pressed else self._KEYEVENTF_KEYUP
        extra = ctypes.pointer(wintypes.ULONG(0))
        inp = self._INPUT(type=self._INPUT_KEYBOARD)
        inp.ki = self._KEYBDINPUT(vk, 0, flags, 0, extra)
        if self._user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp)) != 1:
            raise ctypes.WinError()

    def _send_mouse_move(self, x: int, y: int):
        left = self._user32.GetSystemMetrics(76)
        top = self._user32.GetSystemMetrics(77)
        width = self._user32.GetSystemMetrics(78)
        height = self._user32.GetSystemMetrics(79)
        nx = round((x - left) * 65535 / max(1, width - 1))
        ny = round((y - top) * 65535 / max(1, height - 1))
        extra = ctypes.pointer(wintypes.ULONG(0))
        inp = self._INPUT(type=self._INPUT_MOUSE)
        inp.mi = self._MOUSEINPUT(
            nx,
            ny,
            0,
            self._MOUSEEVENTF_MOVE | self._MOUSEEVENTF_ABSOLUTE | self._MOUSEEVENTF_VIRTUALDESK,
            0,
            extra,
        )
        if self._user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp)) != 1:
            raise ctypes.WinError()

    def _send_mouse_button(self, button, pressed: bool):
        flags = {
            mouse.Button.left: self._MOUSEEVENTF_LEFTDOWN if pressed else self._MOUSEEVENTF_LEFTUP,
            mouse.Button.right: self._MOUSEEVENTF_RIGHTDOWN if pressed else self._MOUSEEVENTF_RIGHTUP,
            mouse.Button.middle: self._MOUSEEVENTF_MIDDLEDOWN if pressed else self._MOUSEEVENTF_MIDDLEUP,
        }.get(button)
        if flags is None:
            return
        extra = ctypes.pointer(wintypes.ULONG(0))
        inp = self._INPUT(type=self._INPUT_MOUSE)
        inp.mi = self._MOUSEINPUT(0, 0, 0, flags, 0, extra)
        if self._user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp)) != 1:
            raise ctypes.WinError()

    def _send_mouse_wheel(self, delta: int):
        if not delta:
            return
        extra = ctypes.pointer(wintypes.ULONG(0))
        inp = self._INPUT(type=self._INPUT_MOUSE)
        inp.mi = self._MOUSEINPUT(0, 0, ctypes.c_uint32(delta * 120), self._MOUSEEVENTF_WHEEL, 0, extra)
        if self._user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp)) != 1:
            raise ctypes.WinError()

    @staticmethod
    def _key_to_vk(key):
        if isinstance(key, keyboard.KeyCode):
            if key.char:
                code = ord(key.char)
                if 0x61 <= code <= 0x7A:
                    return code - 0x20
                if 0x41 <= code <= 0x5A or 0x30 <= code <= 0x39:
                    return code
                result = ctypes.windll.user32.VkKeyScanW(ord(key.char))
                return result & 0xFF if result != -1 else 0
            return int(key.vk or 0)

        mapping = {
            keyboard.Key.alt: 0x12,
            keyboard.Key.alt_l: 0xA4,
            keyboard.Key.alt_r: 0xA5,
            keyboard.Key.ctrl: 0x11,
            keyboard.Key.ctrl_l: 0xA2,
            keyboard.Key.ctrl_r: 0xA3,
            keyboard.Key.shift: 0x10,
            keyboard.Key.shift_l: 0xA0,
            keyboard.Key.shift_r: 0xA1,
            keyboard.Key.cmd: 0x5B,
            keyboard.Key.cmd_l: 0x5B,
            keyboard.Key.cmd_r: 0x5C,
            keyboard.Key.enter: 0x0D,
            keyboard.Key.esc: 0x1B,
            keyboard.Key.tab: 0x09,
            keyboard.Key.backspace: 0x08,
            keyboard.Key.space: 0x20,
            keyboard.Key.delete: 0x2E,
            keyboard.Key.insert: 0x2D,
            keyboard.Key.home: 0x24,
            keyboard.Key.end: 0x23,
            keyboard.Key.page_up: 0x21,
            keyboard.Key.page_down: 0x22,
            keyboard.Key.up: 0x26,
            keyboard.Key.down: 0x28,
            keyboard.Key.left: 0x25,
            keyboard.Key.right: 0x27,
            keyboard.Key.pause: 0x13,
            keyboard.Key.print_screen: 0x2C,
            keyboard.Key.menu: 0x5D,
            keyboard.Key.caps_lock: 0x14,
            keyboard.Key.num_lock: 0x90,
            keyboard.Key.scroll_lock: 0x91,
        }
        for i in range(1, 13):
            mapping[getattr(keyboard.Key, f"f{i}")] = 0x6F + i
        return mapping.get(key, 0)

    def _release_all_inputs(self):
        """无论宏如何结束，都释放播放线程曾按下但尚未释放的输入。"""
        for key in list(self._pressed_keys):
            try:
                if self._windows:
                    self._send_key(key, False)
                else:
                    self.keyboard.release(key)
            except Exception:
                pass
        self._pressed_keys.clear()

        for button in list(self._pressed_buttons):
            try:
                if self._windows:
                    self._send_mouse_button(button, False)
                else:
                    self.mouse.release(button)
            except Exception:
                pass
        self._pressed_buttons.clear()

    @staticmethod
    def _key(name: str):
        normalized = str(name).strip().lower()
        aliases = {
            "ctrl": "ctrl", "control": "ctrl", "ctrl_l": "ctrl_l", "ctrl_r": "ctrl_r",
            "shift": "shift", "shift_l": "shift_l", "shift_r": "shift_r",
            "alt": "alt", "alt_l": "alt_l", "alt_r": "alt_r",
            "cmd": "cmd", "cmd_l": "cmd_l", "cmd_r": "cmd_r", "win": "cmd", "windows": "cmd",
            "enter": "enter", "return": "enter", "esc": "esc", "escape": "esc",
            "tab": "tab", "backspace": "backspace", "space": "space", "delete": "delete",
            "insert": "insert", "home": "home", "end": "end", "page_up": "page_up",
            "page_down": "page_down", "up": "up", "down": "down", "left": "left", "right": "right",
            "pause": "pause", "print_screen": "print_screen", "printscreen": "print_screen", "menu": "menu",
            "caps_lock": "caps_lock", "capslock": "caps_lock", "num_lock": "num_lock", "numlock": "num_lock",
            "scroll_lock": "scroll_lock", "scrolllock": "scroll_lock",
        }
        for i in range(1, 13):
            aliases[f"f{i}"] = f"f{i}"
        key_name = aliases.get(normalized, normalized)
        special_key = getattr(keyboard.Key, key_name, None)
        if special_key is not None:
            return special_key
        if len(name) == 1:
            return keyboard.KeyCode.from_char(name)
        if normalized.startswith("key."):
            special_key = getattr(keyboard.Key, normalized[4:], None)
            if special_key is not None:
                return special_key
        raise ValueError(f"无法识别的按键：{name}")

    def _state(self, state: str):
        if self.on_state:
            self.on_state(state)
