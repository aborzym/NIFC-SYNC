import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

from gui.download_dialog import DownloadSelectionDialog
from gui.main_window import MainWindow
from gui.workers import SyncWorker


class DownloadSelectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_selection_and_scan_option(self):
        files = ({"name": "first.krn"}, {"name": "second.krn"})
        dialog = DownloadSelectionDialog({"name": "KRN-modern", "files": files})
        self.assertFalse(dialog.download_button.isEnabled())
        dialog.table.item(1, 0).setCheckState(Qt.CheckState.Checked)
        self.assertEqual(dialog.selected_files(), (files[1],))
        self.assertTrue(dialog.download_button.isEnabled())
        dialog._select_all()
        self.assertEqual(dialog.selected_files(), files)
        dialog._clear_selection()
        self.assertEqual(dialog.selected_files(), ())
        self.assertTrue(dialog.download_scans())
        dialog.download_scans_checkbox.setChecked(False)
        self.assertFalse(dialog.download_scans())

    def test_accept_passes_only_selected_files_without_mutating_catalog(self):
        files = ({"name": "first.krn"}, {"name": "second.krn"})
        workflow = {"name": "KRN-modern", "key": 2, "files": files}
        window = SimpleNamespace(
            _selected_workflow=lambda: workflow, _start_synchronization=Mock()
        )
        with patch("gui.main_window.DownloadSelectionDialog") as factory:
            dialog = factory.return_value
            dialog.exec.return_value = QDialog.DialogCode.Accepted
            dialog.selected_files.return_value = (files[1],)
            dialog.download_scans.return_value = False
            MainWindow._open_download_dialog(window)
        window._start_synchronization.assert_called_once_with(
            selected_workflow={**workflow, "files": (files[1],)}, download_scans=False
        )
        self.assertEqual(workflow["files"], files)

    def test_cancel_does_not_start(self):
        window = SimpleNamespace(
            _selected_workflow=lambda: {"name": "XML"}, _start_synchronization=Mock()
        )
        with patch("gui.main_window.DownloadSelectionDialog") as factory:
            factory.return_value.exec.return_value = QDialog.DialogCode.Rejected
            MainWindow._open_download_dialog(window)
        window._start_synchronization.assert_not_called()

    def test_disabled_scans_skip_planner(self):
        configuration = SimpleNamespace(destination=Path("/tmp"), storage_kind="local")
        worker = SyncWorker(
            {"name": "XML", "files": ()}, [], configuration, download_scans=False
        )
        completed = Mock()
        failed = Mock()
        worker.completed.connect(completed)
        worker.failed.connect(failed)
        inventory = SimpleNamespace(folder_names=(), next_number=1)
        result = SimpleNamespace(
            target_folders={}, created_count=0, downloaded_count=0, skipped_count=0
        )
        with (
            patch.object(worker, "_check_destination_access"),
            patch("gui.workers.build_scan_indexes", return_value=({}, {})),
            patch("gui.workers.build_storage_inventory", return_value=inventory),
            patch("gui.workers.sync_transcriptions", return_value=result),
            patch("gui.workers.cleanup_scan_staging_folders"),
            patch("gui.workers.plan_scans") as planner,
        ):
            worker.run()
        failed.assert_not_called()
        planner.assert_not_called()
        self.assertEqual(completed.call_args.args[1], ())
        self.assertEqual(completed.call_args.args[0]["scan_issues"], ())
