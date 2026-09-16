import sys

from PySide6.QtWidgets import QApplication

from ui.enhanced_window import EnhancedMainWindow


def run():
    app = QApplication(sys.argv)
    app.setApplicationName("Macro Recorder")
    app.setOrganizationName("Lxkgit")
    window = EnhancedMainWindow()
    window.show()
    return app.exec()
