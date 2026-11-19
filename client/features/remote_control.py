from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QGroupBox
)


class RemoteControl(QWidget):
    TITLE = "🖥️ 远程操控"

    def __init__(self, runtime=None):
        super().__init__()
        self.runtime = runtime
        self._devices = []
        self._build_ui()

        if self.runtime:
            self.runtime.devices_updated.connect(self.update_devices)
            self.runtime.status_updated.connect(self.update_status)
            self.runtime.error_occurred.connect(self.update_error)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

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
        layout.addWidget(self.device_table, 1)

        info_group = QGroupBox("运行状态")
        info_layout = QVBoxLayout(info_group)
        self.status_label = QLabel("正在获取设备列表……")
        self.status_label.setWordWrap(True)
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #c0392b;")
        info_layout.addWidget(self.status_label)
        info_layout.addWidget(self.error_label)
        layout.addWidget(info_group)

        note = QLabel(
            "当前阶段已接入设备注册、心跳和在线设备发现。"
            "选择设备后的 WebRTC 连接、软件列表和远程截图将在下一阶段接入。"
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #777;")
        layout.addWidget(note)

    def update_devices(self, devices):
        self._devices = devices
        self.device_table.setRowCount(len(devices))

        for row, device in enumerate(devices):
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

        self.error_label.clear()

    def update_status(self, message):
        self.status_label.setText(message)

    def update_error(self, message):
        self.error_label.setText(message)
