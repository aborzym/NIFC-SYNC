import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QLabel

from core.filesystem import format_file_modified
from core.submission import SubmissionInspection
from gui.main_window import MainWindow
from gui.statistics_dialog import StatisticsDialog
from gui.submission_dialog import SubmissionPreviewDialog


class SubmissionStatisticsDetailsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def snapshot(self, entries=None):
        return {
            "start_date": "2026-01-01",
            "refreshed_at": "2026-10-17T15:00:00+02:00",
            "entries": entries if entries is not None else [
                {"note_count": 1200}, {"note_count": 345}
            ],
        }

    def statistics_dialog(self, snapshot):
        configuration = Mock()
        configuration.load.return_value.statistics_start_month = "2026-01-01"
        with patch("gui.statistics_dialog.SettlementStore") as factory:
            factory.return_value.load.return_value = ({}, set())
            factory.return_value.snapshot = snapshot
            factory.return_value.sync_error = ""
            factory.return_value.sync_folder = ""
            dialog = StatisticsDialog(configuration, credential_store=Mock())
        self.addCleanup(dialog.close)
        return dialog

    def test_local_modification_time_and_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "score.xml"
            path.touch()
            modified = datetime(2026, 10, 17, 14, 30, 25)
            os.utime(path, (modified.timestamp(), modified.timestamp()))
            self.assertEqual(format_file_modified(path), "17.10.2026, 14:30:25")
            dialog = SubmissionPreviewDialog(
                "XML", path.name, path, SubmissionInspection(path.name, None, ())
            )
            self.addCleanup(dialog.close)
            labels = [label.text() for label in dialog.findChildren(QLabel)]
            self.assertIn("Ostatnia modyfikacja:", labels)
            self.assertIn("17.10.2026, 14:30:25", labels)

    def test_missing_file_has_explicit_unknown_date(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(
                format_file_modified(Path(directory) / "missing.xml"),
                "nie można odczytać",
            )

    def test_statistics_total_is_available_without_payment_pdfs(self):
        dialog = self.statistics_dialog(self.snapshot())
        self.assertEqual(
            dialog.total_label.text(),
            "Łącznie wykonano: 1 545 znaków · od 01.01.2026",
        )
        self.assertEqual(dialog.unpaid_label.text(), "Niewypłacone: —")

    def test_empty_statistics_show_zero(self):
        dialog = self.statistics_dialog(self.snapshot([]))
        self.assertIn("0 znaków", dialog.total_label.text())

    def test_missing_snapshot_does_not_show_zero_as_known_total(self):
        dialog = self.statistics_dialog(None)
        self.assertEqual(dialog.total_label.text(), "Łącznie wykonano: —")

    def test_changing_period_clears_previous_total(self):
        dialog = self.statistics_dialog(self.snapshot())
        dialog.configuration_store.load.return_value = SimpleNamespace()
        dialog.start_month.setDate(QDate(2026, 2, 1))
        with patch("gui.statistics_dialog.replace", return_value=Mock()):
            dialog._save_start_month()
        self.assertEqual(dialog.total_label.text(), "Łącznie wykonano: —")

    def test_main_summary_shows_only_unpaid_and_resets_for_different_period(self):
        configuration = Mock()
        configuration.load.return_value.statistics_start_month = "2026-01-01"
        window = SimpleNamespace(
            configuration_store=configuration,
            unpaid_summary_label=QLabel(),
            unpaid_updated_label=QLabel(),
        )
        with (
            patch("gui.main_window.SettlementStore") as factory,
            patch("gui.main_window.compare_statistics") as compare,
        ):
            factory.return_value.load.return_value = ({"pdf": {"entries": []}}, set())
            factory.return_value.snapshot = self.snapshot()
            compare.return_value = {"unpaid_total": 345, "unresolved_total": 0}
            MainWindow._refresh_unpaid_summary(window)
            self.assertEqual(window.unpaid_summary_label.text(), "Niewypłacone: 345 znaków")
            self.assertFalse(window.unpaid_summary_label.isHidden())
            self.assertFalse(hasattr(window, "total_summary_label"))
            configuration.load.return_value.statistics_start_month = "2026-02-01"
            MainWindow._refresh_unpaid_summary(window)
            self.assertTrue(window.unpaid_summary_label.isHidden())
            self.assertEqual(window.unpaid_summary_label.text(), "Niewypłacone: —")


if __name__ == "__main__":
    unittest.main()
