import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

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
        self.assertEqual(result.workflow, "XML")
        self.assertEqual(result.nifc_username, "andrzej")
        self.assertTrue(result.setup_completed)
        self.configuration_store.save.assert_called_once_with(result)

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

    def test_does_not_expose_password_in_request_repr(self):
        request = SetupRequest(
            destination=self.destination,
            storage_kind="local",
            username="andrzej",
            password="tajne-haslo",
        )

        self.assertNotIn("tajne-haslo", repr(request))


if __name__ == "__main__":
    unittest.main()
