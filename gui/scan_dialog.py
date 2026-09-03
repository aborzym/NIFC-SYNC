from urllib.parse import urlparse

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QColor
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
        self.setWindowTitle("Skany wymagające pobrania")
        self.setMinimumSize(980, 420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        title = QLabel("Skany wymagające pobrania")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        layout.addWidget(
            QLabel(
                "Wybierz pakiety do pobrania. Rozmiar i format "
                "są podane przed rozpoczęciem transferu."
            )
        )

        self.table = QTableWidget(
            len(self.plans),
            6,
        )
        self.table.setHorizontalHeaderLabels(
            (
                "Utwór / sygnatura",
                "Stan",
                "Źródło",
                "Folder docelowy",
                "Format",
                "Rozmiar",
            )
        )

        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)

        initial_widths = (
            280,  # Utwór / sygnatura
            170,  # Stan
            130,  # Źródło
            220,  # Folder docelowy
            90,  # Format
            80,  # Rozmiar
        )

        for column, width in enumerate(initial_widths):
            self.table.setColumnWidth(column, width)

        for row, plan in enumerate(self.plans):
            name_item = QTableWidgetItem(plan.transcription_name)
            name_item.setFlags(name_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            name_item.setCheckState(Qt.CheckState.Checked)
            name_item.setToolTip(plan.transcription_name)
            self.table.setItem(row, 0, name_item)

            if plan.is_incomplete:
                status_item = QTableWidgetItem("Niekompletny — do naprawy")
                status_item.setForeground(QColor("#f4b86a"))
            else:
                status_item = QTableWidgetItem("Brak — do pobrania")
                status_item.setForeground(QColor("#9fb2c8"))
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 1, status_item)

            host = urlparse(plan.source_url).netloc or "nieznane"
            self.table.setItem(
                row,
                2,
                QTableWidgetItem(host),
            )

            target_path = plan.destination_folder / plan.output_folder_name
            destination_item = QTableWidgetItem(
                f"{plan.destination_folder.name}/{plan.output_folder_name}"
            )
            destination_item.setToolTip(str(target_path))
            self.table.setItem(
                row,
                3,
                destination_item,
            )

            format_item = QTableWidgetItem(
                plan.download_info.content_type or "nieznany"
            )
            format_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 4, format_item)
            size_item = QTableWidgetItem(format_file_size(plan.download_info.size))
            size_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.table.setItem(row, 5, size_item)

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
        QTimer.singleShot(
            0,
            self._fit_columns_to_width,
        )
        self._restore_geometry()

    def _restore_geometry(self):
        geometry = QSettings().value("scan_dialog/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

    def done(self, result):
        QSettings().setValue(
            "scan_dialog/geometry",
            self.saveGeometry(),
        )
        super().done(result)

    def selected_plans(self):
        return tuple(
            plan
            for row, plan in enumerate(self.plans)
            if self.table.item(row, 0).checkState() == Qt.CheckState.Checked
        )

    def _fit_columns_to_width(self):
        available_width = self.table.viewport().width()
        column_widths = [
            self.table.columnWidth(column) for column in range(self.table.columnCount())
        ]
        current_width = sum(column_widths)

        if available_width <= 0 or current_width <= 0:
            return

        scale = available_width / current_width
        scaled_widths = [round(width * scale) for width in column_widths]

        scaled_widths[-1] += available_width - sum(scaled_widths)

        for column, width in enumerate(scaled_widths):
            self.table.setColumnWidth(
                column,
                max(50, width),
            )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_columns_to_width()

    def _set_all(self, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setCheckState(state)
        self.table.blockSignals(False)
        self._update_summary()

    def _update_summary(self):
        selected = self.selected_plans()
        known_size = sum(plan.download_info.size or 0 for plan in selected)
        unknown_count = sum(plan.download_info.size is None for plan in selected)
        size_text = format_file_size(known_size)
        if unknown_count:
            size_text += f" + {unknown_count} o nieznanym rozmiarze"
        self.summary_label.setText(
            f"Wybrano: {len(selected)} / {len(self.plans)}  •  {size_text}"
        )
        self.download_button.setEnabled(bool(selected))
