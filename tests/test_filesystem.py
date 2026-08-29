import tempfile
import unittest
from pathlib import Path

from core.filesystem import find_existing_scores


class FindExistingScoresTests(unittest.TestCase):
    def test_ignores_incomplete_scan_staging_folder(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_folder = Path(temporary_directory)
            staging_folder = project_folder / ".skany_tmp_abcd1234"
            staging_folder.mkdir()
            (staging_folder / "scan.djvu").write_bytes(b"incomplete")

            self.assertEqual(
                find_existing_scores(project_folder),
                [],
            )

    def test_finds_scan_in_completed_scans_folder(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_folder = Path(temporary_directory)
            scans_folder = project_folder / "skany"
            scans_folder.mkdir()
            scan_path = scans_folder / "scan.djvu"
            scan_path.write_bytes(b"complete")

            self.assertEqual(
                find_existing_scores(project_folder),
                [scan_path],
            )


if __name__ == "__main__":
    unittest.main()
