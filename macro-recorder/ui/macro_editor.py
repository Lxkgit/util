from __future__ import annotations

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.model import MacroEvent
from ui.event_editor import EventEditorDialog


class PointPicker(QDialog):
    """只捕获屏幕坐标，不向目标窗口发送任何鼠标操作。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.point: tuple[int, int] | None = None
        self._selected: tuple[int, int] | None = None
        self._screen_geometry = QGuiApplication.primaryScreen().geometry() if QGuiApplication.primaryScreen() else QRect(0, 0, 1920, 1080)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setGeometry(self._screen_geometry)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._build_ui()

    def _build_ui(self):
        self.info = QLabel(self)
        self.info.setText("移动鼠标选择位置 · 左键选择 · Enter 确认 · Esc 取消")
        self.info.setStyleSheet(
            "QLabel{background:rgba(20,24,32,225);color:white;padding:10px 16px;"
            "border-radius:8px;font-size:15px;font-weight:600;}"
        )
        self.info.adjustSize()
        self.info.move(24, 24)

        self.confirm = QPushButton("确认此位置", self)
        self.confirm.setStyleSheet(
            "QPushButton{background:#409eff;color:white;border:0;border-radius:7px;"
            "padding:9px 16px;font-weight:600;}"
            "QPushButton:disabled{background:#909399;}"
        )
        self.confirm.setEnabled(False)
        self.confirm.clicked.connect(self._confirm)
        self.confirm.adjustSize()
        self.confirm.move(24, 74)

        self.cancel = QPushButton("取消", self)
        self.cancel.setStyleSheet(
            "QPushButton{background:rgba(255,255,255,235);color:#303133;"
            "border:1px solid #dcdfe6;border-radius:7px;padding:9px 16px;}"
        )
        self.cancel.clicked.connect(self.reject)
        self.cancel.adjustSize()
        self.cancel.move(24 + self.confirm.width() + 8, 74)

    def showEvent(self, event):
        super().showEvent(event)
        self._selected = None
        self.point = None
        self.confirm.setEnabled(False)
        self._update_position_text(self.mapFromGlobal(QGuiApplication.primaryScreen().availableGeometry().center()))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setPen(QPen(Qt.GlobalColor.red, 2))
        pos = self.mapFromGlobal(QGuiApplication.cursor().pos())
        painter.drawLine(pos.x() - 16, pos.y(), pos.x() + 16, pos.y())
        painter.drawLine(pos.x(), pos.y() - 16, pos.x(), pos.y() + 16)
        painter.setPen(QPen(Qt.GlobalColor.white, 1))
        painter.drawEllipse(pos.x() - 4, pos.y() - 4, 8, 8)
        if self._selected:
            x, y = self._selected
            selected = self.mapFromGlobal(QGuiApplication.cursor().pos())
            painter.setPen(QPen(Qt.GlobalColor.green, 2))
            painter.drawEllipse(selected.x() - 7, selected.y() - 7, 14, 14)
            painter.drawText(selected.x() + 12, selected.y() - 12, f"({x}, {y})")
        painter.end()

    def mouseMoveEvent(self, event):
        pos = event.globalPosition().toPoint()
        self._update_position_text(pos)
        self.update()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.globalPosition().toPoint()
        self._selected = (pos.x(), pos.y())
        self._update_position_text(pos, selected=True)
        self.confirm.setEnabled(True)
        self.update()
        event.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self._selected:
            self._confirm()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)

    def _update_position_text(self, pos, selected=False):
        if selected:
            self.info.setText(f"已选择：X={pos.x()}  Y={pos.y()} · Enter 确认 · 重新点击可重新选择")
        else:
            self.info.setText(f"当前：X={pos.x()}  Y={pos.y()} · 左键选择 · Esc 取消")
        self.info.adjustSize()

    def _confirm(self):
        if not self._selected:
            return
        self.point = self._selected
        self.accept()


class MouseActionDialog(QDialog):
    def __init__(self, action: str, parent=None):
        super().__init__(parent)
        self.action = action
        self.events: list[MacroEvent] = []
        self.point: tuple[int, int] | None = None
        titles = {"click": "设置鼠标点击", "move": "设置鼠标移动", "scroll": "设置滚轮"}
        self.setWindowTitle(titles[action])
        self.resize(460, 300)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)
        hint = QLabel("设置参数后选择屏幕位置。选点只记录坐标，不会点击目标窗口。")
        hint.setWordWrap(True)
        root.addWidget(hint)

        form = QFormLayout()
        self.delay = QDoubleSpinBox()
        self.delay.setRange(0, 999999)
        self.delay.setDecimals(3)
        self.delay.setSingleStep(0.01)
        self.delay.setSuffix(" 秒")
        self.delay.setValue(0)
        form.addRow("执行前延迟", self.delay)

        self.button = QComboBox()
        self.button.addItems(["left", "right", "middle"])
        if action == "click":
            form.addRow("鼠标按钮", self.button)

        self.dx = QSpinBox()
        self.dx.setRange(-99999, 99999)
        self.dy = QSpinBox()
        self.dy.setRange(-99999, 99999)
        if action == "scroll":
            form.addRow("水平滚动", self.dx)
            form.addRow("垂直滚动", self.dy)
        root.addLayout(form)

        self.position_label = QLabel("位置：尚未选择")
        self.position_label.setStyleSheet("font-weight:700;color:#303133;")
        root.addWidget(self.position_label)

        pick = QPushButton("🎯 选择位置")
        pick.setMinimumHeight(40)
        pick.clicked.connect(self.pick_position)
        root.addWidget(pick)

        buttons = QHBoxLayout()
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        confirm = QPushButton("确认添加")
        confirm.clicked.connect(self.confirm)
        buttons.addWidget(cancel)
        buttons.addStretch()
        buttons.addWidget(confirm)
        root.addLayout(buttons)

    def pick_position(self):
        picker = PointPicker(self)
        if picker.exec() and picker.point:
            self.point = picker.point
            self.position_label.setText(f"位置：X={picker.point[0]}，Y={picker.point[1]}（已确认）")
            self.raise_()
            self.activateWindow()

    def confirm(self):
        if not self.point:
            QMessageBox.warning(self, "提示", "请先选择并确认一个屏幕位置。")
            return
        x, y = self.point
        delay = round(self.delay.value(), 3)
        if self.action == "click":
            data = {"x": x, "y": y, "button": self.button.currentText()}
            self.events = [
                MacroEvent("mouse_click", delay, {**data, "pressed": True}),
                MacroEvent("mouse_click", 0.0, {**data, "pressed": False}),
            ]
        elif self.action == "move":
            self.events = [MacroEvent("mouse_move", delay, {"x": x, "y": y})]
        else:
            self.events = [
                MacroEvent(
                    "mouse_scroll",
                    delay,
                    {"x": x, "y": y, "dx": self.dx.value(), "dy": self.dy.value()},
                )
            ]
        self.accept()


class ScreenPreviewOverlay(QWidget):
    """覆盖真实桌面，仅绘制模拟光标和操作提示，不接收鼠标事件。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._geometry = QGuiApplication.screens()[0].geometry() if QGuiApplication.screens() else QRect(0, 0, 1920, 1080)
        for screen in QGuiApplication.screens():
            self._geometry = self._geometry.united(screen.geometry())
        self._cursor_pos: tuple[int, int] | None = None
        self._title = "安全预览"
        self._detail = ""
        self._warning = "不会执行任何真实键盘或鼠标操作"
        self.setGeometry(self._geometry)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

    def set_action(self, title: str, detail: str, cursor_pos: tuple[int, int] | None = None):
        self._title = title
        self._detail = detail
        if cursor_pos is not None:
            self._cursor_pos = cursor_pos
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        panel = self.rect().adjusted(24, 24, -24, -24)
        panel.setHeight(128)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(Qt.GlobalColor.transparent)
        painter.drawRoundedRect(panel, 12, 12)

        painter.setPen(Qt.GlobalColor.white)
        painter.setBrush(Qt.GlobalColor.black)
        painter.setOpacity(0.88)
        painter.drawRoundedRect(panel, 12, 12)
        painter.setOpacity(1.0)

        painter.setPen(Qt.GlobalColor.white)
        font = painter.font()
        font.setPointSize(18)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(panel.adjusted(20, 16, -20, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self._title)

        font.setPointSize(14)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(panel.adjusted(20, 50, -20, -36), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self._detail)

        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(Qt.GlobalColor.yellow)
        painter.drawText(panel.adjusted(20, -24, -20, -12), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, self._warning)

        if self._cursor_pos is not None:
            x, y = self._cursor_pos
            px = x - self._geometry.left()
            py = y - self._geometry.top()
            painter.setPen(QPen(Qt.GlobalColor.red, 3))
            painter.drawLine(px - 18, py, px + 18, py)
            painter.drawLine(px, py - 18, px, py + 18)
            painter.setPen(QPen(Qt.GlobalColor.white, 2))
            painter.drawEllipse(px - 8, py - 8, 16, 16)

        painter.end()


class MacroEditorDialog(QDialog):
    def __init__(self, events: list[MacroEvent], parent=None):
        super().__init__(parent)
        self.setWindowTitle("宏编辑器")
        self.resize(1080, 760)
        self.events = [MacroEvent(e.type, e.delay, dict(e.data)) for e in events]
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._preview_timer_tick)
        self._preview_index = 0
        self._preview_running = False
        self._preview_overlay: ScreenPreviewOverlay | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(12)

        head = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("宏编辑器")
        title.setStyleSheet("font-size:24px;font-weight:700;")
        subtitle = QLabel("键盘可以直接添加；鼠标操作通过全屏选点确定位置。")
        subtitle.setStyleSheet("color:#7a8491;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        head.addLayout(title_box, 1)
        self.preview_button = QPushButton("▶ 桌面预览")
        self.preview_button.clicked.connect(self.toggle_preview)
        head.addWidget(self.preview_button)
        root.addLayout(head)

        toolbar = QHBoxLayout()
        for action, text in (
            ("key", "键盘按键"),
            ("click", "设置鼠标点击"),
            ("move", "设置鼠标移动"),
            ("scroll", "设置滚轮"),
            ("delay", "添加等待"),
        ):
            button = QPushButton(f"＋ {text}")
            button.clicked.connect(lambda _, value=action: self.insert_action(value))
            toolbar.addWidget(button)
        toolbar.addStretch()
        root.addLayout(toolbar)

        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.list.setStyleSheet(
            "QListWidget{background:white;border:1px solid #e4e7ed;border-radius:10px;padding:6px;}"
            "QListWidget::item{padding:10px 12px;}"
            "QListWidget::item:selected{background:#eaf2ff;color:#303133;}"
        )
        self.list.itemDoubleClicked.connect(lambda _: self.edit_selected())
        root.addWidget(self.list, 1)

        edit_bar = QHBoxLayout()
        for text, slot in (
            ("编辑", self.edit_selected),
            ("复制", self.duplicate_selected),
            ("上移", lambda: self.move_selected(-1)),
            ("下移", lambda: self.move_selected(1)),
            ("删除", self.delete_selected),
        ):
            button = QPushButton(text)
            button.clicked.connect(slot)
            edit_bar.addWidget(button)
        edit_bar.addStretch()
        root.addLayout(edit_bar)

        bottom = QHBoxLayout()
        self.preview_hint = QLabel("⚠ 桌面预览只显示虚拟光标和操作提示，不会移动鼠标、点击或发送按键。")
        self.preview_hint.setStyleSheet("color:#606266;")
        bottom.addWidget(self.preview_hint, 1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        save = QPushButton("保存修改")
        save.clicked.connect(self.accept)
        bottom.addWidget(cancel)
        bottom.addWidget(save)
        root.addLayout(bottom)
        self._refresh_list()

    @staticmethod
    def format_event(event: MacroEvent) -> str:
        data = event.data
        if event.type == "key_down":
            return f"键盘：按下 {data.get('key')}    延迟 {event.delay:.3f}s"
        if event.type == "key_up":
            return f"键盘：释放 {data.get('key')}    延迟 {event.delay:.3f}s"
        if event.type == "mouse_move":
            return f"鼠标：移动到 ({data.get('x')}, {data.get('y')})    延迟 {event.delay:.3f}s"
        if event.type == "mouse_click":
            state = "按下" if data.get("pressed") else "释放"
            return f"鼠标：{data.get('button')} {state} @ ({data.get('x')}, {data.get('y')})    延迟 {event.delay:.3f}s"
        if event.type == "mouse_scroll":
            return f"鼠标：滚轮 ({data.get('dx')}, {data.get('dy')}) @ ({data.get('x')}, {data.get('y')})    延迟 {event.delay:.3f}s"
        if event.type == "delay":
            return f"等待：{event.delay:.3f} 秒"
        return str(event)

    def _refresh_list(self, selected: int = -1):
        self.list.clear()
        for index, event in enumerate(self.events):
            item = QListWidgetItem(f"{index + 1:03d}   {self.format_event(event)}")
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.list.addItem(item)
        if 0 <= selected < self.list.count():
            self.list.setCurrentRow(selected)

    def _selected_index(self) -> int:
        item = self.list.currentItem()
        return int(item.data(Qt.ItemDataRole.UserRole)) if item else -1

    def insert_action(self, action: str):
        if self._preview_running:
            return
        if action == "key":
            from ui.action_dialog import ActionInsertDialog
            dialog = ActionInsertDialog("key", self)
        elif action == "delay":
            from ui.action_dialog import ActionInsertDialog
            dialog = ActionInsertDialog("delay", self)
        else:
            dialog = MouseActionDialog(action, self)
        if not dialog.exec() or not dialog.events:
            return
        index = self._selected_index()
        insert_at = index + 1 if index >= 0 else len(self.events)
        self.events[insert_at:insert_at] = dialog.events
        self._refresh_list(insert_at)

    def edit_selected(self):
        index = self._selected_index()
        if index < 0 or self._preview_running:
            return
        event = self.events[index]
        if event.type != "delay":
            QMessageBox.information(self, "提示", "当前版本暂时只支持直接编辑等待时间，鼠标位置请重新设置。")
            return
        dialog = EventEditorDialog(event, self)
        if dialog.exec():
            self.events[index] = dialog.event
            self._refresh_list(index)

    def duplicate_selected(self):
        index = self._selected_index()
        if index < 0 or self._preview_running:
            return
        event = self.events[index]
        self.events.insert(index + 1, MacroEvent(event.type, event.delay, dict(event.data)))
        self._refresh_list(index + 1)

    def move_selected(self, offset: int):
        index = self._selected_index()
        target = index + offset
        if index < 0 or target < 0 or target >= len(self.events) or self._preview_running:
            return
        self.events[index], self.events[target] = self.events[target], self.events[index]
        self._refresh_list(target)

    def delete_selected(self):
        index = self._selected_index()
        if index < 0 or self._preview_running:
            return
        del self.events[index]
        self._refresh_list(min(index, len(self.events) - 1))

    def toggle_preview(self):
        if self._preview_running:
            self.stop_preview()
            return
        if not self.events:
            QMessageBox.information(self, "预览", "当前宏没有操作。")
            return
        self._preview_running = True
        self._preview_index = 0
        self._preview_overlay = ScreenPreviewOverlay()
        self._preview_overlay.show()
        self._preview_overlay.raise_()
        self.preview_button.setText("■ 停止桌面预览")
        self.preview_hint.setText("正在桌面上安全预览：只显示模拟动作，不执行任何真实操作。")
        self._preview_tick()

    def stop_preview(self):
        self._preview_timer.stop()
        self._preview_running = False
        if self._preview_overlay is not None:
            self._preview_overlay.close()
            self._preview_overlay.deleteLater()
            self._preview_overlay = None
        self.preview_button.setText("▶ 桌面预览")
        self.preview_hint.setText("⚠ 桌面预览只显示虚拟光标和操作提示，不会移动鼠标、点击或发送按键。")

    def _preview_tick(self):
        if not self._preview_running:
            return
        if self._preview_index >= len(self.events):
            self.stop_preview()
            return

        event = self.events[self._preview_index]
        self.list.setCurrentRow(self._preview_index)
        delay_ms = max(0, int(event.delay * 1000))
        if delay_ms > 0:
            self._preview_timer.start(delay_ms)
            if self._preview_overlay:
                self._preview_overlay.set_action(
                    f"第 {self._preview_index + 1}/{len(self.events)} 步 · 等待",
                    f"等待 {event.delay:.3f} 秒后模拟：{self._event_summary(event)}",
                )
            return
        self._apply_preview_event(event)
        self._preview_index += 1
        QTimer.singleShot(0, self._preview_tick)

    def _preview_timer_tick(self):
        if not self._preview_running or self._preview_index >= len(self.events):
            return
        self._apply_preview_event(self.events[self._preview_index])
        self._preview_index += 1
        QTimer.singleShot(0, self._preview_tick)

    @staticmethod
    def _event_summary(event: MacroEvent) -> str:
        data = event.data
        if event.type == "key_down":
            return f"按下 {data.get('key')}"
        if event.type == "key_up":
            return f"释放 {data.get('key')}"
        if event.type == "mouse_move":
            return f"移动到 ({data.get('x')}, {data.get('y')})"
        if event.type == "mouse_click":
            state = "按下" if data.get('pressed') else "释放"
            return f"鼠标 {data.get('button')} 键{state} @ ({data.get('x')}, {data.get('y')})"
        if event.type == "mouse_scroll":
            return f"滚轮 ({data.get('dx', 0)}, {data.get('dy', 0)}) @ ({data.get('x')}, {data.get('y')})"
        if event.type == "delay":
            return f"等待 {event.delay:.3f} 秒"
        return event.type

    def _apply_preview_event(self, event: MacroEvent):
        if self._preview_overlay is None:
            return
        data = event.data
        if event.type == "key_down":
            key = data.get("key")
            self._preview_overlay.set_action(
                "⌨ 模拟键盘：按下",
                f"按键：{key}\n⚠ 不会真的发送 {key}",
            )
        elif event.type == "key_up":
            key = data.get("key")
            self._preview_overlay.set_action(
                "⌨ 模拟键盘：释放",
                f"按键：{key}\n⚠ 不会真的发送 {key}",
            )
        elif event.type == "mouse_move":
            x, y = int(data.get("x", 0)), int(data.get("y", 0))
            self._preview_overlay.set_action(
                "🖱 模拟鼠标移动",
                f"位置：{x}, {y}\n⚠ 不会真的移动鼠标",
                (x, y),
            )
        elif event.type == "mouse_click":
            x, y = int(data.get("x", 0)), int(data.get("y", 0))
            button = data.get("button", "left")
            state = "按下" if data.get("pressed") else "释放"
            self._preview_overlay.set_action(
                f"🖱 模拟鼠标{button}键{state}",
                f"位置：{x}, {y}\n⚠ 不会真的点击",
                (x, y),
            )
        elif event.type == "mouse_scroll":
            x, y = int(data.get("x", 0)), int(data.get("y", 0))
            dx, dy = data.get("dx", 0), data.get("dy", 0)
            self._preview_overlay.set_action(
                "🖱 模拟鼠标滚轮",
                f"位置：{x}, {y}\n水平：{dx} · 垂直：{dy}\n⚠ 不会真的滚动",
                (x, y),
            )
        elif event.type == "delay":
            self._preview_overlay.set_action(
                "⏱ 模拟等待",
                f"等待：{event.delay:.3f} 秒\n⚠ 预览不会执行任何真实操作",
            )

    def reject(self):
        self.stop_preview()
        super().reject()

    def accept(self):
        self.stop_preview()
        super().accept()
