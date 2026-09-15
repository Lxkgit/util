from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QDoubleSpinBox,
    QVBoxLayout,
)

from core.model import MacroEvent


class EventEditorDialog(QDialog):
    def __init__(self, event: MacroEvent, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑事件")
        self.setModal(True)
        self.resize(420, 220)
        self.event = event

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title = QLabel(self._title(event))
        title.setStyleSheet("font-size:18px;font-weight:600;color:#303133;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.delay_edit = QDoubleSpinBox()
        self.delay_edit.setRange(0, 999999.0)
        self.delay_edit.setDecimals(3)
        self.delay_edit.setSingleStep(0.010)
        self.delay_edit.setValue(max(0.0, float(event.delay)))
        self.delay_edit.setSuffix(" 秒")
        self.delay_edit.setToolTip("当前事件执行前等待的时间")
        form.addRow("执行前延迟", self.delay_edit)
        layout.addLayout(form)

        tip = QLabel(self._detail(event))
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#7a8491;")
        layout.addWidget(tip)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _title(event: MacroEvent) -> str:
        names = {
            "key_down": "键盘按下",
            "key_up": "键盘释放",
            "mouse_move": "鼠标移动",
            "mouse_click": "鼠标点击",
            "mouse_scroll": "鼠标滚轮",
        }
        return names.get(event.type, event.type)

    @staticmethod
    def _detail(event: MacroEvent) -> str:
        data = event.data
        if event.type.startswith("key"):
            return f"按键：{data.get('key', '')}"
        if event.type == "mouse_move":
            return f"坐标：({data.get('x')}, {data.get('y')})"
        if event.type == "mouse_click":
            state = "按下" if data.get("pressed") else "释放"
            return f"按钮：{data.get('button', '')}，状态：{state}，坐标：({data.get('x')}, {data.get('y')})"
        if event.type == "mouse_scroll":
            return f"滚轮：({data.get('dx')}, {data.get('dy')})，坐标：({data.get('x')}, {data.get('y')})"
        return str(data)

    def _accept(self):
        self.event.delay = round(self.delay_edit.value(), 3)
        self.accept()
