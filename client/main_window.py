from PySide6.QtCore import Qt, QRect, QSize, QPoint
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QTabBar, QWidget, QVBoxLayout, QPushButton,
    QMenu, QScrollArea, QLayout
)

from features.file_manager import FileManager
from features.settings import Settings
from features.video_page import VideoPage


# -------------------- FlowLayout --------------------
class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=20, spacing=10):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.item_list = []

    def addItem(self, item):
        self.item_list.append(item)

    def count(self):
        return len(self.item_list)

    def itemAt(self, index):
        if 0 <= index < len(self.item_list):
            return self.item_list[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.item_list):
            return self.item_list.pop(index)
        return None

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.doLayout(QRect(0, 0, width, 0), testOnly=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, testOnly=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        # 返回当前布局实际占用的最小尺寸
        width = 0
        height = self.doLayout(QRect(0, 0, 0, 0), testOnly=True)
        return QSize(width, height)

    def doLayout(self, rect, testOnly=False):
        left, top, right, bottom = self.getContentsMargins()
        x = left
        y = top
        lineHeight = 0
        spacing = self.spacing()
        max_width = rect.width() - left - right if rect.width() > 0 else 500

        for item in self.item_list:
            widget = item.widget()
            if not widget.isVisible():
                continue

            # 使用实际大小
            w = widget.width() if widget.width() > 0 else widget.sizeHint().width()
            h = widget.height() if widget.height() > 0 else widget.sizeHint().height()

            # 换行
            if x + w > left + max_width:
                x = left
                y += lineHeight + spacing
                lineHeight = 0

            if not testOnly:
                item.setGeometry(QRect(QPoint(x, y), QSize(w, h)))

            x += w + spacing
            lineHeight = max(lineHeight, h)

        totalHeight = y + lineHeight + bottom
        if not testOnly and self.parentWidget():
            self.parentWidget().setMinimumHeight(totalHeight)

        return totalHeight


# -------------------- 功能注册表 --------------------
FEATURE_REGISTRY = {
    "file_manager": FileManager,
    "settings": Settings,
    "video_page": VideoPage
}


# -------------------- 首页 & 主窗口 --------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("客户端主界面")
        self.resize(1130, 640)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)

        self.tabs.setStyleSheet("""
            QTabBar::tab {
                height: 24px;
                border: 1px solid #ccc;             
                padding: 4px 12px;
            }
            QTabBar::tab:selected {
                background: #0a64d8;
                color: white;
                border-radius: 4px;
            }
            QTabBar::tab:!selected {
                background: #f0f0f0;
                color: black;
                border-radius: 4px;
            }
        """)

        self.opened_tabs = {}

        # -------------------- 首页 --------------------
        self.home_widget = QWidget()
        self.home_layout = QVBoxLayout(self.home_widget)
        self.home_layout.setContentsMargins(20, 20, 20, 20)
        self.home_layout.setSpacing(10)

        self.card_area_widget = QWidget()
        outer_layout = QVBoxLayout(self.card_area_widget)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self.flow_widget = QWidget()
        self.card_area_layout = FlowLayout(self.flow_widget, margin=20, spacing=10)
        self.flow_widget.setLayout(self.card_area_layout)
        outer_layout.addWidget(self.flow_widget)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.card_area_widget)
        self.home_layout.addWidget(scroll)

        self.tabs.addTab(self.home_widget, "首页")
        self.tabs.tabBar().setTabButton(0, QTabBar.RightSide, None)  # 首页不可关闭

        # -------------------- 首页卡片 --------------------
        self.home_cards = []
        self.add_home_card("📁 文件管理", "file_manager")
        self.add_home_card("📹 监控视频", "video_page")
        self.add_home_card("⚙️ 设置", "settings")

        # -------------------- 右键菜单 --------------------
        self.tabs.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(self.tab_right_click)

    # 添加首页卡片
    def add_home_card(self, title: str, key: str):
        btn = QPushButton(title)
        btn.setFixedSize(140, 100)
        btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #ccc;
                border-radius: 6px;
                background-color: #fafafa;
            }
            QPushButton:hover {
                background-color: #e6f0ff;
            }
        """)
        btn.clicked.connect(lambda: self.open_feature(key))
        self.home_cards.append(btn)
        self.card_area_layout.addWidget(btn)

    # 打开功能 tab
    def open_feature(self, key: str):
        if key in self.opened_tabs:
            self.tabs.setCurrentWidget(self.opened_tabs[key])
            return

        widget_cls = FEATURE_REGISTRY.get(key)
        if not widget_cls:
            return

        widget = widget_cls()
        index = self.tabs.addTab(widget, getattr(widget, "TITLE", key))
        self.tabs.setCurrentIndex(index)
        self.opened_tabs[key] = widget

    # 关闭 tab
    def close_tab(self, index: int):
        if index == 0:
            return

        widget = self.tabs.widget(index)
        if widget:
            self.tabs.removeTab(index)
            widget.deleteLater()

        for k, v in list(self.opened_tabs.items()):
            if v == widget:
                del self.opened_tabs[k]

    # 右键菜单
    def tab_right_click(self, pos):
        index = self.tabs.tabBar().tabAt(pos)
        if index <= 0:
            return

        menu = QMenu()
        menu.addAction("关闭当前", lambda: self.close_tab(index))
        menu.addAction("关闭其它", lambda: self.close_other_tabs(index))
        menu.addAction("关闭右侧", lambda: self.close_right_tabs(index))
        menu.exec(self.tabs.tabBar().mapToGlobal(pos))

    # 关闭其它 tab
    def close_other_tabs(self, index):
        for i in reversed(range(self.tabs.count())):
            if i != 0 and i != index:
                self.close_tab(i)

    # 关闭右侧 tab
    def close_right_tabs(self, index):
        for i in reversed(range(index + 1, self.tabs.count())):
            self.close_tab(i)
