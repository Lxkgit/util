import os
import configparser
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QFileDialog,
    QScrollArea, QHBoxLayout, QFrame, QPushButton, QCheckBox
)

CONFIG_PATH = "config.ini"


# -------------------- 配置读写 --------------------
def load_config():
    config = configparser.ConfigParser()
    if not os.path.exists(CONFIG_PATH):
        config["DEFAULT"] = {
            "HomeDir": str(Path.home()),
            "RemoteEnabled": "true"
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            config.write(f)
    else:
        config.read(CONFIG_PATH, encoding="utf-8")
    return config


def save_config(key, value):
    config = load_config()
    config["DEFAULT"][key] = value
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        config.write(f)


# -------------------- 文件路径设置卡片（三列优化） --------------------
class PathSettingCard(QFrame):
    def __init__(self, title: str, value="", config_key="", parent=None):
        super().__init__(parent)
        self.config_key = config_key
        self.setFixedHeight(60)
        self.setStyleSheet("""
            QFrame {
                border: 1px solid #ccc;
                border-radius: 6px;
                background-color: #e6f0ff;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        self.label = QLabel(title)
        self.label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.label.setFixedWidth(110)
        self.label.setStyleSheet("border: none;")
        layout.addWidget(self.label, stretch=1)

        self.path_edit = QLineEdit()
        self.path_edit.setText(value)
        self.path_edit.setReadOnly(True)
        layout.addWidget(self.path_edit, stretch=3)

        self.select_btn = QPushButton("选择目录")
        self.select_btn.setMinimumWidth(70)
        self.select_btn.clicked.connect(self.browse_dir)
        layout.addWidget(self.select_btn, stretch=0)

    def browse_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, "选择目录", self.path_edit.text() or str(Path.home())
        )
        if path:
            self.path_edit.setText(path)
            self.save_value()

    def save_value(self):
        path = self.path_edit.text().strip()
        if path and os.path.isdir(path):
            save_config(self.config_key, path)


# -------------------- 设置页面 --------------------
class Settings(QWidget):
    TITLE = "⚙️ 设置"

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self.cards_layout = QVBoxLayout(container)
        self.cards_layout.setSpacing(12)
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        config = load_config()
        home_dir = config["DEFAULT"].get("HomeDir", str(Path.home()))
        file_card = PathSettingCard(
            "文件管理首页目录", value=home_dir, config_key="HomeDir"
        )
        self.cards_layout.addWidget(file_card)

        remote_enabled = config["DEFAULT"].getboolean(
            "RemoteEnabled", fallback=True
        )
        self.remote_enabled = QCheckBox("允许本机被发现（注册设备并持续发送心跳）")
        self.remote_enabled.setChecked(remote_enabled)
        self.remote_enabled.stateChanged.connect(self.save_remote_enabled)
        self.cards_layout.addWidget(self.remote_enabled)

        remote_tip = QLabel(
            "关闭后客户端停止发送心跳，服务端设备记录会在 TTL 到期后自动清理；"
            "本机仍可查询其他在线设备。"
        )
        remote_tip.setWordWrap(True)
        remote_tip.setStyleSheet("color: #777;")
        self.cards_layout.addWidget(remote_tip)

        self.cards_layout.addStretch()

    def save_remote_enabled(self, state):
        save_config("RemoteEnabled", "true" if state == Qt.Checked else "false")
