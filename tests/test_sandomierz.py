import sys
import tempfile
import types
import unittest
from pathlib import Path

try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    requests_stub = types.ModuleType("requests")
    requests_stub.Session = object
    requests_stub.RequestException = Exception
    sys.modules["requests"] = requests_stub

from providers.sandomierz import validate_extracted_djvu


class ValidateExtractedDjvuTests(unittest.TestCase):
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
