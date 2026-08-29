from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("NIFC-SYNC 3.0")
        self.setMinimumSize(760, 560)

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
        main_layout.addWidget(self.sync_button)

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

    def _create_workflow_group(self):
        group = QGroupBox("Workflow")
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

        browse_button = QPushButton("Wybierz…")
        browse_button.clicked.connect(self._choose_destination)

        layout.addWidget(self.destination_edit, stretch=1)
        layout.addWidget(browse_button)

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
