from __future__ import annotations

import os
import sys
from typing import Optional

from PySide6.QtCore import QObject, QSettings, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QKeySequenceEdit,
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
        self.resize(700, 440)
        self.start_hotkey = start_hotkey
        self.stop_hotkey = stop_hotkey
        self.shared = shared
        self._build_ui()

    def _build_ui(self):
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

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
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

    @staticmethod
    def _card(title: str, subtitle: str = ""):
        card = QFrame()
        card.setObjectName("settingCard")
        box = QVBoxLayout(card)
        box.setContentsMargins(18, 16, 18, 16)
        label = QLabel(title)
        label.setStyleSheet("font-size: 16px; font-weight: 600;")
        box.addWidget(label)
        if subtitle:
            tip = QLabel(subtitle)
            tip.setWordWrap(True)
            tip.setStyleSheet("color: #777; margin-bottom: 8px;")
            box.addWidget(tip)
        return card, box

    def _shortcut_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        card, box = self._card("录制快捷键", "开始和结束可以使用同一个快捷键，也可以分别配置。")

        self.shared_check = QCheckBox("开始和结束使用同一个快捷键")
        self.shared_check.setChecked(self.shared)
        self.shared_check.toggled.connect(self._toggle_shared)
        box.addWidget(self.shared_check)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.start_edit = QKeySequenceEdit(QKeySequence(self.start_hotkey))
        self.start_edit.setMaximumSequenceLength(1)
        self.stop_edit = QKeySequenceEdit(QKeySequence(self.stop_hotkey))
        self.stop_edit.setMaximumSequenceLength(1)
        form.addRow("开始录制", self.start_edit)
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
        card, box = self._card("录制设置", "高频鼠标移动会进行采样，避免事件过多导致界面卡顿。")
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
        card, box = self._card("播放设置", "播放控制快捷键固定，避免与录制快捷键发生冲突。")
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
            self.shared_tip.setText(
                "保存后，结束录制将与开始录制使用相同快捷键。"
                if checked
                else "开始和结束快捷键必须不同，且不能使用 F9/F10。"
            )

    def _accept(self):
        start = self.start_edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText).strip()
        stop = self.stop_edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText).strip()
        if not start:
            QMessageBox.warning(self, "设置失败", "请设置开始录制快捷键。")
            return
        if self.shared:
            stop = start
        elif not stop:
            QMessageBox.warning(self, "设置失败", "请设置结束录制快捷键。")
            return
        if "," in start or "," in stop:
            QMessageBox.warning(self, "设置失败", "每个快捷键只支持一个按键或一个组合键。")
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
    RECORD_DELAY_MS = 150

    def __init__(self):
        super().__init__()
        self.setWindowTitle("键盘鼠标宏录制器")
        self.resize(960, 650)

        self.bridge = Bridge()
        self.events: list[MacroEvent] = []
        self.current_file = ""
        self.hotkey_listener: Optional[keyboard.GlobalHotKeys] = None
        self._pending_record_start = False

        self.settings = QSettings("Lxkgit", "MacroRecorder")
        self.record_hotkey = str(self.settings.value("record_hotkey", "F8"))
        self.stop_hotkey = str(self.settings.value("stop_hotkey", "F8"))
        self.shared_hotkey = self.settings.value("shared_hotkey", True, type=bool)

        self.recorder = MacroRecorder(on_event=self.bridge.recorded.emit)
        self.player = MacroPlayer(on_progress=self.bridge.progress.emit, on_state=self.bridge.state.emit)

        self._build_ui()
        self._connect_signals()
        self._install_hotkeys()
        self._refresh_ui()

    def _connect_signals(self):
        self.bridge.recorded.connect(self.on_recorded)
        self.bridge.hotkey.connect(self.on_hotkey)
        self.bridge.progress.connect(self.on_progress)
        self.bridge.state.connect(self.on_state)

    def _build_ui(self):
        root = QWidget()
        root.setStyleSheet("""
            QWidget { font-size: 14px; }
            QMainWindow { background: #f5f7fa; }
            QPushButton { min-height: 38px; padding: 0 18px; border: 1px solid #dcdfe6; border-radius: 7px; background: white; }
            QPushButton:hover { background: #f2f6fc; }
            QPushButton:disabled { color: #a8abb2; background: #f5f7fa; }
            QListWidget#eventList { background: white; border: 1px solid #e4e7ed; border-radius: 10px; padding: 6px; color: #303133; }
            QListWidget#eventList::item { padding: 9px 10px; color: #303133; }
            QListWidget#eventList::item:selected { color: #303133; background: #eaf2ff; }
            QFrame#panel { background: white; border: 1px solid #e4e7ed; border-radius: 12px; }
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
        subtitle = QLabel("记录键盘与鼠标操作，并按原始时间间隔重新执行")
        subtitle.setStyleSheet("color: #7a8491;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        title_row.addLayout(title_box, 1)

        self.settings_btn = QPushButton("⚙  设置")
        self.settings_btn.clicked.connect(self.open_settings)
        title_row.addWidget(self.settings_btn)
        layout.addLayout(title_row)

        panel = QFrame()
        panel.setObjectName("panel")
        controls = QHBoxLayout(panel)
        controls.setContentsMargins(14, 12, 14, 12)
        self.record_btn = QPushButton("●  开始录制")
        self.play_btn = QPushButton("▶  播放")
        self.pause_btn = QPushButton("Ⅱ  暂停")
        self.stop_btn = QPushButton("■  停止")
        self.clear_btn = QPushButton("清空")
        self.record_btn.clicked.connect(self.toggle_record)
        self.play_btn.clicked.connect(self.play)
        self.pause_btn.clicked.connect(self.player.toggle_pause)
        self.stop_btn.clicked.connect(self.stop_all)
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
        self.list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.list.setUniformItemSizes(True)
        layout.addWidget(self.list, 1)

        bottom = QHBoxLayout()
        self.file_label = QLabel("尚未保存")
        self.file_label.setStyleSheet("color: #7a8491;")
        bottom.addWidget(self.file_label, 1)
        self.save_btn = QPushButton("保存")
        self.load_btn = QPushButton("加载")
        self.save_btn.clicked.connect(self.save)
        self.load_btn.clicked.connect(self.load)
        bottom.addWidget(self.save_btn)
        bottom.addWidget(self.load_btn)
        self.hotkey_label = QLabel()
        self.hotkey_label.setStyleSheet("color: #7a8491;")
        bottom.addWidget(self.hotkey_label)
        layout.addLayout(bottom)

        self.setCentralWidget(root)

    @staticmethod
    def _shortcut_to_pynput(value: str) -> str:
        parts = [part.strip().lower() for part in value.split("+") if part.strip()]
        mapping = {
            "esc": "esc", "escape": "esc", "return": "enter", "enter": "enter",
            "space": "space", "tab": "tab", "backspace": "backspace", "delete": "delete",
            "insert": "insert", "home": "home", "end": "end", "pageup": "page_up",
            "pagedown": "page_down", "left": "left", "right": "right", "up": "up", "down": "down",
            "pause": "pause", "ctrl": "ctrl", "control": "ctrl", "shift": "shift",
            "alt": "alt", "win": "cmd", "meta": "cmd",
        }
        converted = [mapping.get(part, part) for part in parts]
        if len(converted) == 1:
            return converted[0]
        special = {"ctrl", "shift", "alt", "cmd", "enter", "esc", "space", "tab"}
        return "+".join(f"<{part}>" if part in special else part for part in converted)

    def _ignored_keys(self) -> set[str]:
        keys = {"f9", "f10"}
        for shortcut in {self.record_hotkey, self.stop_hotkey}:
            for part in shortcut.lower().split("+"):
                part = part.strip()
                if part:
                    keys.add(self._shortcut_to_pynput(part).replace("<", "").replace(">", ""))
        return keys

    def _install_hotkeys(self):
        self._remove_hotkeys()
        self.recorder.set_ignored_keys(self._ignored_keys())

        start = self._shortcut_to_pynput(self.record_hotkey)
        stop = self._shortcut_to_pynput(self.stop_hotkey)
        start_spec = f"<{start}>" if "+" not in start and not start.startswith("<") else start
        stop_spec = f"<{stop}>" if "+" not in stop and not stop.startswith("<") else stop

        hotkeys = {}
        if self.shared_hotkey:
            hotkeys[start_spec] = lambda: self.bridge.hotkey.emit("record_toggle")
        else:
            hotkeys[start_spec] = lambda: self.bridge.hotkey.emit("record_start")
            hotkeys[stop_spec] = lambda: self.bridge.hotkey.emit("record_stop")
        hotkeys["<f9>"] = lambda: self.bridge.hotkey.emit("f9")
        hotkeys["<f10>"] = lambda: self.bridge.hotkey.emit("f10")

        self.hotkey_listener = keyboard.GlobalHotKeys(hotkeys)
        self.hotkey_listener.start()

    def _remove_hotkeys(self):
        if self.hotkey_listener:
            self.hotkey_listener.stop()
            self.hotkey_listener = None

    def open_settings(self):
        was_recording = self.recorder.recording
        if was_recording:
            self.stop_recording()
        self._remove_hotkeys()

        dialog = SettingsDialog(self.record_hotkey, self.stop_hotkey, self.shared_hotkey, self)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        if accepted:
            self.record_hotkey = dialog.start_hotkey
            self.stop_hotkey = dialog.stop_hotkey
            self.shared_hotkey = dialog.shared
            self.settings.setValue("record_hotkey", self.record_hotkey)
            self.settings.setValue("stop_hotkey", self.stop_hotkey)
            self.settings.setValue("shared_hotkey", self.shared_hotkey)
            self.settings.sync()
            self.status.setText("设置已保存")
        else:
            self.status.setText("已取消设置")

        self._install_hotkeys()
        self._refresh_ui()

    def toggle_record(self):
        if self.recorder.recording or self._pending_record_start:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        if self.recorder.recording or self._pending_record_start:
            return
        if self.player.running:
            self.player.stop()
        self.events.clear()
        self.list.clear()
        self.current_file = ""
        self.file_label.setText("尚未保存")
        self.progress.setValue(0)
        self.recorder.stop()
        self._pending_record_start = True
        self.status.setText("准备录制……")
        self._refresh_ui()
        QTimer.singleShot(self.RECORD_DELAY_MS, self._begin_recording)

    def _begin_recording(self):
        if not self._pending_record_start:
            return
        self._pending_record_start = False
        if self.recorder.recording:
            return
        self.recorder.start()
        self.status.setText("正在录制……")
        self._refresh_ui()

    def stop_recording(self):
        self._pending_record_start = False
        self.recorder.stop()
        self.status.setText(f"录制结束，共 {len(self.events)} 个操作")
        self._refresh_ui()

    def stop_all(self):
        self._pending_record_start = False
        self.recorder.stop()
        self.player.stop()
        self.status.setText("已停止")
        self._refresh_ui()

    def play(self):
        if self.recorder.recording or self._pending_record_start:
            self.stop_recording()
        if not self.events:
            QMessageBox.information(self, "提示", "没有可播放的操作，请先录制或加载宏。")
            return
        if self.player.play(self.events, self.repeat.value()):
            self.status.setText("播放中")
            self._refresh_ui()

    @Slot(object)
    def on_recorded(self, event: MacroEvent):
        self.events.append(event)
        self.list.addItem(self.format_event(event))
        if self.list.count() == 1 or self.list.count() % 20 == 0:
            self.list.scrollToBottom()

    @Slot(str)
    def on_hotkey(self, key: str):
        if key == "record_toggle":
            self.toggle_record()
        elif key == "record_start" and not self.recorder.recording:
            self.start_recording()
        elif key == "record_stop" and self.recorder.recording:
            self.stop_recording()
        elif key == "f9":
            if self.player.running:
                self.player.toggle_pause()
            elif not self.recorder.recording:
                self.play()
        elif key == "f10":
            self.stop_all()
            self.status.setText("已紧急停止")

    @Slot(int, int)
    def on_progress(self, current: int, total: int):
        self.progress.setValue(int(current * 100 / total) if total else 0)

    @Slot(str)
    def on_state(self, state: str):
        self.status.setText(state)
        self._refresh_ui()

    def _refresh_ui(self):
        recording = self.recorder.recording or self._pending_record_start
        playing = self.player.running
        self.record_btn.setText("■  停止录制" if recording else "●  开始录制")
        self.play_btn.setEnabled(not recording and not playing and bool(self.events))
        self.pause_btn.setEnabled(playing)
        self.stop_btn.setEnabled(recording or playing)
        self.clear_btn.setEnabled(not recording and not playing)
        self.save_btn.setEnabled(not recording and not playing and bool(self.events))
        self.load_btn.setEnabled(not recording and not playing)
        self.settings_btn.setEnabled(not recording and not playing)
        mode = self.record_hotkey if self.shared_hotkey else f"开始 {self.record_hotkey} / 结束 {self.stop_hotkey}"
        self.hotkey_label.setText(f"录制：{mode}  ·  F9 播放/暂停  ·  F10 停止")

    def clear_events(self):
        if self.recorder.recording or self.player.running:
            return
        self.events.clear()
        self.list.clear()
        self.current_file = ""
        self.file_label.setText("尚未保存")
        self.progress.setValue(0)
        self.status.setText("已清空")
        self._refresh_ui()

    def save(self):
        if not self.events:
            return
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
        if self.recorder.recording or self.player.running:
            return
        path, _ = QFileDialog.getOpenFileName(self, "加载宏", "", "Macro JSON (*.json)")
        if not path:
            return
        try:
            events = load_macro(path)
            self.events = events
            self.list.clear()
            self.list.addItems(self.format_event(event) for event in events)
            self.current_file = path
            self.file_label.setText(os.path.basename(path))
            self.progress.setValue(0)
            self.status.setText(f"加载成功，共 {len(events)} 个操作")
            self._refresh_ui()
        except Exception as exc:
            QMessageBox.critical(self, "加载失败", str(exc))

    @staticmethod
    def format_event(event: MacroEvent) -> str:
        data = event.data
        if event.type == "mouse_move":
            detail = f"鼠标移动  →  ({data['x']}, {data['y']})"
        elif event.type == "mouse_click":
            action = "按下" if data["pressed"] else "释放"
            detail = f"鼠标 {data['button']} {action}  →  ({data['x']}, {data['y']})"
        elif event.type == "mouse_scroll":
            detail = f"鼠标滚轮  →  ({data['dx']}, {data['dy']})"
        elif event.type == "key_down":
            detail = f"键盘按下  →  {data['key']}"
        else:
            detail = f"键盘释放  →  {data['key']}"
        return f"+{event.delay * 1000:8.1f} ms    {detail}"

    def closeEvent(self, event):
        self._pending_record_start = False
        self.recorder.stop()
        self.player.stop()
        self._remove_hotkeys()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Macro Recorder")
    app.setOrganizationName("Lxkgit")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
