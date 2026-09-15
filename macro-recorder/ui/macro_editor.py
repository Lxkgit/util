from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, QRect
from PySide6.QtGui import QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from core.model import MacroEvent
from ui.event_editor import EventEditorDialog


class PointPicker(QDialog):
    """全屏鼠标选点，只记录坐标，不执行任何鼠标操作。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.point: tuple[int, int] | None = None
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        screen = QGuiApplication.primaryScreen()
        self._screen_geometry = screen.geometry() if screen else QRect(0, 0, 1920, 1080)
        self.setGeometry(self._screen_geometry)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setPen(QPen(Qt.GlobalColor.red, 2))
        center = self.mapFromGlobal(self.cursor().pos())
        painter.drawLine(center.x() - 14, center.y(), center.x() + 14, center.y())
        painter.drawLine(center.x(), center.y() - 14, center.x(), center.y() + 14)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.globalPosition().toPoint()
        self.hide()
        answer = QMessageBox.question(
            self,
            "确认位置",
            f"当前选择的位置是：\nX = {pos.x()}\nY = {pos.y()}\n\n确认使用这个位置吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.point = (pos.x(), pos.y())
            self.accept()
        else:
            self.show()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)


class MouseActionDialog(QDialog):
    def __init__(self, action: str, parent=None):
        super().__init__(parent)
        self.action = action
        self.events: list[MacroEvent] = []
        self.point: tuple[int, int] | None = None
        self.setWindowTitle({"click": "设置鼠标点击", "move": "设置鼠标移动", "scroll": "设置滚轮"}[action])
        self.resize(460, 300)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)
        hint = QLabel(
            "先设置操作参数，然后点击“选择位置”。\n"
            "程序会进入全屏选点模式，你点击目标位置后会再次确认坐标。"
        )
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


class MacroEditorDialog(QDialog):
    def __init__(self, events: list[MacroEvent], parent=None):
        super().__init__(parent)
        self.setWindowTitle("宏编辑器")
        self.resize(1080, 760)
        self.events = [MacroEvent(e.type, e.delay, dict(e.data)) for e in events]
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._preview_tick)
        self._preview_index = 0
        self._preview_running = False

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
        self.preview_button = QPushButton("▶ 播放预览")
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

        body = QHBoxLayout()
        body.setSpacing(12)

        left = QVBoxLayout()
        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.list.setStyleSheet(
            "QListWidget{background:white;border:1px solid #e4e7ed;border-radius:10px;padding:6px;}"
            "QListWidget::item{padding:10px 12px;}"
            "QListWidget::item:selected{background:#eaf2ff;color:#303133;}"
        )
        self.list.itemDoubleClicked.connect(lambda _: self.edit_selected())
        left.addWidget(self.list, 1)

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
        left.addLayout(edit_bar)
        body.addLayout(left, 3)

        preview = QFrame()
        preview.setStyleSheet("QFrame{background:#f7f8fa;border:1px solid #e4e7ed;border-radius:12px;}")
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(14, 14, 14, 14)
        preview_layout.setSpacing(10)
        preview_title = QLabel("安全预览")
        preview_title.setStyleSheet("font-size:16px;font-weight:700;")
        preview_layout.addWidget(preview_title)
        self.preview_canvas = QFrame()
        self.preview_canvas.setMinimumSize(360, 300)
        self.preview_canvas.setStyleSheet("QFrame{background:#ffffff;border:1px solid #dcdfe6;border-radius:8px;}")
        preview_layout.addWidget(self.preview_canvas, 1)

        self.virtual_cursor = QLabel("●", self.preview_canvas)
        self.virtual_cursor.setStyleSheet("font-size:22px;color:#409eff;background:transparent;border:none;")
        self.virtual_cursor.adjustSize()
        self.virtual_cursor.hide()

        self.preview_action = QLabel("等待播放")
        self.preview_action.setWordWrap(True)
        self.preview_action.setStyleSheet("font-size:15px;font-weight:700;color:#303133;border:none;")
        preview_layout.addWidget(self.preview_action)
        self.preview_status = QLabel("预览不会真的移动鼠标、点击或发送键盘。")
        self.preview_status.setWordWrap(True)
        self.preview_status.setStyleSheet("color:#606266;border:none;")
        preview_layout.addWidget(self.preview_status)
        body.addWidget(preview, 2)
        root.addLayout(body, 1)

        bottom = QHBoxLayout()
        bottom.addWidget(QLabel("⚠ 预览只在右侧模拟执行效果，ESC、鼠标点击等都不会真正执行。"), 1)
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
            self.preview_status.setText("预览：没有操作")
            return
        self._preview_running = True
        self._preview_index = 0
        self.preview_button.setText("■ 停止预览")
        self.preview_status.setText("正在安全预览，不会执行真实操作")
        self.virtual_cursor.show()
        self._preview_tick()

    def stop_preview(self):
        self._preview_timer.stop()
        self._preview_running = False
        self.preview_button.setText("▶ 播放预览")
        self.preview_status.setText("预览：已停止，未执行任何真实操作")
        self.preview_action.setText("等待播放")
        self.list.clearSelection()

    def _preview_tick(self):
        if not self._preview_running:
            return
        if self._preview_index >= len(self.events):
            self._preview_running = False
            self.preview_button.setText("▶ 播放预览")
            self.preview_status.setText("预览完成：所有操作均为模拟，没有执行真实操作")
            self.preview_action.setText("播放完成")
            self.list.clearSelection()
            return

        index = self._preview_index
        event = self.events[index]
        self.list.setCurrentRow(index)
        self._apply_preview_event(event)
        self.preview_status.setText(f"预览 {index + 1}/{len(self.events)} · 延迟 {event.delay:.3f}s · 不执行真实操作")
        self._preview_index += 1
        delay_ms = max(80, int(max(event.delay, 0.08) * 1000))
        self._preview_timer.start(delay_ms)

    def _apply_preview_event(self, event: MacroEvent):
        data = event.data
        if event.type == "key_down":
            self.preview_action.setText(f"模拟键盘操作\n按下：{data.get('key')}\n\n不会真的发送按键")
        elif event.type == "key_up":
            self.preview_action.setText(f"模拟键盘操作\n释放：{data.get('key')}\n\n不会真的发送按键")
        elif event.type == "mouse_move":
            x, y = int(data.get("x", 0)), int(data.get("y", 0))
            self._move_virtual_cursor(x, y)
            self.preview_action.setText(f"模拟鼠标操作\n移动到：({x}, {y})\n\n不会真的移动鼠标")
        elif event.type == "mouse_click":
            x, y = int(data.get("x", 0)), int(data.get("y", 0))
            self._move_virtual_cursor(x, y)
            state = "按下" if data.get("pressed") else "释放"
            self.preview_action.setText(f"模拟鼠标操作\n{data.get('button')} 键：{state}\n位置：({x}, {y})\n\n不会真的点击")
        elif event.type == "mouse_scroll":
            x, y = int(data.get("x", 0)), int(data.get("y", 0))
            self._move_virtual_cursor(x, y)
            self.preview_action.setText(
                f"模拟滚轮操作\n位置：({x}, {y})\n滚动：水平 {data.get('dx', 0)}，垂直 {data.get('dy', 0)}\n\n不会真的滚动"
            )
        elif event.type == "delay":
            self.preview_action.setText(f"模拟等待\n{event.delay:.3f} 秒")
        else:
            self.preview_action.setText("模拟未知操作\n不会执行")

    def _move_virtual_cursor(self, x: int, y: int):
        screen = QGuiApplication.primaryScreen()
        geometry = screen.geometry() if screen else QRect(0, 0, 1920, 1080)
        w = max(1, self.preview_canvas.width() - self.virtual_cursor.width())
        h = max(1, self.preview_canvas.height() - self.virtual_cursor.height())
        px = int((x - geometry.left()) / max(1, geometry.width()) * w)
        py = int((y - geometry.top()) / max(1, geometry.height()) * h)
        self.virtual_cursor.move(max(0, min(w, px)), max(0, min(h, py)))

    def reject(self):
        self.stop_preview()
        super().reject()

    def accept(self):
        self.stop_preview()
        super().accept()
