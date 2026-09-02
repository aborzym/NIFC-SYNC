import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import QSettings

from core.configuration import (
    AppConfiguration,
    ConfigurationStore,
    OrganizationPath,
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
            "andrzej-borzym",
        )
        self.assertEqual(configuration.nifc_username, "")
        self.assertFalse(configuration.setup_completed)

    def test_saves_and_loads_configuration(self):
        expected = AppConfiguration(
            destination=Path("/tmp/nifc-sync"),
            storage_kind="mounted",
            network_url="smb://mac.local/transkrypcje",
            workflow="XML",
            naming_profile="andrzej-borzym",
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

    def test_saves_organization_paths(self):
        expected = AppConfiguration(
            naming_profile="marta-lawrence",
            organization_paths=(
                OrganizationPath(
                    key="libraries/pl-sa/transcriptions",
                    path=Path("/tmp/Sandomierz.krn"),
                ),
                OrganizationPath(
                    key="libraries/pl-sa/scans",
                    path=Path("/tmp/Sandomierz.źródła"),
                ),
            ),
            nifc_username="marta",
            setup_completed=True,
        )

        self.store.save(expected)

        self.assertEqual(
            self.store.load(),
            expected,
        )
        self.assertEqual(
            self.settings.value(
                "accounts/account-1/"
                "organization/paths/values/"
                "libraries/pl-sa/transcriptions"
            ),
            "/tmp/Sandomierz.krn",
        )
        self.assertEqual(
            self.settings.value(
                "accounts/account-1/organization/paths/values/libraries/pl-sa/scans"
            ),
            "/tmp/Sandomierz.źródła",
        )

        loaded = self.store.load()

        self.assertEqual(
            loaded.organization_path("libraries/pl-sa/transcriptions"),
            Path("/tmp/Sandomierz.krn"),
        )
        self.assertEqual(
            loaded.organization_path("libraries/pl-sa/scans"),
            Path("/tmp/Sandomierz.źródła"),
        )
        self.assertIsNone(loaded.organization_path("libraries/pl-wtm/scans"))

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

    def test_updates_existing_account_configuration(self):
        initial = AppConfiguration(
            destination=Path("/tmp/pierwszy"),
            nifc_username="andrzej",
            setup_completed=True,
        )
        updated = AppConfiguration(
            destination=Path("/tmp/drugi"),
            workflow="XML",
            nifc_username="andrzej",
            setup_completed=True,
        )

        self.store.save(initial)
        self.store.save(updated)

        self.assertEqual(self.store.load(), updated)
        self.assertEqual(len(self.store.list_accounts()), 1)

    def test_keeps_separate_configuration_for_each_account(self):
        account_ids = iter(
            (
                "account-1",
                "account-2",
            )
        )
        store = ConfigurationStore(
            self.settings,
            id_factory=lambda: next(account_ids),
        )
        first_configuration = AppConfiguration(
            destination=Path("/tmp/andrzej"),
            workflow="KRN-diplomatic",
            nifc_username="andrzej",
            setup_completed=True,
        )
        second_configuration = AppConfiguration(
            destination=Path("/tmp/barbara"),
            workflow="XML",
            nifc_username="barbara",
            setup_completed=True,
        )

        store.save(first_configuration)
        second_account = store.create_account(
            "Barbara",
            second_configuration,
        )

        self.assertEqual(
            second_account.account_id,
            "account-2",
        )
        self.assertEqual(
            store.load(),
            second_configuration,
        )

        store.set_active_account("account-1")

        self.assertEqual(
            store.load(),
            first_configuration,
        )

    def test_migrates_legacy_organization_profile_id(self):
        self.settings.setValue(
            "naming/profile",
            "legacy-v3",
        )
        self.settings.setValue(
            "setup/completed",
            True,
        )

        configuration = self.store.load()

        self.assertEqual(
            configuration.naming_profile,
            "andrzej-borzym",
        )
        self.assertEqual(
            self.settings.value("accounts/account-1/naming/profile"),
            "andrzej-borzym",
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
        self.assertEqual(
            self.settings.value("accounts/account-1/sync/destination"),
            "/home/user/mac_transkrypcje",
        )
        self.assertEqual(
            self.settings.value("accounts/account-1/sync/workflow"),
            "KRN-modern",
        )

        self.settings.setValue(
            "sync/workflow",
            "XML",
        )

        migrated_configuration = self.store.load()

        self.assertEqual(
            migrated_configuration.workflow,
            "KRN-modern",
        )


if __name__ == "__main__":
    unittest.main()
