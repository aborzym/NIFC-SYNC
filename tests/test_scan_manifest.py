import tempfile
import unittest
from pathlib import Path

from core.scan_manifest import (
    scan_manifest_file_paths,
    validate_scan_manifest,
    write_scan_manifest,
)


class ScanManifestTests(unittest.TestCase):
    def test_legacy_folder_has_unknown_status(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            scans = Path(temporary_directory) / "skany"
            scans.mkdir()
            (scans / "scan.djvu").write_bytes(b"scan")

            self.assertIsNone(validate_scan_manifest(scans))

    def test_accepts_unchanged_package(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            scans = Path(temporary_directory) / "skany"
            scans.mkdir()
            (scans / "scan.djvu").write_bytes(b"scan")
            write_scan_manifest(scans, "https://example.test", "scans.zip")

            self.assertTrue(validate_scan_manifest(scans))

    def test_rejects_missing_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            scans = Path(temporary_directory) / "skany"
            scans.mkdir()
            scan = scans / "scan.djvu"
            scan.write_bytes(b"scan")
            write_scan_manifest(scans, "https://example.test", "scans.zip")
            scan.unlink()

            self.assertFalse(validate_scan_manifest(scans))

    def test_rejects_changed_file_size(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            scans = Path(temporary_directory) / "skany"
            scans.mkdir()
            scan = scans / "scan.djvu"
            scan.write_bytes(b"scan")
            write_scan_manifest(scans, "https://example.test", "scans.zip")
            scan.write_bytes(b"different")

            self.assertFalse(validate_scan_manifest(scans))

    def test_returns_paths_recorded_in_manifest(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            scans = Path(temporary_directory) / "skany"
            nested_folder = scans / "strony"
            nested_folder.mkdir(parents=True)
            first_scan = scans / "okładka.jpg"
            second_scan = nested_folder / "scan.djvu"
            first_scan.write_bytes(b"cover")
            second_scan.write_bytes(b"scan")

            write_scan_manifest(
                scans,
                "https://example.test",
                "scans.zip",
            )

            self.assertEqual(
                set(scan_manifest_file_paths(scans)),
                {
                    first_scan,
                    second_scan,
                },
            )
