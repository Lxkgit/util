from __future__ import annotations

import os
import sys
from PySide6.QtCore import QObject, Signal, Slot, QSettings, QEvent
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QDialog, QDialogButtonBox, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QListWidget, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QSpinBox, QVBoxLayout, QWidget, QKeySequenceEdit
)
from pynput import keyboard

from model import MacroEvent, load_macro, save_macro
from player import MacroPlayer
from recorder import MacroRecorder


class Bridge(QObject):
    recorded = Signal(object)
    hotkey = Signal(str)
    progress = Signal(int, int)
    state = Signal(str)


class HotkeyDialog(QDialog):
    def __init__(self, current: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("快捷键设置")
        self.setModal(True)
        self.resize(420, 150)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.edit = QKeySequenceEdit(QKeySequence(current))
        self.edit.setMaximumSequenceLength(1)
        form.addRow("录制快捷键", self.edit)
        layout.addLayout(form)

        tip = QLabel("仅支持单键快捷键，例如 F6、F8、F9、Pause。")
        tip.setStyleSheet("color: #777;")
        layout.addWidget(tip)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def value(self) -> str:
        return self.edit.keySequence().toString(QKeySequence.PortableText)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Macro Recorder")
        self.resize(900, 620)
        self.bridge = Bridge()
        self.events: list[MacroEvent] = []
        self.current_file = ""
        self.settings = QSettings("Lxkgit", "MacroRecorder")
        self.record_hotkey = self.settings.value("record_hotkey", "F8")

        self.recorder = MacroRecorder(on_event=self.bridge.recorded.emit)
        self.recorder.set_ignored_keys({self.qt_to_pynput_key(self.record_hotkey)})
        self.player = MacroPlayer(
            on_progress=self.bridge.progress.emit,
            on_state=self.bridge.state.emit,
        )
        self.hotkey_listener = None
        self.install_record_hotkey()

        self._build_ui()
        self.bridge.recorded.connect(self.on_recorded)
        self.bridge.hotkey.connect(self.on_hotkey)
        self.bridge.progress.connect(self.on_progress)
        self.bridge.state.connect(self.on_state)
        self.update_ui()

    @staticmethod
    def qt_to_pynput_key(value: str) -> str:
        key = value.strip().lower()
        mapping = {
            "esc": "esc",
            "escape": "esc",
            "return": "enter",
            "enter": "enter",
            "space": "space",
            "tab": "tab",
            "backspace": "backspace",
            "delete": "delete",
            "insert": "insert",
            "home": "home",
            "end": "end",
            "pageup": "page_up",
            "pagedown": "page_down",
            "left": "left",
            "right": "right",
            "up": "up",
            "down": "down",
            "pause": "pause",
        }
        return mapping.get(key, key)

    def install_record_hotkey(self):
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        pynput_key = self.qt_to_pynput_key(self.record_hotkey)
        self.recorder.set_ignored_keys({pynput_key})
        self.hotkey_listener = keyboard.GlobalHotKeys({
            f"<{pynput_key}>": lambda: self.bridge.hotkey.emit("record")
        })
        self.hotkey_listener.start()

    def _build_ui(self):
        root = QWidget()
        root.setStyleSheet("""
            QWidget { font-size: 14px; }
            QGroupBox { font-weight: 600; margin-top: 10px; }
            QPushButton { min-height: 34px; padding: 0 16px; }
            QListWidget { background: #fafafa; border: 1px solid #ddd; }
            QSpinBox { min-height: 32px; }
        """)
        layout = QVBoxLayout(root)

        title_row = QHBoxLayout()
        title = QLabel("键盘鼠标宏录制器")
        title.setStyleSheet("font-size: 24px; font-weight: 700; padding: 8px 0;")
        title_row.addWidget(title, 1)
        settings_btn = QPushButton("⚙ 设置")
        settings_btn.clicked.connect(self.open_settings)
        title_row.addWidget(settings_btn)
        layout.addLayout(title_row)

        controls = QHBoxLayout()
        self.record_btn = QPushButton("● 开始录制")
        self.record_btn.clicked.connect(self.toggle_record)
        self.play_btn = QPushButton("▶ 播放")
        self.play_btn.clicked.connect(self.play)
        self.pause_btn = QPushButton("Ⅱ 暂停")
        self.pause_btn.clicked.connect(self.player.toggle_pause)
        self.stop_btn = QPushButton("■ 停止")
        self.stop_btn.clicked.connect(self.stop_all)
        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self.clear_events)
        for button in (self.record_btn, self.play_btn, self.pause_btn, self.stop_btn, self.clear_btn):
            controls.addWidget(button)
        layout.addLayout(controls)

        settings = QGroupBox("播放设置")
        form = QFormLayout(settings)
        self.repeat = QSpinBox()
        self.repeat.setRange(0, 999999)
        self.repeat.setValue(1)
        self.repeat.setSpecialValueText("无限循环")
        form.addRow("循环次数", self.repeat)
        layout.addWidget(settings)

        self.status = QLabel("就绪")
        self.status.setStyleSheet("font-weight: 600; padding: 4px;")
        layout.addWidget(self.status)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        layout.addWidget(self.progress)

        self.list = QListWidget()
        layout.addWidget(self.list, 1)

        bottom = QHBoxLayout()
        self.file_label = QLabel("尚未保存")
        bottom.addWidget(self.file_label, 1)
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save)
        load_btn = QPushButton("加载")
        load_btn.clicked.connect(self.load)
        bottom.addWidget(save_btn)
        bottom.addWidget(load_btn)
        layout.addLayout(bottom)

        self.shortcuts = QLabel()
        self.shortcuts.setStyleSheet("color: #777; padding-top: 4px;")
        layout.addWidget(self.shortcuts)
        self.setCentralWidget(root)
        self.update_shortcut_label()

    def update_shortcut_label(self):
        self.shortcuts.setText(
            f"全局快捷键：{self.record_hotkey} 录制/停止   F9 播放/暂停   F10 紧急停止"
        )

    @Slot()
    def open_settings(self):
        if self.recorder.recording or self.player.running:
            QMessageBox.information(self, "提示", "录制或播放过程中不能修改快捷键。")
            return
        dialog = HotkeyDialog(self.record_hotkey, self)
        if dialog.exec() != QDialog.Accepted:
            return
        value = dialog.value()
        if not value:
            QMessageBox.warning(self, "设置失败", "请设置一个录制快捷键。")
            return
        if "," in value or "+" in value:
            QMessageBox.warning(self, "设置失败", "录制快捷键暂时只支持单键，请不要使用 Ctrl/Alt/Shift 组合。")
            return
        if value.upper() in {"F9", "F10"}:
            QMessageBox.warning(self, "设置失败", "F9 和 F10 已保留给播放和紧急停止。")
            return
        self.record_hotkey = value
        self.settings.setValue("record_hotkey", value)
        self.install_record_hotkey()
        self.update_shortcut_label()
        self.status.setText(f"录制快捷键已修改为 {value}")

    @Slot()
    def toggle_record(self):
        if self.recorder.recording:
            self.recorder.stop()
            self.status.setText(f"录制结束，共 {len(self.events)} 个操作")
        else:
            if self.player.running:
                self.player.stop()
            self.events.clear()
            self.list.clear()
            self.progress.setValue(0)
            self.recorder.start()
            self.status.setText("正在录制……")
        self.update_ui()

    @Slot()
    def stop_all(self):
        if self.recorder.recording:
            self.recorder.stop()
            self.status.setText(f"录制结束，共 {len(self.events)} 个操作")
        self.player.stop()
        self.update_ui()

    @Slot()
    def play(self):
        if self.recorder.recording:
            self.recorder.stop()
        if not self.events:
            QMessageBox.information(self, "提示", "没有可播放的操作，请先录制或加载宏。")
            return
        if not self.player.play(self.events, self.repeat.value()):
            return
        self.status.setText("播放中")
        self.update_ui()

    @Slot(object)
    def on_recorded(self, event: MacroEvent):
        self.events.append(event)
        self.list.addItem(self.format_event(event))
        if self.list.count() % 20 == 0:
            self.list.scrollToBottom()

    @Slot(str)
    def on_hotkey(self, key: str):
        if key == "record":
            self.toggle_record()
        elif key == "f9":
            if self.player.running:
                self.player.toggle_pause()
            else:
                self.play()
        elif key == "f10":
            self.stop_all()
            self.status.setText("已紧急停止")
            self.update_ui()

    @Slot(int, int)
    def on_progress(self, current: int, total: int):
        self.progress.setValue(int(current * 100 / total) if total else 0)

    @Slot(str)
    def on_state(self, state: str):
        self.status.setText(state)
        self.update_ui()

    def update_ui(self):
        recording = self.recorder.recording
        playing = self.player.running
        self.record_btn.setText("■ 停止录制" if recording else "● 开始录制")
        self.play_btn.setEnabled(not recording and not playing and bool(self.events))
        self.pause_btn.setEnabled(playing)
        self.stop_btn.setEnabled(playing or recording)
        self.clear_btn.setEnabled(not recording and not playing)

    def clear_events(self):
        self.events.clear()
        self.list.clear()
        self.progress.setValue(0)
        self.status.setText("已清空")
        self.update_ui()

    def save(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存宏", "macro.json", "Macro JSON (*.json)")
        if not path:
            return
        try:
            save_macro(path, self.events)
            self.current_file = path
            self.file_label.setText(os.path.basename(path))
            self.status.setText("保存成功")
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", str(exc))

    def load(self):
        path, _ = QFileDialog.getOpenFileName(self, "加载宏", "", "Macro JSON (*.json)")
        if not path:
            return
        try:
            self.events = load_macro(path)
            self.list.clear()
            for event in self.events:
                self.list.addItem(self.format_event(event))
            self.current_file = path
            self.file_label.setText(os.path.basename(path))
            self.progress.setValue(0)
            self.status.setText(f"加载成功，共 {len(self.events)} 个操作")
            self.update_ui()
        except Exception as exc:
            QMessageBox.critical(self, "加载失败", str(exc))

    @staticmethod
    def format_event(event: MacroEvent) -> str:
        data = event.data
        if event.type == "mouse_move":
            detail = f"鼠标移动 → ({data['x']}, {data['y']})"
        elif event.type == "mouse_click":
            detail = f"鼠标 {data['button']} {'按下' if data['pressed'] else '释放'} → ({data['x']}, {data['y']})"
        elif event.type == "mouse_scroll":
            detail = f"鼠标滚轮 → ({data['dx']}, {data['dy']})"
        elif event.type == "key_down":
            detail = f"键盘按下 → {data['key']}"
        else:
            detail = f"键盘释放 → {data['key']}"
        return f"+{event.delay * 1000:8.1f} ms    {detail}"

    def closeEvent(self, event):
        self.recorder.stop()
        self.player.stop()
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
