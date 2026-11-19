import os
import configparser
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QFileDialog,
    QScrollArea, QHBoxLayout, QFrame, QPushButton
)

CONFIG_PATH = "config.ini"


# -------------------- 配置读写 --------------------
def load_config():
    config = configparser.ConfigParser()
    if not os.path.exists(CONFIG_PATH):
        config["DEFAULT"] = {"HomeDir": str(Path.home())}
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

        # 左侧：标题文字，靠右对齐
        self.label = QLabel(title)
        self.label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.label.setFixedWidth(110)
        self.label.setStyleSheet("border: none;")  # 去掉边框
        layout.addWidget(self.label, stretch=1)

        # 中间：路径显示
        self.path_edit = QLineEdit()
        self.path_edit.setText(value)
        self.path_edit.setReadOnly(True)
        layout.addWidget(self.path_edit, stretch=3)

        # 右侧：小按钮
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

        # -------------------- 添加卡片 --------------------
        config = load_config()
        home_dir = config["DEFAULT"].get("HomeDir", str(Path.home()))
        file_card = PathSettingCard(
            "文件管理首页目录", value=home_dir, config_key="HomeDir"
        )
        self.cards_layout.addWidget(file_card)

        # 未来可以继续添加其他设置卡片
        # example_card = SettingCard("🔔 通知设置", value="开启", config_key="Notify")
        # self.cards_layout.addWidget(example_card)

        self.cards_layout.addStretch()
