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
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
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
    """全屏选点。鼠标移动显示十字光标，左键可反复选择，确认时使用最后一次点击的位置。"""

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
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self.info = QLabel(self)
        self.info.setStyleSheet("QLabel{background:rgba(20,24,32,235);color:white;padding:9px 14px;border-radius:8px;font-size:14px;font-weight:600;}")
        self.info.move(24, 24)
        self._update_position_text(self._mouse_pos)

        self.confirm = QPushButton("确认此位置", self)
        self.confirm.setStyleSheet("QPushButton{background:#409eff;color:white;border:0;border-radius:7px;padding:8px 15px;font-weight:600;}")
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
        self.info.setText(f"{'已选择' if selected else '当前'}：X={pos.x()}  Y={pos.y()} · 左键选择 · Enter 确认 · Esc 取消")
        self.info.adjustSize()

    def _confirm(self):
        if self.point is not None:
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
        pick = QPushButton("🎯 选择屏幕位置")
        pick.clicked.connect(self.pick_position)
        actions.addWidget(pick)
        self.preview_position_button = QPushButton("👁 预览点位")
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
        if self.point is None:
            return
        if self.point_preview:
            self.point_preview.close()
            self.point_preview.deleteLater()
        self.point_preview = PointPreviewOverlay(self.point)
        self.point_preview.show_for()

    def confirm(self):
        if self.point is None:
            QMessageBox.warning(self, "提示", "请先点击“选择屏幕位置”并确认坐标。")
            return
        x, y = self.point
        delay = round(self.delay.value(), 3)
        if self.action == "click":
            data = {"x": x, "y": y, "button": self.button.currentText()}
            self.events = [MacroEvent("mouse_click", delay, {**data, "pressed": True}), MacroEvent("mouse_click", 0.0, {**data, "pressed": False})]
        elif self.action == "move":
            self.events = [MacroEvent("mouse_move", delay, {"x": x, "y": y})]
        else:
            self.events = [MacroEvent("mouse_scroll", delay, {"x": x, "y": y, "dx": self.dx.value(), "dy": self.dy.value()})]
        self.accept()

    def closeEvent(self, event):
        if self.point_preview:
            self.point_preview.close()
        super().closeEvent(event)


class ScreenPreviewOverlay(QWidget):
    """安全桌面预览：只绘制提示，不发送任何真实输入。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        screens = QGuiApplication.screens()
        self._geometry = screens[0].geometry() if screens else QRect(0, 0, 1920, 1080)
        for screen in screens[1:]:
            self._geometry = self._geometry.united(screen.geometry())
        self._cursor_pos = None
        self._title = ""
        self._detail = ""
        self._kind = ""
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self.setGeometry(self._geometry)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

    def show_action(self, title: str, detail: str, kind: str = "mouse", cursor_pos=None, duration=650):
        self._title = title
        self._detail = detail
        self._kind = kind
        self._cursor_pos = cursor_pos
        self.show()
        self.raise_()
        self.update()
        self._timer.start(duration)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._kind == "keyboard":
            rect = QRect(self.width() - 330, self.height() - 118, 300, 82)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(Qt.GlobalColor.black)
            painter.setOpacity(.88)
            painter.drawRoundedRect(rect, 12, 12)
            painter.setOpacity(1)
            painter.setPen(Qt.GlobalColor.white)
            font = painter.font(); font.setPointSize(17); font.setBold(True); painter.setFont(font)
            painter.drawText(rect.adjusted(18, 12, -18, -34), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self._title)
            font.setPointSize(12); font.setBold(False); painter.setFont(font)
            painter.drawText(rect.adjusted(18, 43, -18, -8), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self._detail)
        elif self._cursor_pos is not None:
            x, y = self._cursor_pos
            px, py = x - self._geometry.left(), y - self._geometry.top()
            is_click = self._kind == "click"
            is_press = "按下" in self._title
            if is_click:
                painter.setPen(QPen(Qt.GlobalColor.red if is_press else Qt.GlobalColor.green, 4))
                painter.drawEllipse(px - 18, py - 18, 36, 36)
                painter.drawLine(px - 28, py, px + 28, py)
                painter.drawLine(px, py - 28, px, py + 28)
            else:
                painter.setPen(QPen(Qt.GlobalColor.red, 3))
                painter.drawLine(px - 18, py, px + 18, py)
                painter.drawLine(px, py - 18, px, py + 18)
            label_w = max(170, len(self._title) * 14 + 34)
            lx = px + 24
            ly = py - 50
            if lx + label_w > self.width() - 10:
                lx = px - label_w - 24
            if ly < 10:
                ly = py + 24
            rect = QRect(lx, ly, label_w, 42)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(Qt.GlobalColor.red if is_press else Qt.GlobalColor.green if is_click else Qt.GlobalColor.black)
            painter.drawRoundedRect(rect, 9, 9)
            painter.setPen(Qt.GlobalColor.white)
            font = painter.font(); font.setPointSize(14); font.setBold(True); painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._title)
        painter.end()


class MacroEditorDialog(QDialog):
    def __init__(self, events: list[MacroEvent], parent=None):
        super().__init__(parent)
        self.setWindowTitle("宏编辑器")
        self.resize(1080, 760)
        self.setStyleSheet("""
            QDialog { background: #f5f7fa; }
            QLabel { color: #303133; }
            QPushButton { min-height: 34px; padding: 0 14px; border: 1px solid #dcdfe6; border-radius: 7px; background: white; color: #303133; }
            QPushButton:hover { background: #ecf5ff; border-color: #b3d8ff; }
            QPushButton:pressed { background: #d9ecff; }
            QListWidget { background: white; border: 1px solid #dcdfe6; border-radius: 10px; padding: 6px; }
            QListWidget::item { padding: 10px 12px; border-radius: 6px; }
            QListWidget::item:selected { background: #ecf5ff; color: #303133; }
        """)
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
        subtitle = QLabel("添加操作、调整顺序，并使用安全预览检查执行时序。")
        subtitle.setStyleSheet("color:#909399;")
        title_box.addWidget(title); title_box.addWidget(subtitle)
        head.addLayout(title_box, 1)
        self.preview_button = QPushButton("▶ 桌面预览")
        self.preview_button.clicked.connect(self.toggle_preview)
        head.addWidget(self.preview_button)
        root.addLayout(head)
        toolbar = QHBoxLayout()
        for action, text in (("key", "键盘按键"), ("click", "鼠标点击"), ("move", "鼠标移动"), ("scroll", "鼠标滚轮"), ("delay", "添加等待")):
            button = QPushButton(f"＋ {text}")
            button.clicked.connect(lambda _, value=action: self.insert_action(value))
            toolbar.addWidget(button)
        toolbar.addStretch(); root.addLayout(toolbar)
        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list.itemDoubleClicked.connect(lambda _: self.edit_selected())
        root.addWidget(self.list, 1)
        edit_bar = QHBoxLayout()
        for text, slot in (("编辑", self.edit_selected), ("复制", self.duplicate_selected), ("上移", lambda: self.move_selected(-1)), ("下移", lambda: self.move_selected(1)), ("删除", self.delete_selected), ("批量删除", self.batch_delete), ("清空", self.clear_all)):
            button = QPushButton(text); button.clicked.connect(slot); edit_bar.addWidget(button)
        edit_bar.addStretch(); root.addLayout(edit_bar)
        bottom = QHBoxLayout()
        hint = QLabel("安全预览只显示虚拟光标与提示，不会移动鼠标、点击或发送键盘。")
        hint.setStyleSheet("color:#909399;")
        bottom.addWidget(hint, 1)
        cancel = QPushButton("取消"); cancel.clicked.connect(self.reject); bottom.addWidget(cancel)
        save = QPushButton("保存修改"); save.setStyleSheet("QPushButton{background:#409eff;color:white;border-color:#409eff;} QPushButton:hover{background:#66b1ff;}"); save.clicked.connect(self.accept); bottom.addWidget(save)
        root.addLayout(bottom)
        self._reload_list()

    def closeEvent(self, event):
        self.stop_preview()
        super().closeEvent(event)

    def _reload_list(self, selected=-1):
        self.list.clear()
        for index, event in enumerate(self.events):
            self.list.addItem(QListWidgetItem(self._event_text(index, event)))
        if 0 <= selected < self.list.count():
            self.list.setCurrentRow(selected)

    def _event_text(self, index, event):
        d = event.data
        if event.type in ("key", "key_down", "key_up"):
            detail = f"：{d.get('key', '')} {'按下' if event.type == 'key_down' or d.get('action') == 'down' else '释放' if event.type == 'key_up' or d.get('action') == 'up' else d.get('action', '')}"
        elif event.type == "mouse_move": detail = f"：({d.get('x')}, {d.get('y')})"
        elif event.type == "mouse_click": detail = f"：{d.get('button', 'left')} ({d.get('x')}, {d.get('y')}) {'按下' if d.get('pressed') else '释放'}"
        elif event.type == "mouse_scroll": detail = f"：({d.get('x')}, {d.get('y')}) dx={d.get('dx', 0)} dy={d.get('dy', 0)}"
        else: detail = ""
        return f"{index + 1:03d}  {event.type}{detail}    延迟 {event.delay:.3f}s"

    def insert_action(self, action):
        dialog = ActionDialog(action, self) if action in ("key", "delay") else MouseActionDialog(action, self)
        if not dialog.exec():
            return
        row = self.list.currentRow() + 1
        self.events[row:row] = dialog.events
        self._reload_list(row)

    def edit_selected(self):
        rows = self.list.selectedItems()
        if len(rows) != 1: return
        row = self.list.row(rows[0])
        dialog = EventEditorDialog(self.events[row], self)
        if dialog.exec():
            self.events[row] = dialog.event
            self._reload_list(row)

    def duplicate_selected(self):
        row = self.list.currentRow()
        if row < 0: return
        event = self.events[row]
        self.events.insert(row + 1, MacroEvent(event.type, event.delay, dict(event.data)))
        self._reload_list(row + 1)

    def move_selected(self, direction):
        row = self.list.currentRow(); target = row + direction
        if row < 0 or target < 0 or target >= len(self.events): return
        self.events[row], self.events[target] = self.events[target], self.events[row]
        self._reload_list(target)

    def delete_selected(self):
        rows = self.list.selectedItems()
        if not rows: return
        row = self.list.row(rows[0]); self.events.pop(row); self._reload_list(min(row, len(self.events) - 1))

    def batch_delete(self):
        rows = sorted({self.list.row(item) for item in self.list.selectedItems()}, reverse=True)
        if not rows: return
        for row in rows: self.events.pop(row)
        self._reload_list(min(rows[-1], len(self.events) - 1))

    def clear_all(self):
        if not self.events: return
        if QMessageBox.question(self, "清空宏", "确定清空当前全部操作吗？") != QMessageBox.StandardButton.Yes: return
        self.events.clear(); self._reload_list()

    def toggle_preview(self):
        if self._preview_running:
            self.stop_preview(); return
        if not self.events:
            QMessageBox.information(self, "预览", "当前宏没有可预览的操作。"); return
        self._preview_running = True
        self._preview_index = 0
        self.preview_button.setText("■ 停止预览")
        self._preview_overlay = ScreenPreviewOverlay()
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
            self.stop_preview(); return
        delay_ms = max(0, int(round(self.events[self._preview_index].delay * 1000)))
        self._preview_timer.start(delay_ms)

    def _preview_timer_tick(self):
        if not self._preview_running or self._preview_index >= len(self.events):
            self.stop_preview(); return
        self._show_preview_event(self.events[self._preview_index])
        self._preview_index += 1
        if self._preview_index < len(self.events):
            delay_ms = max(1, int(round(self.events[self._preview_index].delay * 1000)))
            self._preview_timer.start(delay_ms)
        else:
            QTimer.singleShot(700, self.stop_preview)

    def _show_preview_event(self, event):
        if not self._preview_overlay:
            return
        d = event.data
        if event.type == "mouse_move":
            cursor = (int(d.get("x", 0)), int(d.get("y", 0)))
            self._preview_overlay.show_action("鼠标移动", f"移动到 X={cursor[0]}  Y={cursor[1]}", "move", cursor)
        elif event.type == "mouse_click":
            cursor = (int(d.get("x", 0)), int(d.get("y", 0)))
            button = d.get("button", "left")
            name = {"left": "左键", "right": "右键", "middle": "中键"}.get(button, button)
            action = "按下" if d.get("pressed") else "释放"
            self._preview_overlay.show_action(f"{name} {action}", f"位置 X={cursor[0]}  Y={cursor[1]}", "click", cursor)
        elif event.type == "mouse_scroll":
            cursor = (int(d.get("x", 0)), int(d.get("y", 0)))
            self._preview_overlay.show_action("鼠标滚轮", f"位置 X={cursor[0]}  Y={cursor[1]}  ΔX={d.get('dx', 0)}  ΔY={d.get('dy', 0)}", "move", cursor)
        elif event.type in ("key", "key_down", "key_up"):
            key = d.get("key", "")
            action = "按下" if event.type == "key_down" or d.get("action") == "down" else "释放"
            self._preview_overlay.show_action(f"⌨ {key} {action}", "键盘操作仅做视觉预览", "keyboard", None)
        else:
            self._preview_overlay.show_action("等待", f"等待 {event.delay:.3f} 秒", "keyboard", None, 500)
