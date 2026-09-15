from __future__ import annotations

import os
import sys
from PySide6.QtCore import QObject, Signal, Slot, QSettings, QTimer
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QDialog, QDialogButtonBox, QFormLayout,
    QFrame, QHBoxLayout, QLabel, QListWidget, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QSpinBox, QStackedWidget, QVBoxLayout,
    QWidget, QKeySequenceEdit, QCheckBox
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


class SettingsDialog(QDialog):
    def __init__(self, start_hotkey: str, stop_hotkey: str, shared: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setModal(True)
        self.resize(680, 430)
        self.start_hotkey = start_hotkey
        self.stop_hotkey = stop_hotkey
        self.shared = shared

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.menu = QListWidget()
        self.menu.setObjectName("settingsMenu")
        self.menu.setFixedWidth(160)
        self.menu.addItems(["快捷键", "录制", "播放"])
        root.addWidget(self.menu)

        right = QVBoxLayout()
        right.setContentsMargins(24, 20, 24, 20)
        root.addLayout(right, 1)

        title = QLabel("设置")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        right.addWidget(title)

        self.pages = QStackedWidget()
        right.addWidget(self.pages, 1)
        self.pages.addWidget(self._shortcut_page())
        self.pages.addWidget(self._record_page())
        self.pages.addWidget(self._play_page())
        self.menu.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.menu.setCurrentRow(0)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        right.addWidget(buttons)

        self.setStyleSheet("""
            QDialog { background: #f5f7fa; }
            QListWidget#settingsMenu { background: #eef2f7; border: 0; padding: 12px 8px; outline: 0; }
            QListWidget#settingsMenu::item { min-height: 42px; padding: 0 14px; border-radius: 7px; color: #4b5563; }
            QListWidget#settingsMenu::item:selected { background: white; color: #111827; font-weight: 600; }
            QFrame#settingCard { background: white; border: 1px solid #e4e7ed; border-radius: 10px; }
            QKeySequenceEdit { min-height: 34px; border: 1px solid #dcdfe6; border-radius: 6px; background: white; }
            QCheckBox { spacing: 8px; }
            QDialogButtonBox QPushButton { min-width: 80px; min-height: 34px; }
        """)

    def _card(self, title: str, subtitle: str = ""):
        card = QFrame()
        card.setObjectName("settingCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        label = QLabel(title)
        label.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(label)
        if subtitle:
            tip = QLabel(subtitle)
            tip.setWordWrap(True)
            tip.setStyleSheet("color: #777; margin-bottom: 8px;")
            layout.addWidget(tip)
        return card, layout

    def _shortcut_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        card, box = self._card("录制快捷键", "可以设置开始和结束录制使用同一个快捷键，也可以分别设置。")
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.shared_check = QCheckBox("开始和结束使用同一个快捷键")
        self.shared_check.setChecked(self.shared)
        self.shared_check.toggled.connect(self._toggle_shared)
        box.addWidget(self.shared_check)
        self.start_edit = QKeySequenceEdit(QKeySequence(self.start_hotkey))
        self.start_edit.setMaximumSequenceLength(1)
        form.addRow("开始录制", self.start_edit)
        self.stop_edit = QKeySequenceEdit(QKeySequence(self.stop_hotkey))
        self.stop_edit.setMaximumSequenceLength(1)
        form.addRow("结束录制", self.stop_edit)
        box.addLayout(form)
        self.shared_tip = QLabel()
        self.shared_tip.setWordWrap(True)
        self.shared_tip.setStyleSheet("color: #777; margin-top: 4px;")
        box.addWidget(self.shared_tip)
        layout.addWidget(card)
        layout.addStretch()
        self._toggle_shared(self.shared)
        return page

    def _record_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        card, box = self._card("录制设置", "录制过程中会自动降低高频鼠标移动事件，减少界面占用。")
        form = QFormLayout()
        form.addRow("鼠标移动采样", QLabel("约 30ms / 次"))
        form.addRow("最小移动距离", QLabel("3 像素"))
        box.addLayout(form)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _play_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        card, box = self._card("播放设置", "播放快捷键暂时保持固定，后续可以继续开放配置。")
        form = QFormLayout()
        form.addRow("播放 / 暂停", QLabel("F9"))
        form.addRow("紧急停止", QLabel("F10"))
        box.addLayout(form)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _toggle_shared(self, checked: bool):
        self.shared = checked
        if hasattr(self, "stop_edit"):
            self.stop_edit.setEnabled(not checked)
        if hasattr(self, "shared_tip"):
            self.shared_tip.setText("保存后，结束录制将与开始录制使用相同快捷键。" if checked else "开始和结束快捷键必须不同，且不能与 F9/F10 冲突。")

    def _accept(self):
        start = self.start_edit.keySequence().toString(QKeySequence.PortableText).strip()
        stop = self.stop_edit.keySequence().toString(QKeySequence.PortableText).strip()
        if not start:
            QMessageBox.warning(self, "设置失败", "请设置开始录制快捷键。")
            return
        if self.shared:
            stop = start
        elif not stop:
            QMessageBox.warning(self, "设置失败", "请设置结束录制快捷键。")
            return
        if "," in start or "," in stop:
            QMessageBox.warning(self, "设置失败", "每个快捷键暂时只支持一个按键或一个组合键。")
            return
        if start.upper() in {"F9", "F10"} or stop.upper() in {"F9", "F10"}:
            QMessageBox.warning(self, "设置失败", "F9 和 F10 已保留给播放/暂停和紧急停止。")
            return
        if not self.shared and start.lower() == stop.lower():
            QMessageBox.warning(self, "设置失败", "独立模式下开始和结束快捷键不能相同。")
            return
        self.start_hotkey = start
        self.stop_hotkey = stop
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Macro Recorder")
        self.resize(960, 650)
        self.bridge = Bridge()
        self.events: list[MacroEvent] = []
        self.current_file = ""
        self.settings = QSettings("Lxkgit", "MacroRecorder")
        self.record_hotkey = self.settings.value("record_hotkey", "F8")
        self.stop_hotkey = self.settings.value("stop_hotkey", "F8")
        self.shared_hotkey = self.settings.value("shared_hotkey", True, type=bool)
        self.recorder = MacroRecorder(on_event=self.bridge.recorded.emit)
        self.player = MacroPlayer(on_progress=self.bridge.progress.emit, on_state=self.bridge.state.emit)
        self.hotkey_listener = None
        self._build_ui()
        self.bridge.recorded.connect(self.on_recorded)
        self.bridge.hotkey.connect(self.on_hotkey)
        self.bridge.progress.connect(self.on_progress)
        self.bridge.state.connect(self.on_state)
        self.install_hotkeys()
        self.update_ui()

    @staticmethod
    def qt_to_pynput_key(value: str) -> str:
        value = value.strip()
        parts = [p.strip().lower() for p in value.split("+") if p.strip()]
        mapping = {"esc":"esc","escape":"esc","return":"enter","enter":"enter","space":"space","tab":"tab","backspace":"backspace","delete":"delete","insert":"insert","home":"home","end":"end","pageup":"page_up","pagedown":"page_down","left":"left","right":"right","up":"up","down":"down","pause":"pause","ctrl":"ctrl","control":"ctrl","shift":"shift","alt":"alt","win":"cmd","meta":"cmd"}
        converted = [mapping.get(part, part) for part in parts]
        if len(converted) == 1:
            return converted[0]
        return "+".join(f"<{p}>" if p in {"ctrl","shift","alt","cmd","enter","esc","space","tab"} else p for p in converted)

    def ignored_keys_for_hotkeys(self) -> set[str]:
        keys = set()
        for shortcut in {self.record_hotkey, self.stop_hotkey}:
            for part in shortcut.lower().split("+"):
                part = part.strip()
                if part:
                    keys.add(self.qt_to_pynput_key(part).replace("<", "").replace(">", ""))
        return keys

    def install_hotkeys(self):
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        self.recorder.set_ignored_keys(self.ignored_keys_for_hotkeys())
        hotkeys = {}
        start = self.qt_to_pynput_key(self.record_hotkey)
        stop = self.qt_to_pynput_key(self.stop_hotkey)
        start_spec = f"<{start}>" if "+" not in start and not start.startswith("<") else start
        stop_spec = f"<{stop}>" if "+" not in stop and not stop.startswith("<") else stop
        if self.shared_hotkey:
            hotkeys[start_spec] = lambda: self.bridge.hotkey.emit("record_toggle")
        else:
            hotkeys[start_spec] = lambda: self.bridge.hotkey.emit("record_start")
            hotkeys[stop_spec] = lambda: self.bridge.hotkey.emit("record_stop")
        hotkeys["<f9>"] = lambda: self.bridge.hotkey.emit("f9")
        hotkeys["<f10>"] = lambda: self.bridge.hotkey.emit("f10")
        self.hotkey_listener = keyboard.GlobalHotKeys(hotkeys)
        self.hotkey_listener.start()

    def _build_ui(self):
        root = QWidget()
        root.setStyleSheet("""
            QWidget { font-size: 14px; }
            QMainWindow { background: #f5f7fa; }
            QPushButton { min-height: 38px; padding: 0 18px; border: 1px solid #dcdfe6; border-radius: 7px; background: white; }
            QPushButton:hover { background: #f2f6fc; }
            QListWidget#eventList { background: white; border: 1px solid #e4e7ed; border-radius: 10px; padding: 6px; }
            QListWidget#eventList::item { padding: 9px 10px; border-bottom: 1px solid #f0f2f5; }
            QFrame#panel { background: white; border: 1px solid #e4e7ed; border-radius: 12px; }
            QFrame#settingCard { background: #f8fafc; border: 1px solid #e5e7eb; border-radius: 10px; }
            QSpinBox { min-height: 34px; border: 1px solid #dcdfe6; border-radius: 6px; padding: 0 8px; }
            QProgressBar { height: 8px; border: 0; border-radius: 4px; background: #e9edf2; }
            QProgressBar::chunk { border-radius: 4px; }
        """)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)
        title_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("键盘鼠标宏录制器")
        title.setStyleSheet("font-size: 26px; font-weight: 700;")
        subtitle = QLabel("记录你的键盘与鼠标操作，并按原始时间间隔重新执行")
        subtitle.setStyleSheet("color: #7a8491;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        title_row.addLayout(title_box, 1)
        settings_btn = QPushButton("⚙  设置")
        settings_btn.clicked.connect(self.open_settings)
        title_row.addWidget(settings_btn)
        layout.addLayout(title_row)
        panel = QFrame()
        panel.setObjectName("panel")
        controls = QHBoxLayout(panel)
        controls.setContentsMargins(14, 12, 14, 12)
        self.record_btn = QPushButton("●  开始录制")
        self.record_btn.pressed.connect(self.toggle_record)
        self.play_btn = QPushButton("▶  播放")
        self.play_btn.clicked.connect(self.play)
        self.pause_btn = QPushButton("Ⅱ  暂停")
        self.pause_btn.clicked.connect(self.player.toggle_pause)
        self.stop_btn = QPushButton("■  停止")
        self.stop_btn.pressed.connect(self.stop_all)
        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self.clear_events)
        for button in (self.record_btn, self.play_btn, self.pause_btn, self.stop_btn, self.clear_btn):
            controls.addWidget(button)
        layout.addWidget(panel)
        settings_row = QHBoxLayout()
        settings_row.addWidget(QLabel("循环次数"))
        self.repeat = QSpinBox()
        self.repeat.setRange(0, 999999)
        self.repeat.setValue(1)
        self.repeat.setSpecialValueText("无限循环")
        settings_row.addWidget(self.repeat)
        settings_row.addStretch()
        self.status = QLabel("就绪")
        self.status.setStyleSheet("font-weight: 600;")
        settings_row.addWidget(self.status)
        layout.addLayout(settings_row)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        layout.addWidget(self.progress)
        self.list = QListWidget()
        self.list.setObjectName("eventList")
        layout.addWidget(self.list, 1)
        bottom = QHBoxLayout()
        self.file_label = QLabel("尚未保存")
        self.file_label.setStyleSheet("color: #7a8491;")
        bottom.addWidget(self.file_label, 1)
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save)
        load_btn = QPushButton("加载")
        load_btn.clicked.connect(self.load)
        bottom.addWidget(save_btn)
        bottom.addWidget(load_btn)
        self.hotkey_label = QLabel()
        self.hotkey_label.setStyleSheet("color: #7a8491;")
        bottom.addWidget(self.hotkey_label)
        layout.addLayout(bottom)
        self.setCentralWidget(root)

    def open_settings(self):
        if self.recorder.recording:
            self.stop_recording()
        if self.hotkey_listener:
            self.hotkey_listener.stop()
            self.hotkey_listener = None
        dialog = SettingsDialog(self.record_hotkey, self.stop_hotkey, self.shared_hotkey, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.record_hotkey = dialog.start_hotkey
            self.stop_hotkey = dialog.stop_hotkey
            self.shared_hotkey = dialog.shared
            self.settings.setValue("record_hotkey", self.record_hotkey)
            self.settings.setValue("stop_hotkey", self.stop_hotkey)
            self.settings.setValue("shared_hotkey", self.shared_hotkey)
            self.settings.sync()
            self.install_hotkeys()
            self.update_shortcut_label()
            self.status.setText("设置已保存")
        else:
            self.install_hotkeys()

    def toggle_record(self):
        if self.recorder.recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        if self.player.running:
            self.player.stop()
        self.events.clear()
        self.list.clear()
        self.progress.setValue(0)
        self.recorder.stop()
        self.status.setText("准备录制……")
        self.update_ui()
        QTimer.singleShot(150, self._begin_recording)

    def _begin_recording(self):
        if self.recorder.recording:
            return
        self.recorder.start()
        self.status.setText("正在录制……")
        self.update_ui()

    def stop_recording(self):
        self.recorder.stop()
        self.status.setText(f"录制结束，共 {len(self.events)} 个操作")
        self.update_ui()

    def stop_all(self):
        if self.recorder.recording:
            self.stop_recording()
        self.player.stop()
        self.update_ui()

    def play(self):
        if self.recorder.recording:
            self.stop_recording()
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
        if key == "record_toggle": self.toggle_record()
        elif key == "record_start":
            if not self.recorder.recording: self.start_recording()
        elif key == "record_stop":
            if self.recorder.recording: self.stop_recording()
        elif key == "f9":
            if self.player.running: self.player.toggle_pause()
            else: self.play()
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

    def update_shortcut_label(self):
        mode = self.record_hotkey if self.shared_hotkey else f"开始 {self.record_hotkey} / 结束 {self.stop_hotkey}"
        self.hotkey_label.setText(f"录制快捷键：{mode}  ·  F9 播放/暂停  ·  F10 停止")

    def update_ui(self):
        recording = self.recorder.recording
        playing = self.player.running
        self.record_btn.setText("■  停止录制" if recording else "●  开始录制")
        self.play_btn.setEnabled(not recording and not playing and bool(self.events))
        self.pause_btn.setEnabled(playing)
        self.stop_btn.setEnabled(playing or recording)
        self.clear_btn.setEnabled(not recording and not playing)
        self.update_shortcut_label()

    def clear_events(self):
        self.events.clear()
        self.list.clear()
        self.progress.setValue(0)
        self.status.setText("已清空")
        self.update_ui()

    def save(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存宏", "macro.json", "Macro JSON (*.json)")
        if not path: return
        try:
            save_macro(path, self.events)
            self.current_file = path
            self.file_label.setText(os.path.basename(path))
            self.status.setText("保存成功")
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", str(exc))

    def load(self):
        path, _ = QFileDialog.getOpenFileName(self, "加载宏", "", "Macro JSON (*.json)")
        if not path: return
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
        if event.type == "mouse_move": detail = f"鼠标移动  →  ({data['x']}, {data['y']})"
        elif event.type == "mouse_click": detail = f"鼠标 {data['button']} {'按下' if data['pressed'] else '释放'}  →  ({data['x']}, {data['y']})"
        elif event.type == "mouse_scroll": detail = f"鼠标滚轮  →  ({data['dx']}, {data['dy']})"
        elif event.type == "key_down": detail = f"键盘按下  →  {data['key']}"
        else: detail = f"键盘释放  →  {data['key']}"
        return f"+{event.delay * 1000:8.1f} ms    {detail}"

    def closeEvent(self, event):
        self.recorder.stop()
        self.player.stop()
        if self.hotkey_listener: self.hotkey_listener.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())