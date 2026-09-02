import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from core.configuration import ConfigurationStore
from core.migration import (
    LegacyCredentialError,
    legacy_credentials_path,
    load_legacy_credentials,
)
from gui.first_run_dialog import FirstRunDialog
from gui.main_window import MainWindow
from gui.theme import STYLESHEET, apply_widget_shadows


def ask_yes_no(
    title,
    text,
    default_yes=False,
):
    dialog = QDialog()
    dialog.setWindowTitle(title)
    dialog.setModal(True)
    dialog.setMinimumWidth(400)

    layout = QVBoxLayout(dialog)
    layout.setSpacing(18)

    message = QLabel(text)
    message.setAlignment(Qt.AlignCenter)
    message.setWordWrap(True)
    layout.addWidget(message)

    yes_button = QPushButton("Tak")
    no_button = QPushButton("Nie")

    yes_button.setMinimumWidth(112)
    no_button.setMinimumWidth(112)

    default_button = yes_button if default_yes else no_button
    default_button.setObjectName("primaryButton")
    default_button.setDefault(True)
    default_button.setAutoDefault(True)

    yes_button.clicked.connect(dialog.accept)
    no_button.clicked.connect(dialog.reject)

    button_layout = QHBoxLayout()
    button_layout.addStretch()
    button_layout.addWidget(yes_button)
    button_layout.addWidget(no_button)
    button_layout.addStretch()
    layout.addLayout(button_layout)

    return dialog.exec() == QDialog.Accepted


def run_first_setup():

    configuration_store = ConfigurationStore()
    configuration = configuration_store.load()

    if configuration.setup_completed:
        return True

    suggested_credentials = None
    legacy_file = legacy_credentials_path()
    imported_legacy_credentials = False

    if legacy_file.exists() and ask_yes_no(
        "Dane logowania z wersji 3.0",
        "Znaleziono dotychczasowe dane logowania NIFC. "
        "Czy wczytać je do konfiguracji 4.0?",
        default_yes=True,
    ):
        try:
            suggested_credentials = load_legacy_credentials(legacy_file)
            imported_legacy_credentials = suggested_credentials is not None
        except LegacyCredentialError as error:
            QMessageBox.warning(
                None,
                "Nie można wczytać danych",
                str(error),
            )

    dialog = FirstRunDialog(
        configuration_store=configuration_store,
        suggested_credentials=suggested_credentials,
    )

    if dialog.exec() != QDialog.Accepted:
        return False

    if imported_legacy_credentials and ask_yes_no(
        "Stary plik danych logowania",
        "Dane zostały zapisane w systemowym magazynie "
        "haseł. Czy usunąć stary plik tekstowy?",
        default_yes=False,
    ):
        try:
            legacy_file.unlink()
        except OSError:
            QMessageBox.warning(
                None,
                "Nie można usunąć pliku",
                "Stary plik danych logowania nie został usunięty.",
            )
    return True


def main():
    application = QApplication(sys.argv)
    application.setApplicationName("NIFC-SYNC")
    application.setOrganizationName("NIFC-SYNC")
    application.setWindowIcon(
        QIcon(str(Path(__file__).resolve().parent / "assets" / "nifc-sync.svg"))
    )
    application.setStyle("Fusion")
    application.setStyleSheet(STYLESHEET)

    if not run_first_setup():
        return 0

    window = MainWindow()
    apply_widget_shadows(window)
    window.show_ready_message()
    window.show()
    window.load_catalog()

    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
