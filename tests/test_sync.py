import base64
import tempfile
import unittest
from pathlib import Path

from core.configuration import (
    AppConfiguration,
    OrganizationPath,
)
from core.sync import sync_transcriptions


class TranscriptionSyncTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temporary_directory.name)
        self.filename = "pl-sa--227-a-vi-31--001_msza.krn"
        self.content = b"**kern\n*clefG2\n*-"
        self.workflow = {
            "name": "KRN-diplomatic",
            "files": (
                {
                    "name": self.filename,
                    "content": base64.b64encode(self.content).decode("ascii"),
                },
            ),
        }

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_creates_work_folder_and_downloads_file(self):
        result = sync_transcriptions(
            self.workflow,
            self.base_dir,
            (),
            1,
            log=lambda _message: None,
        )

        expected_folder = self.base_dir / ("001 - D - pl-sa--227-a-vi-31--001_msza")
        expected_file = expected_folder / self.filename

        self.assertTrue(expected_folder.is_dir())
        self.assertEqual(
            expected_file.read_bytes(),
            self.content,
        )
        self.assertEqual(result.created_count, 1)
        self.assertEqual(result.downloaded_count, 1)
        self.assertEqual(result.skipped_count, 0)
        self.assertEqual(
            result.target_folders[self.filename],
            expected_folder,
        )

    def test_skips_existing_transcription(self):
        folder_name = "005 - D - pl-sa--227-a-vi-31--001_msza"
        target_folder = self.base_dir / folder_name
        target_folder.mkdir()
        existing_file = target_folder / "existing.krn"
        existing_file.write_text(
            "**kern\n*-",
            encoding="utf-8",
        )

        result = sync_transcriptions(
            self.workflow,
            self.base_dir,
            (folder_name,),
            6,
            log=lambda _message: None,
        )

        self.assertEqual(result.created_count, 0)
        self.assertEqual(result.downloaded_count, 0)
        self.assertEqual(result.skipped_count, 1)
        self.assertFalse((target_folder / self.filename).exists())
        self.assertTrue(existing_file.exists())

    def test_marta_writes_file_directly_to_library_folder(
        self,
    ):
        library_folder = Path("Sandomierz.krn")
        configuration = AppConfiguration(
            destination=self.base_dir,
            naming_profile="marta-lawrence",
            organization_paths=(
                OrganizationPath(
                    key="libraries/pl-sa/transcriptions",
                    path=library_folder,
                ),
            ),
        )

        result = sync_transcriptions(
            self.workflow,
            self.base_dir,
            (),
            1,
            log=lambda _message: None,
            configuration=configuration,
        )

        expected_folder = self.base_dir / library_folder
        expected_file = expected_folder / self.filename

        self.assertTrue(expected_folder.is_dir())
        self.assertEqual(
            expected_file.read_bytes(),
            self.content,
        )
        self.assertEqual(result.created_count, 1)
        self.assertEqual(result.downloaded_count, 1)
        self.assertEqual(result.skipped_count, 0)
        self.assertEqual(
            result.target_folders[self.filename],
            expected_folder,
        )
        self.assertFalse(
            (self.base_dir / ("001 - D - pl-sa--227-a-vi-31--001_msza")).exists()
        )

    def test_marta_skips_unconfigured_library(
        self,
    ):
        configuration = AppConfiguration(
            destination=self.base_dir,
            naming_profile="marta-lawrence",
        )
        messages = []

        result = sync_transcriptions(
            self.workflow,
            self.base_dir,
            (),
            1,
            log=messages.append,
            configuration=configuration,
        )

        self.assertEqual(result.created_count, 0)
        self.assertEqual(result.downloaded_count, 0)
        self.assertEqual(result.skipped_count, 1)
        self.assertNotIn(
            self.filename,
            result.target_folders,
        )
        self.assertTrue(
            any("brak folderu transkrypcji" in message.lower() for message in messages)
        )


if __name__ == "__main__":
    unittest.main()
