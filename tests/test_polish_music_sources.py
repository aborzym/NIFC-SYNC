import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock

from core.scans import ScanSourceMetadata
from providers.polish_music_sources import (
    SearchResult,
    download_and_extract,
    get_download_info,
    search_manuscripts,
)


class GetDownloadInfoTest(unittest.TestCase):
    def test_uses_available_pdf(self):
        detail_response = Mock()
        detail_response.json.return_value = {
            "repo_id": "pl-kk:1170",
            "standardized_title": ("94 Sacred songs"),
            "gallery": [
                {
                    "file_name": "1171.jpeg",
                },
                {
                    "file_name": "1172.jpeg",
                },
            ],
        }

        pdf_response = Mock()
        pdf_response.headers = {
            "Content-Type": "application/pdf",
            "Content-Length": "382346729",
        }

        session = Mock()
        session.get.return_value = detail_response
        session.head.return_value = pdf_response

        info = get_download_info(
            session,
            ("https://polish.musicsources.pl/pl/lokalizacje/galeria/rekopisy/5919/1"),
        )

        self.assertEqual(
            info.filename,
            "5919 — 94 Sacred songs.pdf",
        )
        self.assertEqual(
            info.size,
            382346729,
        )
        self.assertEqual(
            info.content_type,
            "PDF",
        )
        self.assertEqual(
            info.pdf_url,
            (
                "https://repozytorium.nifc.pl/"
                "islandora/object/pl-kk%3A1170/"
                "datastream/PDF/download"
            ),
        )
        self.assertEqual(
            len(info.scans),
            2,
        )
        pdf_response.raise_for_status.assert_called_once_with()


class DownloadAndExtractTest(unittest.TestCase):
    def test_downloads_to_named_output_folder(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination_folder = Path(temporary_directory)
            pdf_content = b"%PDF-1.7\nexample-pdf-content"
            pdf_url = (
                "https://repozytorium.nifc.pl/"
                "islandora/object/pl-kk%3A1170/"
                "datastream/PDF/download"
            )

            response = MagicMock()
            response.headers = {
                "Content-Type": "application/pdf",
                "Content-Length": str(len(pdf_content)),
            }
            response.iter_content.return_value = (pdf_content,)
            response.__enter__.return_value = response
            response.__exit__.return_value = False

            session = MagicMock()
            session.get.return_value = response
            info = Mock(
                url=(
                    "https://polish.musicsources.pl/"
                    "pl/lokalizacje/galeria/"
                    "rekopisy/5919/1"
                ),
                pdf_url=pdf_url,
                filename=("5919 — 94 Sacred songs.pdf"),
                size=len(pdf_content),
                manuscript_id="5919",
                title="94 Sacred songs",
            )

            result = download_and_extract(
                session,
                info,
                destination_folder,
                output_folder_name=("5919 — 94 Sacred songs"),
            )

            expected_pdf = result / "5919 — 94 Sacred songs.pdf"

            self.assertEqual(
                result,
                destination_folder / "5919 — 94 Sacred songs",
            )
            self.assertEqual(
                expected_pdf.read_bytes(),
                pdf_content,
            )
            self.assertFalse((destination_folder / "skany").exists())
            self.assertFalse(
                (destination_folder / ("5919 — 94 Sacred songs.problem.txt")).exists()
            )
            session.get.assert_called_once_with(
                pdf_url,
                stream=True,
                timeout=60,
            )

    def test_removes_incomplete_pdf_and_writes_report(
        self,
    ):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination_folder = Path(temporary_directory)
            pdf_content = b"%PDF-1.7\nincomplete"
            pdf_url = (
                "https://repozytorium.nifc.pl/"
                "islandora/object/pl-kk%3A1170/"
                "datastream/PDF/download"
            )
            output_folder_name = "5919 — 94 Sacred songs"

            response = MagicMock()
            response.headers = {
                "Content-Type": "application/pdf",
                "Content-Length": "1000",
            }
            response.iter_content.return_value = (pdf_content,)
            response.__enter__.return_value = response
            response.__exit__.return_value = False

            session = MagicMock()
            session.get.return_value = response
            info = Mock(
                url=(
                    "https://polish.musicsources.pl/"
                    "pl/lokalizacje/galeria/"
                    "rekopisy/5919/1"
                ),
                pdf_url=pdf_url,
                filename=("5919 — 94 Sacred songs.pdf"),
                size=1000,
                manuscript_id="5919",
                title="94 Sacred songs",
            )

            with self.assertRaisesRegex(
                ValueError,
                "Niepełny plik PDF",
            ):
                download_and_extract(
                    session,
                    info,
                    destination_folder,
                    output_folder_name=(output_folder_name),
                )

            self.assertFalse((destination_folder / output_folder_name).exists())
            self.assertEqual(
                tuple(destination_folder.glob(".skany_tmp_*")),
                (),
            )

            problem_path = destination_folder / (f"{output_folder_name}.problem.txt")
            self.assertTrue(problem_path.is_file())
            self.assertIn(
                "Nie pobrano kompletnego pliku PDF",
                problem_path.read_text(encoding="utf-8"),
            )


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
