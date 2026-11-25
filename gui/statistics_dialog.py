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
    QInputDialog,
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
    def __init__(self, configuration_store, parent=None, *, credential_store=None):
        super().__init__(parent)
        self.configuration_store = configuration_store
        self.credential_store = credential_store or CredentialStore()
        self.thread = None
        self.worker = None
        self.entries = ()
        self.snapshot = None
        self.settlements = {}
        self.approved_matches = set()
        self.deferred_matches = set()
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
        self.unpaid_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        font = self.unpaid_label.font()
        font.setPointSize(40)
        font.setBold(True)
        self.unpaid_label.setFont(font)
        self.unpaid_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.unpaid_label.setStyleSheet(
            "font-size: 24px; font-weight: 700; color: #73a2ef;"
        )
        self.unpaid_label.setContentsMargins(0, 0, 0, 0)

        self.total_label = QLabel("Łącznie wykonano: —")
        self.total_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.total_label.setStyleSheet(
            "font-size: 13px; font-weight: 400; color: #9aaac2;"
        )
        self.total_label.setWordWrap(True)

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
        summary_layout.addWidget(self.total_label)
        summary_layout.addWidget(self.refreshed_label)
        period_row.addLayout(summary_layout, stretch=1)

        self.fetch_button = QPushButton("Odśwież statystyki")
        self.fetch_button.clicked.connect(self._fetch_statistics)
        period_row.addWidget(self.fetch_button)
        layout.addLayout(period_row)

        self.status_label = QLabel("Pobierz statystyki dla zapisanego okresu.")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        sync_row = QHBoxLayout()
        self.sync_folder_button = QPushButton("Folder synchronizacji…")
        self.sync_folder_button.clicked.connect(self._choose_sync_folder)
        sync_row.addWidget(self.sync_folder_button)
        self.sync_button = QPushButton("Synchronizuj rozliczenia")
        self.sync_button.clicked.connect(self._sync_settlements)
        sync_row.addWidget(self.sync_button)
        self.local_button = QPushButton("Tylko lokalnie")
        self.local_button.clicked.connect(self._disable_sync)
        sync_row.addWidget(self.local_button)
        self.sync_label = QLabel("Synchronizacja wyłączona — zapis lokalny.")
        self.sync_label.setWordWrap(True)
        sync_row.addWidget(self.sync_label, stretch=1)
        layout.addLayout(sync_row)

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

        report_header = QHBoxLayout()
        report_header.addStretch()
        self.approved_differences_button = QPushButton("Decyzje rozliczeń…")
        self.approved_differences_button.clicked.connect(
            self._show_approved_differences
        )
        report_header.addWidget(self.approved_differences_button)
        self.revisions_button = QPushButton("Rewizje PDF…")
        self.revisions_button.clicked.connect(self._review_revisions)
        report_header.addWidget(self.revisions_button)
        layout.addLayout(report_header)

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
            self.deferred_matches = set(store.deferred_matches)
            self.accepted_revisions = set(store.accepted_revisions)
            self.settlement_store = store
            self._update_sync_status()
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

    def _update_sync_status(self):
        store = self.settlement_store
        if store is None:
            return
        if store.sync_error:
            self.sync_label.setText(
                f"Zapis lokalny; synchronizacja oczekuje: {store.sync_error}"
            )
        elif store.sync_folder:
            self.sync_label.setText(
                "Połączono z folderem. Dostarczenie na drugi komputer zależy "
                "od aplikacji synchronizującej."
            )
        else:
            self.sync_label.setText("Synchronizacja wyłączona — zapis lokalny.")
        self.sync_label.setToolTip(str(store.sync_folder))

    def _choose_sync_folder(self):
        if self.settlement_store is None:
            return
        folder = QFileDialog.getExistingDirectory(
            self,
            "Wybierz wspólny folder rozliczeń (np. Dropbox/NIFC-SYNC)",
            self.settlement_store.sync_folder or str(Path.home() / "Dropbox"),
        )
        if not folder:
            return
        try:
            self.settlement_store.set_sync_folder(folder)
        except OSError as error:
            QMessageBox.warning(self, "Synchronizacja rozliczeń", str(error))
            return
        self._sync_settlements()

    def _disable_sync(self):
        if self.settlement_store is None:
            return
        try:
            self.settlement_store.set_sync_folder("")
            self.settlement_store.sync_error = ""
            self._update_sync_status()
        except OSError as error:
            QMessageBox.warning(self, "Synchronizacja rozliczeń", str(error))

    def _sync_settlements(self):
        if self.settlement_store is None:
            return
        try:
            self.settlement_store.snapshot = self.snapshot
            self.settlements, self.approved_matches = self.settlement_store.synchronize(
                self.settlements,
                self.approved_matches,
                self.deferred_matches,
                self.accepted_revisions,
            )
            self.deferred_matches = set(self.settlement_store.deferred_matches)
            self.accepted_revisions = set(self.settlement_store.accepted_revisions)
            self._refresh_pdf_table()
            self._show_reconciliation(review=False)
            self._update_sync_status()
        except (OSError, ValueError, TypeError, KeyError) as error:
            QMessageBox.warning(self, "Synchronizacja rozliczeń", str(error))

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
        self.total_label.setText("Łącznie wykonano: —")
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
            credentials = self.credential_store.load(configuration.nifc_username)
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
                    self.deferred_matches,
                    self.accepted_revisions,
                )
                if self.settlement_store.sync_error:
                    QMessageBox.warning(
                        self,
                        "Rozliczenia zapisane lokalnie",
                        "Nie udało się zsynchronizować rozliczeń. "
                        "Spróbujemy ponownie przy otwarciu okna.\n\n"
                        + str(self.settlement_store.sync_error),
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

    def _paid_entries(self):
        return [
            {**item, "_pdf_id": (digest, index)}
            for digest, settlement in self.settlements.items()
            for index, item in enumerate(settlement["entries"])
        ]

    def _show_reconciliation(self, *, review=True):
        if self.snapshot is None:
            self.unpaid_label.setText("Niewypłacone: —")
            self.total_label.setText("Łącznie wykonano: —")
            self.report.setPlainText("Pobierz statystyki dla wybranego okresu.")
            return

        total = sum(item["note_count"] for item in self.entries)
        count_total = f"{total:,}".replace(",", " ")
        start = datetime.fromisoformat(self.snapshot["start_date"]).strftime("%d.%m.%Y")
        self.total_label.setText(f"Łącznie wykonano: {count_total} znaków · od {start}")
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

        paid_entries = self._paid_entries()
        result = compare_statistics(
            self.entries,
            paid_entries,
            self.approved_matches,
            self.accepted_revisions,
        )
        for difference in result["differences"] if review else ():
            if difference["identity"] in self.deferred_matches:
                continue
            item = difference["statistics"]
            other = difference["settlement"]
            reasons = []
            if item["scheme"] != other["scheme"]:
                reasons.append("Inny rodzaj transkrypcji.")
            if item["file_name"] != other["file_name"]:
                reasons.append("Inna nazwa pliku.")
            if item["note_count"] != other["note_count"]:
                reasons.append("Inna liczba znaków.")

            message = (
                "NIFC:\n"
                f"{item['scheme']} | {item['note_count']} znaków\n"
                f"{item['file_name']}\n\n"
                "PDF:\n"
                f"{other['scheme']} | {other['note_count']} znaków\n"
                f"{other['file_name']}"
            )
            explanation = (
                "Powód: "
                + " ".join(reasons)
                + "\nSprawdź, czy oba wpisy oznaczają tę samą wypłaconą pozycję."
            )
            difference_count = item["note_count"] - other["note_count"]
            project_id = item["file_name"].split("_", 1)[0]
            corrections = [
                correction
                for correction in self.entries
                if difference_count > 0
                and correction["scheme"] == item["scheme"]
                and correction["note_count"] == -difference_count
                and f"-{project_id}-" in correction["file_name"]
            ]
            if len(corrections) == 1:
                explanation += (
                    "\n\nPrawdopodobna korekta uwzględniona w PDF:\n"
                    f"{corrections[0]['note_count']} znaków\n"
                    f"{corrections[0]['file_name']}\n"
                    "Potwierdź tylko, jeśli PDF uwzględnia tę korektę."
                )
            dialog = QDialog(self)
            dialog.setWindowTitle("Rozbieżność w rozliczeniu")
            dialog.resize(1050, 430)
            dialog_layout = QVBoxLayout(dialog)

            details = QTextEdit(dialog)
            details.setReadOnly(True)
            details.setPlainText(message + "\n\n" + explanation)
            dialog_layout.addWidget(details)

            buttons = QHBoxLayout()
            leave_button = QPushButton("Zostaw do wyjaśnienia", dialog)
            approve_button = QPushButton(
                (
                    "Uznaj za wypłacone"
                    if item["note_count"] == other["note_count"]
                    else "Uznaj kwotę z PDF"
                ),
                dialog,
            )
            leave_button.setMinimumWidth(220)
            approve_button.setMinimumWidth(220)
            leave_button.clicked.connect(
                lambda _checked=False, current_dialog=dialog: current_dialog.done(2)
            )
            approve_button.clicked.connect(
                lambda _checked=False, current_dialog=dialog: current_dialog.done(1)
            )
            buttons.addWidget(leave_button)
            buttons.addStretch()
            buttons.addWidget(approve_button)
            dialog_layout.addLayout(buttons)

            choice = dialog.exec()
            if choice == 1:
                self.approved_matches.add(difference["identity"])
                self.deferred_matches.discard(difference["identity"])
            elif choice == 2:
                self.deferred_matches.add(difference["identity"])

        result = compare_statistics(
            self.entries,
            paid_entries,
            self.approved_matches,
            self.accepted_revisions,
        )
        count = f"{result['unpaid_total']:,}".replace(",", " ")
        self.unpaid_label.setText(f"Niewypłacone: {count} znaków")
        if result["unresolved_total"]:
            pending = f"{result['unresolved_total']:,}".replace(",", " ")
            self.unpaid_label.setText(
                f"Niewypłacone: {count} znaków\n+ {pending} do wyjaśnienia"
            )
        total = sum(item["note_count"] for item in self.entries)
        lines = []

        def is_revision(item):
            return ".krn-revision" in item["file_name"].casefold()

        for heading, key in (
            ("NIEROZLICZONE", "unpaid"),
            ("DO WYJAŚNIENIA — RÓŻNICE NAZW, WORKFLOW LUB LICZBY ZNAKÓW", "unresolved"),
        ):
            lines.extend(["", heading])
            items = sorted(
                (item for item in result[key] if not is_revision(item)),
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
        outside_regular = [item for item in result["outside"] if not is_revision(item)]
        if not outside_regular:
            lines.append("Brak.")
        for item in outside_regular:
            lines.append(
                f"{item['scheme']} | {item['note_count']} | {item['file_name']}"
            )

        lines.extend(["", "REVISIONS"])
        revisions = [
            ("NIFC — nierozliczone", item)
            for item in result["unpaid"]
            if is_revision(item)
        ]
        revisions.extend(
            ("NIFC — do wyjaśnienia", item)
            for item in result["unresolved"]
            if is_revision(item)
        )
        revisions.extend(
            ("PDF — bez przypisanej pozycji NIFC", item)
            for item in result["outside"]
            if is_revision(item)
        )
        revisions.extend(
            ("PDF — uznana rewizja", item) for item in result["accepted_revisions"]
        )
        if not revisions:
            lines.append("Brak.")
        for status, item in revisions:
            lines.append(
                f"{status} | {item['scheme']} | {item['note_count']} | "
                f"{item['file_name']}"
            )

        corrections = [item for item in self.entries if item["note_count"] < 0]
        correction_total = sum(item["note_count"] for item in corrections)

        lines.extend(
            [
                "",
                "SZCZEGÓŁY PODSUMOWANIA",
                f"Wszystkie znaki w okresie (po korektach): {total}",
                f"Korekty znaków łącznie: {correction_total}",
                (
                    "Korekty jeszcze nieuwzględnione w PDF-ach: "
                    f"{sum(item['note_count'] for item in result['pending_corrections'])}"
                ),
                f"Wypłacone — łącznie: {result['paid_total']}",
                (f"W tym rewizje uznane z PDF: {result['accepted_revision_total']}"),
                f"Do wyjaśnienia: {result['unresolved_total']}",
                f"Wczytane PDF-y: {len(self.settlements)}",
            ]
        )
        for heading, key in (
            ("KOREKTY — OCZEKUJĄ NA PDF", "pending_corrections"),
            ("KOREKTY — UJĘTE W PDF", "settled_corrections"),
        ):
            lines.extend(["", heading])
            if not result[key]:
                lines.append("Brak.")
            for item in result[key]:
                method = ""
                if key == "settled_corrections":
                    method = (
                        " | uwzględniona w kwocie utworu"
                        if item in result["implicit_corrections"]
                        else " | osobna pozycja PDF"
                    )
                lines.append(
                    f"{item['submission_time'][:10]} | {item['scheme']} | "
                    f"{item['note_count']} | {item['file_name']}{method}"
                )
        self.report.setPlainText("\n".join(lines))

    def _review_revisions(self):
        if self.snapshot is None or not self.settlements:
            QMessageBox.information(
                self,
                "Rewizje PDF",
                "Najpierw pobierz statystyki i dodaj PDF-y rozliczeń.",
            )
            return

        result = compare_statistics(
            self.entries,
            self._paid_entries(),
            self.approved_matches,
            self.accepted_revisions,
        )
        revisions = [
            item
            for item in result["outside"]
            if ".krn-revision" in item["file_name"].casefold()
        ]
        revisions.extend(result["accepted_revisions"])

        if not revisions:
            QMessageBox.information(self, "Rewizje PDF", "Brak rewizji do oceny.")
            return

        labels = []
        for item in revisions:
            digest, index = item["_pdf_id"]
            filename = self.settlements[digest].get("filename", "Dokument PDF")
            status = (
                "UZNANA" if item["_pdf_id"] in self.accepted_revisions else "DO OCENY"
            )
            labels.append(
                f"{status} | {filename} | pozycja {index + 1} | "
                f"{item['note_count']} | {item['file_name']}"
            )

        selected, accepted = QInputDialog.getItem(
            self, "Rewizje PDF", "Wybierz pozycję:", labels, 0, False
        )
        if not accepted:
            return

        item = revisions[labels.index(selected)]
        pdf_id = item["_pdf_id"]
        filename = self.settlements[pdf_id[0]].get("filename", "Dokument PDF")
        already_accepted = pdf_id in self.accepted_revisions

        dialog = QDialog(self)
        dialog.setWindowTitle("Decyzja o rewizji PDF")
        dialog.resize(1000, 380)
        dialog_layout = QVBoxLayout(dialog)

        details = QTextEdit(dialog)
        details.setReadOnly(True)
        details.setPlainText(
            f"PDF: {filename}\n"
            f"Transza: {item['tranche']}\n"
            f"Pozycja w PDF: {pdf_id[1] + 1}\n"
            f"Workflow: {item['scheme']}\n"
            f"Znaki: {item['note_count']}\n"
            f"Nazwa: {item['file_name']}\n\n"
            "Ta rewizja jest osobną pozycją PDF. Jej uznanie doliczy "
            "wskazaną liczbę znaków do wypłaconych."
        )
        dialog_layout.addWidget(details)

        buttons = QHBoxLayout()
        cancel_button = QPushButton("Bez zmian", dialog)
        action_button = QPushButton(
            "Cofnij uznanie rewizji" if already_accepted else "Uznaj rewizję z PDF",
            dialog,
        )
        action_button.setMinimumWidth(240)
        cancel_button.clicked.connect(dialog.reject)
        action_button.clicked.connect(dialog.accept)
        buttons.addStretch()
        buttons.addWidget(cancel_button)
        buttons.addWidget(action_button)
        dialog_layout.addLayout(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if already_accepted:
            self.accepted_revisions.remove(pdf_id)
        else:
            self.accepted_revisions.add(pdf_id)
        self._show_reconciliation(review=False)

    def _show_approved_differences(self):
        if self.snapshot is None or not self.settlements:
            QMessageBox.information(
                self,
                "Decyzje rozliczeń",
                "Najpierw pobierz statystyki i dodaj PDF-y rozliczeń.",
            )
            return

        paid_entries = self._paid_entries()
        candidates = compare_statistics(self.entries, paid_entries)["differences"]
        decisions = [
            difference
            for difference in candidates
            if difference["identity"] in self.approved_matches
            or difference["identity"] in self.deferred_matches
        ]
        if not decisions:
            QMessageBox.information(
                self, "Decyzje rozliczeń", "Brak zapisanych decyzji."
            )
            return

        labels = []
        for difference in decisions:
            item = difference["statistics"]
            state = (
                "Uznano PDF"
                if difference["identity"] in self.approved_matches
                else "Do wyjaśnienia"
            )
            labels.append(
                f"{state} | {item['scheme']} | {item['note_count']} | "
                f"{item['file_name']}"
            )

        selected, accepted = QInputDialog.getItem(
            self, "Decyzje rozliczeń", "Wybierz pozycję:", labels, 0, False
        )
        if not accepted:
            return
        difference = decisions[labels.index(selected)]
        item = difference["statistics"]
        other = difference["settlement"]

        difference_count = item["note_count"] - other["note_count"]
        project_id = item["file_name"].split("_", 1)[0]
        corrections = [
            correction
            for correction in self.entries
            if difference_count > 0
            and correction["scheme"] == item["scheme"]
            and correction["note_count"] == -difference_count
            and f"-{project_id}-" in correction["file_name"]
        ]

        details = [
            f"NIFC: {item['scheme']} | {item['note_count']} znaków",
            item["file_name"],
            "",
            f"PDF: {other['scheme']} | {other['note_count']} znaków",
            other["file_name"],
            "",
            f"Różnica NIFC − PDF: {difference_count:+d} znaków",
        ]
        if len(corrections) == 1:
            correction = corrections[0]
            details.extend(
                [
                    "",
                    "PRAWDOPODOBNA KOREKTA UJĘTA W KWOCIE PDF:",
                    f"{correction['note_count']} znaków",
                    correction["file_name"],
                    "",
                    "Potwierdź tylko, jeśli PDF uwzględnia tę korektę.",
                ]
            )

        dialog = QDialog(self)
        dialog.setWindowTitle("Zmień decyzję rozliczenia")
        dialog.resize(1050, 430)
        dialog_layout = QVBoxLayout(dialog)

        description = QTextEdit(dialog)
        description.setReadOnly(True)
        description.setPlainText("\n".join(details))
        dialog_layout.addWidget(description)

        buttons = QHBoxLayout()
        defer_button = QPushButton("Zostaw do wyjaśnienia", dialog)
        reset_button = QPushButton("Cofnij decyzję", dialog)
        approve_button = QPushButton("Uznaj kwotę z PDF", dialog)
        for button in (defer_button, reset_button, approve_button):
            button.setMinimumWidth(220)
        defer_button.clicked.connect(lambda: dialog.done(2))
        reset_button.clicked.connect(lambda: dialog.done(3))
        approve_button.clicked.connect(lambda: dialog.done(1))
        buttons.addWidget(defer_button)
        buttons.addWidget(reset_button)
        buttons.addStretch()
        buttons.addWidget(approve_button)
        dialog_layout.addLayout(buttons)

        choice = dialog.exec()
        identity = difference["identity"]
        if choice == 1:
            self.approved_matches.add(identity)
            self.deferred_matches.discard(identity)
        elif choice == 2:
            self.approved_matches.discard(identity)
            self.deferred_matches.add(identity)
        elif choice == 3:
            self.approved_matches.discard(identity)
            self.deferred_matches.discard(identity)
        else:
            return
        self._show_reconciliation(review=False)

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
