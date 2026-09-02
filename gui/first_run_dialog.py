import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox,
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
from core.organization_profiles import (
    list_organization_profiles,
)
from core.setup import (
    SetupError,
    SetupRequest,
    complete_setup,
    verify_nifc_login,
)
from gui.network_dialog import NetworkBrowserDialog


class FirstRunDialog(QDialog):
    def __init__(
        self,
        configuration_store=None,
        credential_store=None,
        suggested_credentials=None,
        initial_setup=True,
        new_account=False,
        parent=None,
    ):
        super().__init__(parent)

        self.configuration_store = configuration_store or ConfigurationStore()
        self.credential_store = credential_store or CredentialStore()
        self.completed_configuration = None
        self.initial_setup = initial_setup
        self.new_account = new_account
        self.setWindowTitle(
            "Dodaj konto NIFC-SYNC"
            if new_account
            else (
                "Pierwsza konfiguracja NIFC-SYNC"
                if initial_setup
                else "Ustawienia NIFC-SYNC"
            )
        )
        self.setMinimumWidth(620)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        title = QLabel(
            "Dodaj konto"
            if new_account
            else ("Skonfiguruj NIFC-SYNC" if initial_setup else "Ustawienia NIFC-SYNC")
        )
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 3)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        if new_account:
            description_text = (
                "Podaj nazwę konta, dane logowania NIFC "
                "oraz jego własny katalog roboczy."
            )
        elif initial_setup:
            description_text = (
                "Dane logowania zostaną zapisane w systemowym "
                "magazynie haseł. Istniejące foldery nie będą "
                "zmieniane ani przenoszone."
            )
        else:
            description_text = (
                "Zmień nazwę konta, dane logowania NIFC, "
                "katalog roboczy lub konfigurację udziału "
                "sieciowego."
            )

        description = QLabel(description_text)
        description.setWordWrap(True)
        layout.addWidget(description)

        layout.addWidget(self._create_account_group())
        layout.addWidget(self._create_organization_group())
        layout.addWidget(self._create_storage_group())

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        save_button = buttons.button(QDialogButtonBox.Save)
        save_button.setText(
            "Utwórz konto"
            if new_account
            else ("Zapisz i kontynuuj" if initial_setup else "Zapisz ustawienia")
        )
        save_button.setIcon(QIcon())
        save_button.setObjectName("primaryButton")

        cancel_button = buttons.button(QDialogButtonBox.Cancel)
        cancel_button.setText("Anuluj")
        cancel_button.setIcon(QIcon())

        buttons.accepted.connect(self._complete_setup)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if not self.new_account:
            self._restore_values(suggested_credentials)

    def _create_account_group(self):
        group = QGroupBox("Konto NIFC")
        layout = QVBoxLayout(group)

        self.account_name_edit = QLineEdit()
        self.account_name_edit.setPlaceholderText("Nazwa konta, np. Andrzej")
        self.account_name_edit.setClearButtonEnabled(True)

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Login")
        self.username_edit.setClearButtonEnabled(True)

        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("Hasło")
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setClearButtonEnabled(True)

        layout.addWidget(self.account_name_edit)
        layout.addWidget(self.username_edit)
        layout.addWidget(self.password_edit)

        return group

    def _create_organization_group(self):
        group = QGroupBox("Organizacja plików")
        layout = QVBoxLayout(group)

        self.organization_profile_combo = QComboBox()

        for profile in list_organization_profiles():
            self.organization_profile_combo.addItem(
                profile.display_name,
                profile.profile_id,
            )

        self.organization_description = QLabel()
        self.organization_description.setWordWrap(True)
        self.organization_description.setObjectName("subtitle")

        self.organization_profile_combo.currentIndexChanged.connect(
            self._update_organization_description
        )

        layout.addWidget(self.organization_profile_combo)
        layout.addWidget(self.organization_description)

        self._update_organization_description(
            self.organization_profile_combo.currentIndex()
        )

        return group

    def _update_organization_description(self, index):
        profile_id = self.organization_profile_combo.itemData(index)
        description = ""

        for profile in list_organization_profiles():
            if profile.profile_id == profile_id:
                description = profile.description
                break

        self.organization_description.setText(description)

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
        self.network_url_edit.setPlaceholderText("Adres wybranego udziału SMB")
        self.network_url_edit.setClearButtonEnabled(True)

        self.network_connect_button = QPushButton("Przeglądaj sieć")
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

        self.mounted_radio.toggled.connect(self._set_network_options_visible)
        return group

    def _restore_values(self, suggested_credentials):
        configuration = self.configuration_store.load()

        profile_index = self.organization_profile_combo.findData(
            configuration.naming_profile
        )

        if profile_index >= 0:
            self.organization_profile_combo.setCurrentIndex(profile_index)

        active_account_id = self.configuration_store.active_account_id()

        for account in self.configuration_store.list_accounts():
            if account.account_id == active_account_id:
                self.account_name_edit.setText(account.name)
                break

        if configuration.destination is not None:
            self.destination_edit.setText(str(configuration.destination))
        self.network_url_edit.setText(configuration.network_url)
        self.network_url_edit.setReadOnly(True)
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
        dialog = NetworkBrowserDialog(self)

        if dialog.exec() != QDialog.Accepted:
            return

        share = dialog.selected_share

        if share is None:
            return

        self.network_url_edit.setText(share.uri)

        if sys.platform == "darwin":
            starting_directory = Path("/Volumes")
        elif sys.platform.startswith("linux"):
            starting_directory = Path("/run/user") / str(os.getuid()) / "gvfs"
        else:
            starting_directory = Path.home()

        if not starting_directory.exists():
            starting_directory = Path.home()

        selected_directory = QFileDialog.getExistingDirectory(
            self,
            "Wybierz katalog w zamontowanym udziale",
            str(starting_directory),
        )

        if selected_directory:
            self.destination_edit.setText(selected_directory)

    def _set_network_options_visible(self, visible):
        top_left = self.frameGeometry().topLeft()
        self.network_options.setVisible(visible)

        if self.isVisible():
            QTimer.singleShot(
                0,
                lambda: self._resize_from_top(top_left),
            )

    def _resize_from_top(self, top_left):
        self.adjustSize()
        self.move(top_left)

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
            account_name=self.account_name_edit.text(),
            organization_profile_id=(self.organization_profile_combo.currentData()),
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
                create_new_account=self.new_account,
            )

        except (SetupError, CredentialStoreError) as error:
            QMessageBox.warning(
                self,
                "Nie można zapisać konfiguracji",
                str(error),
            )
            return

        self.accept()
