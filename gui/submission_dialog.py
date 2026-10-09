from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.filesystem import format_file_size


class SubmissionSelectionDialog(QDialog):
    def __init__(self, workflow, parent=None):
        super().__init__(parent)
        self.files = tuple(workflow["files"])

        self.setWindowTitle(f"Wyślij plik — {workflow['name']}")
        self.setMinimumSize(760, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        title = QLabel("Wybierz pozycję z workflow")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        self.table = QTableWidget(len(self.files), 1)
        self.table.setHorizontalHeaderLabels(("Nazwa pliku w NIFC",))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)

        for row, api_file in enumerate(self.files):
            item = QTableWidgetItem(api_file["name"])
            item.setToolTip(api_file["name"])
            self.table.setItem(row, 0, item)

        layout.addWidget(self.table, stretch=1)

        buttons = QHBoxLayout()
        buttons.addStretch()

        cancel_button = QPushButton("Anuluj")
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(cancel_button)

        self.select_button = QPushButton("Wybierz pozycję")
        self.select_button.setObjectName("primaryButton")
        self.select_button.setEnabled(False)
        self.select_button.clicked.connect(self.accept)
        buttons.addWidget(self.select_button)

        layout.addLayout(buttons)
        self.table.itemSelectionChanged.connect(self._update_selection)

    def _update_selection(self):
        self.select_button.setEnabled(self.table.currentRow() >= 0)

    def selected_file(self):
        row = self.table.currentRow()
        return self.files[row] if row >= 0 else None


class SubmissionPreviewDialog(QDialog):
    def __init__(
        self, workflow_name, expected_filename, file_path, inspection, parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Podgląd wysyłki")
        self.setMinimumWidth(700)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        title = QLabel("Podgląd pliku do wysłania")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        details = [
            ("Workflow", workflow_name),
            ("Nazwa w NIFC", expected_filename),
            ("Plik lokalny", str(file_path)),
        ]
        if workflow_name.startswith("KRN-"):
            details.append(("!!!!SEGMENT:", inspection.segment_name or "brak"))
        details.append(("Rozmiar", format_file_size(file_path.stat().st_size)))

        for label, value in details:
            row = QHBoxLayout()
            heading = QLabel(f"{label}:")
            heading.setMinimumWidth(130)
            text = QLabel(value)
            text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            text.setWordWrap(True)
            row.addWidget(heading)
            row.addWidget(text, stretch=1)
            layout.addLayout(row)

        if inspection.warnings:
            warning = QLabel("Ostrzeżenia:\n" + "\n".join(inspection.warnings))
            warning.setWordWrap(True)
            layout.addWidget(warning)
        else:
            layout.addWidget(QLabel("Kontrola pliku: bez ostrzeżeń."))
        notice = QLabel(
            "Po wysłaniu pliku powrót do edycji w NIFC może nie być możliwy."
        )
        notice.setWordWrap(True)
        layout.addWidget(notice)

        buttons = QHBoxLayout()
        buttons.addStretch()

        close_button = QPushButton("Zamknij")
        close_button.clicked.connect(self.reject)
        buttons.addWidget(close_button)

        self.dry_run_button = QPushButton("Próba wysyłki (na sucho)")
        self.dry_run_button.setObjectName("primaryButton")
        self.dry_run_button.clicked.connect(self.accept)
        buttons.addWidget(self.dry_run_button)
        self.submit_button = QPushButton("Wyślij do NIFC")
        self.submit_button.clicked.connect(lambda: self.done(2))
        buttons.addWidget(self.submit_button)
        layout.addLayout(buttons)
