from pathlib import Path

from PySide6.QtCore import QThread
from PySide6.QtWidgets import (
    QFileDialog,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QProgressBar,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui.workers import CatalogLoader, SyncWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("NIFC-SYNC 3.0")
        self.setMinimumSize(760, 560)
        self.workflows = {}
        self.catalog_thread = None
        self.catalog_worker = None
        self.sync_thread = None
        self.sync_worker = None

        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(18)

        title = QLabel("NIFC-SYNC")
        title_font = title.font()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title.setFont(title_font)

        subtitle = QLabel(
            "Synchronizacja transkrypcji i skanów źródłowych"
        )
        subtitle.setObjectName("subtitle")

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)
        main_layout.addWidget(self._create_workflow_group())
        main_layout.addWidget(self._create_destination_group())

        self.sync_button = QPushButton("Synchronizuj")
        self.sync_button.setEnabled(False)
        self.sync_button.setMinimumHeight(42)
        self.sync_button.clicked.connect(
            self._start_synchronization
        )
        self.download_scans_checkbox = QCheckBox(
            "Pobieraj brakujące skany"
        )
        self.download_scans_checkbox.setChecked(False)

        action_layout = QHBoxLayout()
        action_layout.addWidget(self.download_scans_checkbox)
        action_layout.addStretch()
        main_layout.addLayout(action_layout)
        main_layout.addWidget(self.sync_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        main_layout.addWidget(self.progress_bar)

        log_label = QLabel("Dziennik")
        log_label_font = log_label.font()
        log_label_font.setBold(True)
        log_label.setFont(log_label_font)
        main_layout.addWidget(log_label)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText(
            "Tutaj pojawi się przebieg synchronizacji."
        )
        main_layout.addWidget(self.log_view, stretch=1)

        self.setCentralWidget(central_widget)
        self.statusBar().showMessage("Gotowy")

        self.destination_edit.textChanged.connect(
            self._update_sync_button
        )

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

        self.destination_edit = QLineEdit(
            str(Path.home() / "mac_transkrypcje")
        )
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

    def show_ready_message(self):
        self.log_view.append(
            "Interfejs uruchomiony. Silnik synchronizacji "
            "nie jest jeszcze podłączony."
        )

    def load_catalog(self):
        self.statusBar().showMessage("Łączenie z NIFC…")
        self.sync_button.setEnabled(False)

        self.catalog_thread = QThread(self)
        self.catalog_worker = CatalogLoader()
        self.catalog_worker.moveToThread(self.catalog_thread)

        self.catalog_thread.started.connect(
            self.catalog_worker.run
        )
        self.catalog_worker.log.connect(self.log_view.append)
        self.catalog_worker.loaded.connect(
            self._catalog_loaded
        )
        self.catalog_worker.failed.connect(
            self._catalog_failed
        )
        self.catalog_worker.finished.connect(
            self.catalog_thread.quit
        )
        self.catalog_worker.finished.connect(
            self.catalog_worker.deleteLater
        )
        self.catalog_thread.finished.connect(
            self.catalog_thread.deleteLater
        )
        self.catalog_thread.finished.connect(
            self._catalog_thread_finished
        )

        self.catalog_thread.start()

    def _catalog_loaded(self, workflows, user_name):
        self.workflows = {
            workflow["name"]: workflow
            for workflow in workflows
        }

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
            radio_button.setText(
                f"{labels[workflow_name]} ({file_count})"
            )
            radio_button.setEnabled(workflow is not None)

        self.statusBar().showMessage(
            f"Połączono jako: {user_name}"
        )
        self._update_sync_button()

    def _catalog_failed(self, message):
        self.log_view.append(f"BŁĄD: {message}")
        self.statusBar().showMessage("Błąd połączenia")

    def _catalog_thread_finished(self):
        self.catalog_thread = None
        self.catalog_worker = None

    def _update_sync_button(self):
        has_catalog = bool(self.workflows)
        has_destination = bool(
            self.destination_edit.text().strip()
        )
        self.sync_button.setEnabled(
            has_catalog
            and has_destination
            and self.sync_thread is None
        )

    def _selected_workflow(self):
        if self.modern_radio.isChecked():
            workflow_name = "KRN-modern"
        elif self.xml_radio.isChecked():
            workflow_name = "XML"
        else:
            workflow_name = "KRN-diplomatic"

        return self.workflows.get(workflow_name)

    def _start_synchronization(self):
        selected_workflow = self._selected_workflow()

        if selected_workflow is None:
            self._catalog_failed(
                "Nie wybrano rodzaju transkrypcji."
            )
            return

        self.log_view.clear()
        self.log_view.append(
            f"Synchronizacja: {selected_workflow['name']}"
        )
        self.statusBar().showMessage("Synchronizacja…")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self._set_controls_enabled(False)

        self.sync_thread = QThread(self)
        self.sync_worker = SyncWorker(
            selected_workflow=selected_workflow,
            available_workflows=list(self.workflows.values()),
            destination=self.destination_edit.text().strip(),
            download_scans=(
                self.download_scans_checkbox.isChecked()
            ),
        )
        self.sync_worker.moveToThread(self.sync_thread)

        self.sync_thread.started.connect(self.sync_worker.run)
        self.sync_worker.log.connect(self.log_view.append)
        self.sync_worker.progress.connect(
            self._update_progress
        )
        self.sync_worker.completed.connect(
            self._synchronization_completed
        )
        self.sync_worker.failed.connect(
            self._synchronization_failed
        )
        self.sync_worker.finished.connect(self.sync_thread.quit)
        self.sync_worker.finished.connect(
            self.sync_worker.deleteLater
        )
        self.sync_thread.finished.connect(
            self.sync_thread.deleteLater
        )
        self.sync_thread.finished.connect(
            self._sync_thread_finished
        )

        self.sync_thread.start()

    def _update_progress(self, percentage):
        if percentage >= 0:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(percentage)
        else:
            self.progress_bar.setRange(0, 0)

    def _synchronization_completed(self, summary):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.log_view.append("\n────────────────────────────────")
        self.log_view.append("GOTOWE")
        self.log_view.append(
            f"Utworzono folderów: {summary['created']}"
        )
        self.log_view.append(
            f"Pobrano transkrypcji: {summary['downloaded']}"
        )
        self.log_view.append(
            f"Pobrano pakietów skanów: {summary['scan_packages']}"
        )
        self.log_view.append(
            f"Pominięto transkrypcji: {summary['skipped']}"
        )
        self.statusBar().showMessage("Gotowe")

    def _synchronization_failed(self, message):
        self.log_view.append(f"\nBŁĄD: {message}")
        self.statusBar().showMessage("Błąd synchronizacji")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

    def _sync_thread_finished(self):
        self.sync_thread = None
        self.sync_worker = None
        self._set_controls_enabled(True)
        self._update_sync_button()

    def _set_controls_enabled(self, enabled):
        self.diplomatic_radio.setEnabled(enabled)
        self.modern_radio.setEnabled(enabled)
        self.xml_radio.setEnabled(enabled)
        self.destination_edit.setEnabled(enabled)
        self.browse_button.setEnabled(enabled)
        self.download_scans_checkbox.setEnabled(enabled)
        self.sync_button.setEnabled(enabled)
