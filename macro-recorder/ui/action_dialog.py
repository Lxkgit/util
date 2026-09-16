from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout

from core.model import MacroEvent


class ActionInsertDialog(QDialog):
    """键盘/等待操作编辑器。鼠标操作统一由 macro_editor 的全屏选点界面处理。"""

    def __init__(self, action: str = "key", parent=None):
        super().__init__(parent)
        self.action = action
        self.events: list[MacroEvent] = []
        self.setWindowTitle("添加键盘操作" if action == "key" else "添加等待")
        self.resize(460, 260)
        self.setStyleSheet("QDialog{background:#f5f7fa;} QLabel{color:#303133;} QLineEdit,QDoubleSpinBox{min-height:34px;border:1px solid #dcdfe6;border-radius:7px;padding:0 9px;background:white;} QDialogButtonBox QPushButton{min-height:34px;padding:0 15px;border-radius:7px;}")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)
        title = QLabel("键盘按键" if action == "key" else "添加等待")
        title.setStyleSheet("font-size:20px;font-weight:700;")
        root.addWidget(title)
        form = QFormLayout()
        self.delay = QDoubleSpinBox()
        self.delay.setRange(0, 999999)
        self.delay.setDecimals(3)
        self.delay.setSuffix(" 秒")
        self.key_edit = QLineEdit("enter")
        self.key_edit.setPlaceholderText("例如 a、enter、ctrl、f5")
        if action == "key":
            form.addRow("按键", self.key_edit)
            form.addRow("执行前延迟", self.delay)
        else:
            form.addRow("等待时间", self.delay)
        root.addLayout(form)
        hint = QLabel("提示：鼠标点击、移动、滚轮请使用对应按钮进入全屏选点。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#909399;")
        if action == "key": root.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _accept(self):
        delay = round(self.delay.value(), 3)
        if self.action == "key":
            key = self.key_edit.text().strip().lower()
            if not key:
                self.key_edit.setFocus()
                return
            self.events = [MacroEvent("key_down", delay, {"key": key}), MacroEvent("key_up", 0.0, {"key": key})]
        else:
            self.events = [MacroEvent("delay", delay, {})]
        self.accept()


ActionDialog = ActionInsertDialog
