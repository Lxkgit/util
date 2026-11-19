from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QGroupBox, QPushButton,
    QMessageBox, QSplitter
)


class RemoteControl(QWidget):
    TITLE = "🖥️ 远程操控"

    def __init__(self, runtime=None):
        super().__init__()
        self.runtime = runtime
        self._devices = []
        self._selected_peer = None
        self._build_ui()

        if self.runtime:
            self.runtime.devices_updated.connect(self.update_devices)
            self.runtime.status_updated.connect(self.update_status)
            self.runtime.error_occurred.connect(self.update_error)
            self.runtime.connection_state.connect(self.update_connection_state)
            self.runtime.software_list_received.connect(self.update_software)
            self.runtime.screenshot_received.connect(self.update_screenshot)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("在线设备")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)

        self.device_table = QTableWidget(0, 4)
        self.device_table.setHorizontalHeaderLabels(
            ["设备名称", "操作系统", "设备 Key", "客户端版本"]
        )
        self.device_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.device_table.setSelectionMode(QTableWidget.SingleSelection)
        self.device_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.device_table.verticalHeader().setVisible(False)
        self.device_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.device_table.itemSelectionChanged.connect(self.selection_changed)
        layout.addWidget(self.device_table, 2)

        action_layout = QHBoxLayout()
        self.connect_button = QPushButton("连接选中设备")
        self.software_button = QPushButton("获取软件列表")
        self.screenshot_button = QPushButton("远程截图")
        self.disconnect_button = QPushButton("断开连接")
        action_layout.addWidget(self.connect_button)
        action_layout.addWidget(self.software_button)
        action_layout.addWidget(self.screenshot_button)
        action_layout.addWidget(self.disconnect_button)
        layout.addLayout(action_layout)

        self.connect_button.clicked.connect(self.connect_selected)
        self.software_button.clicked.connect(self.request_software)
        self.screenshot_button.clicked.connect(self.request_screenshot)
        self.disconnect_button.clicked.connect(self.disconnect_selected)

        splitter = QSplitter(Qt.Horizontal)

        software_group = QGroupBox("远程软件列表")
        software_layout = QVBoxLayout(software_group)
        self.software_table = QTableWidget(0, 3)
        self.software_table.setHorizontalHeaderLabels(["软件名称", "版本", "发布者"])
        self.software_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.software_table.setEditTriggers(QTableWidget.NoEditTriggers)
        software_layout.addWidget(self.software_table)
        splitter.addWidget(software_group)

        screenshot_group = QGroupBox("远程屏幕截图")
        screenshot_layout = QVBoxLayout(screenshot_group)
        self.screenshot_label = QLabel("尚未获取截图")
        self.screenshot_label.setAlignment(Qt.AlignCenter)
        self.screenshot_label.setMinimumSize(320, 220)
        self.screenshot_label.setStyleSheet(
            "background: #202020; color: white; border-radius: 4px;"
        )
        screenshot_layout.addWidget(self.screenshot_label)
        splitter.addWidget(screenshot_group)
        layout.addWidget(splitter, 3)

        status_group = QGroupBox("连接状态")
        status_layout = QVBoxLayout(status_group)
        self.status_label = QLabel("正在获取设备列表……")
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #c0392b;")
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.error_label)
        layout.addWidget(status_group)

        note = QLabel(
            "远程连接需要被访问电脑在本地确认。当前仅开放软件列表和截图，"
            "不提供远程命令执行、鼠标或键盘控制。"
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #777;")
        layout.addWidget(note)

    def selection_changed(self):
        row = self.device_table.currentRow()
        if row < 0 or row >= len(self._devices):
            self._selected_peer = None
            return
        self._selected_peer = self._devices[row].get("key")

    def connect_selected(self):
        if not self._selected_peer:
            QMessageBox.information(self, "提示", "请先选择一台设备")
            return
        if self.runtime:
            self.runtime.request_connect(self._selected_peer)
            self.status_label.setText("正在发起 P2P 连接……")

    def request_software(self):
        if self._selected_peer and self.runtime:
            self.runtime.request_software(self._selected_peer)

    def request_screenshot(self):
        if self._selected_peer and self.runtime:
            self.runtime.request_screenshot(self._selected_peer)

    def disconnect_selected(self):
        if self._selected_peer and self.runtime:
            self.runtime.disconnect(self._selected_peer)

    def update_devices(self, devices):
        local_key = self.runtime.device_manager.device_key if self.runtime else None
        self._devices = [
            device for device in devices
            if device.get("key") != local_key
        ]
        selected_key = self._selected_peer
        self.device_table.setRowCount(len(self._devices))

        for row, device in enumerate(self._devices):
            values = [
                device.get("deviceName") or device.get("hostname") or "未命名设备",
                device.get("platform", "未知"),
                device.get("key", ""),
                device.get("version", "")
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.device_table.setItem(row, column, item)

            if device.get("key") == selected_key:
                self.device_table.selectRow(row)

        if selected_key and not any(
            device.get("key") == selected_key for device in self._devices
        ):
            self._selected_peer = None

    def update_status(self, message):
        self.status_label.setText(message)

    def update_error(self, message):
        self.error_label.setText(message)

    def update_connection_state(self, peer_key, state):
        if peer_key == self._selected_peer:
            self.status_label.setText(f"设备 {peer_key}：{state}")

    def update_software(self, peer_key, software):
        if peer_key != self._selected_peer:
            return

        self.software_table.setRowCount(len(software))
        for row, item in enumerate(software):
            values = [
                item.get("name", ""),
                item.get("version", ""),
                item.get("publisher", "")
            ]
            for column, value in enumerate(values):
                self.software_table.setItem(
                    row, column, QTableWidgetItem(str(value))
                )

    def update_screenshot(self, peer_key, image_data):
        if peer_key != self._selected_peer:
            return

        pixmap = QPixmap()
        if not pixmap.loadFromData(image_data, "JPEG"):
            self.update_error("远端返回的截图无法解析")
            return

        self.screenshot_label.setPixmap(
            pixmap.scaled(
                self.screenshot_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        )
