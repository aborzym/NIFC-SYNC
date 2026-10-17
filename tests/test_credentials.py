import unittest
from unittest.mock import Mock

from keyring.errors import KeyringError, PasswordDeleteError

from core.credentials import (
    SERVICE_NAME,
    CredentialStore,
    CredentialStoreError,
    NifcCredentials,
)


class CredentialStoreTest(unittest.TestCase):
    def setUp(self):
        self.backend = Mock()
        self.store = CredentialStore(self.backend)
        self.credentials = NifcCredentials(
            username="andrzej",
            password="tajne-haslo",
        )

    def test_saves_password_in_keyring(self):
        self.store.save(self.credentials)

        self.backend.set_password.assert_called_once_with(
            SERVICE_NAME,
            "andrzej",
            "tajne-haslo",
        )

    def test_loads_credentials_from_keyring(self):
        self.backend.get_password.return_value = "tajne-haslo"

        result = self.store.load("andrzej")

        self.assertEqual(result, self.credentials)

    def test_returns_none_when_password_does_not_exist(self):
        self.backend.get_password.return_value = None

        result = self.store.load("andrzej")

        self.assertIsNone(result)

    def test_does_not_query_keyring_without_username(self):
        result = self.store.load("")

        self.assertIsNone(result)
        self.backend.get_password.assert_not_called()

    def test_deletes_password_from_keyring(self):
        self.store.delete("andrzej")

        self.backend.delete_password.assert_called_once_with(
            SERVICE_NAME,
            "andrzej",
        )

    def test_ignores_deleting_missing_password(self):
        self.backend.delete_password.side_effect = PasswordDeleteError()

        self.store.delete("andrzej")

    def test_converts_keyring_error_to_safe_error(self):
        self.backend.get_password.side_effect = KeyringError("szczegóły backendu")

        with self.assertRaisesRegex(
            CredentialStoreError,
            "Nie udało się odczytać danych logowania",
        ):
            self.store.load("andrzej")

    def test_repeated_operations_read_keyring_once_per_account(self):
        self.backend.get_password.return_value = "tajne-haslo"
        for _ in range(4):
            self.assertEqual(self.store.load("andrzej"), self.credentials)
        self.backend.get_password.assert_called_once()
        self.store.load("other")
        self.assertEqual(self.backend.get_password.call_count, 2)

    def test_successful_save_updates_session(self):
        self.store.save(self.credentials)
        self.assertEqual(self.store.load("andrzej"), self.credentials)
        updated = NifcCredentials("andrzej", "new-password")
        self.store.save(updated)
        self.assertEqual(self.store.load("andrzej"), updated)
        self.backend.get_password.assert_not_called()

    def test_delete_invalidates_session(self):
        self.store.save(self.credentials)
        self.store.delete("andrzej")
        self.backend.get_password.return_value = None
        self.assertIsNone(self.store.load("andrzej"))
        self.backend.get_password.assert_called_once()

    def test_failed_save_does_not_cache_new_or_old_password(self):
        self.store.save(self.credentials)
        self.backend.set_password.side_effect = KeyringError()
        with self.assertRaises(CredentialStoreError):
            self.store.save(NifcCredentials("andrzej", "new-password"))
        self.backend.get_password.return_value = "tajne-haslo"
        self.assertEqual(self.store.load("andrzej"), self.credentials)
        self.backend.get_password.assert_called_once()

    def test_missing_password_is_not_cached(self):
        self.backend.get_password.side_effect = [None, "tajne-haslo"]
        self.assertIsNone(self.store.load("andrzej"))
        self.assertEqual(self.store.load("andrzej"), self.credentials)

    def test_cache_is_not_shared_between_store_instances(self):
        self.store.save(self.credentials)
        backend = Mock()
        backend.get_password.return_value = None
        self.assertIsNone(CredentialStore(backend).load("andrzej"))
        backend.get_password.assert_called_once()

    def test_does_not_expose_password_in_representation(self):
        representation = repr(self.credentials)

        self.assertNotIn("tajne-haslo", representation)
        self.assertIn("andrzej", representation)


if __name__ == "__main__":
    unittest.main()
