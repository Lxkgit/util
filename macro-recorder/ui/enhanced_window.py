from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ui.macro_editor import MacroEditorDialog
from ui.main_window import MainWindow


class EnhancedMainWindow(MainWindow):
    def __init__(self):
        super().__init__()
        self._simplify_main_page()
        self._build_countdown_overlay()
        self._refresh()

    def _simplify_main_page(self):
        # 编辑相关内容全部移入独立宏编辑器，主页面只负责录制、播放和文件管理。
        self.list.hide()
        for widget in (
            self.edit_button,
            self.duplicate_button,
            self.up_button,
            self.down_button,
            self.delete_button,
        ):
            widget.hide()

        editor_button = QPushButton("✎  打开宏编辑器")
        editor_button.setMinimumHeight(38)
        editor_button.clicked.connect(self.open_macro_editor)
        controls = self.record_btn.parentWidget().layout()
        controls.addWidget(editor_button)
        self.editor_button = editor_button

        root = self.centralWidget()
        layout = root.layout()
        summary = QFrame()
        summary.setObjectName("macroSummary")
        summary.setStyleSheet(
            "QFrame#macroSummary{background:white;border:1px solid #e4e7ed;border-radius:12px;}"
            "QLabel#summaryTitle{font-size:16px;font-weight:700;}"
            "QLabel#summaryText{color:#7a8491;}"
        )
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(16, 12, 16, 12)
        title_box = QVBoxLayout()
        title = QLabel("当前宏")
        title.setObjectName("summaryTitle")
        self.summary_text = QLabel()
        self.summary_text.setObjectName("summaryText")
        title_box.addWidget(title)
        title_box.addWidget(self.summary_text)
        summary_layout.addLayout(title_box, 1)
        open_editor = QPushButton("编辑宏")
        open_editor.clicked.connect(self.open_macro_editor)
        summary_layout.addWidget(open_editor)
        # 原事件列表所在位置替换成简洁摘要。
        layout.insertWidget(layout.indexOf(self.progress) + 1, summary)
        self.summary_panel = summary

    def open_macro_editor(self):
        if self.recorder.recording or self._pending or self.player.running:
            self.status.setText("请先停止当前录制或播放，再打开宏编辑器")
            return
        dialog = MacroEditorDialog(self.events, self)
        if dialog.exec():
            self.events = dialog.events
            self._reload_event_list(-1)
            self.progress.setValue(0)
            self.status.setText(f"宏已更新，共 {len(self.events)} 个操作")
            self._refresh()

    def _refresh(self):
        super()._refresh()
        if hasattr(self, "summary_text"):
            if not self.events:
                self.summary_text.setText("暂无操作，可以录制新宏或打开编辑器手动创建")
            else:
                self.summary_text.setText(f"共 {len(self.events)} 个操作，双击“打开宏编辑器”进行详细编辑和安全预览")

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

    def _begin_recording(self):
        self.countdown_overlay.hide()
        super()._begin_recording()

    def closeEvent(self, event):
        if hasattr(self, "countdown_overlay"):
            self.countdown_overlay.hide()
        super().closeEvent(event)
