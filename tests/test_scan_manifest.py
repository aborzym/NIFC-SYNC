import tempfile
import unittest
from pathlib import Path

from core.scan_manifest import validate_scan_manifest, write_scan_manifest


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
