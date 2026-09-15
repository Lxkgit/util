from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from core.model import MacroEvent


class ActionInsertDialog(QDialog):
    ACTIONS = (
        ("key", "键盘按键"),
        ("click", "鼠标点击"),
        ("move", "鼠标移动"),
        ("scroll", "滚轮"),
        ("delay", "延迟"),
    )

    def __init__(self, action: str = "key", parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加操作")
        self.setModal(True)
        self.resize(460, 320)
        self.events: list[MacroEvent] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        self.action_combo = QComboBox()
        for value, name in self.ACTIONS:
            self.action_combo.addItem(name, value)
        index = max(0, self.action_combo.findData(action))
        self.action_combo.setCurrentIndex(index)
        self.action_combo.currentIndexChanged.connect(self._rebuild_form)
        layout.addWidget(QLabel("操作类型"))
        layout.addWidget(self.action_combo)

        self.form = QFormLayout()
        self.form.setContentsMargins(0, 4, 0, 0)
        layout.addLayout(self.form)

        self.delay = QDoubleSpinBox()
        self.delay.setRange(0.0, 999999.0)
        self.delay.setDecimals(3)
        self.delay.setSingleStep(0.010)
        self.delay.setSuffix(" 秒")
        self.delay.setValue(0.0)

        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("例如 a、enter、ctrl、f5")
        self.key_edit.setText("enter")

        self.x_spin = QSpinBox()
        self.x_spin.setRange(-99999, 99999)
        self.y_spin = QSpinBox()
        self.y_spin.setRange(-99999, 99999)
        self.dx_spin = QSpinBox()
        self.dx_spin.setRange(-99999, 99999)
        self.dy_spin = QSpinBox()
        self.dy_spin.setRange(-99999, 99999)

        self.button_combo = QComboBox()
        self.button_combo.addItems(["left", "right", "middle"])
        self.press_combo = QComboBox()
        self.press_combo.addItem("按下", True)
        self.press_combo.addItem("释放", False)

        self._rebuild_form()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _clear_form(self):
        while self.form.rowCount():
            self.form.removeRow(0)

    def _rebuild_form(self):
        self._clear_form()
        action = self.action_combo.currentData()
        if action == "key":
            self.form.addRow("按键", self.key_edit)
            self.form.addRow("执行前延迟", self.delay)
        elif action == "click":
            self.form.addRow("X", self.x_spin)
            self.form.addRow("Y", self.y_spin)
            self.form.addRow("鼠标按钮", self.button_combo)
            self.form.addRow("状态", self.press_combo)
            self.form.addRow("执行前延迟", self.delay)
        elif action == "move":
            self.form.addRow("X", self.x_spin)
            self.form.addRow("Y", self.y_spin)
            self.form.addRow("执行前延迟", self.delay)
        elif action == "scroll":
            self.form.addRow("X", self.x_spin)
            self.form.addRow("Y", self.y_spin)
            self.form.addRow("水平滚动", self.dx_spin)
            self.form.addRow("垂直滚动", self.dy_spin)
            self.form.addRow("执行前延迟", self.delay)
        elif action == "delay":
            self.form.addRow("等待时间", self.delay)

    def _accept(self):
        action = self.action_combo.currentData()
        delay = round(self.delay.value(), 3)

        if action == "key":
            key = self.key_edit.text().strip().lower()
            if not key:
                self.key_edit.setFocus()
                return
            self.events = [
                MacroEvent("key_down", delay, {"key": key}),
                MacroEvent("key_up", 0.0, {"key": key}),
            ]
        elif action == "click":
            data = {
                "x": self.x_spin.value(),
                "y": self.y_spin.value(),
                "button": self.button_combo.currentData() or self.button_combo.currentText(),
                "pressed": bool(self.press_combo.currentData()),
            }
            self.events = [MacroEvent("mouse_click", delay, data)]
        elif action == "move":
            self.events = [
                MacroEvent(
                    "mouse_move",
                    delay,
                    {"x": self.x_spin.value(), "y": self.y_spin.value()},
                )
            ]
        elif action == "scroll":
            self.events = [
                MacroEvent(
                    "mouse_scroll",
                    delay,
                    {
                        "x": self.x_spin.value(),
                        "y": self.y_spin.value(),
                        "dx": self.dx_spin.value(),
                        "dy": self.dy_spin.value(),
                    },
                )
            ]
        elif action == "delay":
            self.events = [MacroEvent("delay", delay, {})]

        self.accept()
