import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from core.credentials import (
    CredentialStore,
    NifcCredentials,
)
from core.migration import (
    LegacyCredentialError,
    load_legacy_credentials,
    migrate_legacy_credentials,
)


class LegacyCredentialsMigrationTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.credentials_file = Path(self.temporary_directory.name) / ".nifccredentials"

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_returns_none_when_legacy_file_does_not_exist(self):
        result = load_legacy_credentials(self.credentials_file)

        self.assertIsNone(result)

    def test_loads_legacy_credentials(self):
        self.credentials_file.write_text(
            "# stare dane NIFC\n\nlogin=andrzej\npassword=tajne-haslo\n",
            encoding="utf-8",
        )

        result = load_legacy_credentials(self.credentials_file)

        self.assertEqual(
            result,
            NifcCredentials(
                username="andrzej",
                password="tajne-haslo",
            ),
        )

    def test_rejects_malformed_legacy_file(self):
        self.credentials_file.write_text(
            "login=andrzej\nuszkodzona-linia\npassword=tajne-haslo\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            LegacyCredentialError,
            "nieprawidłowy format",
        ):
            load_legacy_credentials(self.credentials_file)

    def test_rejects_incomplete_legacy_credentials(self):
        self.credentials_file.write_text(
            "login=andrzej\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            LegacyCredentialError,
            "kompletnego loginu i hasła",
        ):
            load_legacy_credentials(self.credentials_file)

    def test_migrates_without_deleting_legacy_file(self):
        self.credentials_file.write_text(
            "login=andrzej\npassword=tajne-haslo\n",
            encoding="utf-8",
        )
        credential_store = Mock(spec=CredentialStore)

        result = migrate_legacy_credentials(
            credential_store,
            self.credentials_file,
        )

        credential_store.save.assert_called_once_with(result)
        self.assertTrue(self.credentials_file.exists())


if __name__ == "__main__":
    unittest.main()
