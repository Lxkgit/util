import os
import vlc
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem,
    QFrame, QSizePolicy, QMenu
)
from PySide6.QtGui import QAction, QResizeEvent
from PySide6.QtCore import Qt


class VideoPage(QWidget):
    TITLE = "📹 监控视频"

    ICON_IDLE = "⚪ "     # 未播放
    ICON_PLAYING = "🟢 "  # 正在播放
    ICON_PAUSED = "🟡 "   # 已暂停

    def __init__(self):
        super().__init__()
        self.vlc_instance = vlc.Instance("--no-xlib")
        self.vlc_player = None
        self.current_name = None   # 当前播放的名称
        self.init_ui()

    def init_ui(self):

        main_layout = QVBoxLayout(self)

        frame = QFrame()
        h_layout = QHBoxLayout(frame)

        # 左侧列表
        self.list_widget = QListWidget()
        self.list_widget.setFixedWidth(200)
        self.list_widget.setStyleSheet("font-size: 15px;")
        self.list_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        # 必须开启右键菜单
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.open_context_menu)

        self.streams = {
            "摄像头1": "rtsp://49.232.129.253:8554/cam1"
        }

        # 初始化列表（全部设为 idle 图标）
        for name in self.streams:
            item = QListWidgetItem(self.ICON_IDLE + name)
            self.list_widget.addItem(item)

        self.list_widget.clicked.connect(self.on_stream_selected)
        h_layout.addWidget(self.list_widget)

        # 视频区域
        self.video_frame = QFrame()
        self.video_frame.setStyleSheet("background:black;")
        self.video_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        h_layout.addWidget(self.video_frame, 1)
        main_layout.addWidget(frame, 1)

    # =======================================================
    # 右键菜单
    # =======================================================
    def open_context_menu(self, position):
        item = self.list_widget.itemAt(position)
        if not item:
            return

        menu = QMenu(self)

        name = item.text().replace(self.ICON_IDLE, "").replace(self.ICON_PLAYING, "").replace(self.ICON_PAUSED, "")

        act_play = QAction("播放", self)

        if self.vlc_player and self.current_name == name and not self.vlc_player.is_playing():
            act_toggle = QAction("继续", self)
        else:
            act_toggle = QAction("暂停", self)

        act_close = QAction("关闭", self)

        act_play.triggered.connect(lambda: self.play_stream(item))
        act_toggle.triggered.connect(self.toggle_pause)
        act_close.triggered.connect(self.close_stream)

        menu.addAction(act_play)
        menu.addAction(act_toggle)
        menu.addAction(act_close)
        menu.exec(self.list_widget.mapToGlobal(position))

    # =======================================================
    # 列表状态图标更新
    # =======================================================
    def set_item_state(self, name, state):
        """
        state: idle / playing / paused
        """
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            raw_name = item.text().replace(self.ICON_IDLE, "").replace(self.ICON_PLAYING, "").replace(self.ICON_PAUSED, "")

            if raw_name == name:
                if state == "playing":
                    item.setText(self.ICON_PLAYING + raw_name)
                elif state == "paused":
                    item.setText(self.ICON_PAUSED + raw_name)
                else:
                    item.setText(self.ICON_IDLE + raw_name)
            else:
                # 非当前项全部显示空闲
                item.setText(self.ICON_IDLE + raw_name)

    # =======================================================
    # 播放选中项
    # =======================================================
    def play_stream(self, item):
        name = item.text().replace(self.ICON_IDLE, "").replace(self.ICON_PLAYING, "").replace(self.ICON_PAUSED, "")
        url = self.streams[name]
        self.start_play(name, url)

    def on_stream_selected(self):
        name = self.list_widget.currentItem().text().replace(self.ICON_IDLE, "").replace(self.ICON_PLAYING, "").replace(self.ICON_PAUSED, "")
        url = self.streams[name]
        self.start_play(name, url)

    # =======================================================
    # 播放封装
    # =======================================================
    def start_play(self, name, url):
        self.current_name = name
        print(f"▶ 播放: {name}")

        if self.vlc_player:
            self.vlc_player.stop()

        self.vlc_player = self.vlc_instance.media_player_new()
        media = self.vlc_instance.media_new(url, ":rtsp-tcp")
        self.vlc_player.set_media(media)

        wid = self.video_frame.winId()
        if os.name == "nt":
            self.vlc_player.set_hwnd(wid)
        else:
            self.vlc_player.set_xwindow(wid)

        self.vlc_player.play()

        # 更新播放状态
        self.set_item_state(name, "playing")

    # =======================================================
    # 暂停 / 继续
    # =======================================================
    def toggle_pause(self):
        if not self.vlc_player:
            return

        if self.vlc_player.is_playing():
            print("⏸ 暂停")
            self.vlc_player.pause()
            self.set_item_state(self.current_name, "paused")
        else:
            print("▶ 继续")
            self.vlc_player.play()
            self.set_item_state(self.current_name, "playing")

    # =======================================================
    # 关闭
    # =======================================================
    def close_stream(self):
        if self.vlc_player:
            print("■ 停止")
            self.vlc_player.stop()
            self.set_item_state(self.current_name, "idle")

    # =======================================================
    # 窗口调整
    # =======================================================
    def resizeEvent(self, event: QResizeEvent):
        if self.vlc_player:
            wid = self.video_frame.winId()
            if os.name == "nt":
                self.vlc_player.set_hwnd(wid)
            else:
                self.vlc_player.set_xwindow(wid)
        return super().resizeEvent(event)