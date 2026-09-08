import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from core.credentials import CredentialStoreError
from gui.first_run_dialog import FirstRunDialog


class FirstRunDialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    @patch("gui.first_run_dialog.QMessageBox.warning")
    @patch(
        "gui.first_run_dialog.remove_obsolete_credentials",
        side_effect=CredentialStoreError("Nie udało się usunąć danych logowania."),
    )
    @patch("gui.first_run_dialog.complete_setup")
    @patch("gui.first_run_dialog.verify_nifc_login")
    def test_warns_when_obsolete_credentials_cannot_be_removed(
        self,
        _verify_login,
        complete_setup,
        remove_credentials,
        warning,
    ):
        configuration_store = Mock()
        configuration_store.load.return_value = Mock(
            nifc_username="stary-login",
        )
        credential_store = Mock()

        dialog = FirstRunDialog(
            configuration_store=configuration_store,
            credential_store=credential_store,
            initial_setup=False,
            new_account=True,
        )
        dialog.new_account = False
        dialog.destination_path = Path("/tmp")
        dialog.account_name_edit.setText("Konto testowe")
        dialog.username_edit.setText("nowy-login")
        dialog.password_edit.setText("nowe-hasło")

        complete_setup.return_value = Mock(
            nifc_username="nowy-login",
        )

        with patch.object(dialog, "accept") as accept:
            dialog._complete_setup()

        remove_credentials.assert_called_once_with(
            "stary-login",
            "nowy-login",
            configuration_store,
            credential_store,
        )
        warning.assert_called_once()

        warning_arguments = warning.call_args.args
        self.assertEqual(
            warning_arguments[1],
            "Pozostały stare dane logowania",
        )
        self.assertIn(
            "nie udało się usunąć poprzednich danych logowania",
            warning_arguments[2],
        )
        accept.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
