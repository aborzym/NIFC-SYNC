import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import QSettings

from core.configuration import (
    AppConfiguration,
    ConfigurationStore,
)


class ConfigurationStoreTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        settings_path = Path(self.temporary_directory.name) / "settings.ini"
        self.settings = QSettings(
            str(settings_path),
            QSettings.IniFormat,
        )
        self.store = ConfigurationStore(
            self.settings,
            id_factory=lambda: "account-1",
        )

    def tearDown(self):
        self.settings.clear()
        self.settings.sync()
        del self.settings
        self.temporary_directory.cleanup()

    def test_loads_defaults_for_empty_settings(self):
        configuration = self.store.load()

        self.assertIsNone(configuration.destination)
        self.assertEqual(configuration.storage_kind, "local")
        self.assertEqual(configuration.network_url, "")
        self.assertEqual(
            configuration.workflow,
            "KRN-diplomatic",
        )
        self.assertEqual(
            configuration.naming_profile,
            "legacy-v3",
        )
        self.assertEqual(configuration.nifc_username, "")
        self.assertFalse(configuration.setup_completed)

    def test_saves_and_loads_configuration(self):
        expected = AppConfiguration(
            destination=Path("/tmp/nifc-sync"),
            storage_kind="mounted",
            network_url="smb://mac.local/transkrypcje",
            workflow="XML",
            naming_profile="legacy-v3",
            nifc_username="andrzej",
            setup_completed=True,
        )

        self.store.save(expected)

        self.assertEqual(self.store.load(), expected)

    def test_creates_first_account_when_saving_configuration(self):
        configuration = AppConfiguration(
            nifc_username="andrzej",
            setup_completed=True,
        )

        self.store.save(configuration)

        accounts = self.store.list_accounts()

        self.assertEqual(len(accounts), 1)
        self.assertEqual(accounts[0].account_id, "account-1")
        self.assertEqual(accounts[0].name, "andrzej")
        self.assertEqual(
            self.store.active_account_id(),
            "account-1",
        )

    def test_renames_account(self):
        self.store.save(
            AppConfiguration(
                nifc_username="andrzej",
                setup_completed=True,
            )
        )

        self.store.rename_account(
            "account-1",
            "  Andrzej  ",
        )

        accounts = self.store.list_accounts()

        self.assertEqual(accounts[0].name, "Andrzej")

    def test_rejects_empty_account_name(self):
        self.store.save(
            AppConfiguration(
                nifc_username="andrzej",
                setup_completed=True,
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "nie może być pusta",
        ):
            self.store.rename_account(
                "account-1",
                "   ",
            )

    def test_loads_version_3_settings(self):
        self.settings.setValue(
            "sync/destination",
            "/home/user/mac_transkrypcje",
        )
        self.settings.setValue(
            "sync/workflow",
            "KRN-modern",
        )

        configuration = self.store.load()

        self.assertEqual(
            configuration.destination,
            Path("/home/user/mac_transkrypcje"),
        )
        self.assertEqual(
            configuration.workflow,
            "KRN-modern",
        )
        self.assertEqual(configuration.storage_kind, "local")
        self.assertEqual(configuration.network_url, "")
        self.assertEqual(configuration.nifc_username, "")
        self.assertFalse(configuration.setup_completed)
        accounts = self.store.list_accounts()

        self.assertEqual(len(accounts), 1)
        self.assertEqual(accounts[0].account_id, "account-1")
        self.assertEqual(
            accounts[0].name,
            "Dotychczasowe konto",
        )
        self.assertEqual(
            self.store.active_account_id(),
            "account-1",
        )


if __name__ == "__main__":
    unittest.main()
