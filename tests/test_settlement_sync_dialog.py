import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from core.configuration import AppConfiguration, ConfigurationStore
from gui.statistics_dialog import StatisticsDialog
from tests.test_settlement_sync import document


class SettlementSyncDialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.folder = self.root / "shared"
        self.folder.mkdir()

    def dialog(self, name):
        settings = QSettings(str(self.root / f"{name}.ini"), QSettings.Format.IniFormat)
        config = ConfigurationStore(settings)
        config.create_account(name, AppConfiguration(nifc_username="test"))
        dialog = StatisticsDialog(config, credential_store=Mock())
        self.addCleanup(dialog.close)
        return dialog

    def choose(self, dialog):
        with patch(
            "gui.statistics_dialog.QFileDialog.getExistingDirectory",
            return_value=str(self.folder),
        ):
            dialog.sync_folder_button.click()

    def test_choose_folder_publish_and_read_on_other_device(self):
        first = self.dialog("linux")
        first.settlements = {"a": document()}
        self.choose(first)
        second = self.dialog("mac")
        self.choose(second)
        self.assertEqual(second.settlements, {"a": document()})
        self.assertEqual(second.pdf_table.rowCount(), 1)
        self.assertIn("Połączono", second.sync_label.text())
        second.local_button.click()
        self.assertEqual(second.settlement_store.sync_folder, "")
        self.assertEqual(second.settlements, {"a": document()})

    def test_unavailable_folder_keeps_data_and_shows_pending(self):
        dialog = self.dialog("linux")
        self.choose(dialog)
        self.folder.rename(self.root / "unavailable")
        dialog.settlements = {"a": document()}
        dialog.sync_button.click()
        self.assertEqual(dialog.settlements, {"a": document()})
        self.assertIn("oczekuje", dialog.sync_label.text())
        with patch("gui.statistics_dialog.QMessageBox.warning") as warning:
            dialog.done(0)
            warning.assert_called_once()
        dialog.settlement_store.set_sync_folder("")
        dialog.settlement_store.sync_error = ""


if __name__ == "__main__":
    unittest.main()
