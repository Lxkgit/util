from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from core.model import MacroEvent
from ui.action_dialog import ActionInsertDialog
from ui.event_editor import EventEditorDialog


class MacroEditorDialog(QDialog):
    def __init__(self, events: list[MacroEvent], parent=None):
        super().__init__(parent)
        self.setWindowTitle("宏编辑器")
        self.resize(980, 680)
        self.events = [MacroEvent(e.type, e.delay, dict(e.data)) for e in events]
        self._preview_timer = QTimer(self)
        self._preview_timer.timeout.connect(self._preview_tick)
        self._preview_index = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(12)

        head = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("宏编辑器")
        title.setStyleSheet("font-size:24px;font-weight:700;")
        subtitle = QLabel("在这里整理、添加和预览操作。预览只模拟显示，不会真的控制键盘和鼠标。")
        subtitle.setStyleSheet("color:#7a8491;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        head.addLayout(title_box, 1)
        self.preview_button = QPushButton("▶ 预览")
        self.preview_button.clicked.connect(self.toggle_preview)
        head.addWidget(self.preview_button)
        root.addLayout(head)

        toolbar = QHBoxLayout()
        for action, text in (
            ("key", "键盘按键"),
            ("click", "鼠标点击"),
            ("move", "鼠标移动"),
            ("scroll", "滚轮"),
            ("delay", "等待"),
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
        self.preview_status = QLabel("预览：未开始")
        self.preview_status.setStyleSheet("color:#606266;font-weight:600;")
        edit_bar.addWidget(self.preview_status)
        root.addLayout(edit_bar)

        bottom = QHBoxLayout()
        bottom.addWidget(QLabel("提示：预览会逐项高亮操作，并显示将执行的内容；不会发送真实键盘、鼠标事件。"), 1)
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
        dialog = ActionInsertDialog(action, self)
        if not dialog.exec() or not dialog.events:
            return
        index = self._selected_index()
        insert_at = index + 1 if index >= 0 else len(self.events)
        self.events[insert_at:insert_at] = dialog.events
        self._refresh_list(insert_at)

    def edit_selected(self):
        index = self._selected_index()
        if index < 0:
            return
        event = self.events[index]
        if event.type != "delay":
            QMessageBox.information(self, "提示", "当前版本暂时只支持直接编辑等待时间，其他操作可复制、删除或重新添加。")
            return
        dialog = EventEditorDialog(event, self)
        if dialog.exec():
            self.events[index] = dialog.event
            self._refresh_list(index)

    def duplicate_selected(self):
        index = self._selected_index()
        if index < 0:
            return
        event = self.events[index]
        self.events.insert(index + 1, MacroEvent(event.type, event.delay, dict(event.data)))
        self._refresh_list(index + 1)

    def move_selected(self, offset: int):
        index = self._selected_index()
        target = index + offset
        if index < 0 or target < 0 or target >= len(self.events):
            return
        self.events[index], self.events[target] = self.events[target], self.events[index]
        self._refresh_list(target)

    def delete_selected(self):
        index = self._selected_index()
        if index < 0:
            return
        del self.events[index]
        self._refresh_list(min(index, len(self.events) - 1))

    def toggle_preview(self):
        if self._preview_timer.isActive():
            self._preview_timer.stop()
            self.preview_button.setText("▶ 预览")
            self.preview_status.setText("预览：已停止")
            self.list.clearSelection()
            return
        if not self.events:
            self.preview_status.setText("预览：没有操作")
            return
        self._preview_index = 0
        self.preview_button.setText("■ 停止预览")
        self._preview_tick()

    def _preview_tick(self):
        if self._preview_index >= len(self.events):
            self._preview_timer.stop()
            self.preview_button.setText("▶ 预览")
            self.preview_status.setText("预览：完成（未执行真实操作）")
            self.list.clearSelection()
            return
        event = self.events[self._preview_index]
        self.list.setCurrentRow(self._preview_index)
        self.preview_status.setText(
            f"预览 {self._preview_index + 1}/{len(self.events)}：{self.preview_description(event)}"
        )
        self._preview_index += 1
        self._preview_timer.start(max(250, int(max(event.delay, 0.25) * 1000)))

    @staticmethod
    def preview_description(event: MacroEvent) -> str:
        data = event.data
        if event.type == "key_down":
            return f"模拟：按下 {data.get('key')}（不会真的按键）"
        if event.type == "key_up":
            return f"模拟：释放 {data.get('key')}（不会真的按键）"
        if event.type == "mouse_move":
            return f"模拟：移动鼠标到 ({data.get('x')}, {data.get('y')})（不会移动）"
        if event.type == "mouse_click":
            state = "按下" if data.get("pressed") else "释放"
            return f"模拟：鼠标 {state} {data.get('button')}（不会点击）"
        if event.type == "mouse_scroll":
            return f"模拟：滚轮 dx={data.get('dx')} dy={data.get('dy')}（不会滚动）"
        if event.type == "delay":
            return f"模拟：等待 {event.delay:.3f} 秒"
        return "模拟：未知操作"

    def reject(self):
        self._preview_timer.stop()
        super().reject()

    def accept(self):
        self._preview_timer.stop()
        super().accept()
