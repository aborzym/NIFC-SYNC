import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from requests import RequestException

from core.configuration import (
    AppConfiguration,
    ConfigurationStore,
    OrganizationPath,
)
from core.credentials import (
    CredentialStore,
    NifcCredentials,
)
from core.setup import (
    SetupError,
    SetupRequest,
    complete_setup,
    remove_obsolete_credentials,
    verify_nifc_login,
)


class CompleteSetupTest(unittest.TestCase):
    def test_removes_obsolete_credentials(
        self,
    ):
        self.configuration_store.has_account_for_username.return_value = False

        removed = remove_obsolete_credentials(
            "stary-login",
            "nowy-login",
            self.configuration_store,
            self.credential_store,
        )

        self.assertTrue(removed)
        self.credential_store.delete.assert_called_once_with("stary-login")

    def test_preserves_credentials_used_by_another_account(
        self,
    ):
        self.configuration_store.has_account_for_username.return_value = True

        removed = remove_obsolete_credentials(
            "wspolny-login",
            "nowy-login",
            self.configuration_store,
            self.credential_store,
        )

        self.assertFalse(removed)
        self.credential_store.delete.assert_not_called()

    def test_rejects_duplicate_account_before_saving_password(
        self,
    ):
        self.configuration_store.validate_account_name.side_effect = ValueError(
            "Konto o tej nazwie już istnieje."
        )
        request = SetupRequest(
            destination=self.destination,
            storage_kind="local",
            username="andrzej",
            password="tajne-haslo",
            account_name="Andrzej",
        )

        with self.assertRaisesRegex(
            SetupError,
            "już istnieje",
        ):
            complete_setup(
                request,
                self.configuration_store,
                self.credential_store,
                create_new_account=True,
            )

        self.credential_store.save.assert_not_called()
        self.configuration_store.create_account.assert_not_called()

    def test_rejects_duplicate_nifc_username_before_saving_password(
        self,
    ):
        self.configuration_store.validate_nifc_username.side_effect = ValueError(
            "Konto korzystające z tego loginu NIFC już istnieje."
        )
        request = SetupRequest(
            destination=self.destination,
            storage_kind="local",
            username="andrzej",
            password="nowe-haslo",
            account_name="Drugie konto",
        )

        with self.assertRaisesRegex(
            SetupError,
            "Konto korzystające z tego loginu",
        ):
            complete_setup(
                request,
                self.configuration_store,
                self.credential_store,
                create_new_account=True,
            )

        self.credential_store.save.assert_not_called()
        self.configuration_store.create_account.assert_not_called()

        self.credential_store.save.assert_not_called()
        self.configuration_store.create_account.assert_not_called()

    def test_rejects_empty_account_name_before_saving_password(
        self,
    ):
        self.configuration_store.validate_account_name.side_effect = ValueError(
            "Nazwa konta nie może być pusta."
        )
        request = SetupRequest(
            destination=self.destination,
            storage_kind="local",
            username="andrzej",
            password="tajne-haslo",
            account_name="   ",
        )

        with self.assertRaisesRegex(
            SetupError,
            "Nazwa konta nie może być pusta",
        ):
            complete_setup(
                request,
                self.configuration_store,
                self.credential_store,
            )

        self.credential_store.save.assert_not_called()
        self.configuration_store.save.assert_not_called()

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.destination = Path(self.temporary_directory.name)
        self.configuration_store = Mock(spec=ConfigurationStore)
        self.configuration_store.load.return_value = AppConfiguration(workflow="XML")
        self.credential_store = Mock(spec=CredentialStore)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_saves_credentials_and_configuration(self):
        request = SetupRequest(
            destination=self.destination,
            storage_kind="local",
            username="  andrzej  ",
            password="tajne-haslo",
        )

        result = complete_setup(
            request,
            self.configuration_store,
            self.credential_store,
        )

        self.credential_store.save.assert_called_once_with(
            NifcCredentials(
                username="andrzej",
                password="tajne-haslo",
            )
        )
        self.assertEqual(
            result.destination,
            self.destination.resolve(),
        )
        self.assertEqual(result.storage_kind, "local")
        self.assertEqual(result.network_url, "")
        self.assertEqual(result.workflow, "XML")
        self.assertEqual(result.nifc_username, "andrzej")
        self.assertTrue(result.setup_completed)
        self.configuration_store.save.assert_called_once_with(result)

    def test_renames_current_account(self):
        self.configuration_store.active_account_id.return_value = "account-1"
        request = SetupRequest(
            destination=self.destination,
            storage_kind="local",
            username="andrzej",
            password="tajne-haslo",
            account_name="  Andrzej  ",
        )

        complete_setup(
            request,
            self.configuration_store,
            self.credential_store,
        )

        self.configuration_store.rename_account.assert_called_once_with(
            "account-1",
            "Andrzej",
        )

    def test_creates_new_account_with_separate_configuration(self):
        request = SetupRequest(
            destination=self.destination,
            storage_kind="local",
            username="barbara",
            password="tajne-haslo",
            account_name="  Barbara  ",
        )

        result = complete_setup(
            request,
            self.configuration_store,
            self.credential_store,
            create_new_account=True,
        )

        self.configuration_store.load.assert_not_called()
        self.configuration_store.save.assert_not_called()
        self.configuration_store.create_account.assert_called_once_with(
            "Barbara",
            result,
        )
        self.assertEqual(
            result.destination,
            self.destination.resolve(),
        )
        self.assertEqual(
            result.nifc_username,
            "barbara",
        )
        self.assertTrue(result.setup_completed)

    def test_requires_parent_directory_for_marta_profile(
        self,
    ):
        request = SetupRequest(
            destination=None,
            storage_kind="local",
            username="marta",
            password="tajne-haslo",
            account_name="Marta",
            organization_profile_id="marta-lawrence",
            organization_paths=(
                OrganizationPath(
                    key="libraries/pl-sa/transcriptions",
                    path=Path("Sandomierz.krn"),
                ),
            ),
        )

        with self.assertRaisesRegex(
            SetupError,
            "główny katalog",
        ):
            complete_setup(
                request,
                self.configuration_store,
                self.credential_store,
            )

        self.credential_store.save.assert_not_called()

    def test_saves_selected_organization_profile(self):
        request = SetupRequest(
            destination=self.destination,
            storage_kind="local",
            username="marta",
            password="tajne-haslo",
            account_name="Marta",
            organization_profile_id="marta-lawrence",
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
        )

        result = complete_setup(
            request,
            self.configuration_store,
            self.credential_store,
        )

        self.assertEqual(
            result.naming_profile,
            "marta-lawrence",
        )

        self.assertEqual(
            result.organization_paths,
            request.organization_paths,
        )

    def test_rejects_unknown_organization_profile(self):
        request = SetupRequest(
            destination=self.destination,
            storage_kind="local",
            username="andrzej",
            password="tajne-haslo",
            organization_profile_id="profil-z-kosmosu",
        )

        with self.assertRaisesRegex(
            SetupError,
            "profil organizacji",
        ):
            complete_setup(
                request,
                self.configuration_store,
                self.credential_store,
            )

        self.credential_store.save.assert_not_called()

    @patch("core.setup.validate_storage")
    def test_saves_network_url_for_mounted_storage(
        self,
        validate_storage_mock,
    ):
        validate_storage_mock.return_value = Mock(
            is_valid=True,
        )
        request = SetupRequest(
            destination=self.destination,
            storage_kind="mounted",
            username="andrzej",
            password="tajne-haslo",
            network_url="  smb://mac.local/transkrypcje  ",
        )

        result = complete_setup(
            request,
            self.configuration_store,
            self.credential_store,
        )

        self.assertEqual(
            result.network_url,
            "smb://mac.local/transkrypcje",
        )

    def test_rejects_empty_username(self):
        request = SetupRequest(
            destination=self.destination,
            storage_kind="local",
            username="   ",
            password="tajne-haslo",
        )

        with self.assertRaisesRegex(SetupError, "Podaj login"):
            complete_setup(
                request,
                self.configuration_store,
                self.credential_store,
            )

        self.credential_store.save.assert_not_called()

    def test_rejects_empty_password(self):
        request = SetupRequest(
            destination=self.destination,
            storage_kind="local",
            username="andrzej",
            password="",
        )

        with self.assertRaisesRegex(SetupError, "Podaj hasło"):
            complete_setup(
                request,
                self.configuration_store,
                self.credential_store,
            )

        self.credential_store.save.assert_not_called()

    def test_rejects_invalid_destination(self):
        request = SetupRequest(
            destination=self.destination / "nie-istnieje",
            storage_kind="local",
            username="andrzej",
            password="tajne-haslo",
        )

        with self.assertRaisesRegex(
            SetupError,
            "Katalog nie istnieje",
        ):
            complete_setup(
                request,
                self.configuration_store,
                self.credential_store,
            )

        self.credential_store.save.assert_not_called()

    def test_rejects_missing_destination(self):
        request = SetupRequest(
            destination=None,
            storage_kind="local",
            username="andrzej",
            password="tajne-haslo",
        )

        with self.assertRaisesRegex(
            SetupError,
            "Wybierz główny katalog",
        ):
            complete_setup(
                request,
                self.configuration_store,
                self.credential_store,
            )

        self.credential_store.save.assert_not_called()

    def test_does_not_expose_password_in_request_repr(self):
        request = SetupRequest(
            destination=self.destination,
            storage_kind="local",
            username="andrzej",
            password="tajne-haslo",
        )

        self.assertNotIn("tajne-haslo", repr(request))

    def test_keeps_credentials_when_username_is_unchanged(
        self,
    ):
        removed = remove_obsolete_credentials(
            "andrzej",
            "andrzej",
            self.configuration_store,
            self.credential_store,
        )

        self.assertFalse(removed)
        (self.configuration_store.has_account_for_username.assert_not_called())
        self.credential_store.delete.assert_not_called()


class VerifyNifcLoginTest(unittest.TestCase):
    def test_accepts_valid_credentials(self):
        client = Mock()
        client.login.return_value = Mock(
            status_code=200,
            ok=True,
        )

        verify_nifc_login(
            "  andrzej  ",
            "tajne-haslo",
            client,
        )

        client.login.assert_called_once_with(
            "andrzej",
            "tajne-haslo",
        )

    def test_rejects_invalid_credentials(self):
        client = Mock()
        client.login.return_value = Mock(
            status_code=401,
            ok=False,
        )

        with self.assertRaisesRegex(
            SetupError,
            "Nieprawidłowy login lub hasło",
        ):
            verify_nifc_login(
                "andrzej",
                "złe-hasło",
                client,
            )

    def test_reports_server_error(self):
        client = Mock()
        client.login.return_value = Mock(
            status_code=500,
            ok=False,
        )

        with self.assertRaisesRegex(
            SetupError,
            "HTTP 500",
        ):
            verify_nifc_login(
                "andrzej",
                "tajne-haslo",
                client,
            )

    def test_reports_connection_error(self):
        client = Mock()
        client.login.side_effect = RequestException()

        with self.assertRaisesRegex(
            SetupError,
            "Nie udało się połączyć",
        ):
            verify_nifc_login(
                "andrzej",
                "tajne-haslo",
                client,
            )


if __name__ == "__main__":
    unittest.main()
