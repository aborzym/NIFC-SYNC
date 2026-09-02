from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThread, QTimer
from PySide6.QtGui import QFontDatabase, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
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

from core.configuration import ConfigurationStore
from core.credentials import (
    CredentialStore,
    CredentialStoreError,
)
from gui.first_run_dialog import FirstRunDialog
from gui.scan_dialog import ScanSelectionDialog
from gui.workers import CatalogLoader, ScanDownloadWorker, SyncWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.configuration_store = ConfigurationStore()
        self.credential_store = CredentialStore()
        self.setWindowTitle("NIFC-SYNC 3.0")
        self.setMinimumSize(760, 560)
        self.workflows = {}
        self.catalog_thread = None
        self.catalog_worker = None
        self.sync_thread = None
        self.sync_worker = None
        self.scan_thread = None
        self.scan_worker = None
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
        main_layout.addWidget(self.sync_button)

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
        self.copyright_label = QLabel("© 2026 Andrzej Borzym · NIFC-SYNC 3.0")
        self.copyright_label.setObjectName("copyrightLabel")
        self.statusBar().addPermanentWidget(self.copyright_label)
        self.statusBar().showMessage("Gotowy")

        self._restore_settings()
        self._populate_account_selector()
        self.destination_edit.textChanged.connect(self._update_sync_button)

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
        group = QGroupBox("Katalog docelowy")
        layout = QHBoxLayout(group)

        self.destination_edit = QLineEdit(str(Path.home() / "mac_transkrypcje"))
        self.destination_edit.setClearButtonEnabled(True)

        self.browse_button = QPushButton("Wybierz…")
        self.browse_button.clicked.connect(self._choose_destination)

        layout.addWidget(self.destination_edit, stretch=1)
        layout.addWidget(self.browse_button)

        return group

    def _choose_destination(self):
        selected_directory = QFileDialog.getExistingDirectory(
            self,
            "Wybierz katalog docelowy",
            self.destination_edit.text(),
        )

        if selected_directory:
            self.destination_edit.setText(selected_directory)

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
        self.destination_edit.setText(str(configuration.destination))

        if self.workflows:
            self._disconnect_catalog()
            self.load_catalog()

    def show_ready_message(self):
        self.log_view.append("Interfejs uruchomiony.")

    def load_catalog(self):
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
        configuration = self.configuration_store.load()

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
        has_destination = bool(self.destination_edit.text().strip())
        self.sync_button.setEnabled(
            has_catalog and has_destination and self.sync_thread is None
        )

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

    def _start_synchronization(self):
        selected_workflow = self._selected_workflow()

        if selected_workflow is None:
            self._catalog_failed("Nie wybrano rodzaju transkrypcji.")
            return

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
            destination=self.destination_edit.text().strip(),
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
        self._stop_activity_indicator()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.log_view.append("\n────────────────────────────────")
        self.log_view.append("GOTOWE")
        self.log_view.append(f"Utworzono folderów: {summary['created']}")
        self.log_view.append(f"Pobrano transkrypcji: {summary['downloaded']}")
        self.log_view.append(f"Pobrano pakietów skanów: {summary['scan_packages']}")
        self.log_view.append(f"Pominięto transkrypcji: {summary['skipped']}")
        self.log_view.append("────────────────────────────────")
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

        QTimer.singleShot(0, self._offer_scan_downloads)

    def _offer_scan_downloads(self):
        summary = self.pending_summary
        plans = self.pending_scan_plans
        self.pending_summary = None
        self.pending_scan_plans = ()

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

    def _set_controls_enabled(self, enabled):
        self.diplomatic_radio.setEnabled(enabled)
        self.modern_radio.setEnabled(enabled)
        self.xml_radio.setEnabled(enabled)
        self.destination_edit.setEnabled(enabled)
        self.browse_button.setEnabled(enabled)
        self.account_combo.setEnabled(enabled)
        self.connection_button.setEnabled(enabled)
        self.sync_button.setEnabled(enabled)

    def _populate_account_selector(self):
        active_account_id = self.configuration_store.active_account_id()

        self.account_combo.blockSignals(True)
        self.account_combo.clear()

        for account in self.configuration_store.list_accounts():
            self.account_combo.addItem(
                account.name,
                account.account_id,
            )

        active_index = self.account_combo.findData(active_account_id)

        if active_index >= 0:
            self.account_combo.setCurrentIndex(active_index)

        self.account_combo.blockSignals(False)

    def _change_active_account(self, index):
        account_id = self.account_combo.itemData(index)

        if not account_id or account_id == self.configuration_store.active_account_id():
            return

        self._save_settings()

        if self.workflows:
            self._disconnect_catalog()

        self.configuration_store.set_active_account(account_id)
        configuration = self.configuration_store.load()
        self._apply_configuration(configuration)
        self.log_view.append(f"Wybrano konto: {self.account_combo.currentText()}.")

    def _apply_configuration(self, configuration):
        destination = (
            str(configuration.destination)
            if configuration.destination is not None
            else ""
        )
        self.destination_edit.setText(destination)

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

        destination_value = self.destination_edit.text().strip()
        configuration = replace(
            self.configuration_store.load(),
            destination=(Path(destination_value) if destination_value else None),
            workflow=self._selected_workflow_name(),
        )
        self.configuration_store.save(configuration)

    def closeEvent(self, event):
        threads = (
            self.catalog_thread,
            self.sync_thread,
            self.scan_thread,
        )
        is_busy = any(thread is not None and thread.isRunning() for thread in threads)

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
