from PySide6.QtCore import QEvent, QRect, Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class CenteredCheckboxDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        style = option.widget.style() if option.widget else QApplication.style()
        checkbox = QStyleOptionButton()
        checkbox.state = QStyle.StateFlag.State_Enabled
        checked = index.data(Qt.ItemDataRole.CheckStateRole)
        checkbox.state |= (
            QStyle.StateFlag.State_On
            if checked in (Qt.CheckState.Checked, Qt.CheckState.Checked.value)
            else QStyle.StateFlag.State_Off
        )
        width = style.pixelMetric(QStyle.PixelMetric.PM_IndicatorWidth)
        height = style.pixelMetric(QStyle.PixelMetric.PM_IndicatorHeight)
        checkbox.rect = QRect(0, 0, width, height)
        checkbox.rect.moveCenter(option.rect.center())
        style.drawControl(
            QStyle.ControlElement.CE_CheckBox, checkbox, painter, option.widget
        )

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.Type.MouseButtonRelease:
            if event.button() != Qt.MouseButton.LeftButton:
                return False
        elif event.type() == QEvent.Type.KeyPress:
            if event.key() not in (Qt.Key.Key_Space, Qt.Key.Key_Select):
                return False
        else:
            return False
        checked = index.data(Qt.ItemDataRole.CheckStateRole)
        state = (
            Qt.CheckState.Unchecked
            if checked in (Qt.CheckState.Checked, Qt.CheckState.Checked.value)
            else Qt.CheckState.Checked
        )
        return model.setData(index, state, Qt.ItemDataRole.CheckStateRole)


class DownloadSelectionDialog(QDialog):
    def __init__(self, workflow, parent=None):
        super().__init__(parent)
        self.files = tuple(workflow["files"])

        self.setWindowTitle(f"Pobierz pliki — {workflow['name']}")
        self.setMinimumSize(760, 460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        title = QLabel("Wybierz pozycje do pobrania")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        self.table = QTableWidget(len(self.files), 2)
        self.table.setHorizontalHeaderLabels(("Pobierz", "Nazwa pliku w NIFC"))
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 82)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setItemDelegateForColumn(0, CenteredCheckboxDelegate(self.table))

        for row, api_file in enumerate(self.files):
            checkbox_item = QTableWidgetItem()
            checkbox_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
            )
            checkbox_item.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, checkbox_item)

            name_item = QTableWidgetItem(api_file["name"])
            name_item.setToolTip(api_file["name"])
            self.table.setItem(row, 1, name_item)

        layout.addWidget(self.table, stretch=1)

        self.download_scans_checkbox = QCheckBox("Pobierz także przypisane skany")
        self.download_scans_checkbox.setChecked(True)
        layout.addWidget(self.download_scans_checkbox)

        buttons = QHBoxLayout()

        select_all_button = QPushButton("Zaznacz wszystko")
        select_all_button.clicked.connect(self._select_all)
        buttons.addWidget(select_all_button)

        clear_button = QPushButton("Odznacz wszystko")
        clear_button.clicked.connect(self._clear_selection)
        buttons.addWidget(clear_button)

        buttons.addStretch()

        cancel_button = QPushButton("Anuluj")
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(cancel_button)

        self.download_button = QPushButton("Pobierz zaznaczone")
        self.download_button.setObjectName("primaryButton")
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self.accept)
        buttons.addWidget(self.download_button)

        layout.addLayout(buttons)
        self.table.itemChanged.connect(self._update_download_button)

    def _set_all_checked(self, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked

        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setCheckState(state)
        self.table.blockSignals(False)
        self._update_download_button()

    def _select_all(self):
        self._set_all_checked(True)

    def _clear_selection(self):
        self._set_all_checked(False)

    def _update_download_button(self):
        self.download_button.setEnabled(bool(self.selected_files()))

    def selected_files(self):
        return tuple(
            api_file
            for row, api_file in enumerate(self.files)
            if self.table.item(row, 0).checkState() == Qt.CheckState.Checked
        )

    def download_scans(self):
        return self.download_scans_checkbox.isChecked()
