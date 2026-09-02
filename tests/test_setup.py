import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from requests import RequestException

from core.configuration import (
    AppConfiguration,
    ConfigurationStore,
)
from core.credentials import (
    CredentialStore,
    NifcCredentials,
)
from core.setup import (
    SetupError,
    SetupRequest,
    complete_setup,
    verify_nifc_login,
)


class CompleteSetupTest(unittest.TestCase):
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
            "Wybierz katalog docelowy",
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
