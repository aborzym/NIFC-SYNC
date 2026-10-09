from dataclasses import replace
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThread, QTimer
from PySide6.QtGui import QFontDatabase, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core import __version__
from core.configuration import ConfigurationStore
from core.credentials import (
    CredentialStore,
    CredentialStoreError,
)
from core.destinations import (
    scan_package_folder_name,
)
from core.filesystem import format_file_size
from core.network import (
    find_mounted_smb_path,
    format_smb_location,
)
from core.scan_manifest import (
    validate_scan_manifest,
)
from core.scan_sync import ScanDownloadRequest
from core.settlement_store import SettlementStore
from core.settlements import compare_statistics
from core.submission import (
    find_configured_submission_files,
    inspect_submission_file,
)
from gui.first_run_dialog import FirstRunDialog
from gui.network_dialog import NetworkBrowserDialog
from gui.scan_dialog import ScanSelectionDialog
from gui.statistics_dialog import StatisticsDialog
from gui.submission_dialog import (
    SubmissionPreviewDialog,
    SubmissionSelectionDialog,
)
from gui.updater import UpdateManager
from gui.workers import (
    CatalogLoader,
    PolishMusicSourcesLookupWorker,
    ScanDownloadWorker,
    SubmissionWorker,
    SyncWorker,
)
from providers import polish_music_sources


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.configuration_store = ConfigurationStore()
        self.credential_store = CredentialStore()
        self.setWindowTitle(f"NIFC-SYNC {__version__}")
        self.setMinimumSize(760, 560)
        self.workflows = {}
        self.catalog_thread = None
        self.catalog_worker = None
        self.sync_thread = None
        self.sync_worker = None
        self.submission_thread = None
        self.submission_worker = None
        self.submission_succeeded = False
        self.scan_thread = None
        self.scan_worker = None
        self.lookup_thread = None
        self.lookup_worker = None
        self.pending_summary = None
        self.pending_scan_plans = ()
        self.activity_frame = 0
        self.activity_colors = (
            "#315fb9",
            "#3d6fc8",
            "#4b80d8",
            "#5e91e5",
            "#73a2ef",
            "#8fb7ff",
            "#73a2ef",
            "#5e91e5",
            "#4b80d8",
            "#3d6fc8",
        )
        self.activity_timer = QTimer(self)
        self.activity_timer.setInterval(110)
        self.activity_timer.timeout.connect(self._animate_activity_indicator)

        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(18)

        main_layout.addLayout(self._create_header())
        main_layout.addWidget(self._create_workflow_group())
        main_layout.addWidget(self._create_destination_group())

        self.sync_button = QPushButton("Synchronizuj")
        self.sync_button.setObjectName("primaryButton")
        self.sync_button.setEnabled(False)
        self.sync_button.setMinimumHeight(42)
        self.sync_button.clicked.connect(self._start_synchronization)

        action_layout = QHBoxLayout()
        action_layout.addWidget(self.sync_button, stretch=1)

        self.submit_button = QPushButton("Wyślij plik")
        self.submit_button.setMinimumHeight(42)
        self.submit_button.setEnabled(False)
        self.submit_button.clicked.connect(self._open_submission_dialog)
        action_layout.addWidget(self.submit_button)

        self.statistics_button = QPushButton("Rozliczenia…")
        self.statistics_button.setMinimumHeight(42)
        self.statistics_button.clicked.connect(self._open_statistics_dialog)
        action_layout.addWidget(self.statistics_button)

        self.unpaid_summary_label = QLabel("Niewypłacone: —")
        summary_font = self.unpaid_summary_label.font()
        summary_font.setPointSize(32)
        summary_font.setBold(True)
        self.unpaid_summary_label.setFont(summary_font)
        self.unpaid_summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.unpaid_summary_label.setStyleSheet(
            "font-size: 22px; font-weight: 700; color: #73a2ef;"
        )
        self.unpaid_summary_label.setWordWrap(True)
        main_layout.addWidget(self.unpaid_summary_label)

        self.unpaid_updated_label = QLabel("")
        self.unpaid_updated_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.unpaid_updated_label)

        main_layout.addLayout(action_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        main_layout.addWidget(self.progress_bar)

        log_label = QLabel("Dziennik")
        log_label_font = log_label.font()
        log_label_font.setBold(True)
        log_label.setFont(log_label_font)
        log_header = QHBoxLayout()
        log_header.addWidget(log_label)
        log_header.addStretch()
        self.activity_indicator = QLabel("")
        self.activity_indicator.setObjectName("activityIndicator")
        self.activity_indicator.setFixedWidth(12)
        self.activity_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        log_header.addWidget(self.activity_indicator)
        self.progress_stage_label = QLabel("")
        self.progress_stage_label.setObjectName("progressStage")
        log_header.addWidget(self.progress_stage_label)
        main_layout.addLayout(log_header)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        )
        self.log_view.setPlaceholderText("Tutaj pojawi się przebieg synchronizacji.")
        main_layout.addWidget(self.log_view, stretch=1)

        self.setCentralWidget(central_widget)
        self.copyright_label = QLabel(
            f"© 2026 Andrzej Borzym · NIFC-SYNC {__version__}"
        )
        self.copyright_label.setObjectName("copyrightLabel")
        self.statusBar().addPermanentWidget(self.copyright_label)
        self.statusBar().showMessage("Gotowy")

        self._restore_settings()
        self._populate_account_selector()
        self.destination_edit.textChanged.connect(self._update_sync_button)

        self.update_manager = UpdateManager(
            self,
            settings=QSettings(),
            current_version=__version__,
        )
        self.update_button = QPushButton("Sprawdź aktualizacje…")
        self.update_button.setObjectName("smallButton")
        self.update_button.clicked.connect(
            lambda: self._check_for_updates(show_current_message=True)
        )
        main_layout.addWidget(
            self.update_button,
            alignment=Qt.AlignmentFlag.AlignRight,
        )
        QTimer.singleShot(2500, self._check_for_updates)

    def _open_statistics_dialog(self):
        if self._is_busy():
            return

        dialog = StatisticsDialog(self.configuration_store, self)
        try:
            dialog.exec()
        finally:
            self._refresh_unpaid_summary()
            dialog.deleteLater()

    def _refresh_unpaid_summary(self):
        self.unpaid_summary_label.hide()
        self.unpaid_updated_label.hide()
        self.unpaid_summary_label.setText("Niewypłacone: —")
        self.unpaid_updated_label.setText("Otwórz rozliczenia i odśwież dane.")

        try:
            configuration = self.configuration_store.load()
            store = SettlementStore(self.configuration_store)
            settlements, approved = store.load()
            snapshot = store.snapshot
            if snapshot is None:
                return
            if snapshot["start_date"] != configuration.statistics_start_month:
                self.unpaid_updated_label.setText(
                    "Zmieniono okres — odśwież statystyki w rozliczeniach."
                )
                return
            if not settlements:
                self.unpaid_updated_label.setText(
                    "Dodaj PDF-y wypłaconych transz w rozliczeniach."
                )
                return

            paid_entries = [
                item
                for settlement in settlements.values()
                for item in settlement["entries"]
            ]
            result = compare_statistics(snapshot["entries"], paid_entries, approved)
            count = f"{result['unpaid_total']:,}".replace(",", " ")
            refreshed = datetime.fromisoformat(snapshot["refreshed_at"])
            detail = f"Odświeżono: {refreshed.strftime('%d.%m.%Y, %H:%M')}"
            if result["unresolved_total"]:
                pending = f"{result['unresolved_total']:,}".replace(",", " ")
                detail += f" · Do wyjaśnienia: {pending} znaków"

            self.unpaid_summary_label.setText(f"Niewypłacone: {count} znaków")
            self.unpaid_updated_label.setText(detail)
            self.unpaid_summary_label.show()
            self.unpaid_updated_label.show()
        except (OSError, ValueError, TypeError, KeyError):
            self.unpaid_updated_label.setText(
                "Nie można odczytać rozliczeń. Otwórz okno „Rozliczenia…”."
            )

    def _is_busy(self):

        if self.findChild(StatisticsDialog) is not None:
            return True

        threads = (
            self.catalog_thread,
            self.sync_thread,
            self.scan_thread,
            self.submission_thread,
            self.lookup_thread,
        )
        return any(thread is not None and thread.isRunning() for thread in threads)

    def _check_for_updates(self, *, show_current_message=False):
        if self._is_busy():
            if show_current_message:
                QMessageBox.information(
                    self,
                    "NIFC-SYNC pracuje",
                    "Sprawdź aktualizacje po zakończeniu bieżącej operacji.",
                )
            else:
                QTimer.singleShot(15000, self._check_for_updates)
            return

        self.update_manager.check_for_updates(show_current_message=show_current_message)

    def _create_header(self):
        layout = QHBoxLayout()
        layout.setSpacing(12)

        self.brand_mark = QLabel()
        self.brand_mark.setObjectName("brandMark")
        self.brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brand_mark.setFixedSize(42, 42)
        icon_path = Path(__file__).resolve().parent.parent / "assets" / "sync.svg"
        icon = QPixmap(str(icon_path)).scaled(
            32,
            32,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.brand_mark.setPixmap(icon)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        title = QLabel("NIFC-SYNC")
        title.setObjectName("title")
        subtitle = QLabel("Synchronizacja transkrypcji i skanów źródłowych")
        subtitle.setObjectName("subtitle")
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)

        self.connection_label = QLabel("Nie połączono")
        self.connection_label.setObjectName("connectionStatus")
        self.connection_label.setProperty("connected", False)
        self.connection_dot = QLabel()
        self.connection_dot.setObjectName("connectionDot")
        self.connection_dot.setProperty(
            "state",
            "disconnected",
        )
        self.connection_dot.setFixedSize(8, 8)
        self.connection_button = QPushButton("Połącz")
        self.connection_button.setObjectName("smallButton")
        self.connection_button.setFixedWidth(132)
        self.connection_button.setProperty(
            "connectionAction",
            "connect",
        )
        self.connection_button.setEnabled(True)
        self.connection_button.clicked.connect(self._toggle_connection)
        self.account_combo = QComboBox()
        self.account_combo.setObjectName("accountSelector")
        self.account_combo.setMinimumWidth(130)
        self.account_combo.setMaximumWidth(180)
        self.account_combo.currentIndexChanged.connect(self._change_active_account)
        self.settings_button = QPushButton("Ustawienia")
        self.settings_button.setObjectName("smallButton")
        self.settings_button.setFixedWidth(100)
        self.settings_button.clicked.connect(self._open_settings)
        layout.addWidget(self.brand_mark)
        layout.addLayout(title_layout)
        layout.addStretch()
        layout.addWidget(self.account_combo)
        layout.addWidget(self.settings_button)
        status_layout = QHBoxLayout()
        status_layout.setSpacing(6)
        status_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        status_layout.addWidget(self.connection_dot)
        status_layout.addWidget(self.connection_label)
        layout.addLayout(status_layout)
        layout.addWidget(self.connection_button)

        return layout

    def _create_workflow_group(self):
        group = QGroupBox("Rodzaj transkrypcji")
        layout = QHBoxLayout(group)

        self.diplomatic_radio = QRadioButton("KRN diplomatic")
        self.modern_radio = QRadioButton("KRN modern")
        self.xml_radio = QRadioButton("XML")
        self.diplomatic_radio.setChecked(True)

        layout.addWidget(self.diplomatic_radio)
        layout.addWidget(self.modern_radio)
        layout.addWidget(self.xml_radio)
        layout.addStretch()

        return group

    def _create_destination_group(self):
        self.destination_group = QGroupBox("Katalog docelowy")
        layout = QHBoxLayout(self.destination_group)
        self.destination_path = None
        self.destination_edit = QLineEdit()
        self.destination_edit.setPlaceholderText("Katalog docelowy")
        self.destination_edit.setReadOnly(True)
        self.browse_button = QPushButton("Wybierz…")
        self.browse_button.clicked.connect(self._choose_destination)

        layout.addWidget(self.destination_edit, stretch=1)
        layout.addWidget(self.browse_button)

        return self.destination_group

    def _destination_display_text(
        self,
        configuration,
    ):
        if configuration.destination is None:
            return ""

        if configuration.storage_kind == "mounted" and configuration.network_url:
            return format_smb_location(configuration.network_url)

        return str(configuration.destination)

    def _choose_destination(self):
        configuration = self.configuration_store.load()
        dialog_title = (
            "Wybierz folder nadrzędny"
            if configuration.naming_profile
            in (
                "marta-lawrence",
                "andrzej-kubiczek",
            )
            else "Wybierz katalog docelowy"
        )

        starting_directory = (
            str(self.destination_path) if self.destination_path is not None else ""
        )
        selected_directory = QFileDialog.getExistingDirectory(
            self,
            dialog_title,
            starting_directory,
        )

        if selected_directory:
            self.destination_path = Path(selected_directory)
            updated_configuration = replace(
                configuration,
                destination=self.destination_path,
            )
            self.destination_edit.setText(
                self._destination_display_text(updated_configuration)
            )

    def _open_settings(self):
        if any(
            thread is not None
            for thread in (
                self.catalog_thread,
                self.sync_thread,
                self.scan_thread,
            )
        ):
            QMessageBox.information(
                self,
                "Operacja w toku",
                "Poczekaj na zakończenie bieżącej operacji.",
            )
            return

        configuration = self.configuration_store.load()

        try:
            credentials = self.credential_store.load(configuration.nifc_username)
        except CredentialStoreError as error:
            QMessageBox.warning(
                self,
                "Nie można odczytać danych logowania",
                str(error),
            )
            return

        dialog = FirstRunDialog(
            configuration_store=self.configuration_store,
            credential_store=self.credential_store,
            suggested_credentials=credentials,
            initial_setup=False,
            parent=self,
        )

        if dialog.exec() != QDialog.Accepted:
            return

        configuration = dialog.completed_configuration
        self._populate_account_selector()
        self._apply_configuration(configuration)

        if self.workflows:
            self._disconnect_catalog()
            self.load_catalog()

    def show_ready_message(self):
        self.log_view.append("Interfejs uruchomiony.")

    def _restore_network_share(
        self,
        configuration,
    ):
        if configuration.storage_kind != "mounted" or (
            configuration.destination is not None and configuration.destination.is_dir()
        ):
            return configuration

        question = QMessageBox(self)
        question.setIcon(QMessageBox.Icon.Question)
        question.setWindowTitle("Udział sieciowy nie jest zamontowany")
        question.setText(
            "Katalog sieciowy tego konta nie jest "
            "obecnie dostępny.\n\n"
            "Czy zamontować udział teraz?"
        )
        mount_button = question.addButton(
            "Zamontuj udział",
            QMessageBox.ButtonRole.AcceptRole,
        )
        question.addButton(
            "Anuluj",
            QMessageBox.ButtonRole.RejectRole,
        )
        question.setDefaultButton(mount_button)
        question.exec()

        if question.clickedButton() is not mount_button:
            return None

        network_dialog = NetworkBrowserDialog(self)

        if network_dialog.exec() != QDialog.DialogCode.Accepted:
            return None

        share = network_dialog.selected_share

        if share is None:
            return None

        destination = find_mounted_smb_path(share.uri)

        if destination is None:
            QMessageBox.warning(
                self,
                "Nie znaleziono zamontowanego udziału",
                (
                    "Udział został zamontowany, ale "
                    "program nie odnalazł jego "
                    "lokalnego katalogu."
                ),
            )
            return None

        configuration = replace(
            configuration,
            destination=destination,
            network_url=share.uri,
        )
        self.configuration_store.save(configuration)
        self._apply_configuration(configuration)

        return configuration

    def load_catalog(self):
        configuration = self.configuration_store.load()
        configuration = self._restore_network_share(configuration)

        if configuration is None:
            return

        self.statusBar().clearMessage()
        self.sync_button.setEnabled(False)
        self.statusBar().clearMessage()
        self.sync_button.setEnabled(False)
        self.connection_button.setText("Łączenie…")
        self._set_connection_button_action("busy")
        self.connection_button.setEnabled(False)
        self.connection_label.setText("Łączenie z NIFC…")
        self.connection_label.setProperty("connected", False)
        self._set_connection_dot_state("connecting")
        self.connection_label.style().unpolish(self.connection_label)
        self.connection_label.style().polish(self.connection_label)
        self._start_activity_indicator()

        try:
            credentials = self.credential_store.load(configuration.nifc_username)
        except CredentialStoreError as error:
            self._catalog_failed(str(error))
            self.connection_button.setEnabled(True)
            return

        if credentials is None:
            self._catalog_failed(
                "Nie znaleziono danych logowania w systemowym magazynie haseł."
            )
            self.connection_button.setEnabled(True)
            return

        self.catalog_thread = QThread(self)
        self.catalog_worker = CatalogLoader(credentials)
        self.catalog_worker.moveToThread(self.catalog_thread)

        self.catalog_thread.started.connect(self.catalog_worker.run)
        self.catalog_worker.log.connect(self.log_view.append)
        self.catalog_worker.loaded.connect(self._catalog_loaded)
        self.catalog_worker.failed.connect(self._catalog_failed)
        self.catalog_worker.finished.connect(self.catalog_thread.quit)
        self.catalog_worker.finished.connect(self.catalog_worker.deleteLater)
        self.catalog_thread.finished.connect(self.catalog_thread.deleteLater)
        self.catalog_thread.finished.connect(self._catalog_thread_finished)

        self.catalog_thread.start()

    def _catalog_loaded(self, workflows, user_name):
        self.workflows = {workflow["name"]: workflow for workflow in workflows}

        radio_buttons = {
            "KRN-diplomatic": self.diplomatic_radio,
            "KRN-modern": self.modern_radio,
            "XML": self.xml_radio,
        }
        labels = {
            "KRN-diplomatic": "KRN diplomatic",
            "KRN-modern": "KRN modern",
            "XML": "XML",
        }

        for workflow_name, radio_button in radio_buttons.items():
            workflow = self.workflows.get(workflow_name)
            file_count = len(workflow["files"]) if workflow else 0
            radio_button.setText(f"{labels[workflow_name]} ({file_count})")
            radio_button.setEnabled(workflow is not None)

        self.statusBar().showMessage("Gotowy")
        self.connection_label.setText(f"Zalogowano jako: {user_name}")
        self.connection_label.setProperty("connected", True)
        self._set_connection_dot_state("connected")
        self.connection_label.style().unpolish(self.connection_label)
        self.connection_label.style().polish(self.connection_label)
        self._update_sync_button()
        self._stop_activity_indicator()
        self.connection_button.setText("Rozłącz")
        self._set_connection_button_action("disconnect")
        self.connection_button.setEnabled(True)

    def _catalog_failed(self, message):
        self.log_view.append(f"BŁĄD: {message}")
        self.statusBar().showMessage("Błąd połączenia")
        self.connection_label.setText("Brak połączenia")
        self.connection_label.setProperty("connected", False)
        self._set_connection_dot_state("error")
        self.connection_button.setText("Połącz ponownie")
        self._set_connection_button_action("connect")
        self.connection_button.setEnabled(False)
        self._stop_activity_indicator()

    def _catalog_thread_finished(self):
        self.catalog_thread = None
        self.catalog_worker = None
        if not self.workflows:
            self.connection_button.setEnabled(True)

    def _toggle_connection(self):
        if self.workflows:
            self._disconnect_catalog()
        else:
            self.load_catalog()

    def _disconnect_catalog(self):
        self.workflows = {}
        self.connection_label.setText("Rozłączono")
        self.connection_label.setProperty("connected", False)
        self._set_connection_dot_state("disconnected")
        self.connection_label.style().unpolish(self.connection_label)
        self.connection_label.style().polish(self.connection_label)
        self.connection_button.setText("Połącz")
        self._set_connection_button_action("connect")
        self.log_view.append("Rozłączono z NIFC.")
        self.statusBar().showMessage("Rozłączono")
        self._set_workflow_counts_empty()
        self._update_sync_button()

    def _set_connection_button_action(self, action):
        self.connection_button.setProperty(
            "connectionAction",
            action,
        )
        self.connection_button.style().unpolish(self.connection_button)
        self.connection_button.style().polish(self.connection_button)

    def _set_connection_dot_state(self, state):
        self.connection_dot.setProperty("state", state)
        self.connection_dot.style().unpolish(self.connection_dot)
        self.connection_dot.style().polish(self.connection_dot)

    def _set_workflow_counts_empty(self):
        buttons = (
            (self.diplomatic_radio, "KRN diplomatic"),
            (self.modern_radio, "KRN modern"),
            (self.xml_radio, "XML"),
        )
        for radio_button, label in buttons:
            radio_button.setText(label)
            radio_button.setEnabled(False)

    def _update_sync_button(self):
        has_catalog = bool(self.workflows)
        has_destination = self.destination_path is not None
        can_start = (
            has_catalog
            and has_destination
            and self.sync_thread is None
            and self.submission_thread is None
        )
        self.sync_button.setEnabled(can_start)
        self.submit_button.setEnabled(can_start)

    def _selected_workflow(self):
        if self.modern_radio.isChecked():
            workflow_name = "KRN-modern"
        elif self.xml_radio.isChecked():
            workflow_name = "XML"
        else:
            workflow_name = "KRN-diplomatic"

        return self.workflows.get(workflow_name)

    def _selected_workflow_name(self):
        if self.modern_radio.isChecked():
            return "KRN-modern"
        if self.xml_radio.isChecked():
            return "XML"
        return "KRN-diplomatic"

    def _open_submission_dialog(self):
        workflow = self._selected_workflow()
        if workflow is None:
            return
        self.log_view.append(
            f"Workflow {workflow['name']}: key={workflow.get('key')!r}"
        )

        dialog = SubmissionSelectionDialog(workflow, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            api_file = dialog.selected_file()
            configuration = replace(
                self.configuration_store.load(),
                destination=self.destination_path,
                workflow=workflow["name"],
            )
            search = find_configured_submission_files(
                configuration,
                workflow["name"],
                api_file["name"],
            )

            self.log_view.append(
                f"Tryb na sucho: {api_file['name']} — "
                f"znaleziono {len(search.matches)} plik(ów)."
            )
            self.log_view.append(
                f"Katalog wyszukiwania: {search.search_root or 'nieustalony'}"
            )
            for path in search.matches:
                self.log_view.append(f"  {path}")
            matches = search.matches
            if not matches:
                selected_path, _ = QFileDialog.getOpenFileName(
                    self,
                    "Wskaż plik do wysłania",
                    str(search.search_root or self.destination_path or Path.home()),
                    "Pliki transkrypcji (*.krn *.xml *.musicxml *.mxl);;Wszystkie pliki (*)",
                )
                if not selected_path:
                    return
                matches = (Path(selected_path),)
            if len(matches) > 1:
                paths = [str(path) for path in matches]
                selected_path, accepted = QInputDialog.getItem(
                    self,
                    "Wybierz lokalny plik",
                    "Znaleziono kilka plików. Wybierz ścieżkę:",
                    paths,
                    0,
                    False,
                )
                if not accepted:
                    return
                matches = (Path(selected_path),)
            if len(matches) == 1:
                file_path = matches[0]
                inspection = inspect_submission_file(
                    workflow["name"],
                    api_file["name"],
                    file_path,
                )
                self.log_view.append(f"Plik lokalny: {inspection.actual_filename}")
                self.log_view.append(
                    f"!!!!SEGMENT: {inspection.segment_name or 'brak'}"
                )
                self.log_view.append(
                    f"Rozmiar: {format_file_size(file_path.stat().st_size)}"
                )
                for warning in inspection.warnings:
                    self.log_view.append(f"OSTRZEŻENIE: {warning}")
                preview = SubmissionPreviewDialog(
                    workflow["name"],
                    api_file["name"],
                    file_path,
                    inspection,
                    self,
                )
                preview_result = preview.exec()

                if preview_result == QDialog.DialogCode.Accepted:
                    content = file_path.read_bytes()
                    self.log_view.append("PRÓBA WYSYŁKI — bez połączenia z serwerem:")
                    self.log_view.append(f"  workflow_key: {workflow['key']}")
                    self.log_view.append(f"  nazwa w NIFC: {api_file['name']}")
                    self.log_view.append(
                        f"  odczytano: {format_file_size(len(content))}"
                    )
                    self.log_view.append("  POST nie został wykonany.")

                elif preview_result == 2:
                    confirmation = QMessageBox.question(
                        self,
                        "Potwierdź wysłanie do NIFC",
                        (
                            f"Czy wysłać plik do NIFC?\n\n"
                            f"Workflow: {workflow['name']}\n"
                            f"Nazwa: {api_file['name']}\n"
                            f"Ścieżka: {file_path}\n\n"
                            "Po wysłaniu powrót do edycji w NIFC "
                            "może nie być możliwy."
                        ),
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if confirmation == QMessageBox.StandardButton.Yes:
                        self._start_submission(workflow, api_file, file_path)

    def _start_submission(self, workflow, api_file, file_path):
        configuration = self.configuration_store.load()

        try:
            credentials = self.credential_store.load(configuration.nifc_username)
        except CredentialStoreError as error:
            QMessageBox.warning(self, "Błąd danych logowania", str(error))
            return

        if credentials is None:
            QMessageBox.warning(
                self,
                "Brak danych logowania",
                "Nie znaleziono zapisanych danych logowania do NIFC.",
            )
            return

        self.submission_succeeded = False
        self.submission_response = ""
        self._set_controls_enabled(False)
        self.log_view.append(f"Wysyłanie do NIFC: {api_file['name']}")
        self.statusBar().showMessage("Wysyłanie pliku…")
        self.progress_bar.setRange(0, 0)
        self.progress_stage_label.setText("Logowanie do NIFC…")
        self._start_activity_indicator()

        self.submission_thread = QThread(self)
        self.submission_worker = SubmissionWorker(
            credentials,
            workflow["key"],
            api_file["name"],
            file_path,
        )
        self.submission_worker.moveToThread(self.submission_thread)

        self.submission_thread.started.connect(self.submission_worker.run)
        self.submission_worker.progress.connect(self._submission_progress)
        self.submission_worker.stage.connect(self._submission_stage)
        self.submission_worker.validation.connect(self._submission_validation)
        self.submission_worker.submitted.connect(self._submission_completed)
        self.submission_worker.failed.connect(self._submission_failed)
        self.submission_worker.finished.connect(self.submission_thread.quit)
        self.submission_worker.finished.connect(self.submission_worker.deleteLater)
        self.submission_thread.finished.connect(self.submission_thread.deleteLater)
        self.submission_thread.finished.connect(self._submission_thread_finished)
        self.submission_thread.start()

    def _submission_progress(self, percentage):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(percentage)
        self.progress_stage_label.setText(f"Wysyłanie pliku… {percentage}%")

    def _submission_stage(self, message):
        self.progress_stage_label.setText(message)
        self.statusBar().showMessage(message)
        if message != "Wysyłanie pliku…":
            self.progress_bar.setRange(0, 0)

    def _submission_validation(self, message):
        self.submission_response = message
        self.log_view.insertPlainText(f"\nOdpowiedź NIFC:\n{message}\n")

    def _submission_completed(self):
        self.submission_succeeded = True
        self.log_view.append("NIFC potwierdził przyjęcie pliku.")
        self.statusBar().showMessage("Plik wysłany")

        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setWindowTitle("Plik przyjęty przez NIFC")
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        dialog.setText(self.submission_response or "Plik został przyjęty przez NIFC.")
        close_button = dialog.addButton(
            "Zamknij",
            QMessageBox.ButtonRole.AcceptRole,
        )
        dialog.setDefaultButton(close_button)
        dialog.exec()

    def _submission_failed(self, message):
        self.log_view.append(f"BŁĄD WYSYŁKI: {message}")
        self.statusBar().showMessage("Błąd wysyłki")

        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle("Błąd wysyłki do NIFC")
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        dialog.setText(message)
        if self.submission_response:
            dialog.setDetailedText(self.submission_response)
        dialog.exec()

    def _submission_thread_finished(self):
        self._stop_activity_indicator()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100 if self.submission_succeeded else 0)
        self.progress_stage_label.clear()
        self.submission_thread = None
        self.submission_worker = None
        self._set_controls_enabled(True)
        self._update_sync_button()

        if self.submission_succeeded:
            self.load_catalog()

    def _start_synchronization(self):
        selected_workflow = self._selected_workflow()

        if selected_workflow is None:
            self._catalog_failed("Nie wybrano rodzaju transkrypcji.")
            return

        configuration = replace(
            self.configuration_store.load(),
            destination=self.destination_path,
            workflow=self._selected_workflow_name(),
        )

        self.log_view.clear()
        self.log_view.append(f"Synchronizacja: {selected_workflow['name']}")
        self.statusBar().showMessage("Synchronizacja…")
        self.progress_stage_label.setText("Przygotowanie… 0%")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self._set_controls_enabled(False)
        self._start_activity_indicator()

        self.sync_thread = QThread(self)
        self.sync_worker = SyncWorker(
            selected_workflow=selected_workflow,
            available_workflows=list(self.workflows.values()),
            configuration=configuration,
        )
        self.sync_worker.moveToThread(self.sync_thread)

        self.sync_thread.started.connect(self.sync_worker.run)
        self.sync_worker.log.connect(self.log_view.append)
        self.sync_worker.progress.connect(self._update_progress)
        self.sync_worker.completed.connect(self._synchronization_completed)
        self.sync_worker.failed.connect(self._synchronization_failed)
        self.sync_worker.finished.connect(self.sync_thread.quit)
        self.sync_worker.finished.connect(self.sync_worker.deleteLater)
        self.sync_thread.finished.connect(self.sync_thread.deleteLater)
        self.sync_thread.finished.connect(self._sync_thread_finished)

        self.sync_thread.start()

    def _update_progress(self, percentage):
        if percentage >= 0:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(percentage)
            self.progress_stage_label.setText(f"Synchronizacja… {percentage}%")
        else:
            self.progress_bar.setRange(0, 0)
            self.progress_stage_label.setText("Pobieranie skanów…")

    def _synchronization_completed(self, summary, scan_plans):
        self.pending_summary = summary
        self.pending_scan_plans = scan_plans

    def _finish_synchronization(self, summary):
        scan_issues = summary.get(
            "scan_issues",
            (),
        )
        self._stop_activity_indicator()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.log_view.append("\n────────────────────────────────")
        self.log_view.append("GOTOWE")
        self.log_view.append(f"Utworzono folderów: {summary['created']}")
        self.log_view.append(f"Pobrano transkrypcji: {summary['downloaded']}")
        self.log_view.append(f"Pobrano pakietów skanów: {summary['scan_packages']}")
        self.log_view.append(f"Pominięto transkrypcji: {summary['skipped']}")
        self.log_view.append(f"Źródła wymagające ręcznego pobrania: {len(scan_issues)}")
        self.log_view.append("────────────────────────────────")
        if scan_issues:
            self.log_view.append("\nSKANY WYMAGAJĄCE RĘCZNEGO POBRANIA:")

            for issue in scan_issues:
                self.log_view.append(f"\nGRUPA: {issue.group_key}")
                self.log_view.append(f"POWÓD: {issue.reason}")

                for transcription_name in issue.transcription_names:
                    self.log_view.append(f"UTWÓR: {transcription_name}")

                self.log_view.append(f"URL-scan: {issue.source_url}")
        self.statusBar().showMessage("Gotowe")
        self.progress_stage_label.clear()

    def _synchronization_failed(self, message):
        self.log_view.append(f"\nBŁĄD: {message}")
        self.statusBar().showMessage("Błąd synchronizacji")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_stage_label.setText("Błąd")
        self._stop_activity_indicator()

    def _sync_thread_finished(self):
        self.sync_thread = None
        self.sync_worker = None
        if self.pending_summary is None:
            self._set_controls_enabled(True)
            self._update_sync_button()
            return

        QTimer.singleShot(
            0,
            self._offer_polish_music_sources_lookup,
        )

    def _offer_polish_music_sources_lookup(self):
        summary = self.pending_summary

        if summary is None:
            return

        searchable_issues = tuple(
            issue
            for issue in summary.get(
                "scan_issues",
                (),
            )
            if (
                issue.source_metadata is not None
                and (
                    issue.source_metadata.rism_id
                    or (
                        issue.source_metadata.siglum and issue.source_metadata.shelfmark
                    )
                )
            )
        )

        if not searchable_issues:
            self._offer_scan_downloads()
            return

        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setWindowTitle("Wyszukiwanie skanów")
        dialog.setText(
            "Nie znaleziono skanów pod zapisanym "
            f"adresem dla {len(searchable_issues)} "
            "źródeł.\n\n"
            "Czy wyszukać je w Polish Music Sources?"
        )

        search_button = dialog.addButton(
            "Wyszukaj w Polish Music Sources",
            QMessageBox.ButtonRole.AcceptRole,
        )
        dialog.addButton(
            "Pomiń",
            QMessageBox.ButtonRole.RejectRole,
        )
        dialog.setDefaultButton(search_button)
        dialog.exec()

        if dialog.clickedButton() is not search_button:
            self._offer_scan_downloads()
            return

        self._start_polish_music_sources_lookup(searchable_issues)

    def _start_polish_music_sources_lookup(
        self,
        scan_issues,
    ):
        self.statusBar().showMessage("Wyszukiwanie skanów…")
        self.progress_stage_label.setText("Wyszukiwanie w Polish Music Sources…")
        self.pending_lookup_results = None

        self.lookup_thread = QThread(self)
        self.lookup_worker = PolishMusicSourcesLookupWorker(scan_issues)
        self.lookup_worker.moveToThread(self.lookup_thread)

        self.lookup_thread.started.connect(self.lookup_worker.run)
        self.lookup_worker.log.connect(self.log_view.append)
        self.lookup_worker.completed.connect(
            self._polish_music_sources_lookup_completed
        )
        self.lookup_worker.failed.connect(self._polish_music_sources_lookup_failed)
        self.lookup_worker.finished.connect(self.lookup_thread.quit)
        self.lookup_worker.finished.connect(self.lookup_worker.deleteLater)
        self.lookup_thread.finished.connect(self.lookup_thread.deleteLater)
        self.lookup_thread.finished.connect(self._polish_music_sources_lookup_finished)
        self.lookup_thread.start()

    def _polish_music_sources_lookup_completed(
        self,
        lookup_results,
    ):
        self.pending_lookup_results = tuple(lookup_results)

    def _polish_music_sources_lookup_failed(
        self,
        message,
    ):
        self.pending_lookup_results = ()
        self.log_view.append(f"\nNIE UDAŁO SIĘ WYSZUKAĆ SKANÓW: {message}")

    def _polish_music_sources_lookup_finished(self):
        self.lookup_thread = None
        self.lookup_worker = None
        lookup_results = self.pending_lookup_results or ()
        self.pending_lookup_results = None
        configuration = self.configuration_store.load()
        found_plans = []
        resolved_issues = []

        for issue, results in lookup_results:
            metadata = issue.source_metadata

            if not results:
                self.log_view.append("\nNIE ZNALEZIONO W POLISH MUSIC SOURCES:")
                self.log_view.append(f"  ŹRÓDŁO: {issue.group_key}")
                self.log_view.append(
                    f"  SIGLUM I SYGNATURA: {metadata.siglum} {metadata.shelfmark}"
                )
                continue

            if len(results) > 1:
                self.log_view.append(
                    "\nZNALEZIONO KILKA PASUJĄCYCH ŹRÓDEŁ — WYMAGANY WYBÓR RĘCZNY:"
                )

                for search_result, _download_info in results:
                    self.log_view.append(
                        "  "
                        f"{search_result.title} — "
                        f"{search_result.siglum} "
                        f"{search_result.shelfmark}"
                    )
                    self.log_view.append(f"  {search_result.url}")

                continue

            search_result, download_info = results[0]

            self.log_view.append("\nZNALEZIONO W POLISH MUSIC SOURCES:")
            self.log_view.append(f"  TYTUŁ: {search_result.title}")
            self.log_view.append(
                "  SIGLUM I SYGNATURA: "
                f"{search_result.siglum} "
                f"{search_result.shelfmark}"
            )
            self.log_view.append(f"  LICZBA SKANÓW: {len(download_info.scans)}")
            self.log_view.append(f"  ADRES: {search_result.url}")

            if issue.destination_folder is None:
                continue

            if configuration.naming_profile in (
                "marta-lawrence",
                "andrzej-kubiczek",
            ):
                output_folder_name = scan_package_folder_name(download_info.filename)
            else:
                output_folder_name = "skany"

            scans_folder = issue.destination_folder / output_folder_name
            manifest_status = validate_scan_manifest(
                scans_folder,
                verify_sizes=False,
            )

            if scans_folder.exists() and manifest_status is not False:
                self.log_view.append(f"  SKANY JUŻ ISTNIEJĄ: {scans_folder}")
                resolved_issues.append(issue)
                continue

            found_plans.append(
                ScanDownloadRequest(
                    group_key=issue.group_key,
                    transcription_name=(issue.transcription_names[0]),
                    source_url=search_result.url,
                    destination_folder=(issue.destination_folder),
                    download_info=download_info,
                    provider=polish_music_sources,
                    is_incomplete=(scans_folder.exists() and manifest_status is False),
                    output_folder_name=(output_folder_name),
                )
            )
            resolved_issues.append(issue)

        self.pending_scan_plans = tuple(self.pending_scan_plans) + tuple(found_plans)

        if self.pending_summary is not None:
            self.pending_summary["scan_issues"] = tuple(
                issue
                for issue in self.pending_summary.get(
                    "scan_issues",
                    (),
                )
                if issue not in resolved_issues
            )

        QTimer.singleShot(
            0,
            self._offer_scan_downloads,
        )

    def _offer_scan_downloads(self):
        summary = self.pending_summary
        plans = self.pending_scan_plans
        self.pending_summary = None
        self.pending_scan_plans = ()
        self.pending_lookup_results = None

        if not plans:
            self._finish_synchronization(summary)
            self._set_controls_enabled(True)
            self._update_sync_button()
            return

        dialog = ScanSelectionDialog(plans, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self.log_view.append("Pominięto pobieranie skanów.")
            self._finish_synchronization(summary)
            self._set_controls_enabled(True)
            self._update_sync_button()
            return

        selected_plans = dialog.selected_plans()
        self.pending_summary = summary
        self._start_scan_download(selected_plans)

    def _start_scan_download(self, plans):
        self.statusBar().showMessage("Pobieranie skanów…")
        self.progress_stage_label.setText("Pobieranie skanów…")
        self._start_activity_indicator()
        self.scan_thread = QThread(self)
        self.scan_worker = ScanDownloadWorker(plans)
        self.scan_worker.moveToThread(self.scan_thread)

        self.scan_thread.started.connect(self.scan_worker.run)
        self.scan_worker.log.connect(self.log_view.append)
        self.scan_worker.progress.connect(self._update_scan_progress)
        self.scan_worker.completed.connect(self._scan_download_completed)
        self.scan_worker.failed.connect(self._synchronization_failed)
        self.scan_worker.finished.connect(self.scan_thread.quit)
        self.scan_worker.finished.connect(self.scan_worker.deleteLater)
        self.scan_thread.finished.connect(self.scan_thread.deleteLater)
        self.scan_thread.finished.connect(self._scan_thread_finished)
        self.scan_thread.start()

    def _update_scan_progress(self, percentage, detail):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(percentage)
        self.progress_stage_label.setText(detail)
        self.statusBar().showMessage("Pobieranie skanów…")

    def _scan_download_completed(self, downloaded_packages):
        self.pending_summary["scan_packages"] = downloaded_packages
        self._finish_synchronization(self.pending_summary)
        self.pending_summary = None

    def _scan_thread_finished(self):
        self.scan_thread = None
        self.scan_worker = None
        self._set_controls_enabled(True)
        self._update_sync_button()

    def _start_activity_indicator(self):
        self.activity_frame = 0
        self.activity_indicator.setText("●")
        self.activity_indicator.setStyleSheet(f"color: {self.activity_colors[0]};")
        self.activity_timer.start()

    def _stop_activity_indicator(self):
        self.activity_timer.stop()
        self.activity_indicator.clear()

    def _animate_activity_indicator(self):
        self.activity_frame = (self.activity_frame + 1) % len(self.activity_colors)
        self.activity_indicator.setStyleSheet(
            f"color: {self.activity_colors[self.activity_frame]};"
        )

    def _animate_activity_indicator(self):
        self.activity_frame = (self.activity_frame + 1) % len(self.activity_colors)
        self.activity_indicator.setStyleSheet(
            f"color: {self.activity_colors[self.activity_frame]};"
        )

    def _set_controls_enabled(self, enabled):
        self.diplomatic_radio.setEnabled(enabled)
        self.modern_radio.setEnabled(enabled)
        self.xml_radio.setEnabled(enabled)
        self.destination_edit.setEnabled(enabled)
        self.browse_button.setEnabled(enabled)
        self.account_combo.setEnabled(enabled)
        self.connection_button.setEnabled(enabled)
        self.submit_button.setEnabled(enabled)
        self.sync_button.setEnabled(enabled)
        self.statistics_button.setEnabled(enabled)

    def _populate_account_selector(self):
        active_account_id = self.configuration_store.active_account_id()
        accounts = self.configuration_store.list_accounts()

        self.account_combo.blockSignals(True)
        self.account_combo.clear()

        for account in accounts:
            self.account_combo.addItem(
                account.name,
                account.account_id,
            )

        if accounts:
            self.account_combo.insertSeparator(self.account_combo.count())

        self.account_combo.addItem(
            "Dodaj konto…",
            "__add_account__",
        )

        if len(accounts) > 1:
            self.account_combo.addItem(
                "Usuń bieżące konto…",
                "__delete_account__",
            )

        active_index = self.account_combo.findData(active_account_id)

        if active_index >= 0:
            self.account_combo.setCurrentIndex(active_index)

        self.account_combo.blockSignals(False)

    def _change_active_account(self, index):
        account_id = self.account_combo.itemData(index)

        if account_id == "__add_account__":
            self._open_new_account()
            return

        if account_id == "__delete_account__":
            self._delete_active_account()
            return

        if not account_id or account_id == self.configuration_store.active_account_id():
            return

        self._save_settings()

        if self.workflows:
            self._disconnect_catalog()

        self.configuration_store.set_active_account(account_id)
        configuration = self.configuration_store.load()
        self._apply_configuration(configuration)
        self.log_view.append(f"Wybrano konto: {self.account_combo.currentText()}.")

    def _open_new_account(self):
        self._save_settings()

        dialog = FirstRunDialog(
            configuration_store=self.configuration_store,
            credential_store=self.credential_store,
            initial_setup=False,
            new_account=True,
            parent=self,
        )

        if dialog.exec() != QDialog.Accepted:
            self._populate_account_selector()
            return

        if self.workflows:
            self._disconnect_catalog()

        configuration = dialog.completed_configuration
        self._populate_account_selector()
        self._apply_configuration(configuration)
        self.log_view.append(
            f"Utworzono i wybrano konto: {self.account_combo.currentText()}."
        )

    def _delete_active_account(self):
        accounts = self.configuration_store.list_accounts()
        active_account_id = self.configuration_store.active_account_id()
        active_account = next(
            (
                account
                for account in accounts
                if account.account_id == active_account_id
            ),
            None,
        )

        if active_account is None:
            self._populate_account_selector()
            return

        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Icon.NoIcon)
        message_box.setWindowTitle("Usuń konto")
        message_box.setText(
            f"Czy usunąć konto „{active_account.name}” "
            "wraz z jego ustawieniami?\n\n"
            "Dane logowania również zostaną usunięte, "
            "jeśli nie korzysta z nich inne konto."
        )
        message_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        delete_button = message_box.button(QMessageBox.StandardButton.Yes)
        cancel_button = message_box.button(QMessageBox.StandardButton.No)
        delete_button.setText("Usuń")
        cancel_button.setText("Anuluj")
        message_box.setDefaultButton(QMessageBox.StandardButton.No)

        if message_box.exec() != QMessageBox.StandardButton.Yes:
            self._populate_account_selector()
            return

        deleted_username = self.configuration_store.load().nifc_username

        if self.workflows:
            self._disconnect_catalog()

        self.configuration_store.delete_account(active_account_id)

        if deleted_username and not self.configuration_store.has_account_for_username(
            deleted_username
        ):
            try:
                self.credential_store.delete(deleted_username)
            except CredentialStoreError as error:
                QMessageBox.warning(
                    self,
                    "Nie można usunąć danych logowania",
                    str(error),
                )

        configuration = self.configuration_store.load()
        self._populate_account_selector()
        self._apply_configuration(configuration)
        self.log_view.append(f"Usunięto konto: {active_account.name}.")

    def _apply_configuration(self, configuration):

        self._refresh_unpaid_summary()

        if configuration.naming_profile == "marta-lawrence":
            self.destination_group.setTitle("Folder nadrzędny")
            self.destination_edit.setPlaceholderText("Folder nadrzędny, np. Pulpit")
        elif configuration.naming_profile == "andrzej-kubiczek":
            self.destination_group.setTitle("Folder nadrzędny")
            self.destination_edit.setPlaceholderText(
                "Folder nadrzędny katalogów rocznych"
            )
        else:
            self.destination_group.setTitle("Katalog docelowy")
            self.destination_edit.setPlaceholderText("Katalog docelowy")

        self.destination_path = configuration.destination
        self.destination_edit.setText(self._destination_display_text(configuration))

        radio_buttons = {
            "KRN-diplomatic": self.diplomatic_radio,
            "KRN-modern": self.modern_radio,
            "XML": self.xml_radio,
        }
        radio_buttons.get(
            configuration.workflow,
            self.diplomatic_radio,
        ).setChecked(True)

    def _restore_settings(self):
        settings = QSettings()

        geometry = settings.value("window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

        configuration = self.configuration_store.load()
        self._apply_configuration(configuration)

    def _save_settings(self):
        settings = QSettings()
        settings.setValue(
            "window/geometry",
            self.saveGeometry(),
        )

        configuration = replace(
            self.configuration_store.load(),
            destination=self.destination_path,
            workflow=self._selected_workflow_name(),
        )
        self.configuration_store.save(configuration)

    def closeEvent(self, event):
        is_busy = (
            self._is_busy()
            or self.update_manager.download_reply is not None
            or self.update_manager.install_process is not None
        )

        if is_busy:
            QMessageBox.warning(
                self,
                "NIFC-SYNC pracuje",
                "Poczekaj na zakończenie bieżącej operacji "
                "przed zamknięciem aplikacji.",
            )
            event.ignore()
            return

        self._save_settings()
        event.accept()
