from __future__ import annotations

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QCursor, QGuiApplication, QPainter, QPen
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
        self._mouse_pos = QCursor.pos()
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
        self._mouse_pos = QCursor.pos()
        self._update_position_text(self._mouse_pos)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(Qt.GlobalColor.red, 2))
        pos = self.mapFromGlobal(self._mouse_pos)
        painter.drawLine(pos.x() - 16, pos.y(), pos.x() + 16, pos.y())
        painter.drawLine(pos.x(), pos.y() - 16, pos.x(), pos.y() + 16)
        painter.setPen(QPen(Qt.GlobalColor.white, 1))
        painter.drawEllipse(pos.x() - 4, pos.y() - 4, 8, 8)
        if self._selected:
            x, y = self._selected
            selected = self.mapFromGlobal(QPoint(x, y))
            painter.setPen(QPen(Qt.GlobalColor.green, 2))
            painter.drawEllipse(selected.x() - 7, selected.y() - 7, 14, 14)
            painter.drawText(selected.x() + 12, selected.y() - 12, f"({x}, {y})")
        painter.end()

    def mouseMoveEvent(self, event):
        self._mouse_pos = event.globalPosition().toPoint()
        self._update_position_text(self._mouse_pos)
        self.update()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            event.accept()
            return
        pos = event.globalPosition().toPoint()
        self._mouse_pos = pos
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
        for action, text in (("key", "键盘按键"), ("click", "设置鼠标点击"), ("move", "设置鼠标移动"), ("scroll", "设置滚轮"), ("delay", "添加等待")):
            button = QPushButton(f"＋ {text}")
            button.clicked.connect(lambda _, value=action: self.insert_action(value))
            toolbar.addWidget(button)
        toolbar.addStretch()
        root.addLayout(toolbar)

        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.list.setStyleSheet("QListWidget{background:white;border:1px solid #e4e7ed;border-radius:10px;padding:6px;}QListWidget::item{padding:10px 12px;}QListWidget::item:selected{background:#eaf2ff;color:#303133;}")
        self.list.itemDoubleClicked.connect(lambda _: self.edit_selected())
        root.addWidget(self.list, 1)

        edit_bar = QHBoxLayout()
        for text, slot in (("编辑", self.edit_selected), ("复制", self.duplicate_selected), ("上移", lambda: self.move_selected(-1)), ("下移", lambda: self.move_selected(1)), ("删除", self.delete_selected)):
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
        self._reload_list()

    def closeEvent(self, event):
        self.stop_preview()
        super().closeEvent(event)

    def _reload_list(self, selected: int = -1):
        self.list.clear()
        for index, event in enumerate(self.events):
            item = QListWidgetItem(self._event_text(index, event))
            self.list.addItem(item)
        if 0 <= selected < self.list.count():
            self.list.setCurrentRow(selected)

    def _event_text(self, index, event):
        d = event.data
        detail = ""
        if event.type == "key":
            detail = f"：{d.get('key', '')} {d.get('action', '')}"
        elif event.type == "mouse_move":
            detail = f"：({d.get('x')}, {d.get('y')})"
        elif event.type == "mouse_click":
            detail = f"：{d.get('button', 'left')} ({d.get('x')}, {d.get('y')}) {'按下' if d.get('pressed') else '释放'}"
        elif event.type == "mouse_scroll":
            detail = f"：({d.get('x')}, {d.get('y')}) dx={d.get('dx', 0)} dy={d.get('dy', 0)}"
        elif event.type == "delay":
            detail = ""
        return f"{index + 1:03d}  {event.type}{detail}    延迟 {event.delay:.3f}s"

    def insert_action(self, action):
        if action == "key":
            dialog = __import__('ui.action_dialog', fromlist=['ActionDialog']).ActionDialog('key', self)
        elif action == "delay":
            dialog = __import__('ui.action_dialog', fromlist=['ActionDialog']).ActionDialog('delay', self)
        else:
            dialog = MouseActionDialog(action, self)
        if not dialog.exec():
            return
        row = self.list.currentRow() + 1
        self.events[row:row] = dialog.events
        self._reload_list(row)

    def edit_selected(self):
        row = self.list.currentRow()
        if row < 0 or row >= len(self.events):
            return
        event = self.events[row]
        dialog = EventEditorDialog(event, self)
        if dialog.exec():
            self.events[row] = dialog.event
            self._reload_list(row)

    def duplicate_selected(self):
        row = self.list.currentRow()
        if row < 0:
            return
        event = self.events[row]
        self.events.insert(row + 1, MacroEvent(event.type, event.delay, dict(event.data)))
        self._reload_list(row + 1)

    def move_selected(self, direction):
        row = self.list.currentRow()
        target = row + direction
        if row < 0 or target < 0 or target >= len(self.events):
            return
        self.events[row], self.events[target] = self.events[target], self.events[row]
        self._reload_list(target)

    def delete_selected(self):
        row = self.list.currentRow()
        if row < 0:
            return
        self.events.pop(row)
        self._reload_list(min(row, len(self.events) - 1))

    def toggle_preview(self):
        if self._preview_running:
            self.stop_preview()
            return
        if not self.events:
            QMessageBox.information(self, "预览", "当前宏没有可预览的操作。")
            return
        self._preview_running = True
        self._preview_index = 0
        self.preview_button.setText("■ 停止预览")
        self._preview_overlay = ScreenPreviewOverlay()
        self._preview_overlay.show()
        self._preview_tick()

    def stop_preview(self):
        self._preview_timer.stop()
        self._preview_running = False
        self.preview_button.setText("▶ 桌面预览")
        if self._preview_overlay:
            self._preview_overlay.close()
            self._preview_overlay.deleteLater()
            self._preview_overlay = None

    def _preview_tick(self):
        if not self._preview_running or self._preview_index >= len(self.events):
            self.stop_preview()
            return
        event = self.events[self._preview_index]
        delay_ms = max(0, int(round(event.delay * 1000)))
        self._preview_timer.start(delay_ms)

    def _preview_timer_tick(self):
        if not self._preview_running or self._preview_index >= len(self.events):
            self.stop_preview()
            return
        event = self.events[self._preview_index]
        self._show_preview_event(event)
        self._preview_index += 1
        if self._preview_index < len(self.events):
            self._preview_timer.start(450)
        else:
            self._preview_timer.start(1000)

    def _show_preview_event(self, event):
        if not self._preview_overlay:
            return
        d = event.data
        cursor = None
        if event.type == "mouse_move":
            cursor = (int(d.get("x", 0)), int(d.get("y", 0)))
            title = "🖱 模拟鼠标移动"
            detail = f"位置：{cursor[0]}, {cursor[1]}"
        elif event.type == "mouse_click":
            cursor = (int(d.get("x", 0)), int(d.get("y", 0)))
            action = "按下" if d.get("pressed") else "释放"
            title = f"🖱 模拟鼠标{d.get('button', 'left')}键{action}"
            detail = f"位置：{cursor[0]}, {cursor[1]}"
        elif event.type == "mouse_scroll":
            cursor = (int(d.get("x", 0)), int(d.get("y", 0)))
            title = "🖱 模拟鼠标滚轮"
            detail = f"位置：{cursor[0]}, {cursor[1]}  水平：{d.get('dx', 0)}  垂直：{d.get('dy', 0)}"
        elif event.type == "key":
            key = d.get("key", "")
            title = f"⌨ 模拟按键：{key}"
            detail = f"操作：{d.get('action', '')}"
        else:
            title = "⏱ 模拟等待"
            detail = f"等待：{event.delay:.3f} 秒"
        self._preview_overlay.set_action(title, detail, cursor)
