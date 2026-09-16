from __future__ import annotations

import time
from threading import Event, Thread

from pynput import keyboard, mouse

from core.model import MacroEvent


class MacroPlayer:
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
            self.keyboard.press(key)
            self._pressed_keys.add(key)
        elif event.type == "key_up":
            key = self._key(data["key"])
            self.keyboard.release(key)
            self._pressed_keys.discard(key)
        elif event.type == "mouse_move":
            self.mouse.position = (int(data["x"]), int(data["y"]))
        elif event.type == "mouse_click":
            self.mouse.position = (int(data["x"]), int(data["y"]))
            button = getattr(mouse.Button, data["button"])
            if data["pressed"]:
                self.mouse.press(button)
                self._pressed_buttons.add(button)
            else:
                self.mouse.release(button)
                self._pressed_buttons.discard(button)
        elif event.type == "mouse_scroll":
            self.mouse.position = (int(data["x"]), int(data["y"]))
            self.mouse.scroll(int(data["dx"]), int(data["dy"]))

    def _release_all_inputs(self):
        """无论宏如何结束，都释放播放线程曾按下但尚未释放的输入。"""
        for key in list(self._pressed_keys):
            try:
                self.keyboard.release(key)
            except Exception:
                pass
        self._pressed_keys.clear()

        for button in list(self._pressed_buttons):
            try:
                self.mouse.release(button)
            except Exception:
                pass
        self._pressed_buttons.clear()

    @staticmethod
    def _key(name: str):
        """将录制时保存的按键名称转换成 pynput 可发送的按键对象。"""
        normalized = str(name).strip().lower()

        aliases = {
            "ctrl": "ctrl",
            "control": "ctrl",
            "ctrl_l": "ctrl_l",
            "ctrl_r": "ctrl_r",
            "shift": "shift",
            "shift_l": "shift_l",
            "shift_r": "shift_r",
            "alt": "alt",
            "alt_l": "alt_l",
            "alt_r": "alt_r",
            "cmd": "cmd",
            "cmd_l": "cmd_l",
            "cmd_r": "cmd_r",
            "win": "cmd",
            "windows": "cmd",
            "enter": "enter",
            "return": "enter",
            "esc": "esc",
            "escape": "esc",
            "tab": "tab",
            "backspace": "backspace",
            "space": "space",
            "delete": "delete",
            "insert": "insert",
            "home": "home",
            "end": "end",
            "page_up": "page_up",
            "page_down": "page_down",
            "up": "up",
            "down": "down",
            "left": "left",
            "right": "right",
            "pause": "pause",
            "print_screen": "print_screen",
            "printscreen": "print_screen",
            "menu": "menu",
            "caps_lock": "caps_lock",
            "capslock": "caps_lock",
            "num_lock": "num_lock",
            "numlock": "num_lock",
            "scroll_lock": "scroll_lock",
            "scrolllock": "scroll_lock",
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
            key_name = normalized[4:]
            special_key = getattr(keyboard.Key, key_name, None)
            if special_key is not None:
                return special_key

        raise ValueError(f"无法识别的按键：{name}")

    def _state(self, state: str):
        if self.on_state:
            self.on_state(state)
