import sys

from PySide6.QtWidgets import QApplication

from ui.enhanced_window import EnhancedMainWindow
from ui.macro_editor import PointPicker


def _patch_point_picker():
    """确保选点后已选绿色标记立即重绘。"""
    original = PointPicker.mousePressEvent
    if getattr(original, "_instant_repaint", False):
        return

    def mouse_press_event(self, event):
        original(self, event)
        if event.button().name == "LeftButton":
            self.repaint()

    mouse_press_event._instant_repaint = True
    PointPicker.mousePressEvent = mouse_press_event


def run():
    app = QApplication(sys.argv)
    app.setApplicationName("Macro Recorder")
    app.setOrganizationName("Lxkgit")
    _patch_point_picker()
    window = EnhancedMainWindow()
    window.show()
    return app.exec()
