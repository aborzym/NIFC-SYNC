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
    QGridLayout,
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

from core.configuration import (
    ConfigurationStore,
    OrganizationPath,
)
from core.credentials import (
    CredentialStore,
    CredentialStoreError,
)
from core.libraries import (
    library_scans_path_key,
    library_transcriptions_path_key,
    list_known_libraries,
)
from core.organization_profiles import (
    list_organization_profiles,
)
from core.setup import (
    SetupError,
    SetupRequest,
    complete_setup,
    remove_obsolete_credentials,
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
        self.resize(620, 680)
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

        account_group = self._create_account_group()
        organization_group = self._create_organization_group()
        storage_group = self._create_storage_group()

        layout.addStretch(1)
        layout.addWidget(account_group)
        layout.addStretch(1)
        layout.addWidget(organization_group)
        layout.addStretch(1)
        layout.addWidget(storage_group)
        layout.addStretch(1)

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

        self.account_name_edit.setToolTip(
            "Nazwa wyświetlana na liście kont, "
            "np. imię użytkownika.\n"
            "Nie musi być taka sama jak login NIFC."
        )

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

        self.library_paths_group = self._create_library_paths_group()
        layout.addSpacing(20)
        layout.addWidget(self.library_paths_group)

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
        show_library_paths = profile_id == "marta-lawrence"
        self.library_paths_group.setVisible(show_library_paths)

        if hasattr(self, "storage_group"):
            self._update_storage_labels(profile_id)

        if self.isVisible():
            top_left = self.frameGeometry().topLeft()
            QTimer.singleShot(
                0,
                lambda: self._resize_from_top(top_left),
            )

    def _create_library_paths_group(self):
        group = QGroupBox("Foldery bibliotek")
        layout = QGridLayout(group)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)

        library_header = QLabel("Biblioteka")
        transcriptions_header = QLabel("Folder transkrypcji")
        scans_header = QLabel("Folder skanów")

        layout.addWidget(library_header, 0, 0)
        layout.addWidget(transcriptions_header, 0, 1)
        layout.addWidget(scans_header, 0, 3)

        self.organization_path_edits = {}

        for row, (
            library_id,
            display_name,
        ) in enumerate(
            list_known_libraries(),
            start=1,
        ):
            library_label = QLabel(display_name)

            transcriptions_edit = QLineEdit()
            transcriptions_edit.setPlaceholderText("Opcjonalnie")
            transcriptions_edit.setClearButtonEnabled(True)
            transcriptions_edit.setToolTip(
                "<b>Folder transkrypcji</b><br>"
                "Tutaj będą zapisywane transkrypcje "
                f"biblioteki {display_name}.<br><br>"
                "Pole jest opcjonalne.<br>"
                "Folder zostanie utworzony dopiero przy "
                "pierwszym zapisie pliku."
            )

            transcriptions_button = QPushButton("Wybierz…")
            transcriptions_button.setToolTip(
                "Wybierz istniejący folder "
                "transkrypcji.<br>"
                "Nową ścieżkę możesz wpisać ręcznie."
            )

            transcriptions_button.clicked.connect(
                lambda _checked=False, edit=transcriptions_edit: (
                    self._choose_organization_path(edit)
                )
            )

            scans_edit = QLineEdit()
            scans_edit.setPlaceholderText("Opcjonalnie")
            scans_edit.setClearButtonEnabled(True)
            scans_edit.setToolTip(
                "<b>Folder skanów</b><br>"
                "Tutaj będą zapisywane skany "
                f"biblioteki {display_name}.<br><br>"
                "Pole jest opcjonalne.<br>"
                "Folder zostanie utworzony dopiero przy "
                "pierwszym pobraniu skanów."
            )

            scans_button = QPushButton("Wybierz…")
            scans_button.setToolTip(
                "Wybierz istniejący folder skanów.<br>"
                "Nową ścieżkę możesz wpisać ręcznie."
            )

            scans_button.clicked.connect(
                lambda _checked=False, edit=scans_edit: self._choose_organization_path(
                    edit
                )
            )

            transcriptions_key = library_transcriptions_path_key(library_id)
            scans_key = library_scans_path_key(library_id)
            self.organization_path_edits[transcriptions_key] = transcriptions_edit
            self.organization_path_edits[scans_key] = scans_edit

            layout.addWidget(library_label, row, 0)
            layout.addWidget(
                transcriptions_edit,
                row,
                1,
            )
            layout.addWidget(
                transcriptions_button,
                row,
                2,
            )
            layout.addWidget(scans_edit, row, 3)
            layout.addWidget(scans_button, row, 4)

        group.setVisible(False)
        return group

    def _choose_organization_path(self, edit):
        starting_directory = edit.text().strip() or self.destination_edit.text().strip()
        selected_directory = QFileDialog.getExistingDirectory(
            self,
            "Wybierz folder",
            starting_directory,
        )

        if selected_directory:
            edit.setText(selected_directory)

    def _update_storage_labels(self, profile_id):
        if profile_id == "marta-lawrence":
            self.storage_group.setTitle("Folder nadrzędny")
            self.destination_edit.setPlaceholderText("Folder nadrzędny, np. Pulpit")
            self.destination_edit.setToolTip(
                "<b>Folder nadrzędny</b><br>"
                "W nim będą umieszczane skonfigurowane "
                "foldery bibliotek.<br><br>"
                "Sam wybór tego folderu nie tworzy "
                "katalogów transkrypcji ani skanów."
            )
            return

        if profile_id == "andrzej-kubiczek":
            self.storage_group.setTitle("Folder nadrzędny")
            self.destination_edit.setPlaceholderText(
                "Folder nadrzędny katalogów rocznych"
            )
            self.destination_edit.setToolTip(
                "<b>Folder nadrzędny</b><br>"
                "Program zapisze pliki w katalogu "
                "&lt;rok&gt;/in progress, osobno dla "
                "workflow diplomatic, modern i XML.<br><br>"
                "Foldery zostaną utworzone dopiero podczas "
                "pierwszej synchronizacji."
            )
            return

        self.storage_group.setTitle("Katalog roboczy")
        self.destination_edit.setPlaceholderText("Katalog docelowy")
        self.destination_edit.setToolTip("")

    def _create_storage_group(self):
        self.storage_group = QGroupBox("Katalog roboczy")
        layout = QVBoxLayout(self.storage_group)
        storage_types = QHBoxLayout()
        self.local_radio = QRadioButton("Katalog lokalny")
        self.local_radio.setMinimumWidth(155)

        self.mounted_radio = QRadioButton("Katalog sieciowy / udział SMB")
        self.mounted_radio.setMinimumWidth(230)

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
        self._update_storage_labels(self.organization_profile_combo.currentData())

        return self.storage_group

    def _restore_values(self, suggested_credentials):
        configuration = self.configuration_store.load()

        profile_index = self.organization_profile_combo.findData(
            configuration.naming_profile
        )

        if profile_index >= 0:
            self.organization_profile_combo.setCurrentIndex(profile_index)

        for organization_path in configuration.organization_paths:
            edit = self.organization_path_edits.get(organization_path.key)

            if edit is not None:
                edit.setText(str(organization_path.path))

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
        profile_id = self.organization_profile_combo.currentData()
        dialog_title = (
            "Wybierz folder nadrzędny"
            if profile_id
            in (
                "marta-lawrence",
                "andrzej-kubiczek",
            )
            else "Wybierz katalog roboczy"
        )

        selected_directory = QFileDialog.getExistingDirectory(
            self,
            dialog_title,
            self.destination_edit.text().strip(),
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
        organization_paths = tuple(
            OrganizationPath(
                key=key,
                path=Path(value),
            )
            for key, edit in (self.organization_path_edits.items())
            if (value := edit.text().strip())
        )

        request = SetupRequest(
            destination=(Path(destination_value) if destination_value else None),
            storage_kind=self._selected_storage_kind(),
            username=self.username_edit.text(),
            password=self.password_edit.text(),
            account_name=self.account_name_edit.text(),
            organization_profile_id=(self.organization_profile_combo.currentData()),
            organization_paths=organization_paths,
            network_url=self.network_url_edit.text(),
        )

        previous_username = (
            "" if self.new_account else self.configuration_store.load().nifc_username
        )

        try:
            excluded_account_id = (
                None
                if self.new_account
                else self.configuration_store.active_account_id()
            )
            account_name = request.account_name.strip()

            self.configuration_store.validate_nifc_username(
                request.username,
                excluded_account_id=excluded_account_id,
            )
            self.configuration_store.validate_account_name(
                account_name,
                excluded_account_id=excluded_account_id,
            )

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

        except (
            SetupError,
            CredentialStoreError,
            ValueError,
        ) as error:
            QMessageBox.warning(
                self,
                "Nie można zapisać konfiguracji",
                str(error),
            )
            return

        try:
            remove_obsolete_credentials(
                previous_username,
                self.completed_configuration.nifc_username,
                self.configuration_store,
                self.credential_store,
            )
        except CredentialStoreError as error:
            QMessageBox.warning(
                self,
                "Pozostały stare dane logowania",
                (
                    "Ustawienia zostały zapisane, ale nie udało "
                    "się usunąć poprzednich danych logowania.\n\n"
                    f"{error}"
                ),
            )

        self.accept()
