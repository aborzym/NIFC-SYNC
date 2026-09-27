import tempfile
import unittest
from pathlib import Path

from core.submission import (
    find_submission_files,
    inspect_submission_file,
)


class SubmissionInspectionTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temporary_directory.name)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_accepts_matching_krn_filename_and_segment(self):
        expected_name = "pl-sa--227_msza.krn"
        file_path = self.base_dir / expected_name
        file_path.write_text(
            (f"!!!!SEGMENT: {expected_name}\n**kern\n*M4/4\n*-\n"),
            encoding="utf-8",
        )

        result = inspect_submission_file(
            "KRN-diplomatic",
            expected_name,
            file_path,
        )

        self.assertEqual(result.actual_filename, expected_name)
        self.assertEqual(result.segment_name, expected_name)
        self.assertEqual(result.warnings, ())

    def test_warns_about_mismatching_krn_segment(self):
        expected_name = "pl-sa--227_msza.krn"
        file_path = self.base_dir / expected_name
        file_path.write_text(
            ("!!!!SEGMENT: inny-plik.krn\n**kern\n*-\n"),
            encoding="utf-8",
        )

        result = inspect_submission_file(
            "KRN-modern",
            expected_name,
            file_path,
        )

        self.assertTrue(any("!!!!SEGMENT:" in warning for warning in result.warnings))

    def test_warns_when_krn_segment_is_missing(self):
        expected_name = "pl-sa--227_msza.krn"
        file_path = self.base_dir / expected_name
        file_path.write_text(
            "**kern\n*-\n",
            encoding="utf-8",
        )

        result = inspect_submission_file(
            "KRN-diplomatic",
            expected_name,
            file_path,
        )

        self.assertIsNone(result.segment_name)
        self.assertTrue(
            any("brak !!!!SEGMENT:" in warning for warning in result.warnings)
        )

    def test_xml_requires_only_matching_filename(self):
        expected_name = "pl-wnifc--yyy_koncert.musicxml"
        file_path = self.base_dir / expected_name
        file_path.write_text(
            "<?xml version='1.0'?><score-partwise/>",
            encoding="utf-8",
        )

        result = inspect_submission_file(
            "XML",
            expected_name,
            file_path,
        )

        self.assertIsNone(result.segment_name)
        self.assertEqual(result.warnings, ())

    def test_warns_about_mismatching_local_filename(self):
        file_path = self.base_dir / "inny-plik.musicxml"
        file_path.write_text(
            "<?xml version='1.0'?><score-partwise/>",
            encoding="utf-8",
        )

        result = inspect_submission_file(
            "XML",
            "oczekiwany-plik.musicxml",
            file_path,
        )

        self.assertTrue(any("Nazwa pliku" in warning for warning in result.warnings))

    def test_finds_matching_file_in_nested_folder(self):
        expected_name = "pl-sa--227_msza.krn"
        project_folder = self.base_dir / "001 - D - pl-sa--227_msza"
        project_folder.mkdir()
        expected_path = project_folder / expected_name
        expected_path.write_text(
            "**kern\n*-\n",
            encoding="utf-8",
        )

        results = find_submission_files(
            self.base_dir,
            expected_name,
        )

        self.assertEqual(
            results,
            (expected_path,),
        )

    def test_ignores_scans_folders_when_searching(self):
        expected_name = "pl-sa--227_msza.krn"
        scans_folder = self.base_dir / "001 - D - pl-sa--227_msza" / "skany"
        scans_folder.mkdir(parents=True)
        (scans_folder / expected_name).write_text(
            "**kern\n*-\n",
            encoding="utf-8",
        )

        results = find_submission_files(
            self.base_dir,
            expected_name,
        )

        self.assertEqual(results, ())


if __name__ == "__main__":
    unittest.main()
