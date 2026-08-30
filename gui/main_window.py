from pathlib import Path

from PySide6.QtCore import QSettings, QThread, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
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

        main_layout.addLayout(self._create_header())
        main_layout.addWidget(self._create_workflow_group())
        main_layout.addWidget(self._create_destination_group())

        self.sync_button = QPushButton("Synchronizuj")
        self.sync_button.setObjectName("primaryButton")
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
        self.progress_bar.setTextVisible(False)
        main_layout.addWidget(self.progress_bar)

        log_label = QLabel("Dziennik")
        log_label_font = log_label.font()
        log_label_font.setBold(True)
        log_label.setFont(log_label_font)
        log_header = QHBoxLayout()
        log_header.addWidget(log_label)
        log_header.addStretch()
        self.progress_stage_label = QLabel("Gotowy")
        self.progress_stage_label.setObjectName("progressStage")
        log_header.addWidget(self.progress_stage_label)
        main_layout.addLayout(log_header)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText(
            "Tutaj pojawi się przebieg synchronizacji."
        )
        main_layout.addWidget(self.log_view, stretch=1)

        self.setCentralWidget(central_widget)
        self.statusBar().showMessage("Gotowy")

        self._restore_settings()
        self.destination_edit.textChanged.connect(
            self._update_sync_button
        )

    def _create_header(self):
        layout = QHBoxLayout()
        layout.setSpacing(12)

        self.brand_mark = QLabel()
        self.brand_mark.setObjectName("brandMark")
        self.brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brand_mark.setFixedSize(42, 42)
        icon_path = (
            Path(__file__).resolve().parent.parent
            / "assets"
            / "sync.svg"
        )
        icon = QPixmap(str(icon_path)).scaled(
            24,
            24,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.brand_mark.setPixmap(icon)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        title = QLabel("NIFC-SYNC")
        title.setObjectName("title")
        subtitle = QLabel(
            "Synchronizacja transkrypcji i skanów źródłowych"
        )
        subtitle.setObjectName("subtitle")
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)

        self.connection_label = QLabel("Łączenie z NIFC…")
        self.connection_label.setObjectName("connectionStatus")
        self.connection_label.setProperty("connected", False)

        layout.addWidget(self.brand_mark)
        layout.addLayout(title_layout)
        layout.addStretch()
        layout.addWidget(self.connection_label)

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
        self.log_view.append("Interfejs uruchomiony.")

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
        self.connection_label.setText("●  Połączono z NIFC")
        self.connection_label.setProperty("connected", True)
        self.connection_label.style().unpolish(
            self.connection_label
        )
        self.connection_label.style().polish(
            self.connection_label
        )
        self._update_sync_button()

    def _catalog_failed(self, message):
        self.log_view.append(f"BŁĄD: {message}")
        self.statusBar().showMessage("Błąd połączenia")
        self.connection_label.setText("●  Brak połączenia")
        self.connection_label.setProperty("connected", False)

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

    def _selected_workflow_name(self):
        if self.modern_radio.isChecked():
            return "KRN-modern"
        if self.xml_radio.isChecked():
            return "XML"
        return "KRN-diplomatic"

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
        self.progress_stage_label.setText("Przygotowanie… 0%")
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
            self.progress_stage_label.setText(
                f"Synchronizacja… {percentage}%"
            )
        else:
            self.progress_bar.setRange(0, 0)
            self.progress_stage_label.setText("Pobieranie skanów…")

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
        self.progress_stage_label.setText("Gotowe — 100%")

    def _synchronization_failed(self, message):
        self.log_view.append(f"\nBŁĄD: {message}")
        self.statusBar().showMessage("Błąd synchronizacji")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_stage_label.setText("Błąd")

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

    def _restore_settings(self):
        settings = QSettings()

        geometry = settings.value("window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

        destination = settings.value("sync/destination")
        if destination:
            self.destination_edit.setText(destination)

        self.download_scans_checkbox.setChecked(
            settings.value(
                "sync/download_scans",
                False,
                type=bool,
            )
        )

        workflow_name = settings.value(
            "sync/workflow",
            "KRN-diplomatic",
        )
        radio_buttons = {
            "KRN-diplomatic": self.diplomatic_radio,
            "KRN-modern": self.modern_radio,
            "XML": self.xml_radio,
        }
        radio_buttons.get(
            workflow_name,
            self.diplomatic_radio,
        ).setChecked(True)

    def _save_settings(self):
        settings = QSettings()
        settings.setValue("window/geometry", self.saveGeometry())
        settings.setValue(
            "sync/destination",
            self.destination_edit.text().strip(),
        )
        settings.setValue(
            "sync/download_scans",
            self.download_scans_checkbox.isChecked(),
        )
        settings.setValue(
            "sync/workflow",
            self._selected_workflow_name(),
        )

    def closeEvent(self, event):
        threads = (
            self.catalog_thread,
            self.sync_thread,
        )
        is_busy = any(
            thread is not None and thread.isRunning()
            for thread in threads
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
