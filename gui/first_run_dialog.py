from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from core.configuration import ConfigurationStore
from core.credentials import (
    CredentialStore,
    CredentialStoreError,
)
from core.setup import (
    SetupError,
    SetupRequest,
    complete_setup,
    verify_nifc_login,
)


class FirstRunDialog(QDialog):
    def __init__(
        self,
        configuration_store=None,
        credential_store=None,
        suggested_credentials=None,
        parent=None,
    ):
        super().__init__(parent)

        self.configuration_store = configuration_store or ConfigurationStore()
        self.credential_store = credential_store or CredentialStore()
        self.completed_configuration = None

        self.setWindowTitle("Pierwsza konfiguracja NIFC-SYNC")
        self.setMinimumSize(620, 540)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        title = QLabel("Skonfiguruj NIFC-SYNC")
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 3)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        description = QLabel(
            "Dane logowania zostaną zapisane w systemowym "
            "magazynie haseł. Istniejące foldery nie będą "
            "zmieniane ani przenoszone."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        layout.addWidget(self._create_account_group())
        layout.addWidget(self._create_storage_group())

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        save_button = buttons.button(QDialogButtonBox.Save)
        save_button.setText("Zapisz i kontynuuj")
        save_button.setIcon(QIcon())
        save_button.setObjectName("primaryButton")

        cancel_button = buttons.button(QDialogButtonBox.Cancel)
        cancel_button.setText("Anuluj")
        cancel_button.setIcon(QIcon())

        buttons.accepted.connect(self._complete_setup)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._restore_values(suggested_credentials)

    def _create_account_group(self):
        group = QGroupBox("Konto NIFC")
        layout = QVBoxLayout(group)

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Login")
        self.username_edit.setClearButtonEnabled(True)

        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("Hasło")
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setClearButtonEnabled(True)

        layout.addWidget(self.username_edit)
        layout.addWidget(self.password_edit)

        return group

    def _create_storage_group(self):
        group = QGroupBox("Katalog roboczy")
        layout = QVBoxLayout(group)

        storage_types = QHBoxLayout()
        self.local_radio = QRadioButton("Katalog lokalny")
        self.mounted_radio = QRadioButton("Katalog sieciowy / udział SMB")
        self.local_radio.setChecked(True)

        storage_types.addWidget(self.local_radio)
        storage_types.addWidget(self.mounted_radio)
        storage_types.addStretch()
        layout.addLayout(storage_types)

        self.network_options = QWidget()
        network_layout = QHBoxLayout(self.network_options)
        network_layout.setContentsMargins(0, 0, 0, 0)

        self.network_url_edit = QLineEdit()
        self.network_url_edit.setPlaceholderText(
            "Adres udziału, np. smb://serwer/udział"
        )
        self.network_url_edit.setClearButtonEnabled(True)

        self.network_connect_button = QPushButton("Połącz z udziałem")
        self.network_connect_button.clicked.connect(self._connect_to_network_share)

        network_layout.addWidget(
            self.network_url_edit,
            stretch=1,
        )
        network_layout.addWidget(self.network_connect_button)
        self.network_options.setVisible(False)
        layout.addWidget(self.network_options)

        destination_row = QHBoxLayout()
        self.destination_edit = QLineEdit()
        self.destination_edit.setPlaceholderText("Katalog docelowy")
        self.destination_edit.setClearButtonEnabled(True)

        browse_button = QPushButton("Wybierz…")
        browse_button.clicked.connect(self._choose_destination)

        destination_row.addWidget(
            self.destination_edit,
            stretch=1,
        )
        destination_row.addWidget(browse_button)
        layout.addLayout(destination_row)

        self.mounted_radio.toggled.connect(self.network_options.setVisible)

        return group

    def _restore_values(self, suggested_credentials):
        configuration = self.configuration_store.load()

        if configuration.destination is not None:
            self.destination_edit.setText(str(configuration.destination))
        self.network_url_edit.setText(configuration.network_url)
        if configuration.storage_kind == "mounted":
            self.mounted_radio.setChecked(True)

        if configuration.nifc_username:
            self.username_edit.setText(configuration.nifc_username)

        if suggested_credentials is not None:
            self.username_edit.setText(suggested_credentials.username)
            self.password_edit.setText(suggested_credentials.password)

    def _choose_destination(self):
        starting_directory = self.destination_edit.text().strip() or str(Path.home())
        selected_directory = QFileDialog.getExistingDirectory(
            self,
            "Wybierz katalog roboczy",
            starting_directory,
        )

        if selected_directory:
            self.destination_edit.setText(selected_directory)

    def _connect_to_network_share(self):
        url_value = self.network_url_edit.text().strip()
        url = QUrl.fromUserInput(url_value)

        if not url_value or not url.isValid() or url.scheme().lower() != "smb":
            QMessageBox.warning(
                self,
                "Nieprawidłowy adres udziału",
                "Podaj adres rozpoczynający się od smb://",
            )
            return

        if not QDesktopServices.openUrl(url):
            QMessageBox.warning(
                self,
                "Nie można otworzyć udziału",
                "System nie obsłużył podanego adresu SMB.",
            )

    def _selected_storage_kind(self):
        if self.mounted_radio.isChecked():
            return "mounted"

        return "local"

    def _complete_setup(self):
        destination_value = self.destination_edit.text().strip()
        request = SetupRequest(
            destination=(Path(destination_value) if destination_value else None),
            storage_kind=self._selected_storage_kind(),
            network_url=self.network_url_edit.text(),
            username=self.username_edit.text(),
            password=self.password_edit.text(),
        )

        try:
            verify_nifc_login(
                request.username,
                request.password,
            )
            self.completed_configuration = complete_setup(
                request,
                self.configuration_store,
                self.credential_store,
            )

        except (SetupError, CredentialStoreError) as error:
            QMessageBox.warning(
                self,
                "Nie można zapisać konfiguracji",
                str(error),
            )
            return

        self.accept()
