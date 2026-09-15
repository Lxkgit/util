from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QLabel,
    QListWidget,
    QMessageBox,
    QKeySequenceEdit,
    QStackedWidget,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)


class SettingsDialog(QDialog):
    def __init__(self, start: str, stop: str, shared: bool, play_pause: str, stop_playback: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setModal(True)
        self.resize(700, 500)
        self.start_hotkey = start
        self.stop_hotkey = stop
        self.shared = shared
        self.play_pause_hotkey = play_pause
        self.stop_playback_hotkey = stop_playback

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.menu = QListWidget()
        self.menu.setObjectName("settingsMenu")
        self.menu.setFixedWidth(160)
        self.menu.addItems(["快捷键", "录制", "播放"])
        root.addWidget(self.menu)

        right = QVBoxLayout()
        right.setContentsMargins(24, 20, 24, 20)
        root.addLayout(right, 1)

        title = QLabel("设置")
        title.setStyleSheet("font-size:24px;font-weight:700;color:#303133;")
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

        self.setStyleSheet(
            "QDialog{background:#f5f7fa;}"
            "QListWidget#settingsMenu{background:#eef2f7;border:0;padding:12px 8px;color:#303133;}"
            "QListWidget#settingsMenu::item{min-height:42px;padding:0 14px;border-radius:7px;color:#303133;}"
            "QListWidget#settingsMenu::item:hover{background:#e5ebf3;color:#303133;}"
            "QListWidget#settingsMenu::item:selected{background:#ffffff;color:#303133;font-weight:600;}"
            "QListWidget#settingsMenu::item:selected:active{background:#ffffff;color:#303133;}"
            "QListWidget#settingsMenu::item:selected:!active{background:#ffffff;color:#303133;}"
            "QFrame#card{background:white;border:1px solid #e4e7ed;border-radius:10px;}"
            "QLabel{color:#303133;}"
            "QKeySequenceEdit{min-height:34px;border:1px solid #dcdfe6;border-radius:6px;}"
            "QDialogButtonBox QPushButton{min-width:80px;min-height:34px;}"
        )

    def _card(self, title, tip):
        card = QFrame()
        card.setObjectName("card")
        box = QVBoxLayout(card)
        box.setContentsMargins(18, 16, 18, 16)

        label = QLabel(title)
        label.setStyleSheet("font-size:16px;font-weight:600;color:#303133;")
        box.addWidget(label)

        text = QLabel(tip)
        text.setWordWrap(True)
        text.setStyleSheet("color:#777;margin-bottom:8px;")
        box.addWidget(text)
        return card, box

    def _shortcut_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        card, box = self._card("录制快捷键", "开始和结束可以使用同一个快捷键，也可以分别配置。支持单键和组合键。")

        self.shared_check = QCheckBox("开始和结束使用同一个快捷键")
        self.shared_check.setChecked(self.shared)
        self.shared_check.toggled.connect(self._toggle_shared)
        box.addWidget(self.shared_check)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.start_edit = QKeySequenceEdit(QKeySequence(self.start_hotkey))
        self.stop_edit = QKeySequenceEdit(QKeySequence(self.stop_hotkey))
        self.start_edit.setMaximumSequenceLength(1)
        self.stop_edit.setMaximumSequenceLength(1)
        form.addRow("开始录制", self.start_edit)
        form.addRow("结束录制", self.stop_edit)
        box.addLayout(form)

        self.tip = QLabel()
        self.tip.setStyleSheet("color:#777;")
        box.addWidget(self.tip)
        layout.addWidget(card)
        layout.addStretch()
        self._toggle_shared(self.shared)
        return page

    def _record_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        card, box = self._card("录制设置", "鼠标移动会进行采样，降低高频事件对界面的影响。")
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.addRow("鼠标移动采样", QLabel("约 30ms / 次"))
        form.addRow("最小移动距离", QLabel("3 像素"))
        box.addLayout(form)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _play_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        card, box = self._card("播放设置", "播放控制快捷键均可自定义，并支持组合键。")

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.play_pause_edit = QKeySequenceEdit(QKeySequence(self.play_pause_hotkey))
        self.stop_playback_edit = QKeySequenceEdit(QKeySequence(self.stop_playback_hotkey))
        self.play_pause_edit.setMaximumSequenceLength(1)
        self.stop_playback_edit.setMaximumSequenceLength(1)
        form.addRow("播放 / 暂停", self.play_pause_edit)
        form.addRow("结束播放", self.stop_playback_edit)
        box.addLayout(form)

        layout.addWidget(card)
        layout.addStretch()
        return page

    def _toggle_shared(self, checked):
        self.shared = checked
        if hasattr(self, "stop_edit"):
            self.stop_edit.setEnabled(not checked)
        if hasattr(self, "tip"):
            self.tip.setText("结束录制使用相同快捷键。" if checked else "开始和结束快捷键必须不同。")

    def _accept(self):
        start = self.start_edit.keySequence().toString(QKeySequence.PortableText).strip()
        stop = self.stop_edit.keySequence().toString(QKeySequence.PortableText).strip()
        play_pause = self.play_pause_edit.keySequence().toString(QKeySequence.PortableText).strip()
        stop_playback = self.stop_playback_edit.keySequence().toString(QKeySequence.PortableText).strip()

        if self.shared:
            stop = start

        values = {
            "开始录制": start,
            "结束录制": stop,
            "播放 / 暂停": play_pause,
            "结束播放": stop_playback,
        }
        for name, value in values.items():
            if not value:
                QMessageBox.warning(self, "设置失败", f"请设置{name}快捷键。")
                return

        if not self.shared and start.lower() == stop.lower():
            QMessageBox.warning(self, "设置失败", "独立模式下开始和结束录制快捷键不能相同。")
            return

        normalized = {}
        for name, value in values.items():
            key = value.lower().replace(" ", "")
            if key in normalized:
                QMessageBox.warning(self, "设置失败", f"{name}与{normalized[key]}不能使用相同快捷键。")
                return
            normalized[key] = name

        self.start_hotkey = start
        self.stop_hotkey = stop
        self.play_pause_hotkey = play_pause
        self.stop_playback_hotkey = stop_playback
        self.accept()
