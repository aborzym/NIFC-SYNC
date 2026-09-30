import unittest
from unittest.mock import Mock

from core.scans import find_scan_provider
from providers import nifc_repository

SCAN_URL = (
    "https://repozytorium.nifc.pl/islandora/object/"
    "islandora%3A308/datastream/OBJ/view#page=151"
)


class NifcRepositoryTest(unittest.TestCase):
    def test_selects_provider_for_islandora_url(self):
        self.assertIs(find_scan_provider(SCAN_URL), nifc_repository)
        self.assertFalse(
            nifc_repository.supports(
                SCAN_URL.replace("repozytorium.nifc.pl", "example.com")
            )
        )

    def test_reads_pdf_metadata_without_page_fragment(self):
        session = Mock()
        session.head.return_value.headers = {
            "Content-Type": "application/pdf",
            "Content-Length": "198371341",
        }

        info = nifc_repository.get_download_info(session, SCAN_URL)

        self.assertEqual(info.filename, "islandora-308.pdf")
        self.assertEqual(info.size, 198371341)
        self.assertEqual(info.url, SCAN_URL)
        self.assertEqual(info.pdf_url, SCAN_URL.split("#")[0])
        session.head.assert_called_once_with(
            info.pdf_url, allow_redirects=True, timeout=30
        )

    def test_rejects_html_response(self):
        session = Mock()
        session.head.return_value.headers = {"Content-Type": "text/html"}

        with self.assertRaises(ValueError):
            nifc_repository.get_download_info(session, SCAN_URL)
