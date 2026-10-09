import hashlib
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PySide6.QtCore import QDate, Qt, QThread
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from core.credentials import CredentialStore, CredentialStoreError
from core.settlement_store import SettlementStore
from core.settlements import compare_statistics, read_settlement_pdf
from core.statistics import statistics_entries, statistics_months
from gui.workers import StatisticsWorker


class StatisticsDialog(QDialog):
    def __init__(self, configuration_store, parent=None):
        super().__init__(parent)
        self.configuration_store = configuration_store
        self.thread = None
        self.worker = None
        self.entries = ()
        self.snapshot = None
        self.settlements = {}
        self.approved_matches = set()
        self.setWindowTitle("Statystyki i rozliczenia")
        self.setMinimumWidth(420)

        configuration = configuration_store.load()
        today = QDate.currentDate()
        current_month = QDate(today.year(), today.month(), 1)
        saved_month = QDate.fromString(
            configuration.statistics_start_month,
            "yyyy-MM-dd",
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self.unpaid_label = QLabel("Niewypłacone: —")
        font = self.unpaid_label.font()
        font.setPointSize(40)
        font.setBold(True)
        self.unpaid_label.setFont(font)
        self.unpaid_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.unpaid_label.setStyleSheet(
            "font-size: 24px; font-weight: 700; color: #73a2ef;"
        )
        self.unpaid_label.setContentsMargins(0, 0, 0, 0)

        self.refreshed_label = QLabel("Brak zapisanych statystyk.")
        self.refreshed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        period_row = QHBoxLayout()
        period_row.addWidget(QLabel("Licz od:"))

        self.start_month = QDateEdit()
        self.start_month.setDisplayFormat("dd.MM.yyyy")
        self.start_month.setCalendarPopup(True)
        self.start_month.setMaximumDate(today)
        self.start_month.setDate(
            saved_month if saved_month.isValid() else current_month
        )
        period_row.addWidget(self.start_month)

        self.save_button = QPushButton("Zapisz datę")
        self.save_button.clicked.connect(self._save_start_month)
        period_row.addWidget(self.save_button)
        summary_layout = QVBoxLayout()
        summary_layout.setSpacing(4)
        summary_layout.addWidget(self.unpaid_label)
        summary_layout.addWidget(self.refreshed_label)
        period_row.addLayout(summary_layout, stretch=1)

        self.fetch_button = QPushButton("Odśwież statystyki")
        self.fetch_button.clicked.connect(self._fetch_statistics)
        period_row.addWidget(self.fetch_button)
        layout.addLayout(period_row)

        self.status_label = QLabel("Pobierz statystyki dla zapisanego okresu.")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        pdf_header = QHBoxLayout()
        pdf_header.addWidget(QLabel("Wypłacone transze"))
        pdf_header.addStretch()
        self.import_button = QPushButton("Dodaj PDF-y…")
        self.import_button.clicked.connect(self._import_settlements)
        pdf_header.addWidget(self.import_button)

        self.remove_pdf_button = QPushButton("Usuń zaznaczony")
        self.remove_pdf_button.clicked.connect(self._remove_settlement)
        pdf_header.addWidget(self.remove_pdf_button)
        layout.addLayout(pdf_header)

        self.pdf_table = QTableWidget(0, 4)
        self.pdf_table.setHorizontalHeaderLabels(
            ["Dokument", "Wykonawca", "Transza", "Znaki"]
        )
        self.pdf_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.pdf_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.pdf_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.pdf_table.verticalHeader().hide()
        self.pdf_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        for column in (1, 2, 3):
            self.pdf_table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self.pdf_table.setMaximumHeight(180)
        layout.addWidget(self.pdf_table)

        self.report = QTextEdit()
        self.report.setReadOnly(True)
        layout.addWidget(self.report, stretch=1)

        footer = QHBoxLayout()
        footer.addStretch()
        close_button = QPushButton("Zamknij")
        close_button.clicked.connect(self.accept)
        footer.addWidget(close_button)
        layout.addLayout(footer)
        self.resize(1100, 720)

        self.settlement_store = None
        try:
            store = SettlementStore(self.configuration_store)
            self.settlements, self.approved_matches = store.load()
            self.settlement_store = store
            self._refresh_pdf_table()
            snapshot = store.snapshot
            if (
                snapshot is not None
                and snapshot["start_date"] == configuration.statistics_start_month
            ):
                self.snapshot = snapshot
                self.entries = tuple(snapshot["entries"])
            self._show_reconciliation(review=False)

        except (OSError, ValueError, TypeError, KeyError) as error:
            QMessageBox.warning(
                self,
                "Błąd odczytu zapisanych rozliczeń",
                f"{error}\n\nZapis jest zablokowany, aby nie nadpisać danych.",
            )

    def _save_start_month(self):
        selected = self.start_month.date()
        configuration = self.configuration_store.load()
        self.configuration_store.save(
            replace(
                configuration,
                statistics_start_month=selected.toString("yyyy-MM-dd"),
            )
        )
        self.entries = ()
        self.snapshot = None
        self.unpaid_label.setText("Niewypłacone: —")
        self.refreshed_label.setText("Zmieniono okres — odśwież statystyki.")
        self.report.clear()
        self.status_label.setText(
            f"Zapisano: od {selected.toString('dd.MM.yyyy')} włącznie. "
            "Pobierz statystyki ponownie."
        )

    def _fetch_statistics(self):
        if self.thread is not None:
            return

        configuration = self.configuration_store.load()
        try:
            months = statistics_months(configuration.statistics_start_month)
            credentials = CredentialStore().load(configuration.nifc_username)
            if credentials is None:
                raise ValueError("Brak zapisanych danych logowania do NIFC.")
        except (ValueError, CredentialStoreError) as error:
            QMessageBox.warning(self, "Statystyki", str(error))
            return

        self.fetch_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.start_month.setEnabled(False)
        self.status_label.setText("Logowanie do NIFC…")

        self.thread = QThread(self)
        self.worker = StatisticsWorker(credentials, months)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self.status_label.setText)
        self.worker.loaded.connect(self._statistics_loaded)
        self.worker.failed.connect(self._statistics_failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self._fetch_finished)
        self.thread.start()

    def _statistics_loaded(self, data):
        try:
            configuration = self.configuration_store.load()
            self.entries = statistics_entries(
                data,
                start_date=configuration.statistics_start_month,
            )
        except (TypeError, ValueError) as error:
            self._statistics_failed(str(error))
            return

        self.snapshot = {
            "start_date": configuration.statistics_start_month,
            "refreshed_at": datetime.now(ZoneInfo("Europe/Warsaw")).isoformat(
                timespec="seconds"
            ),
            "entries": list(self.entries),
        }
        self.status_label.setText(f"Pobrano {len(self.entries)} pozycji.")
        self._show_reconciliation()

    def _statistics_failed(self, message):
        self.status_label.setText(
            "Odświeżenie nie powiodło się. Zachowano ostatni poprawnie pobrany wynik."
        )
        QMessageBox.warning(self, "Statystyki", message)

    def _fetch_finished(self):
        self.thread = None
        self.worker = None
        self.fetch_button.setEnabled(True)
        self.save_button.setEnabled(True)
        self.start_month.setEnabled(True)

    def done(self, result):
        if self.thread is not None:
            QMessageBox.information(
                self,
                "Pobieranie statystyk",
                "Poczekaj na zakończenie pobierania.",
            )
            return

        if self.settlement_store is not None:
            try:
                self.settlement_store.snapshot = self.snapshot
                self.settlement_store.save(
                    self.settlements,
                    self.approved_matches,
                )
            except (OSError, ValueError, TypeError) as error:
                QMessageBox.warning(
                    self,
                    "Nie zapisano rozliczeń",
                    f"{error}\n\nOkno pozostaje otwarte. Spróbuj zamknąć ponownie.",
                )
                return

        super().done(result)

    def closeEvent(self, event):
        if self.thread is not None:
            event.ignore()
            return
        super().closeEvent(event)

    def _import_settlements(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Wybierz wypłacone transze",
            "",
            "Dokumenty PDF (*.pdf)",
        )
        if not paths:
            return

        imported = {}
        try:
            for path in paths:
                digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
                if digest not in self.settlements:
                    imported[digest] = read_settlement_pdf(path)
                    imported[digest]["filename"] = Path(path).name
        except Exception as error:  # noqa: BLE001
            QMessageBox.warning(self, "Błąd odczytu PDF", str(error))
            return

        self.settlements.update(imported)
        self._refresh_pdf_table()
        self._show_reconciliation()

    def _show_reconciliation(self, *, review=True):
        if self.snapshot is None:
            self.unpaid_label.setText("Niewypłacone: —")
            self.report.setPlainText("Pobierz statystyki dla wybranego okresu.")
            return

        refreshed = datetime.fromisoformat(self.snapshot["refreshed_at"])
        self.refreshed_label.setText(
            f"Odświeżono: {refreshed.strftime('%d.%m.%Y, %H:%M')}"
        )
        if not self.settlements:
            self.unpaid_label.setText("Niewypłacone: —")
            self.report.setPlainText(
                "Dodaj PDF-y wypłaconych transz, aby obliczyć niewypłacone znaki."
            )
            return

        paid_entries = [
            item
            for settlement in self.settlements.values()
            for item in settlement["entries"]
        ]
        result = compare_statistics(self.entries, paid_entries, self.approved_matches)
        for difference in result["differences"] if review else ():
            item = difference["statistics"]
            other = difference["settlement"]
            message = (
                "NIFC:\n"
                f"{item['scheme']} | {item['note_count']} znaków\n"
                f"{item['file_name']}\n\n"
                "PDF:\n"
                f"{other['scheme']} | {other['note_count']} znaków\n"
                f"{other['file_name']}"
            )
            box = QMessageBox(self)
            box.setWindowTitle("Rozbieżność w rozliczeniu")
            box.setIcon(QMessageBox.Icon.Question)
            box.setText(message)
            box.setInformativeText(
                "Sprawdź, czy oba wpisy oznaczają tę samą wypłaconą pozycję."
            )
            accept_button = None
            if item["note_count"] == other["note_count"]:
                accept_button = box.addButton(
                    "Uznaj za wypłacone",
                    QMessageBox.ButtonRole.AcceptRole,
                )
            leave_button = box.addButton(
                "Zostaw do wyjaśnienia",
                QMessageBox.ButtonRole.RejectRole,
            )
            box.setDefaultButton(leave_button)
            box.exec()
            if accept_button is not None and box.clickedButton() is accept_button:
                self.approved_matches.add(difference["identity"])

        result = compare_statistics(self.entries, paid_entries, self.approved_matches)
        count = f"{result['unpaid_total']:,}".replace(",", " ")
        self.unpaid_label.setText(f"Niewypłacone: {count} znaków")
        if result["unresolved_total"]:
            pending = f"{result['unresolved_total']:,}".replace(",", " ")
            self.unpaid_label.setText(
                f"Niewypłacone: {count} znaków\n+ {pending} do wyjaśnienia"
            )
        total = sum(item["note_count"] for item in self.entries)
        lines = []

        for heading, key in (
            ("NIEROZLICZONE", "unpaid"),
            ("DO WYJAŚNIENIA — POWTÓRZENIA LUB RÓŻNE LICZBY ZNAKÓW", "unresolved"),
        ):
            lines.extend(["", heading])
            items = sorted(
                result[key],
                key=lambda item: (
                    item["submission_time"],
                    item["scheme"],
                    item["file_name"],
                ),
            )
            if not items:
                lines.append("Brak.")
            for item in items:
                lines.append(
                    f"{item['submission_time'][:10]} | {item['scheme']} | "
                    f"{item['note_count']} | {item['file_name']}"
                )

        lines.extend(["", "POZYCJE PDF BEZ ODPOWIEDNIKA W POBRANYCH DANYCH"])
        if not result["outside"]:
            lines.append("Brak.")
        for item in result["outside"]:
            lines.append(
                f"{item['scheme']} | {item['note_count']} | {item['file_name']}"
            )
        lines.extend(
            [
                "",
                "SZCZEGÓŁY PODSUMOWANIA",
                f"Wszystkie znaki w okresie: {total}",
                f"Wypłacone — dopasowane: {result['paid_total']}",
                f"Do wyjaśnienia: {result['unresolved_total']}",
                f"Wczytane PDF-y: {len(self.settlements)}",
            ]
        )
        self.report.setPlainText("\n".join(lines))

    def _refresh_pdf_table(self):
        self.pdf_table.setRowCount(0)
        for digest, settlement in self.settlements.items():
            row = self.pdf_table.rowCount()
            self.pdf_table.insertRow(row)
            tranches = sorted({item["tranche"] for item in settlement["entries"]})
            values = (
                settlement.get("filename", "Dokument PDF"),
                settlement["performer"],
                ", ".join(str(value) for value in tranches),
                f"{settlement['total']:,}".replace(",", " "),
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setToolTip(value)
                if column == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, digest)
                self.pdf_table.setItem(row, column, cell)

    def _remove_settlement(self):
        row = self.pdf_table.currentRow()
        if row < 0:
            return
        digest = self.pdf_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        del self.settlements[digest]
        self._refresh_pdf_table()
        self._show_reconciliation()
