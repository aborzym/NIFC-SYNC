import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock

from providers.polish_music_sources import (
    download_and_extract,
)


class DownloadAndExtractTest(unittest.TestCase):
    def test_downloads_to_named_output_folder(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination_folder = Path(temporary_directory)
            jpeg_content = b"example-jpeg-content"

            response = MagicMock()
            response.headers = {
                "Content-Type": "image/jpeg",
                "Content-Length": str(len(jpeg_content)),
            }
            response.iter_content.return_value = (jpeg_content,)
            response.__enter__.return_value = response
            response.__exit__.return_value = False

            session = MagicMock()
            session.get.return_value = response
            scan = Mock(
                filename="001.jpeg",
                url="https://example.test/001.jpeg",
            )
            info = Mock(
                url="https://example.test/manuscript",
                manuscript_id="1234",
                title="Missa",
                scans=(scan,),
            )

            result = download_and_extract(
                session,
                info,
                destination_folder,
                output_folder_name="1234_Missa",
            )

            self.assertEqual(
                result,
                destination_folder / "1234_Missa",
            )
            self.assertEqual(
                (result / "001.jpeg").read_bytes(),
                jpeg_content,
            )
            self.assertFalse((destination_folder / "skany").exists())
            self.assertFalse((destination_folder / "1234_Missa.problem.txt").exists())


if __name__ == "__main__":
    unittest.main()
