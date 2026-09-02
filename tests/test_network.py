import subprocess
import unittest
from unittest.mock import Mock, patch

from core.network import (
    NetworkShareError,
    SmbResource,
    _run_gio,
    authenticate_smb,
    discover_smb_servers,
    list_smb_shares,
)


class SmbDiscoveryTest(unittest.TestCase):
    @patch("core.network._run_gio")
    def test_discovers_only_smb_servers(self, run_gio):
        run_gio.return_value = (
            "sftp-entry\t0\t(shortcut) "
            "standard::display-name=Mac (SSH) "
            "standard::target-uri=sftp://mac.local:22/\n"
            "smb-entry\t0\t(shortcut) "
            "standard::display-name=Mac (Pliki) "
            "standard::target-uri=smb://mac.local:445/\n"
        )

        result = discover_smb_servers()

        self.assertEqual(
            result,
            (
                SmbResource(
                    display_name="Mac (Pliki)",
                    uri="smb://mac.local:445/",
                ),
            ),
        )

    @patch("core.network._run_gio")
    def test_lists_and_encodes_smb_shares(self, run_gio):
        run_gio.return_value = (
            "TRANSKRYPCJE 2026\t0\t(mountable)\t"
            "standard::display-name=TRANSKRYPCJE 2026\n"
        )

        result = list_smb_shares("smb://mac.local:445/")

        self.assertEqual(
            result,
            (
                SmbResource(
                    display_name="TRANSKRYPCJE 2026",
                    uri=("smb://mac.local:445/TRANSKRYPCJE%202026"),
                ),
            ),
        )


class SmbAuthenticationTest(unittest.TestCase):
    @patch("core.network._run_gio")
    def test_passes_password_through_standard_input(
        self,
        run_gio,
    ):
        authenticate_smb(
            "smb://mac.local/",
            "Andrzej Borzym",
            "tajne-haslo",
        )

        arguments = run_gio.call_args.args[0]
        input_text = run_gio.call_args.kwargs["input_text"]

        self.assertNotIn("tajne-haslo", arguments)
        self.assertEqual(
            input_text,
            ("Andrzej Borzym\nWORKGROUP\ntajne-haslo\n"),
        )

    @patch("core.network._run_gio")
    def test_rejects_newline_in_credentials(self, run_gio):
        with self.assertRaisesRegex(
            NetworkShareError,
            "niedozwolony znak",
        ):
            authenticate_smb(
                "smb://mac.local/",
                "Andrzej\nBorzym",
                "tajne-haslo",
            )

        run_gio.assert_not_called()


class RunGioTest(unittest.TestCase):
    @patch("core.network.subprocess.run")
    def test_returns_standard_output(self, run):
        run.return_value = Mock(
            returncode=0,
            stdout="wynik",
        )

        result = _run_gio(
            ["list", "network:///"],
            error_message="Błąd.",
        )

        self.assertEqual(result, "wynik")

    @patch(
        "core.network.subprocess.run",
        side_effect=FileNotFoundError,
    )
    def test_reports_missing_gio(self, run):
        with self.assertRaisesRegex(
            NetworkShareError,
            "nie udostępnia narzędzia GIO",
        ):
            _run_gio(
                ["list", "network:///"],
                error_message="Błąd.",
            )

    @patch(
        "core.network.subprocess.run",
        side_effect=subprocess.TimeoutExpired(
            "gio",
            20,
        ),
    )
    def test_reports_timeout(self, run):
        with self.assertRaisesRegex(
            NetworkShareError,
            "przekroczyła limit czasu",
        ):
            _run_gio(
                ["list", "network:///"],
                error_message="Błąd.",
            )

    @patch("core.network.subprocess.run")
    def test_does_not_expose_process_error(self, run):
        run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="tajne-haslo",
        )

        with self.assertRaisesRegex(
            NetworkShareError,
            "^Bezpieczny komunikat[.]$",
        ):
            _run_gio(
                ["mount", "smb://mac.local/"],
                error_message="Bezpieczny komunikat.",
            )


if __name__ == "__main__":
    unittest.main()
