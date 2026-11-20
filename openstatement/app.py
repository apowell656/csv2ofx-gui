import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QStyleFactory

from .resources import app_icon_path
from .ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    # Name the app explicitly so saved profiles live in the same AppData folder
    # whether it runs as the packaged app or from source (where Qt would use "Python").
    app.setApplicationName("OpenStatement")
    app.setStyle(QStyleFactory.create("Fusion"))
    icon_path = app_icon_path()
    if icon_path is not None:
        app.setWindowIcon(QIcon(str(icon_path)))
    window = MainWindow()
    if icon_path is not None:
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()
    sys.exit(app.exec())
