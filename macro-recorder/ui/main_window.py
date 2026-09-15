from __future__ import annotations

import os

from PySide6.QtCore import QSettings, QTimer, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.model import load_macro, save_macro
from core.player import MacroPlayer
from recording.recorder import MacroRecorder
from services.hotkeys import HotkeyService
from ui.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    event_signal = Signal(object)
    action_signal = Signal(str)
    progress_signal = Signal(int, int)
    state_signal = Signal(str)

    MODES = (
        ("all", "⌨ + 🖱", "键盘 + 鼠标", "同时录制全部操作"),
        ("keyboard", "⌨", "仅键盘", "只记录按键操作"),
        ("mouse", "🖱", "仅鼠标", "只记录移动、点击和滚轮"),
    )

    def __init__(self):
        super().__init__()
        self.setWindowTitle("键盘鼠标宏录制器")
        self.resize(1000, 720)

        self.events = []
        self.current_file = ""
        self.record_mode = "all"
        self._pending = False

        settings = QSettings("Lxkgit", "MacroRecorder")
        self.record_hotkey = str(settings.value("record_hotkey", "F8"))
        self.stop_hotkey = str(settings.value("stop_hotkey", "F8"))
        self.shared_hotkey = settings.value("shared_hotkey", True, type=bool)
        self.play_pause_hotkey = str(settings.value("play_pause_hotkey", "F9"))
        self.stop_playback_hotkey = str(settings.value("stop_playback_hotkey", "F10"))

        self.recorder = MacroRecorder(self.event_signal.emit)
        self.player = MacroPlayer(self.progress_signal.emit, self.state_signal.emit)
        self.hotkeys = HotkeyService(self.action_signal.emit)

        self._build_ui()
        self.event_signal.connect(self._on_event)
        self.action_signal.connect(self._on_action)
        self.progress_signal.connect(self._on_progress)
        self.state_signal.connect(self._on_state)
        self._install_hotkeys()
        self._refresh()

    def _build_ui(self):
        root = QWidget()
        root.setStyleSheet(
            "QWidget{font-size:14px;}"
            "QMainWindow{background:#f5f7fa;}"
            "QPushButton{min-height:38px;padding:0 16px;border:1px solid #dcdfe6;border-radius:8px;background:white;}"
            "QPushButton:hover{background:#f2f6fc;}"
            "QPushButton:disabled{color:#a8abb2;background:#f5f7fa;}"
            "QFrame#panel{background:white;border:1px solid #e4e7ed;border-radius:12px;}"
            "QFrame#modeCard{background:white;border:1px solid #e4e7ed;border-radius:12px;}"
            'QFrame#modeCard[selected="true"]{border:2px solid #409eff;background:#f4f9ff;}'
            "QLabel#modeTitle{font-size:16px;font-weight:700;}"
            "QLabel#modeIcon{font-size:28px;}"
            "QListWidget#eventList{background:white;border:1px solid #e4e7ed;border-radius:10px;padding:6px;color:#303133;}"
            "QListWidget#eventList::item{padding:8px 10px;color:#303133;}"
            "QListWidget#eventList::item:selected{color:#303133;background:#eaf2ff;}"
            "QSpinBox{min-height:34px;border:1px solid #dcdfe6;border-radius:6px;padding:0 8px;}"
            "QProgressBar{height:8px;border:0;border-radius:4px;background:#e9edf2;}"
        )

        layout = QVBoxLayout(root)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)

        head = QHBoxLayout()
        box = QVBoxLayout()
        title = QLabel("键盘鼠标宏录制器")
        title.setStyleSheet("font-size:26px;font-weight:700;")
        sub = QLabel("选择录制类型，记录操作并按原始时间间隔重新执行")
        sub.setStyleSheet("color:#7a8491;")
        box.addWidget(title)
        box.addWidget(sub)
        head.addLayout(box, 1)

        setting = QPushButton("⚙  设置")
        setting.clicked.connect(self.open_settings)
        head.addWidget(setting)
        layout.addLayout(head)

        modes = QHBoxLayout()
        self.mode_cards = {}
        for mode, icon, name, desc in self.MODES:
            card = QFrame()
            card.setObjectName("modeCard")
            card.setProperty("selected", mode == self.record_mode)
            card.mousePressEvent = lambda event, selected_mode=mode: self.select_mode(selected_mode)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(18, 14, 18, 14)
            icon_label = QLabel(icon)
            icon_label.setObjectName("modeIcon")
            name_label = QLabel(name)
            name_label.setObjectName("modeTitle")
            desc_label = QLabel(desc)
            desc_label.setStyleSheet("color:#7a8491;")
            card_layout.addWidget(icon_label)
            card_layout.addWidget(name_label)
            card_layout.addWidget(desc_label)
            modes.addWidget(card)
            self.mode_cards[mode] = card
        layout.addLayout(modes)

        panel = QFrame()
        panel.setObjectName("panel")
        controls = QHBoxLayout(panel)
        controls.setContentsMargins(14, 12, 14, 12)
        self.record_btn = QPushButton("●  开始录制")
        self.play_btn = QPushButton("▶  播放")
        self.pause_btn = QPushButton("Ⅱ  暂停播放")
        self.stop_btn = QPushButton("■  停止")
        self.clear_btn = QPushButton("清空")
        self.record_btn.clicked.connect(self.toggle_record)
        self.play_btn.clicked.connect(self.play)
        self.pause_btn.clicked.connect(self.player.toggle_pause)
        self.stop_btn.clicked.connect(self.stop_all)
        self.clear_btn.clicked.connect(self.clear_events)
        for widget in (self.record_btn, self.play_btn, self.pause_btn, self.stop_btn, self.clear_btn):
            controls.addWidget(widget)
        layout.addWidget(panel)

        row = QHBoxLayout()
        row.addWidget(QLabel("循环次数"))
        self.repeat = QSpinBox()
        self.repeat.setRange(0, 999999)
        self.repeat.setValue(1)
        self.repeat.setSpecialValueText("无限循环")
        row.addWidget(self.repeat)
        row.addStretch()
        self.status = QLabel("就绪")
        self.status.setStyleSheet("font-weight:600;")
        row.addWidget(self.status)
        layout.addLayout(row)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        layout.addWidget(self.progress)
        self.list = QListWidget()
        self.list.setObjectName("eventList")
        self.list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.list, 1)

        bottom = QHBoxLayout()
        self.file_label = QLabel("尚未保存")
        self.file_label.setStyleSheet("color:#7a8491;")
        bottom.addWidget(self.file_label, 1)
        save_button = QPushButton("保存")
        load_button = QPushButton("加载")
        save_button.clicked.connect(self.save)
        load_button.clicked.connect(self.load)
        bottom.addWidget(save_button)
        bottom.addWidget(load_button)
        self.hotkey_label = QLabel()
        self.hotkey_label.setStyleSheet("color:#7a8491;")
        bottom.addWidget(self.hotkey_label)
        layout.addLayout(bottom)
        self.setCentralWidget(root)

    def select_mode(self, mode):
        if self.recorder.recording or self.player.running:
            return
        self.record_mode = mode
        for name, card in self.mode_cards.items():
            card.setProperty("selected", name == mode)
            card.style().unpolish(card)
            card.style().polish(card)
            card.update()
        self.status.setText({"all": "已选择：键盘 + 鼠标", "keyboard": "已选择：仅键盘", "mouse": "已选择：仅鼠标"}[mode])

    def toggle_record(self):
        if self.recorder.recording:
            self.toggle_record_pause()
        else:
            self.start_recording()

    def toggle_record_pause(self):
        if not self.recorder.recording:
            return
        if self.recorder.paused:
            self.recorder.resume()
            self.status.setText(self._recording_text())
        else:
            self.recorder.pause()
            self.status.setText("录制已暂停")
        self._refresh()

    def start_recording(self):
        if self.player.running:
            self.player.stop()
        self.events.clear()
        self.list.clear()
        self.progress.setValue(0)
        self.recorder.stop()
        self._pending = True
        self.status.setText("准备录制……")
        self._refresh()
        QTimer.singleShot(150, self._begin_recording)

    def _begin_recording(self):
        if not self._pending or self.recorder.recording:
            return
        self._pending = False
        self.recorder.start(self.record_mode)
        self.status.setText(self._recording_text())
        self._refresh()

    def _recording_text(self):
        return {"all": "正在录制：键盘 + 鼠标", "keyboard": "正在录制：仅键盘", "mouse": "正在录制：仅鼠标"}[self.record_mode]

    def stop_recording(self):
        self._pending = False
        self.recorder.stop()
        self.status.setText(f"录制结束，共 {len(self.events)} 个操作")
        self._refresh()

    def stop_all(self):
        self._pending = False
        self.recorder.stop()
        self.player.stop()
        self._refresh()

    def end_playback(self):
        if self.player.running:
            self.player.stop()
        self.status.setText("播放已结束")
        self._refresh()

    def play(self):
        if self.recorder.recording:
            self.stop_recording()
        if not self.events:
            QMessageBox.information(self, "提示", "没有可播放的操作，请先录制或加载宏。")
            return
        if self.player.play(self.events, self.repeat.value()):
            self.status.setText("播放中")
            self._refresh()

    def _on_event(self, event):
        self.events.append(event)
        self.list.addItem(self.format_event(event))
        if self.list.count() % 20 == 0:
            self.list.scrollToBottom()

    def _on_action(self, action):
        if action == "record_toggle":
            self.toggle_record()
        elif action == "record_start" and not self.recorder.recording:
            self.start_recording()
        elif action == "record_stop" and self.recorder.recording:
            self.stop_recording()
        elif action == "play_pause":
            if self.player.running:
                self.player.toggle_pause()
            else:
                self.play()
        elif action == "stop_playback":
            self.end_playback()

    def _on_progress(self, current, total):
        self.progress.setValue(int(current * 100 / total) if total else 0)

    def _on_state(self, state):
        self.status.setText(state)
        self._refresh()

    def _install_hotkeys(self):
        self.recorder.set_ignored_keys(
            self.hotkeys.ignored_keys(
                self.record_hotkey,
                self.stop_hotkey,
                self.play_pause_hotkey,
                self.stop_playback_hotkey,
            )
        )
        self.hotkeys.install(
            self.record_hotkey,
            self.stop_hotkey,
            self.shared_hotkey,
            self.play_pause_hotkey,
            self.stop_playback_hotkey,
        )

    def _remove_hotkeys(self):
        self.hotkeys.stop()

    def open_settings(self):
        if self.recorder.recording:
            self.stop_recording()
        self._remove_hotkeys()
        dialog = SettingsDialog(
            self.record_hotkey,
            self.stop_hotkey,
            self.shared_hotkey,
            self.play_pause_hotkey,
            self.stop_playback_hotkey,
            self,
        )
        if dialog.exec():
            self.record_hotkey = dialog.start_hotkey
            self.stop_hotkey = dialog.stop_hotkey
            self.shared_hotkey = dialog.shared
            self.play_pause_hotkey = dialog.play_pause_hotkey
            self.stop_playback_hotkey = dialog.stop_playback_hotkey
            settings = QSettings("Lxkgit", "MacroRecorder")
            settings.setValue("record_hotkey", self.record_hotkey)
            settings.setValue("stop_hotkey", self.stop_hotkey)
            settings.setValue("shared_hotkey", self.shared_hotkey)
            settings.setValue("play_pause_hotkey", self.play_pause_hotkey)
            settings.setValue("stop_playback_hotkey", self.stop_playback_hotkey)
            settings.sync()
            self._install_hotkeys()
            self.status.setText("设置已保存")
        else:
            self._install_hotkeys()

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
            self.status.setText(f"加载成功，共 {len(self.events)} 个操作")
            self._refresh()
        except Exception as exc:
            QMessageBox.critical(self, "加载失败", str(exc))

    def clear_events(self):
        if self.recorder.recording or self.player.running:
            return
        self.events.clear()
        self.list.clear()
        self.current_file = ""
        self.file_label.setText("尚未保存")
        self.progress.setValue(0)
        self.status.setText("已清空")
        self._refresh()

    @staticmethod
    def format_event(event):
        data = event.data
        if event.type.startswith("key"):
            return f"{event.type}  {data.get('key')}  +{event.delay:.3f}s"
        if event.type == "mouse_move":
            return f"mouse_move  ({data['x']}, {data['y']})  +{event.delay:.3f}s"
        if event.type == "mouse_click":
            state = "按下" if data["pressed"] else "释放"
            return f"mouse_click  {data['button']} {state}  +{event.delay:.3f}s"
        if event.type == "mouse_scroll":
            return f"mouse_scroll  ({data['dx']}, {data['dy']})  +{event.delay:.3f}s"
        return str(event)

    def _refresh(self):
        recording = self.recorder.recording
        playing = self.player.running
        if recording:
            self.record_btn.setText("Ⅱ  继续录制" if self.recorder.paused else "Ⅱ  暂停录制")
        else:
            self.record_btn.setText("●  开始录制")
        self.play_btn.setEnabled(not playing and not recording)
        self.pause_btn.setEnabled(playing)
        self.stop_btn.setEnabled(recording or playing or self._pending)
        self.clear_btn.setEnabled(not recording and not playing and not self._pending)
        self.hotkey_label.setText(
            f"录制：{self.record_hotkey}  |  播放/暂停：{self.play_pause_hotkey}  |  结束播放：{self.stop_playback_hotkey}"
        )

    def closeEvent(self, event):
        self._pending = False
        self._remove_hotkeys()
        self.recorder.stop()
        self.player.stop()
        event.accept()
