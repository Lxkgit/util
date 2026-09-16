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
        label = QRect(px + 22, py - 22, 170, 34)
        if label.right() > self.width() - 8:
            label.moveLeft(px - 192)
        if label.top() < 8:
            label.moveTop(py + 22)
        p.drawRoundedRect(label, 7, 7)
        p.setOpacity(1)
        p.setPen(Qt.GlobalColor.white)
        p.drawText(label, Qt.AlignmentFlag.AlignCenter, f"预览点位  X={x}  Y={y}")
        p.end()


class PointPicker(QDialog):
    """全屏实时选点：右上角显示当前鼠标位置，最后一次左键为最终点。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.point: tuple[int, int] | None = None
        self._mouse_pos = QCursor.pos()
        self._desktop = self._desktop_geometry()
        self.setGeometry(self._desktop)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self.info = QLabel(self)
        self.info.setStyleSheet("QLabel{background:rgba(20,24,32,245);color:white;padding:10px 16px;border-radius:8px;font-size:15px;font-weight:700;}")
        self._update_cursor_info()

        self.hint = QLabel("左键：选择当前位置  ·  可重复选择  ·  Enter：确认最后一次选择  ·  Esc：取消", self)
        self.hint.setStyleSheet("QLabel{background:rgba(20,24,32,225);color:white;padding:8px 12px;border-radius:7px;font-size:13px;}")
        self.hint.adjustSize()
        self.hint.move(24, 24)

        self.confirm = QPushButton("确认此位置", self)
        self.confirm.setStyleSheet("QPushButton{background:#409eff;color:white;border:0;border-radius:7px;padding:9px 16px;font-weight:700;}")
        self.confirm.clicked.connect(self._confirm)
        self.confirm.setEnabled(False)
        self.cancel = QPushButton("取消", self)
        self.cancel.clicked.connect(self.reject)
        self._move_buttons()

    @staticmethod
    def _desktop_geometry():
        screens = QGuiApplication.screens()
        geometry = screens[0].geometry() if screens else QRect(0, 0, 1920, 1080)
        for screen in screens[1:]:
            geometry = geometry.united(screen.geometry())
        return geometry

    def showEvent(self, event):
        super().showEvent(event)
        self._mouse_pos = QCursor.pos()
        self._update_cursor_info()
        self._move_buttons()
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
        self._move_buttons()
        self._update_cursor_info()

    def _move_buttons(self):
        y = self.height() - 60
        self.cancel.move(self.width() - 110, y)
        self.confirm.move(self.width() - 250, y)

    def _update_cursor_info(self, selected=False):
        pos = self._mouse_pos
        self.info.setText(f"{'已选择' if selected else '当前鼠标'}：X={pos.x()}  Y={pos.y()}")
        self.info.adjustSize()
        self.info.move(max(10, self.width() - self.info.width() - 20), 20)

    def mouseMoveEvent(self, event):
        self._mouse_pos = event.globalPosition().toPoint()
        self._update_cursor_info()
        self.update()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.globalPosition().toPoint()
            self.point = (pos.x(), pos.y())
            self._mouse_pos = pos
            self.confirm.setEnabled(True)
            self._update_cursor_info(True)
            self.update()
        event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.point is not None:
            self._confirm()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        p.fillRect(self.rect(), Qt.GlobalColor.transparent)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        pos = self.mapFromGlobal(self._mouse_pos)
        p.setPen(QPen(Qt.GlobalColor.red, 2))
        p.drawLine(pos.x() - 14, pos.y(), pos.x() + 14, pos.y())
        p.drawLine(pos.x(), pos.y() - 14, pos.x(), pos.y() + 14)
        p.setPen(QPen(Qt.GlobalColor.white, 1))
        p.drawEllipse(pos.x() - 4, pos.y() - 4, 8, 8)
        p.end()


class MouseActionDialog(QDialog):
    def __init__(self, action: str, parent=None):
        super().__init__(parent)
        self.action = action
        self.events: list[MacroEvent] = []
        self.point: tuple[int, int] | None = None
        self.preview_overlay = None
        self.setWindowTitle({"click": "鼠标点击", "move": "鼠标移动", "scroll": "鼠标滚轮"}[action])
        self.resize(520, 330)
        self.setStyleSheet("QDialog{background:#f5f7fa;} QLabel{color:#303133;} QPushButton{min-height:36px;padding:0 15px;border:1px solid #dcdfe6;border-radius:7px;background:white;} QPushButton:hover{background:#ecf5ff;border-color:#b3d8ff;}")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(13)
        title = QLabel("鼠标操作参数")
        title.setStyleSheet("font-size:20px;font-weight:700;")
        root.addWidget(title)
        desc = QLabel("位置不需要手工输入。点击下面按钮后，直接移动鼠标到目标位置并左键选择。")
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#909399;")
        root.addWidget(desc)
        form = QFormLayout()
        self.delay = QDoubleSpinBox(); self.delay.setRange(0, 999999); self.delay.setDecimals(3); self.delay.setSuffix(" 秒")
        form.addRow("执行前延迟", self.delay)
        self.button = QComboBox(); self.button.addItems(["left", "right", "middle"])
        if action == "click": form.addRow("鼠标按钮", self.button)
        self.dx = QSpinBox(); self.dx.setRange(-99999, 99999)
        self.dy = QSpinBox(); self.dy.setRange(-99999, 99999)
        if action == "scroll":
            form.addRow("水平滚动", self.dx); form.addRow("垂直滚动", self.dy)
        root.addLayout(form)
        self.position = QLabel("尚未选择位置")
        self.position.setStyleSheet("background:white;border:1px solid #e4e7ed;border-radius:7px;padding:10px;font-weight:700;")
        root.addWidget(self.position)
        row = QHBoxLayout()
        pick = QPushButton("🎯 选择屏幕位置"); pick.clicked.connect(self.pick_position)
        preview = QPushButton("👁 预览点位"); preview.setEnabled(False); preview.clicked.connect(self.preview_position)
        self.preview_button = preview
        row.addWidget(pick); row.addWidget(preview); row.addStretch(); root.addLayout(row)
        buttons = QHBoxLayout(); buttons.addStretch()
        cancel = QPushButton("取消"); cancel.clicked.connect(self.reject)
        ok = QPushButton("确认添加"); ok.setStyleSheet("QPushButton{background:#409eff;color:white;border-color:#409eff;}"); ok.clicked.connect(self.confirm)
        buttons.addWidget(cancel); buttons.addWidget(ok); root.addLayout(buttons)

    def pick_position(self):
        picker = PointPicker(self)
        if picker.exec() == QDialog.DialogCode.Accepted and picker.point is not None:
            self.point = picker.point
            x, y = self.point
            self.position.setText(f"已选择：X={x}，Y={y}")
            self.preview_button.setEnabled(True)
            self.raise_(); self.activateWindow()

    def preview_position(self):
        if self.point is None: return
        if self.preview_overlay: self.preview_overlay.close()
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
            self.events = [MacroEvent("mouse_click", delay, {**data, "pressed": True}), MacroEvent("mouse_click", 0.0, {**data, "pressed": False})]
        elif self.action == "move":
            self.events = [MacroEvent("mouse_move", delay, {"x": x, "y": y})]
        else:
            self.events = [MacroEvent("mouse_scroll", delay, {"x": x, "y": y, "dx": self.dx.value(), "dy": self.dy.value()})]
        self.accept()

    def closeEvent(self, event):
        if self.preview_overlay: self.preview_overlay.close()
        super().closeEvent(event)


class ScreenPreviewOverlay(QWidget):
    """安全预览：只绘制提示，绝不发送真实输入。"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.geometry_rect = self._desktop_geometry()
        self.setGeometry(self.geometry_rect)
        self._title = ""; self._detail = ""; self._kind = ""; self._cursor = None
        self._timer = QTimer(self); self._timer.setSingleShot(True); self._timer.timeout.connect(self.hide)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

    @staticmethod
    def _desktop_geometry():
        screens = QGuiApplication.screens()
        geometry = screens[0].geometry() if screens else QRect(0, 0, 1920, 1080)
        for screen in screens[1:]: geometry = geometry.united(screen.geometry())
        return geometry

    def show_action(self, title, detail, kind="mouse", cursor=None, duration=600):
        self._title = title; self._detail = detail; self._kind = kind; self._cursor = cursor
        self.show(); self.raise_(); self.update(); self._timer.start(duration)

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._kind == "keyboard":
            rect = QRect(self.width() - 350, self.height() - 120, 320, 86)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(Qt.GlobalColor.black); p.setOpacity(.9); p.drawRoundedRect(rect, 12, 12); p.setOpacity(1)
            p.setPen(Qt.GlobalColor.white); f = p.font(); f.setPointSize(17); f.setBold(True); p.setFont(f); p.drawText(rect.adjusted(18,12,-18,-38), Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop, self._title)
            f.setPointSize(12); f.setBold(False); p.setFont(f); p.drawText(rect.adjusted(18,45,-18,-8), Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop, self._detail)
        elif self._cursor is not None:
            x, y = self._cursor; px = x - self.geometry_rect.left(); py = y - self.geometry_rect.top()
            color = Qt.GlobalColor.red if "按下" in self._title else Qt.GlobalColor.green if "释放" in self._title else Qt.GlobalColor.red
            p.setPen(QPen(color, 4)); p.drawLine(px-25,py,px+25,py); p.drawLine(px,py-25,px,py+25); p.drawEllipse(px-20,py-20,40,40)
            label_w = max(170, len(self._title)*15+30); lx = px+28; ly = py-52
            if lx+label_w > self.width()-8: lx = px-label_w-28
            if ly < 8: ly = py+28
            rect = QRect(lx,ly,label_w,44); p.setPen(Qt.PenStyle.NoPen); p.setBrush(color); p.drawRoundedRect(rect,9,9)
            p.setPen(Qt.GlobalColor.white); f=p.font(); f.setPointSize(14); f.setBold(True); p.setFont(f); p.drawText(rect,Qt.AlignmentFlag.AlignCenter,self._title)
        p.end()


class MacroEditorDialog(QDialog):
    def __init__(self, events: list[MacroEvent], parent=None):
        super().__init__(parent)
        self.setWindowTitle("宏编辑器"); self.resize(1080,760)
        self.setStyleSheet("""QDialog{background:#f5f7fa;color:#303133;} QLabel{color:#303133;} QPushButton{min-height:36px;padding:0 14px;border:1px solid #dcdfe6;border-radius:8px;background:white;color:#303133;} QPushButton:hover{background:#ecf5ff;border-color:#b3d8ff;} QListWidget{background:white;border:1px solid #dcdfe6;border-radius:10px;padding:6px;} QListWidget::item{padding:10px 12px;border-radius:6px;} QListWidget::item:selected{background:#ecf5ff;color:#303133;}""")
        self.events=[MacroEvent(e.type,e.delay,dict(e.data)) for e in events]
        self._preview_timer=QTimer(self); self._preview_timer.setSingleShot(True); self._preview_timer.timeout.connect(self._preview_step)
        self._preview_index=0; self._preview_running=False; self._overlay=None
        root=QVBoxLayout(self); root.setContentsMargins(22,18,22,18); root.setSpacing(12)
        head=QHBoxLayout(); title=QLabel("宏编辑器"); title.setStyleSheet("font-size:24px;font-weight:700;"); head.addWidget(title); head.addStretch(); self.preview=QPushButton("▶ 安全预览"); self.preview.clicked.connect(self.toggle_preview); head.addWidget(self.preview); root.addLayout(head)
        sub=QLabel("鼠标位置通过屏幕选点确定；安全预览不会真实操作键盘和鼠标。"); sub.setStyleSheet("color:#909399;"); root.addWidget(sub)
        tools=QHBoxLayout()
        for action,text in (("key","键盘按键"),("click","鼠标点击"),("move","鼠标移动"),("scroll","鼠标滚轮"),("delay","添加等待")):
            b=QPushButton("＋ "+text); b.clicked.connect(lambda _,a=action:self.insert_action(a)); tools.addWidget(b)
        tools.addStretch(); root.addLayout(tools)
        self.list=QListWidget(); self.list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection); self.list.itemDoubleClicked.connect(lambda _:self.edit_selected()); root.addWidget(self.list,1)
        bar=QHBoxLayout()
        for text,slot in (("编辑",self.edit_selected),("复制",self.duplicate_selected),("上移",lambda:self.move_selected(-1)),("下移",lambda:self.move_selected(1)),("删除",self.delete_selected),("批量删除",self.batch_delete),("清空",self.clear_all)):
            b=QPushButton(text); b.clicked.connect(slot); bar.addWidget(b)
        bar.addStretch(); root.addLayout(bar)
        bottom=QHBoxLayout(); hint=QLabel("预览结束后自动退出；鼠标提示跟随虚拟指针，键盘提示固定右下角。"); hint.setStyleSheet("color:#909399;"); bottom.addWidget(hint,1); cancel=QPushButton("取消"); cancel.clicked.connect(self.reject); save=QPushButton("保存修改"); save.setStyleSheet("QPushButton{background:#409eff;color:white;border-color:#409eff;}"); save.clicked.connect(self.accept); bottom.addWidget(cancel); bottom.addWidget(save); root.addLayout(bottom)
        self._reload_list()

    def closeEvent(self,event): self.stop_preview(); super().closeEvent(event)
    def _reload_list(self,selected=-1):
        self.list.clear()
        for i,e in enumerate(self.events): self.list.addItem(QListWidgetItem(self._event_text(i,e)))
        if 0<=selected<self.list.count(): self.list.setCurrentRow(selected)
    def _event_text(self,i,e):
        d=e.data
        if e.type in ("key","key_down","key_up"): detail=f" {d.get('key','')} {'按下' if e.type=='key_down' else '释放' if e.type=='key_up' else d.get('action','')}"
        elif e.type=='mouse_move': detail=f" ({d.get('x')},{d.get('y')})"
        elif e.type=='mouse_click': detail=f" {d.get('button','left')} ({d.get('x')},{d.get('y')}) {'按下' if d.get('pressed') else '释放'}"
        elif e.type=='mouse_scroll': detail=f" ({d.get('x')},{d.get('y')}) Δ({d.get('dx',0)},{d.get('dy',0)})"
        else: detail=f" {e.delay:.3f}s"
        return f"{i+1:03d}  {e.type}{detail}    延迟 {e.delay:.3f}s"
    def insert_action(self,action):
        dialog=ActionDialog(action,self) if action in ('key','delay') else MouseActionDialog(action,self)
        if dialog.exec()!=QDialog.DialogCode.Accepted: return
        row=self.list.currentRow()+1; self.events[row:row]=dialog.events; self._reload_list(row)
    def edit_selected(self):
        items=self.list.selectedItems()
        if len(items)!=1:return
        row=self.list.row(items[0]); d=EventEditorDialog(self.events[row],self)
        if d.exec()==QDialog.DialogCode.Accepted: self.events[row]=d.event; self._reload_list(row)
    def duplicate_selected(self):
        row=self.list.currentRow()
        if row<0:return
        e=self.events[row]; self.events.insert(row+1,MacroEvent(e.type,e.delay,dict(e.data))); self._reload_list(row+1)
    def move_selected(self,direction):
        row=self.list.currentRow(); target=row+direction
        if row<0 or target<0 or target>=len(self.events):return
        self.events[row],self.events[target]=self.events[target],self.events[row]; self._reload_list(target)
    def delete_selected(self):
        rows=sorted({self.list.row(i) for i in self.list.selectedItems()},reverse=True)
        if not rows:return
        for r in rows:self.events.pop(r)
        self._reload_list(min(rows[-1],len(self.events)-1))
    def batch_delete(self): self.delete_selected()
    def clear_all(self):
        if not self.events:return
        if QMessageBox.question(self,'清空宏','确定清空当前全部操作吗？')==QMessageBox.StandardButton.Yes:self.events.clear();self._reload_list()
    def toggle_preview(self):
        if self._preview_running:self.stop_preview();return
        if not self.events:QMessageBox.information(self,'预览','当前宏没有可预览的操作。');return
        self._preview_running=True;self._preview_index=0;self.preview.setText('■ 停止预览');self._overlay=ScreenPreviewOverlay();self._schedule_preview()
    def _schedule_preview(self):
        if not self._preview_running or self._preview_index>=len(self.events):self.stop_preview();return
        self._preview_timer.start(max(1,int(round(max(0,self.events[self._preview_index].delay)*1000))))
    def _preview_step(self):
        if not self._preview_running or self._preview_index>=len(self.events):self.stop_preview();return
        e=self.events[self._preview_index];d=e.data
        if e.type=='mouse_move':self._overlay.show_action('鼠标移动',f"移动到 X={d.get('x')}  Y={d.get('y')}",'move',(int(d.get('x',0)),int(d.get('y',0))))
        elif e.type=='mouse_click':
            name={'left':'左键','right':'右键','middle':'中键'}.get(d.get('button','left'),d.get('button','left'));state='按下' if d.get('pressed') else '释放';self._overlay.show_action(f'{name} {state}',f"X={d.get('x')}  Y={d.get('y')}",'click',(int(d.get('x',0)),int(d.get('y',0))))
        elif e.type=='mouse_scroll':self._overlay.show_action('鼠标滚轮',f"ΔX={d.get('dx',0)}  ΔY={d.get('dy',0)}",'move',(int(d.get('x',0)),int(d.get('y',0))))
        elif e.type in ('key','key_down','key_up'):
            state='按下' if e.type=='key_down' else '释放';self._overlay.show_action(f"⌨ {d.get('key','')} {state}",'仅视觉预览','keyboard')
        else:self._overlay.show_action('等待',f'等待 {e.delay:.3f} 秒','keyboard',None,500)
        self._preview_index+=1
        if self._preview_index<len(self.events):self._schedule_preview()
        else:QTimer.singleShot(650,self.stop_preview)
    def stop_preview(self):
        self._preview_timer.stop();self._preview_running=False;self.preview.setText('▶ 安全预览')
        if self._overlay:self._overlay.close();self._overlay.deleteLater();self._overlay=None
