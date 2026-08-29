import sys

from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow


def main():
    application = QApplication(sys.argv)
    application.setApplicationName("NIFC-SYNC")
    application.setOrganizationName("NIFC-SYNC")

    window = MainWindow()
    window.show_ready_message()
    window.show()

    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
