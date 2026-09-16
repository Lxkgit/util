from __future__ import annotations

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QCursor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSpinBox,
    QVBoxLayout, QWidget,
)

from core.model import MacroEvent
from ui.event_editor import EventEditorDialog
from ui.action_dialog import ActionDialog


class PointPreviewOverlay(QWidget):
    """只预览一个已记录的屏幕坐标，不接收任何真实输入。"""

    def __init__(self, point: tuple[int, int], parent=None):
        super().__init__(parent)
        screens = QGuiApplication.screens()
        geometry = screens[0].geometry() if screens else QRect(0, 0, 1920, 1080)
        for screen in screens[1:]:
            geometry = geometry.united(screen.geometry())
        self.geometry_rect = geometry
        self.point = point
        self.setGeometry(geometry)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.close)

    def show_for(self, ms=1800):
        self.show()
        self.raise_()
        self.timer.start(ms)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        x, y = self.point
        px, py = x - self.geometry_rect.left(), y - self.geometry_rect.top()
        painter.setPen(QPen(Qt.GlobalColor.red, 3))
        painter.drawLine(px - 14, py, px + 14, py)
        painter.drawLine(px, py - 14, px, py + 14)
        painter.setPen(QPen(Qt.GlobalColor.white, 2))
        painter.drawEllipse(px - 6, py - 6, 12, 12)
        label = QRect(px + 16, py - 38, 180, 32)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(Qt.GlobalColor.black)
        painter.setOpacity(0.85)
        painter.drawRoundedRect(label, 6, 6)
        painter.setOpacity(1)
        painter.setPen(Qt.GlobalColor.white)
        painter.drawText(label, Qt.AlignmentFlag.AlignCenter, f"预览位置：{x}, {y}")
        painter.end()


class PointPicker(QDialog):
    """全屏选点。左键可反复选择，确认时提交最后一次点击的位置。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.point: tuple[int, int] | None = None
        self._mouse_pos = QCursor.pos()
        screens = QGuiApplication.screens()
        geometry = screens[0].geometry() if screens else QRect(0, 0, 1920, 1080)
        for screen in screens[1:]:
            geometry = geometry.united(screen.geometry())
        self._screen_geometry = geometry
        self.setGeometry(geometry)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self.info = QLabel(self)
        self.info.setStyleSheet(
            "QLabel{background:rgba(20,24,32,235);color:white;"
            "padding:9px 14px;border-radius:8px;font-size:14px;font-weight:600;}"
        )
        self.info.move(24, 24)
        self._update_position_text(self._mouse_pos)

        self.confirm = QPushButton("确认此位置", self)
        self.confirm.setStyleSheet(
            "QPushButton{background:#409eff;color:white;border:0;"
            "border-radius:7px;padding:8px 15px;font-weight:600;}"
        )
        self.confirm.clicked.connect(self._confirm)
        self.confirm.move(24, 70)
        self.confirm.setEnabled(False)

        self.cancel = QPushButton("取消", self)
        self.cancel.clicked.connect(self.reject)
        self.cancel.move(128, 70)

    def showEvent(self, event):
        super().showEvent(event)
        self._mouse_pos = QCursor.pos()
        self._update_position_text(self._mouse_pos)
        self.update()
        QTimer.singleShot(0, self._activate_picker)

    def _activate_picker(self):
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self.grabMouse()
        self.grabKeyboard()

    def closeEvent(self, event):
        self.releaseMouse()
        self.releaseKeyboard()
        super().closeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        pos = self.mapFromGlobal(self._mouse_pos)
        painter.setPen(QPen(Qt.GlobalColor.red, 2))
        painter.drawLine(pos.x() - 11, pos.y(), pos.x() + 11, pos.y())
        painter.drawLine(pos.x(), pos.y() - 11, pos.x(), pos.y() + 11)
        painter.setPen(QPen(Qt.GlobalColor.white, 1))
        painter.drawEllipse(pos.x() - 3, pos.y() - 3, 6, 6)
        painter.end()

    def mouseMoveEvent(self, event):
        self._mouse_pos = event.globalPosition().toPoint()
        self._update_position_text(self._mouse_pos)
        self.update()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.globalPosition().toPoint()
            self.point = (pos.x(), pos.y())
            self._mouse_pos = pos
            self._update_position_text(pos, True)
            self.confirm.setEnabled(True)
            self.update()
            event.accept()
            return
        event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.point is not None:
            self._confirm()
        else:
            super().keyPressEvent(event)

    def _update_position_text(self, pos, selected=False):
        self.info.setText(
            f"{'已选择' if selected else '当前'}：X={pos.x()}  Y={pos.y()} · "
            "左键选择 · Enter 确认 · Esc 取消"
        )
        self.info.adjustSize()

    def _confirm(self):
        if self.point is None:
            return
        self.accept()


class MouseActionDialog(QDialog):
    def __init__(self, action: str, parent=None):
        super().__init__(parent)
        self.action = action
        self.events = []
        self.point: tuple[int, int] | None = None
        self.point_preview = None
        self.setWindowTitle({"click": "设置鼠标点击", "move": "设置鼠标移动", "scroll": "设置滚轮"}[action])
        self.resize(470, 320)
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
        actions = QHBoxLayout()
        pick = QPushButton("🎯 选择位置")
        pick.clicked.connect(self.pick_position)
        actions.addWidget(pick)
        self.preview_position_button = QPushButton("👁 预览位置")
        self.preview_position_button.setEnabled(False)
        self.preview_position_button.clicked.connect(self.preview_position)
        actions.addWidget(self.preview_position_button)
        actions.addStretch()
        root.addLayout(actions)
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
        if picker.exec() == QDialog.DialogCode.Accepted and picker.point is not None:
            x, y = picker.point
            self.point = (x, y)
            self.position_label.setText(f"位置：X={x}，Y={y}（已确认）")
            self.preview_position_button.setEnabled(True)
            self.raise_()
            self.activateWindow()

    def preview_position(self):
        point = self.point
        if point is None:
            return
        if self.point_preview:
            self.point_preview.close()
            self.point_preview.deleteLater()
        self.point_preview = PointPreviewOverlay(point)
        self.point_preview.show_for()

    def confirm(self):
        if self.point is None:
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

    def closeEvent(self, event):
        if self.point_preview:
            self.point_preview.close()
        super().closeEvent(event)


class ScreenPreviewOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        screens = QGuiApplication.screens()
        self._geometry = screens[0].geometry() if screens else QRect(0, 0, 1920, 1080)
        for screen in screens[1:]:
            self._geometry = self._geometry.united(screen.geometry())
        self._cursor_pos = None
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

    def set_action(self, title, detail, cursor_pos=None):
        self._title = title
        self._detail = detail
        self._cursor_pos = cursor_pos if cursor_pos is not None else self._cursor_pos
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        panel = self.rect().adjusted(24, 24, -24, -24)
        panel.setHeight(128)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(Qt.GlobalColor.black)
        painter.setOpacity(.88)
        painter.drawRoundedRect(panel, 12, 12)
        painter.setOpacity(1)
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
        if self._cursor_pos:
            x, y = self._cursor_pos
            px, py = x - self._geometry.left(), y - self._geometry.top()
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
        self._preview_overlay = None
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
        self.list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list.setStyleSheet(
            "QListWidget{background:white;border:1px solid #e4e7ed;border-radius:10px;padding:6px;}"
            "QListWidget::item{padding:10px 12px;border-radius:6px;}"
            "QListWidget::item:selected{background:#ecf5ff;color:#1f2d3d;}"
        )
        self.list.itemDoubleClicked.connect(lambda _: self.edit_selected())
        root.addWidget(self.list, 1)
        bottom = QHBoxLayout()
        for text, slot in (
            ("编辑", self.edit_selected),
            ("复制", self.copy_selected),
            ("上移", self.move_up),
            ("下移", self.move_down),
            ("删除", self.delete_selected),
            ("批量删除", self.batch_delete),
            ("清空", self.clear_all),
        ):
            button = QPushButton(text)
            button.clicked.connect(slot)
            bottom.addWidget(button)
        bottom.addStretch()
        root.addLayout(bottom)
        self._refresh()

    def _describe(self, event: MacroEvent):
        d = event.data
        delay = f"延迟 {event.delay:.3f}s"
        if event.type == "key_down":
            return f"按下键：{d.get('key')}    {delay}"
        if event.type == "key_up":
            return f"释放键：{d.get('key')}    {delay}"
        if event.type == "mouse_move":
            return f"鼠标移动：({d.get('x')}, {d.get('y')})    {delay}"
        if event.type == "mouse_click":
            state = "按下" if d.get("pressed") else "释放"
            return f"鼠标{d.get('button', 'left')} {state}：({d.get('x')}, {d.get('y')})    {delay}"
        if event.type == "mouse_scroll":
            return f"鼠标滚轮：({d.get('x')}, {d.get('y')}) Δ({d.get('dx')}, {d.get('dy')})    {delay}"
        if event.type == "delay":
            return f"等待：{event.delay:.3f}s"
        return f"{event.type}    {delay}"

    def _refresh(self):
        self.list.clear()
        for index, event in enumerate(self.events, 1):
            item = QListWidgetItem(f"{index:03d}  {self._describe(event)}")
            self.list.addItem(item)

    def _selected_rows(self):
        return sorted({self.list.row(item) for item in self.list.selectedItems()})

    def insert_action(self, action):
        if action == "key":
            dialog = ActionDialog("key", self)
        elif action == "delay":
            dialog = ActionDialog("delay", self)
        else:
            dialog = ActionDialog(action, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.events:
            rows = self._selected_rows()
            insert_at = rows[-1] + 1 if rows else len(self.events)
            self.events[insert_at:insert_at] = dialog.events
            self._refresh()
            self.list.setCurrentRow(insert_at)

    def edit_selected(self):
        rows = self._selected_rows()
        if len(rows) != 1:
            return
        row = rows[0]
        dialog = EventEditorDialog(self.events[row], self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.event:
            self.events[row] = dialog.event
            self._refresh()
            self.list.setCurrentRow(row)

    def copy_selected(self):
        rows = self._selected_rows()
        if not rows:
            return
        copied = [MacroEvent(self.events[row].type, self.events[row].delay, dict(self.events[row].data)) for row in rows]
        insert_at = rows[-1] + 1
        self.events[insert_at:insert_at] = copied
        self._refresh()

    def move_up(self):
        rows = self._selected_rows()
        if not rows or rows[0] == 0:
            return
        selected = [self.events[row] for row in rows]
        for row in reversed(rows):
            self.events[row - 1], self.events[row] = self.events[row], self.events[row - 1]
        self._refresh()
        for row in [r - 1 for r in rows]:
            self.list.item(row).setSelected(True)

    def move_down(self):
        rows = self._selected_rows()
        if not rows or rows[-1] >= len(self.events) - 1:
            return
        for row in reversed(rows):
            self.events[row + 1], self.events[row] = self.events[row], self.events[row + 1]
        self._refresh()
        for row in [r + 1 for r in rows]:
            self.list.item(row).setSelected(True)

    def delete_selected(self):
        rows = self._selected_rows()
        if len(rows) != 1:
            return
        row = rows[0]
        self.events.pop(row)
        self._refresh()
        if self.events:
            self.list.setCurrentRow(min(row, len(self.events) - 1))

    def batch_delete(self):
        rows = self._selected_rows()
        if not rows:
            return
        if QMessageBox.question(self, "确认删除", f"确定删除选中的 {len(rows)} 个操作吗？") != QMessageBox.StandardButton.Yes:
            return
        for row in reversed(rows):
            self.events.pop(row)
        self._refresh()

    def clear_all(self):
        if not self.events:
            return
        if QMessageBox.question(self, "确认清空", "确定清空全部宏操作吗？") != QMessageBox.StandardButton.Yes:
            return
        self.events.clear()
        self._refresh()

    def toggle_preview(self):
        if self._preview_running:
            self._stop_preview()
            return
        if not self.events:
            QMessageBox.information(self, "提示", "当前没有可预览的宏操作。")
            return
        self._preview_running = True
        self._preview_index = 0
        self.preview_button.setText("■ 停止预览")
        self._preview_overlay = ScreenPreviewOverlay()
        self._preview_tick()

    def _preview_tick(self):
        if not self._preview_running:
            return
        if self._preview_index >= len(self.events):
            self._preview_timer.start(700)
            self._preview_running = False
            self.preview_button.setText("▶ 桌面预览")
            return
        event = self.events[self._preview_index]
        delay = max(0.0, float(event.delay))
        self._preview_timer.start(max(1, int(delay * 1000)))

    def _preview_timer_tick(self):
        if not self._preview_running:
            return
        if self._preview_index >= len(self.events):
            self._stop_preview()
            return
        event = self.events[self._preview_index]
        title = "模拟操作"
        detail = self._describe(event)
        cursor = None
        if event.type == "key_down":
            title = f"模拟按键：{event.data.get('key')}"
            detail = "不会真的按下键盘"
        elif event.type == "key_up":
            title = f"模拟释放：{event.data.get('key')}"
            detail = "不会真的释放键盘"
        elif event.type == "mouse_click":
            title = f"模拟鼠标{event.data.get('button', 'left')} {'按下' if event.data.get('pressed') else '释放'}"
            detail = f"位置：{event.data.get('x')}, {event.data.get('y')}"
            cursor = (event.data.get('x'), event.data.get('y'))
        elif event.type == "mouse_move":
            title = "模拟鼠标移动"
            detail = f"位置：{event.data.get('x')}, {event.data.get('y')}"
            cursor = (event.data.get('x'), event.data.get('y'))
        elif event.type == "mouse_scroll":
            title = "模拟鼠标滚轮"
            detail = f"位置：{event.data.get('x')}, {event.data.get('y')}  Δ({event.data.get('dx')}, {event.data.get('dy')})"
            cursor = (event.data.get('x'), event.data.get('y'))
        elif event.type == "delay":
            title = "模拟等待"
            detail = f"等待 {event.delay:.3f} 秒"
        self._preview_overlay.set_action(title, detail, cursor)
        if not self._preview_overlay.isVisible():
            self._preview_overlay.show()
            self._preview_overlay.raise_()
        self._preview_index += 1
        if self._preview_index < len(self.events):
            next_delay = max(0.0, float(self.events[self._preview_index].delay))
            self._preview_timer.start(max(1, int(next_delay * 1000)))
        else:
            self._preview_timer.start(700)
            self._preview_running = False
            self.preview_button.setText("▶ 桌面预览")

    def _stop_preview(self):
        self._preview_timer.stop()
        self._preview_running = False
        self.preview_button.setText("▶ 桌面预览")
        if self._preview_overlay:
            self._preview_overlay.close()
            self._preview_overlay.deleteLater()
            self._preview_overlay = None

    def closeEvent(self, event):
        self._stop_preview()
        super().closeEvent(event)
