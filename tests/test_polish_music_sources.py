import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock

from core.scans import ScanSourceMetadata
from providers.polish_music_sources import (
    SearchResult,
    download_and_extract,
    search_manuscripts,
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


class SearchManuscriptsTest(unittest.TestCase):
    def test_falls_back_to_exact_siglum_and_shelfmark(
        self,
    ):
        rism_response = Mock()
        rism_response.json.return_value = []

        shelfmark_response = Mock()
        shelfmark_response.json.return_value = [
            {
                "id_object": "5823",
                "type": "manuscripts",
                "library_siglum": "PL-Kk",
                "shelfmark": "Kk.I.195",
                "rism_id": "1001151874",
                "standardized_title": "2 Hymns",
            },
            {
                "id_object": "5828",
                "type": "manuscripts",
                "library_siglum": "PL-Kk",
                "shelfmark": "Kk.I.2",
                "rism_id": "300258016",
                "standardized_title": "55 Sacred songs",
            },
        ]

        session = Mock()
        session.post.side_effect = (
            rism_response,
            shelfmark_response,
        )
        metadata = ScanSourceMetadata(
            rism_id="300258019",
            siglum="PL-Kk",
            shelfmark="Kk.I.2",
            composer="Terzago, Bernardino",
            title="O beatum pontificem",
        )

        results = search_manuscripts(
            session,
            metadata,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0],
            SearchResult(
                manuscript_id="5828",
                title="55 Sacred songs",
                siglum="PL-Kk",
                shelfmark="Kk.I.2",
                rism_id="300258016",
                url=(
                    "https://polish.musicsources.pl/pl/"
                    "lokalizacje/galeria/rekopisy/5828/1"
                ),
            ),
        )
        self.assertEqual(session.post.call_count, 2)
        rism_response.raise_for_status.assert_called_once_with()
        shelfmark_response.raise_for_status.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
