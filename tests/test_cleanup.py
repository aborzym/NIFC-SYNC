import tempfile
import unittest
from pathlib import Path

from core.cleanup import cleanup_scan_staging_folders


class CleanupScanStagingFoldersTests(unittest.TestCase):
    def test_removes_scan_staging_folder(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            base_dir = Path(temporary_directory)
            project_folder = base_dir / "001 - D - test"
            staging_folder = project_folder / ".skany_tmp_test"
            staging_folder.mkdir(parents=True)
            (staging_folder / "scan.djvu").write_bytes(b"partial")

            result = cleanup_scan_staging_folders(
                base_dir,
                log=lambda message: None,
            )

            self.assertFalse(staging_folder.exists())
            self.assertEqual(result.removed, (staging_folder,))
            self.assertEqual(result.failures, ())

    def test_preserves_completed_scans_folder(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            base_dir = Path(temporary_directory)
            project_folder = base_dir / "001 - D - test"
            scans_folder = project_folder / "skany"
            scans_folder.mkdir(parents=True)
            scan_path = scans_folder / "scan.djvu"
            scan_path.write_bytes(b"complete")

            cleanup_scan_staging_folders(
                base_dir,
                log=lambda message: None,
            )

            self.assertTrue(scan_path.exists())


if __name__ == "__main__":
    unittest.main()
