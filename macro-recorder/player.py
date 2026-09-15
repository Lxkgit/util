from __future__ import annotations

import time
from threading import Event, Thread
from pynput import keyboard, mouse

from model import MacroEvent


class MacroPlayer:
    def __init__(self, on_progress=None, on_state=None):
        self.on_progress = on_progress
        self.on_state = on_state
        self.mouse = mouse.Controller()
        self.keyboard = keyboard.Controller()
        self._stop = Event()
        self._pause = Event()
        self._thread: Thread | None = None
        self.running = False
        self.paused = False

    def play(self, events: list[MacroEvent], repeat: int = 1):
        if self.running or not events:
            return False
        self._stop.clear()
        self._pause.clear()
        self.running = True
        self.paused = False
        self._thread = Thread(target=self._run, args=(list(events), repeat), daemon=True)
        self._thread.start()
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

    def _run(self, events: list[MacroEvent], repeat: int):
        try:
            total = len(events) * repeat if repeat > 0 else 0
            completed = 0
            cycle = 0
            while not self._stop.is_set() and (repeat <= 0 or cycle < repeat):
                for event in events:
                    if self._wait(event.delay) or self._stop.is_set():
                        return
                    self._execute(event)
                    completed += 1
                    if self.on_progress and total:
                        self.on_progress(completed, total)
                cycle += 1
            if self.on_progress:
                self.on_progress(total if total else completed, total)
        finally:
            self.running = False
            self.paused = False
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
        if event.type == "key_down":
            self.keyboard.press(self._key(data["key"]))
        elif event.type == "key_up":
            self.keyboard.release(self._key(data["key"]))
        elif event.type == "mouse_move":
            self.mouse.position = (int(data["x"]), int(data["y"]))
        elif event.type == "mouse_click":
            self.mouse.position = (int(data["x"]), int(data["y"]))
            button = getattr(mouse.Button, data["button"])
            if data["pressed"]:
                self.mouse.press(button)
            else:
                self.mouse.release(button)
        elif event.type == "mouse_scroll":
            self.mouse.position = (int(data["x"]), int(data["y"]))
            self.mouse.scroll(int(data["dx"]), int(data["dy"]))

    @staticmethod
    def _key(name: str):
        special = {
            "ctrl": keyboard.Key.ctrl,
            "ctrl_l": keyboard.Key.ctrl_l,
            "ctrl_r": keyboard.Key.ctrl_r,
            "shift": keyboard.Key.shift,
            "shift_l": keyboard.Key.shift_l,
            "shift_r": keyboard.Key.shift_r,
            "alt": keyboard.Key.alt,
            "alt_l": keyboard.Key.alt_l,
            "alt_r": keyboard.Key.alt_r,
            "cmd": keyboard.Key.cmd,
            "cmd_l": keyboard.Key.cmd_l,
            "cmd_r": keyboard.Key.cmd_r,
            "enter": keyboard.Key.enter,
            "esc": keyboard.Key.esc,
            "tab": keyboard.Key.tab,
            "backspace": keyboard.Key.backspace,
            "space": keyboard.Key.space,
            "delete": keyboard.Key.delete,
            "insert": keyboard.Key.insert,
            "home": keyboard.Key.home,
            "end": keyboard.Key.end,
            "page_up": keyboard.Key.page_up,
            "page_down": keyboard.Key.page_down,
            "up": keyboard.Key.up,
            "down": keyboard.Key.down,
            "left": keyboard.Key.left,
            "right": keyboard.Key.right,
            "pause": keyboard.Key.pause,
            "print_screen": keyboard.Key.print_screen,
            "menu": keyboard.Key.menu,
            "caps_lock": keyboard.Key.caps_lock,
            "num_lock": keyboard.Key.num_lock,
            "scroll_lock": keyboard.Key.scroll_lock,
            "f1": keyboard.Key.f1,
            "f2": keyboard.Key.f2,
            "f3": keyboard.Key.f3,
            "f4": keyboard.Key.f4,
            "f5": keyboard.Key.f5,
            "f6": keyboard.Key.f6,
            "f7": keyboard.Key.f7,
            "f8": keyboard.Key.f8,
            "f9": keyboard.Key.f9,
            "f10": keyboard.Key.f10,
            "f11": keyboard.Key.f11,
            "f12": keyboard.Key.f12,
        }
        return special.get(name.lower(), keyboard.KeyCode.from_char(name))

    def _state(self, state: str):
        if self.on_state:
            self.on_state(state)
