import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.inventory import build_storage_inventory
from core.scans import get_scan_group_key


class StorageInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temporary_directory.name)
        self.filename = "pl-sa--227-a-vi-31--001-005_anonim--msza-agnus-dei.krn"
        self.group_key = get_scan_group_key(self.filename)
        self.normalized_url = "sandomierz-1551"
        self.project_folder = self.base_dir / (
            "001 - D - " + self.filename.removesuffix(".krn")
        )
        self.scans_folder = self.project_folder / "skany"
        self.scans_folder.mkdir(parents=True)
        self.scan_file = self.scans_folder / "scan.djvu"
        self.scan_file.write_bytes(b"scan")

    def tearDown(self):
        self.temporary_directory.cleanup()

    @patch("core.inventory.scan_manifest_file_paths")
    @patch("core.inventory.validate_scan_manifest")
    def test_always_checks_manifest_file_sizes(
        self,
        validate_manifest,
        manifest_paths,
    ):
        validate_manifest.return_value = True
        manifest_paths.return_value = (self.scan_file,)

        build_storage_inventory(
            self.base_dir,
            {
                self.group_key: {
                    self.normalized_url,
                },
            },
        )

        validate_manifest.assert_called_once_with(
            self.scans_folder,
            verify_sizes=True,
        )

    @patch("core.inventory.find_existing_scores")
    @patch(
        "core.inventory.validate_scan_manifest",
        return_value=None,
    )
    def test_scans_legacy_files(
        self,
        _validate_manifest,
        find_scores,
    ):
        find_scores.return_value = (self.scan_file,)

        result = build_storage_inventory(
            self.base_dir,
            {
                self.group_key: {
                    self.normalized_url,
                },
            },
        )

        find_scores.assert_called_once_with(
            self.scans_folder,
        )
        self.assertEqual(
            result.existing_scans_by_url[self.normalized_url][self.project_folder],
            (self.scan_file,),
        )


if __name__ == "__main__":
    unittest.main()
