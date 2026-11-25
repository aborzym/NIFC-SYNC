import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.settlement_sync import materialize, record_changes
from core.settlements import compare_statistics, parse_settlement_text

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QLabel

from core.configuration import AppConfiguration
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
            "entries": entries
            if entries is not None
            else [{"note_count": 1200}, {"note_count": 345}],
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

    def test_submission_moves_prefixed_project_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            project = base / "PILNE - 140 - D - utwor"
            project.mkdir()
            score = project / "utwor.krn"
            score.write_text("moja edycja", encoding="utf-8")

            configuration = AppConfiguration(
                destination=base,
                naming_profile="andrzej-borzym",
                folder_index_role="master",
            )
            window = SimpleNamespace(
                configuration_store=Mock(),
                destination_path=base,
                submission_file_path=score,
                submission_project_key="D - utwor",
                log_view=Mock(),
            )
            window.configuration_store.load.return_value = configuration

            with patch("gui.main_window.refresh_folder_index") as refresh:
                MainWindow._move_submitted_folder(window)

            target = base / "WYSŁANE" / project.name
            self.assertFalse(project.exists())
            self.assertEqual(
                (target / score.name).read_text(encoding="utf-8"),
                "moja edycja",
            )
            refresh.assert_called_once()

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
            self.assertEqual(
                window.unpaid_summary_label.text(), "Niewypłacone: 345 znaków"
            )
            self.assertFalse(window.unpaid_summary_label.isHidden())
            self.assertFalse(hasattr(window, "total_summary_label"))
            configuration.load.return_value.statistics_start_month = "2026-02-01"
            MainWindow._refresh_unpaid_summary(window)
            self.assertTrue(window.unpaid_summary_label.isHidden())
            self.assertEqual(window.unpaid_summary_label.text(), "Niewypłacone: —")

    def test_negative_correction_reduces_unpaid_until_it_appears_in_pdf(self):
        score = {"scheme": "XML", "file_name": "utwor.xml", "note_count": 100}
        correction = {
            "scheme": "XML",
            "file_name": "*** korekta.xml",
            "note_count": -10,
        }

        before_payment = compare_statistics((score, correction), ())
        self.assertEqual(before_payment["unpaid_total"], 90)

        score_paid = compare_statistics((score, correction), (score,))
        self.assertEqual(score_paid["unpaid_total"], -10)
        self.assertEqual(score_paid["pending_corrections"], (correction,))

        correction_paid = compare_statistics((score, correction), (score, correction))
        self.assertEqual(correction_paid["unpaid_total"], 0)
        self.assertEqual(correction_paid["settled_corrections"], (correction,))
        self.assertEqual(correction_paid["outside"], ())

    def test_settlement_parser_accepts_negative_correction(self):
        text = (
            "Wykonawca: Andrzej Borzym\n"
            "łączna liczba znaków: 90\n"
            "1 XML utwor.xml 100\n"
            "1 XML *** korekta.xml -10\n"
        )
        parsed = parse_settlement_text(text)
        self.assertEqual(parsed["total"], 90)
        self.assertEqual(parsed["entries"][1]["note_count"], -10)

    def test_confirmed_submission_moves_only_matching_project_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            project = base / "105 - XML - piece"
            project.mkdir()
            file_path = project / "piece.musicxml"
            file_path.write_text("edited score", encoding="utf-8")

            configuration = AppConfiguration(
                destination=base,
                naming_profile="andrzej-borzym",
                folder_index_role="master",
            )
            window = SimpleNamespace(
                configuration_store=Mock(),
                destination_path=base,
                submission_file_path=file_path,
                submission_project_key="XML - piece",
                log_view=Mock(),
            )
            window.configuration_store.load.return_value = configuration

            with patch("gui.main_window.refresh_folder_index") as refresh:
                MainWindow._move_submitted_folder(window)

            moved = base / "WYSŁANE" / project.name
            self.assertFalse(project.exists())
            self.assertEqual(
                (moved / file_path.name).read_text(encoding="utf-8"),
                "edited score",
            )
            refresh.assert_called_once()

            unrelated = base / "106 - XML - other"
            unrelated.mkdir()
            other_file = unrelated / "piece.musicxml"
            other_file.write_text("keep", encoding="utf-8")
            window.submission_file_path = other_file
            with patch("gui.main_window.refresh_folder_index") as refresh:
                MainWindow._move_submitted_folder(window)
            self.assertTrue(other_file.exists())
            refresh.assert_not_called()
            pending = base / "DO WYSŁANIA" / "107 - XML - pending"
            pending.mkdir(parents=True)
            pending_file = pending / "pending.musicxml"
            pending_file.write_text("pending score", encoding="utf-8")
            window.submission_file_path = pending_file
            window.submission_project_key = "XML - pending"

            with patch("gui.main_window.refresh_folder_index") as refresh:
                MainWindow._move_submitted_folder(window)

            self.assertFalse(pending.exists())
            self.assertEqual(
                (base / "WYSŁANE" / pending.name / pending_file.name).read_text(
                    encoding="utf-8"
                ),
                "pending score",
            )
            refresh.assert_called_once()

    def test_approved_pdf_amount_preserves_shortfall_or_overpayment(self):
        nifc = {
            "scheme": "XML",
            "file_name": "utwor.musicxml",
            "submission_time": "2026-11-21T12:00:00+01:00",
            "note_count": 100,
        }

        for pdf_count, unpaid, overpayment in (
            (90, 10, 0),
            (110, 0, 10),
        ):
            with self.subTest(pdf_count=pdf_count):
                pdf = {
                    "scheme": "XML",
                    "file_name": "utwor.musicxml",
                    "note_count": pdf_count,
                }
                proposed = compare_statistics((nifc,), (pdf,))
                self.assertEqual(len(proposed["differences"]), 1)

                approved = compare_statistics(
                    (nifc,),
                    (pdf,),
                    {proposed["differences"][0]["identity"]},
                )
                self.assertEqual(approved["paid_total"], pdf_count)
                self.assertEqual(approved["unpaid_total"], unpaid)
                self.assertEqual(approved["overpayment_total"], overpayment)

    def test_deferred_decision_survives_old_save_and_can_be_removed(self):
        identity = (
            "XML",
            "utwor.musicxml",
            "2026-11-21T12:00:00+01:00",
            100,
            "KRN-diplomatic",
            "utwor.musicxml",
            90,
        )

        events = record_changes({}, {}, set(), {identity})
        events = record_changes(events, {}, set())
        values, _ = materialize(events)
        self.assertEqual(
            {tuple(value) for value in values["deferred"].values()},
            {identity},
        )

        events = record_changes(events, {}, set(), set())
        values, _ = materialize(events)
        self.assertEqual(values["deferred"], {})

    def test_approved_pdf_difference_can_include_nifc_correction(self):
        stem = "pl-cz--iii-248--001-002_gulitz-alexius--requiem-ex-eis-kyrie"
        score = {
            "scheme": "XML",
            "file_name": f"{stem}.musicxml",
            "submission_time": "2026-11-02T12:00:00+01:00",
            "note_count": 3290,
        }
        correction = {
            "scheme": "XML",
            "file_name": (
                "*** aborzym-korektaznakow-pl-cz--iii-248--001-002-2026-11-03"
            ),
            "submission_time": "2026-11-03T12:00:00+01:00",
            "note_count": -1302,
        }
        pdf = {
            "scheme": "XML",
            "file_name": f"{stem}.musicxml",
            "note_count": 1988,
        }

        proposed = compare_statistics((score, correction), (pdf,))
        approved = compare_statistics(
            (score, correction),
            (pdf,),
            {proposed["differences"][0]["identity"]},
        )
        self.assertEqual(approved["paid_total"], 1988)
        self.assertEqual(approved["unpaid_total"], 0)
        self.assertEqual(approved["shortfall_total"], 0)
        self.assertEqual(approved["pending_corrections"], ())
        self.assertEqual(approved["settled_corrections"], (correction,))

    def test_approved_match_selects_one_of_two_pdf_rows(self):
        filename = "utwor.krn-revision"
        nifc = {
            "scheme": "KRN-diplomatic",
            "file_name": "*** \t" + filename,
            "submission_time": "2026-10-19T11:47:46",
            "note_count": 3779,
        }
        third_pdf = {
            "scheme": "KRN-diplomatic",
            "file_name": filename,
            "note_count": 3779,
        }
        fourth_pdf = {
            "scheme": "KRN-diplomatic",
            "file_name": "***" + filename,
            "note_count": 3779,
        }
        approved_identity = (
            nifc["scheme"],
            nifc["file_name"],
            nifc["submission_time"],
            nifc["note_count"],
            third_pdf["scheme"],
            third_pdf["file_name"],
            third_pdf["note_count"],
        )

        result = compare_statistics(
            (nifc,), (third_pdf, fourth_pdf), {approved_identity}
        )
        self.assertEqual(result["paid"], (nifc,))
        self.assertEqual(result["unresolved"], ())
        self.assertEqual(result["outside"], (fourth_pdf,))
        self.assertEqual(result["paid_total"], 3779)

    def test_accepted_revision_is_separate_pdf_payment(self):
        nifc = {
            "scheme": "KRN-diplomatic",
            "file_name": "*** \tutwor.krn-revision",
            "submission_time": "2026-10-19T11:47:46",
            "note_count": 3779,
        }
        first_pdf = {
            "scheme": "KRN-diplomatic",
            "file_name": "utwor.krn-revision",
            "note_count": 3779,
            "_pdf_id": ("pdf-03", 0),
        }
        second_pdf = {
            "scheme": "KRN-diplomatic",
            "file_name": "***utwor.krn-revision",
            "note_count": 3779,
            "_pdf_id": ("pdf-04", 0),
        }
        normal_pdf = {
            "scheme": "KRN-diplomatic",
            "file_name": "utwor.krn",
            "note_count": 3652,
            "_pdf_id": ("pdf-03", 1),
        }
        approval = (
            nifc["scheme"],
            nifc["file_name"],
            nifc["submission_time"],
            nifc["note_count"],
            first_pdf["scheme"],
            first_pdf["file_name"],
            first_pdf["note_count"],
        )

        result = compare_statistics(
            (nifc,),
            (first_pdf, second_pdf, normal_pdf),
            {approval},
            {("pdf-04", 0)},
        )
        self.assertEqual(result["paid"], (nifc,))
        self.assertEqual(result["accepted_revisions"], (second_pdf,))
        self.assertEqual(result["outside"], (normal_pdf,))
        self.assertEqual(result["paid_total"], 7558)
        self.assertEqual(result["unresolved_total"], 0)


if __name__ == "__main__":
    unittest.main()
