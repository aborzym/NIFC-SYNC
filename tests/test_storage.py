import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.storage import validate_storage


class ValidateStorageTest(unittest.TestCase):
    def test_accepts_accessible_local_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            result = validate_storage(directory, "local")

        self.assertTrue(result.is_valid)
        self.assertIsNone(result.mount_point)

    def test_rejects_missing_directory(self):
        missing = Path(tempfile.gettempdir()) / "nifc-missing"

        result = validate_storage(missing, "local")

        self.assertFalse(result.is_valid)
        self.assertIn("nie istnieje", result.message)

    def test_rejects_file_instead_of_directory(self):
        with tempfile.NamedTemporaryFile() as file:
            result = validate_storage(file.name, "local")

        self.assertFalse(result.is_valid)
        self.assertIn("nie jest katalogiem", result.message)

    def test_rejects_directory_without_write_access(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch(
                "core.storage.os.access",
                side_effect=lambda path, mode: mode != os.W_OK,
            ),
        ):
            result = validate_storage(directory, "local")

        self.assertFalse(result.is_valid)
        self.assertIn("Brak prawa zapisu", result.message)

    def test_accepts_directory_inside_mounted_storage(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch(
                "core.storage.find_mount_point",
                return_value=Path("/mnt/mac"),
            ),
        ):
            result = validate_storage(directory, "mounted")

        self.assertTrue(result.is_valid)
        self.assertEqual(
            result.mount_point,
            Path("/mnt/mac"),
        )

    def test_rejects_unmounted_network_directory(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch(
                "core.storage.find_mount_point",
                return_value=Path("/"),
            ),
        ):
            result = validate_storage(directory, "mounted")

        self.assertFalse(result.is_valid)
        self.assertIn("nie jest obecnie zamontowany", result.message)


if __name__ == "__main__":
    unittest.main()
