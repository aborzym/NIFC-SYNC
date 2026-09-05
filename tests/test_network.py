import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core.network import (
    NetworkShareError,
    SmbResource,
    _run_gio,
    authenticate_smb,
    connect_and_list_smb_shares,
    discover_smb_servers,
    find_mounted_smb_path,
    list_smb_shares,
)


class SmbDiscoveryTest(unittest.TestCase):
    @patch("core.network.list_smb_shares")
    @patch("core.network.authenticate_smb")
    def test_uses_existing_authenticated_connection(
        self,
        authenticate,
        list_shares,
    ):
        expected = (
            SmbResource(
                display_name="TRANSKRYPCJE 2026",
                uri="smb://mac/transkrypcje",
            ),
        )
        list_shares.return_value = expected

        result = connect_and_list_smb_shares(
            "smb://mac/",
            "Andrzej Borzym",
            "tajne-haslo",
        )

        authenticate.assert_not_called()
        self.assertEqual(result, expected)

    @patch("core.network.list_smb_shares")
    @patch("core.network.authenticate_smb")
    def test_authenticates_when_connection_is_unavailable(
        self,
        authenticate,
        list_shares,
    ):
        expected = (
            SmbResource(
                display_name="TRANSKRYPCJE 2026",
                uri="smb://mac/transkrypcje",
            ),
        )
        list_shares.side_effect = (
            NetworkShareError("Brak połączenia."),
            expected,
        )

        result = connect_and_list_smb_shares(
            "smb://mac/",
            "Andrzej Borzym",
            "tajne-haslo",
        )

        authenticate.assert_called_once_with(
            "smb://mac/",
            "Andrzej Borzym",
            "tajne-haslo",
            "WORKGROUP",
        )
        self.assertEqual(result, expected)
        self.assertEqual(list_shares.call_count, 2)

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


class SmbMountPathTest(unittest.TestCase):
    def test_finds_mounted_share_in_gvfs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            gvfs_root = Path(temporary_directory)
            expected = gvfs_root / (
                "smb-share:server=mac-studio-andrzej.local,share=transkrypcje%202026"
            )
            expected.mkdir()

            result = find_mounted_smb_path(
                ("smb://Mac-Studio-Andrzej.local:445/TRANSKRYPCJE%202026"),
                gvfs_root=gvfs_root,
            )

            self.assertEqual(result, expected)

    def test_returns_none_for_unmounted_share(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = find_mounted_smb_path(
                "smb://mac.local/NIE-ISTNIEJE",
                gvfs_root=Path(temporary_directory),
            )

            self.assertIsNone(result)


class SmbAuthenticationTest(unittest.TestCase):
    @patch("core.network._run_gio_mount")
    def test_uses_interactive_terminal_mount(
        self,
        run_gio_mount,
    ):
        authenticate_smb(
            "smb://mac.local/",
            "Andrzej Borzym",
            "tajne-haslo",
        )

        run_gio_mount.assert_called_once_with(
            "smb://mac.local/",
            "Andrzej Borzym",
            "tajne-haslo",
            "WORKGROUP",
        )

    @patch("core.network._run_gio_mount")
    def test_rejects_newline_in_credentials(
        self,
        run_gio_mount,
    ):
        with self.assertRaisesRegex(
            NetworkShareError,
            "niedozwolony znak",
        ):
            authenticate_smb(
                "smb://mac.local/",
                "Andrzej\nBorzym",
                "tajne-haslo",
            )

        run_gio_mount.assert_not_called()


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
