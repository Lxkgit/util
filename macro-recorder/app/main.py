import sys

from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import QApplication

# 兼容 PointPicker 中旧版 QGuiApplication.cursor() 的调用。
if not hasattr(QGuiApplication, "cursor"):
    QGuiApplication.cursor = staticmethod(QCursor.pos)

from ui.enhanced_window import EnhancedMainWindow


def run():
    app = QApplication(sys.argv)
    app.setApplicationName("Macro Recorder")
    app.setOrganizationName("Lxkgit")
    window = EnhancedMainWindow()
    window.show()
    return app.exec()
