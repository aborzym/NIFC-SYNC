import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow
from gui.theme import STYLESHEET, apply_widget_shadows


def main():
    application = QApplication(sys.argv)
    application.setApplicationName("NIFC-SYNC")
    application.setOrganizationName("NIFC-SYNC")
    application.setWindowIcon(
        QIcon(
            str(
                Path(__file__).resolve().parent
                / "assets"
                / "nifc-sync.svg"
            )
        )
    )
    application.setStyle("Fusion")
    application.setStyleSheet(STYLESHEET)

    window = MainWindow()
    apply_widget_shadows(window)
    window.show_ready_message()
    window.show()
    window.load_catalog()

    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
