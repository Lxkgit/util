from __future__ import annotations

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QCursor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSpinBox,
    QVBoxLayout, QWidget,
)

from core.model import MacroEvent
from ui.action_dialog import ActionDialog
from ui.event_editor import EventEditorDialog


class PointPreviewOverlay(QWidget):
    def __init__(self, point: tuple[int, int], parent=None):
        super().__init__(parent)
        self.point = point
        self.geometry_rect = self._desktop_geometry()
        self.setGeometry(self.geometry_rect)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.close)

    @staticmethod
    def _desktop_geometry():
        screens = QGuiApplication.screens()
        geometry = screens[0].geometry() if screens else QRect(0, 0, 1920, 1080)
        for screen in screens[1:]:
            geometry = geometry.united(screen.geometry())
        return geometry

    def show_for(self, duration=1500):
        self.show()
        self.raise_()
        self.timer.start(duration)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        x, y = self.point
        px, py = x - self.geometry_rect.left(), y - self.geometry_rect.top()
        p.setPen(QPen(Qt.GlobalColor.red, 4))
        p.drawLine(px - 16, py, px + 16, py)
        p.drawLine(px, py - 16, px, py + 16)
        p.setPen(QPen(Qt.GlobalColor.white, 2))
        p.drawEllipse(px - 7, py - 7, 14, 14)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(Qt.GlobalColor.black)
        p.setOpacity(.88)
        label = QRect(px + 22, py - 22, 190, 34)
        if label.right() > self.width() - 8:
            label.moveLeft(px - 212)
        if label.top() < 8:
            label.moveTop(py + 22)
        p.drawRoundedRect(label, 7, 7)
        p.setOpacity(1)
        p.setPen(Qt.GlobalColor.white)
        p.drawText(label, Qt.AlignmentFlag.AlignCenter, f"预览点位  X={x}  Y={y}")


class PointPicker(QDialog):
    """全屏选点：鼠标移动到目标位置后，按 Enter 或右上角按钮确认。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.point: tuple[int, int] | None = None
        self._desktop = self._desktop_geometry()
        self.setGeometry(self._desktop)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self.info = QLabel(self)
        self.info.setStyleSheet(
            "QLabel{background:rgba(20,24,32,245);color:white;padding:10px 16px;"
            "border-radius:8px;font-size:15px;font-weight:700;}"
        )

        self.hint = QLabel(
            "移动鼠标到目标位置，然后按 Enter 或点击右上角「确认当前鼠标位置」\n"
            "Esc：取消",
            self,
        )
        self.hint.setStyleSheet(
            "QLabel{background:rgba(20,24,32,225);color:white;padding:9px 13px;"
            "border-radius:7px;font-size:13px;}"
        )
        self.hint.adjustSize()
        self.hint.move(24, 24)

        self.confirm = QPushButton("✓ 确认当前鼠标位置", self)
        self.confirm.setStyleSheet(
            "QPushButton{background:#409eff;color:white;border:0;border-radius:7px;"
            "padding:10px 16px;font-size:14px;font-weight:700;}"
            "QPushButton:hover{background:#66b1ff;}"
        )
        self.confirm.clicked.connect(self._confirm_current_position)

        self.cancel = QPushButton("取消", self)
        self.cancel.setStyleSheet(
            "QPushButton{background:#30343b;color:white;border:0;border-radius:7px;"
            "padding:10px 16px;font-size:14px;}"
        )
        self.cancel.clicked.connect(self.reject)
        self._update_layout()
        self._update_cursor_info()

    @staticmethod
    def _desktop_geometry():
        screens = QGuiApplication.screens()
        geometry = screens[0].geometry() if screens else QRect(0, 0, 1920, 1080)
        for screen in screens[1:]:
            geometry = geometry.united(screen.geometry())
        return geometry

    def showEvent(self, event):
        super().showEvent(event)
        self._update_cursor_info()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        self.grabMouse()
        self.grabKeyboard()

    def closeEvent(self, event):
        self.releaseMouse()
        self.releaseKeyboard()
        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_layout()
        self._update_cursor_info()

    def _update_layout(self):
        margin = 20
        self.info.move(max(margin, self.width() - self.info.width() - margin), margin)
        self.confirm.adjustSize()
        self.cancel.adjustSize()
        self.cancel.move(self.width() - self.cancel.width() - margin, margin + self.confirm.height() + 10)
        self.confirm.move(self.width() - self.confirm.width() - margin, margin)

    def _update_cursor_info(self):
        # 直接从系统读取当前真实指针位置，不使用之前缓存的点击位置。
        pos = QCursor.pos()
        self.info.setText(f"当前鼠标：X={pos.x()}  Y={pos.y()}")
        self.info.adjustSize()
        self._update_layout()
        self.update()

    def mouseMoveEvent(self, event):
        self._update_cursor_info()
        event.accept()

    def mousePressEvent(self, event):
        # 选点模式下不再用左键保存坐标，避免点击确认控件前改变目标点。
        event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._confirm_current_position()
        else:
            super().keyPressEvent(event)

    def _confirm_current_position(self):
        # 最终确认瞬间重新读取系统鼠标位置，这就是实际保存的点位。
        pos = QCursor.pos()
        self.point = (pos.x(), pos.y())
        self.accept()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pos = QCursor.pos()
        local = self.mapFromGlobal(pos)
        p.setPen(QPen(Qt.GlobalColor.red, 2))
        p.drawLine(local.x() - 14, local.y(), local.x() + 14, local.y())
        p.drawLine(local.x(), local.y() - 14, local.x(), local.y() + 14)
        p.setPen(QPen(Qt.GlobalColor.white, 1))
        p.drawEllipse(local.x() - 4, local.y() - 4, 8, 8)


class MouseActionDialog(QDialog):
    def __init__(self, action: str, parent=None):
        super().__init__(parent)
        self.action = action
        self.events: list[MacroEvent] = []
        self.point: tuple[int, int] | None = None
        self.preview_overlay = None
        self.setWindowTitle({"click": "鼠标点击", "move": "鼠标移动", "scroll": "鼠标滚轮"}[action])
        self.resize(520, 330)
        self.setStyleSheet(
            "QDialog{background:#f5f7fa;} QLabel{color:#303133;} "
            "QPushButton{min-height:36px;padding:0 15px;border:1px solid #dcdfe6;"
            "border-radius:7px;background:white;} QPushButton:hover{background:#ecf5ff;border-color:#b3d8ff;}"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(13)
        title = QLabel("鼠标操作参数")
        title.setStyleSheet("font-size:20px;font-weight:700;")
        root.addWidget(title)
        desc = QLabel("点击「选择屏幕位置」后，直接把鼠标移动到目标位置，再按 Enter 确认。")
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#909399;")
        root.addWidget(desc)
        form = QFormLayout()
        self.delay = QDoubleSpinBox()
        self.delay.setRange(0, 999999)
        self.delay.setDecimals(3)
        self.delay.setSuffix(" 秒")
        form.addRow("执行前延迟", self.delay)
        self.button = QComboBox()
        self.button.addItems(["left", "right", "middle"])
        if action == "click":
            form.addRow("鼠标按钮", self.button)
        self.dx = QSpinBox(); self.dx.setRange(-99999, 99999)
        self.dy = QSpinBox(); self.dy.setRange(-99999, 99999)
        if action == "scroll":
            form.addRow("水平滚动", self.dx)
            form.addRow("垂直滚动", self.dy)
        root.addLayout(form)
        self.position = QLabel("尚未选择位置")
        self.position.setStyleSheet("background:white;border:1px solid #e4e7ed;border-radius:7px;padding:10px;font-weight:700;")
        root.addWidget(self.position)
        row = QHBoxLayout()
        pick = QPushButton("🎯 选择屏幕位置")
        pick.clicked.connect(self.pick_position)
        preview = QPushButton("👁 预览点位")
        preview.setEnabled(False)
        preview.clicked.connect(self.preview_position)
        self.preview_button = preview
        row.addWidget(pick); row.addWidget(preview); row.addStretch()
        root.addLayout(row)
        buttons = QHBoxLayout(); buttons.addStretch()
        cancel = QPushButton("取消"); cancel.clicked.connect(self.reject)
        ok = QPushButton("确认添加")
        ok.setStyleSheet("QPushButton{background:#409eff;color:white;border-color:#409eff;}")
        ok.clicked.connect(self.confirm)
        buttons.addWidget(cancel); buttons.addWidget(ok); root.addLayout(buttons)

    def pick_position(self):
        picker = PointPicker(self)
        if picker.exec() == QDialog.DialogCode.Accepted and picker.point is not None:
            self.point = picker.point
            x, y = self.point
            self.position.setText(f"已选择：X={x}  Y={y}")
            self.preview_button.setEnabled(True)
            self.raise_()
            self.activateWindow()

    def preview_position(self):
        if self.point is None:
            return
        if self.preview_overlay:
            self.preview_overlay.close()
            self.preview_overlay.deleteLater()
        self.preview_overlay = PointPreviewOverlay(self.point)
        self.preview_overlay.show_for()

    def confirm(self):
        if self.point is None:
            QMessageBox.warning(self, "提示", "请先选择屏幕位置。")
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
            self.events = [MacroEvent("mouse_scroll", delay, {"x": x, "y": y, "dx": self.dx.value(), "dy": self.dy.value()})]
        self.accept()

    def closeEvent(self, event):
        if self.preview_overlay:
            self.preview_overlay.close()
        super().closeEvent(event)


class ScreenPreviewOverlay(QWidget):
    """安全预览，只绘制提示，不执行真实鼠标键盘操作。"""

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
        self.show(); self.raise_(); self.update(); self._timer.start(duration)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._kind == "keyboard":
            rect = QRect(self.width() - 330, self.height() - 118, 300, 82)
            painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(Qt.GlobalColor.black); painter.setOpacity(.88)
            painter.drawRoundedRect(rect, 12, 12); painter.setOpacity(1); painter.setPen(Qt.GlobalColor.white)
            font = painter.font(); font.setPointSize(17); font.setBold(True); painter.setFont(font)
            painter.drawText(rect.adjusted(18, 12, -18, -34), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self._title)
            font.setPointSize(12); font.setBold(False); painter.setFont(font)
            painter.drawText(rect.adjusted(18, 43, -18, -8), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self._detail)
        elif self._cursor_pos is not None:
            x, y = self._cursor_pos
            px, py = x - self._geometry.left(), y - self._geometry.top()
            is_click = self._kind == "click"
            is_press = "按下" in self._title
            pen_color = Qt.GlobalColor.red if is_press else Qt.GlobalColor.green
            painter.setPen(QPen(pen_color if is_click else Qt.GlobalColor.red, 4 if is_click else 3))
            if is_click:
                painter.drawEllipse(px - 18, py - 18, 36, 36)
                painter.drawLine(px - 28, py, px + 28, py)
                painter.drawLine(px, py - 28, px, py + 28)
            else:
                painter.drawLine(px - 18, py, px + 18, py)
                painter.drawLine(px, py - 18, px, py + 18)
            label_w = max(170, len(self._title) * 14 + 34)
            lx = px + 24; ly = py - 50
            if lx + label_w > self.width() - 10: lx = px - label_w - 24
            if ly < 10: ly = py + 24
            rect = QRect(lx, ly, label_w, 42)
            painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(Qt.GlobalColor.black); painter.setOpacity(.88)
            painter.drawRoundedRect(rect, 7, 7); painter.setOpacity(1); painter.setPen(Qt.GlobalColor.white)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._title)


class MacroEditorDialog(QDialog):
    def __init__(self, events: list[MacroEvent], parent=None):
        super().__init__(parent)
        self.events = events
        self.setWindowTitle("宏编辑器")
        self.resize(920, 620)
        self.setStyleSheet("QDialog{background:#f5f7fa;} QListWidget{background:white;border:1px solid #dcdfe6;border-radius:8px;} QPushButton{min-height:34px;padding:0 13px;border:1px solid #dcdfe6;border-radius:7px;background:white;} QPushButton:hover{background:#ecf5ff;border-color:#b3d8ff;}")
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        title = QLabel("宏编辑器")
        title.setStyleSheet("font-size:22px;font-weight:700;color:#303133;")
        root.addWidget(title)
        self.summary = QLabel()
        self.summary.setStyleSheet("color:#7a8491;")
        root.addWidget(self.summary)

        toolbar = QHBoxLayout()
        for text, action in [("⌨ 键盘按键", "key"), ("🖱 鼠标点击", "click"), ("↔ 鼠标移动", "move"), ("↕ 鼠标滚轮", "scroll"), ("⏱ 添加等待", "delay")]:
            button = QPushButton(text)
            button.clicked.connect(lambda checked=False, a=action: self.insert_action(a))
            toolbar.addWidget(button)
        toolbar.addStretch()
        root.addLayout(toolbar)

        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list.itemDoubleClicked.connect(lambda item: self.edit_selected())
        root.addWidget(self.list, 1)

        row = QHBoxLayout()
        for text, slot in [("编辑", self.edit_selected), ("复制", self.copy_selected), ("上移", self.move_up), ("下移", self.move_down), ("删除", self.delete_selected), ("批量删除", self.batch_delete), ("清空", self.clear_all)]:
            b = QPushButton(text); b.clicked.connect(slot); row.addWidget(b)
        row.addStretch()
        preview = QPushButton("👁 安全预览"); preview.clicked.connect(self.preview_macro); row.addWidget(preview)
        close = QPushButton("完成"); close.setStyleSheet("QPushButton{background:#409eff;color:white;border-color:#409eff;}"); close.clicked.connect(self.accept); row.addWidget(close)
        root.addLayout(row)
        self.refresh()

    def refresh(self):
        self.list.clear()
        names = {"key_down":"键盘按下", "key_up":"键盘释放", "mouse_move":"鼠标移动", "mouse_click":"鼠标点击", "mouse_scroll":"鼠标滚轮", "delay":"等待"}
        for i, event in enumerate(self.events):
            d = event.data
            if event.type.startswith("key"):
                detail = f"{names.get(event.type,event.type)}：{d.get('key','')}"
            elif event.type == "mouse_move":
                detail = f"鼠标移动：X={d.get('x')} Y={d.get('y')}"
            elif event.type == "mouse_click":
                detail = f"鼠标点击：{d.get('button')} {'按下' if d.get('pressed') else '释放'} X={d.get('x')} Y={d.get('y')}"
            elif event.type == "mouse_scroll":
                detail = f"鼠标滚轮：X={d.get('x')} Y={d.get('y')} Δ({d.get('dx')},{d.get('dy')})"
            else:
                detail = f"等待：{event.delay:.3f} 秒"
            item = QListWidgetItem(f"{i + 1:03d}   {detail}   [前置 {event.delay:.3f}s]")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.list.addItem(item)
        self.summary.setText(f"共 {len(self.events)} 个事件")

    def _indexes(self):
        return sorted({item.data(Qt.ItemDataRole.UserRole) for item in self.list.selectedItems()})

    def insert_action(self, action):
        dialog = ActionDialog(action, self) if action in ("key", "delay") else MouseActionDialog(action, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.events:
            row = self.list.currentRow()
            insert_at = row + 1 if row >= 0 else len(self.events)
            self.events[insert_at:insert_at] = dialog.events
            self.refresh()
            self.list.setCurrentRow(insert_at)

    def edit_selected(self):
        indexes = self._indexes()
        if len(indexes) != 1: return
        index = indexes[0]
        dialog = EventEditorDialog(self.events[index], self)
        if dialog.exec() == QDialog.DialogCode.Accepted: self.refresh(); self.list.setCurrentRow(index)

    def copy_selected(self):
        indexes = self._indexes()
        if not indexes: return
        copied = [MacroEvent(e.type, e.delay, dict(e.data)) for e in (self.events[i] for i in indexes)]
        insert_at = indexes[-1] + 1
        self.events[insert_at:insert_at] = copied
        self.refresh()

    def move_up(self):
        indexes = self._indexes()
        for i in indexes:
            if i > 0 and i - 1 not in indexes:
                self.events[i - 1], self.events[i] = self.events[i], self.events[i - 1]
        self.refresh()

    def move_down(self):
        indexes = self._indexes()
        for i in reversed(indexes):
            if i < len(self.events) - 1 and i + 1 not in indexes:
                self.events[i + 1], self.events[i] = self.events[i], self.events[i + 1]
        self.refresh()

    def delete_selected(self):
        indexes = self._indexes()
        for i in reversed(indexes): del self.events[i]
        self.refresh()

    def batch_delete(self):
        self.delete_selected()

    def clear_all(self):
        if self.events and QMessageBox.question(self, "确认", "确定清空全部事件吗？") == QMessageBox.StandardButton.Yes:
            self.events.clear(); self.refresh()

    def preview_macro(self):
        if not self.events:
            QMessageBox.information(self, "提示", "当前没有可预览的事件。")
            return
        overlay = ScreenPreviewOverlay()
        index = 0
        elapsed = 0
        def tick():
            nonlocal index, elapsed
            if index >= len(self.events):
                QTimer.singleShot(700, overlay.close)
                return
            event = self.events[index]
            elapsed = max(0.0, event.delay)
            detail = str(event.data)
            if event.type.startswith("key"):
                overlay.show_action("键盘操作", detail, "keyboard")
            elif event.type in ("mouse_move", "mouse_click", "mouse_scroll"):
                p = event.data
                overlay.show_action(event.type, detail, "click" if event.type == "mouse_click" else "mouse", (p.get("x", 0), p.get("y", 0)))
            index += 1
            QTimer.singleShot(max(50, int(elapsed * 1000)), tick)
        tick()
