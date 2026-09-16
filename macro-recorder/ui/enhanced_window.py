from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from ui.main_window import MainWindow


class EnhancedMainWindow(MainWindow):
    def __init__(self):
        super().__init__()
        self._build_countdown_overlay()
        self._play_restore_timer = QTimer(self)
        self._play_restore_timer.setSingleShot(True)
        self._play_restore_timer.timeout.connect(self._restore_after_playback)

    def _build_countdown_overlay(self):
        root = self.centralWidget()
        root.setStyleSheet(
            root.styleSheet()
            + "QFrame#countdownOverlay{background:white;border:2px solid #409eff;border-radius:18px;}"
            + "QLabel#countdownTitle{font-size:20px;font-weight:700;color:#303133;}"
            + "QLabel#countdownNumber{font-size:88px;font-weight:800;color:#409eff;}"
            + "QLabel#countdownHint{font-size:13px;color:#909399;}"
        )
        self.countdown_overlay = QFrame(root)
        self.countdown_overlay.setObjectName("countdownOverlay")
        self.countdown_overlay.setFixedSize(320, 240)
        overlay_layout = QVBoxLayout(self.countdown_overlay)
        overlay_layout.setContentsMargins(20, 18, 20, 18)
        overlay_layout.setSpacing(4)

        title = QLabel("准备录制")
        title.setObjectName("countdownTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.countdown_number = QLabel("3")
        self.countdown_number.setObjectName("countdownNumber")
        self.countdown_number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.countdown_hint = QLabel()
        self.countdown_hint.setObjectName("countdownHint")
        self.countdown_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        overlay_layout.addWidget(title)
        overlay_layout.addWidget(self.countdown_number, 1)
        overlay_layout.addWidget(self.countdown_hint)
        self.countdown_overlay.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._center_countdown()

    def _center_countdown(self):
        if not hasattr(self, "countdown_overlay"):
            return
        root = self.centralWidget()
        self.countdown_overlay.move(
            max(0, (root.width() - self.countdown_overlay.width()) // 2),
            max(0, (root.height() - self.countdown_overlay.height()) // 2),
        )
        self.countdown_overlay.raise_()

    def start_recording(self):
        super().start_recording()
        if self._pending and self.record_countdown > 0:
            self._show_countdown()

    def _show_countdown(self):
        self.countdown_number.setText(str(self._countdown_remaining))
        self.countdown_hint.setText(
            f"移动到目标窗口后开始\n按 {self.record_hotkey} 或 {self.stop_hotkey} 可取消"
        )
        self.countdown_overlay.show()
        self._center_countdown()

    def _countdown_tick(self):
        if not self._pending:
            self._countdown_timer.stop()
            self.countdown_overlay.hide()
            return
        self._countdown_remaining -= 1
        if self._countdown_remaining <= 0:
            self._countdown_timer.stop()
            self.countdown_overlay.hide()
            self._begin_recording()
            return
        self.countdown_number.setText(str(self._countdown_remaining))
        self.status.setText(f"准备录制：{self._countdown_remaining}")

    def cancel_record_countdown(self):
        super().cancel_record_countdown()
        self.countdown_overlay.hide()

    def stop_recording(self):
        super().stop_recording()
        self.countdown_overlay.hide()

    def stop_all(self):
        super().stop_all()
        self.countdown_overlay.hide()
        if self.isMinimized() and not self.player.running:
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def play(self):
        """播放屏幕级宏时最小化录制器，保持原尺寸，不干扰目标窗口和系统 UI。"""
        if self.recorder.recording:
            self.stop_recording()
        if not self.events:
            self.status.setText("没有可播放的操作，请先录制或加载宏。")
            return
        if self.player.running:
            return

        self._play_restore_timer.stop()
        if self.player.play(self.events, self.repeat.value()):
            self.status.setText("播放中：屏幕级键盘/鼠标操作")
            self._refresh()
            self.showMinimized()

    def _on_state(self, state: str):
        super()._on_state(state)
        if state in {"播放完成", "已停止"} or state.startswith("播放异常："):
            self._play_restore_timer.start(150)

    def _restore_after_playback(self):
        if self.player.running:
            return
        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()
        self._refresh()

    def _begin_recording(self):
        self.countdown_overlay.hide()
        super()._begin_recording()

    def closeEvent(self, event):
        self._play_restore_timer.stop()
        if hasattr(self, "countdown_overlay"):
            self.countdown_overlay.hide()
        super().closeEvent(event)
