import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow


def run():
    app = QApplication(sys.argv)
    app.setApplicationName("Macro Recorder")
    app.setOrganizationName("Lxkgit")
    window = MainWindow()
    window.show()
    return app.exec()
