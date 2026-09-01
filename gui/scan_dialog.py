from urllib.parse import urlparse

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.filesystem import format_file_size


class ScanSelectionDialog(QDialog):
    def __init__(self, plans, parent=None):
        super().__init__(parent)
        self.plans = tuple(plans)
        self.setWindowTitle("Brakujące skany")
        self.setMinimumSize(820, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        title = QLabel("Znaleziono brakujące skany")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        layout.addWidget(
            QLabel(
                "Wybierz pakiety do pobrania. Rozmiar i format "
                "są podane przed rozpoczęciem transferu."
            )
        )

        self.table = QTableWidget(len(self.plans), 4)
        self.table.setHorizontalHeaderLabels(
            ("Utwór / sygnatura", "Źródło", "Format", "Rozmiar")
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        for column in (1, 2, 3):
            self.table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )

        for row, plan in enumerate(self.plans):
            name_item = QTableWidgetItem(plan.transcription_name)
            name_item.setFlags(
                name_item.flags() | Qt.ItemFlag.ItemIsUserCheckable
            )
            name_item.setCheckState(Qt.CheckState.Checked)
            name_item.setToolTip(plan.transcription_name)
            self.table.setItem(row, 0, name_item)

            host = urlparse(plan.source_url).netloc or "nieznane"
            self.table.setItem(row, 1, QTableWidgetItem(host))
            self.table.setItem(
                row,
                2,
                QTableWidgetItem(
                    plan.download_info.content_type or "nieznany"
                ),
            )
            size_item = QTableWidgetItem(
                format_file_size(plan.download_info.size)
            )
            size_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight
                | Qt.AlignmentFlag.AlignVCenter
            )
            self.table.setItem(row, 3, size_item)

        self.table.itemChanged.connect(self._update_summary)
        layout.addWidget(self.table, stretch=1)

        selection_layout = QHBoxLayout()
        select_all = QPushButton("Zaznacz wszystkie")
        select_all.clicked.connect(lambda: self._set_all(True))
        select_none = QPushButton("Odznacz wszystkie")
        select_none.clicked.connect(lambda: self._set_all(False))
        selection_layout.addWidget(select_all)
        selection_layout.addWidget(select_none)
        selection_layout.addStretch()
        self.summary_label = QLabel()
        selection_layout.addWidget(self.summary_label)
        layout.addLayout(selection_layout)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel_button = QPushButton("Anuluj")
        cancel_button.clicked.connect(self.reject)
        self.download_button = QPushButton("Pobierz wybrane")
        self.download_button.setObjectName("primaryButton")
        self.download_button.clicked.connect(self.accept)
        buttons.addWidget(cancel_button)
        buttons.addWidget(self.download_button)
        layout.addLayout(buttons)

        self._update_summary()

    def selected_plans(self):
        return tuple(
            plan
            for row, plan in enumerate(self.plans)
            if self.table.item(row, 0).checkState()
            == Qt.CheckState.Checked
        )

    def _set_all(self, checked):
        state = (
            Qt.CheckState.Checked
            if checked
            else Qt.CheckState.Unchecked
        )
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setCheckState(state)
        self.table.blockSignals(False)
        self._update_summary()

    def _update_summary(self):
        selected = self.selected_plans()
        known_size = sum(
            plan.download_info.size or 0 for plan in selected
        )
        unknown_count = sum(
            plan.download_info.size is None for plan in selected
        )
        size_text = format_file_size(known_size)
        if unknown_count:
            size_text += f" + {unknown_count} o nieznanym rozmiarze"
        self.summary_label.setText(
            f"Wybrano: {len(selected)} / {len(self.plans)}  •  {size_text}"
        )
        self.download_button.setEnabled(bool(selected))
