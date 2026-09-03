import io
import sys
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    requests_stub = types.ModuleType("requests")
    requests_stub.Session = object
    requests_stub.RequestException = Exception
    sys.modules["requests"] = requests_stub

from providers.sandomierz import (
    download_and_extract,
    validate_extracted_djvu,
)


class ValidateExtractedDjvuTests(unittest.TestCase):
    def test_extracts_to_named_output_folder(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination_folder = Path(temporary_directory)
            archive_buffer = io.BytesIO()

            with zipfile.ZipFile(
                archive_buffer,
                "w",
            ) as archive:
                archive.writestr(
                    "page.djvu",
                    b"example-djvu-content",
                )

            archive_content = archive_buffer.getvalue()
            response = MagicMock()
            response.headers = {"Content-Length": str(len(archive_content))}
            response.iter_content.return_value = (archive_content,)
            response.__enter__.return_value = response
            response.__exit__.return_value = False

            session = MagicMock()
            session.get.return_value = response
            info = MagicMock(
                url="https://example.test/package.zip",
                filename="package.zip",
                size=len(archive_content),
            )

            result = download_and_extract(
                session,
                info,
                destination_folder,
                output_folder_name="package",
            )

            self.assertEqual(
                result,
                destination_folder / "package",
            )
            self.assertEqual(
                (result / "page.djvu").read_bytes(),
                b"example-djvu-content",
            )
            self.assertFalse((destination_folder / "skany").exists())

    def test_rejects_empty_djvu_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            staging_folder = Path(temporary_directory)
            (staging_folder / "empty.djvu").write_bytes(b"")

            with self.assertRaisesRegex(
                ValueError,
                "puste pliki DjVu: empty.djvu",
            ):
                validate_extracted_djvu(staging_folder)

    def test_accepts_non_empty_djvu_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            staging_folder = Path(temporary_directory)
            first = staging_folder / "first.djvu"
            second = staging_folder / "second.djvu"
            first.write_bytes(b"first")
            second.write_bytes(b"second")

            self.assertCountEqual(
                validate_extracted_djvu(staging_folder),
                [first, second],
            )


if __name__ == "__main__":
    unittest.main()
