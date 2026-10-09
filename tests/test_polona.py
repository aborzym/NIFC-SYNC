import unittest
from unittest.mock import Mock

from providers.polona import get_download_info, supports

SCAN_URL = "https://polona.pl/item-view/7b369fcb-3d2d-4fe7-920a-c05f46eb8643?page=4"


class PolonaProviderTest(unittest.TestCase):
    def test_recognizes_item_view_with_page_number(self):
        self.assertTrue(supports(SCAN_URL))
        self.assertFalse(supports("https://example.com/item-view/7b369fcb"))

    def test_finds_collective_pdf_and_checks_headers(self):
        contents_response = Mock()
        contents_response.json.return_value = {
            "shared": True,
            "copyrightProtected": False,
            "collective": {
                "content": [
                    {
                        "fileName": "1-BN_Mus_III_108_606_0002.pdf",
                        "mimeType": "application/pdf",
                        "fileUrl": (
                            "/download/digital-content/"
                            "79b20ba7-2c99-46d6-902e-1af17065402e"
                        ),
                    }
                ]
            },
        }

        pdf_response = Mock()
        pdf_response.headers = {
            "Content-Type": "application/pdf",
            "Content-Length": "65720865",
        }

        session = Mock()
        session.get.return_value = contents_response
        session.head.return_value = pdf_response

        info = get_download_info(session, SCAN_URL)

        self.assertEqual(info.filename, "1-BN_Mus_III_108_606_0002.pdf")
        self.assertEqual(info.size, 65720865)
        self.assertEqual(
            info.pdf_url,
            (
                "https://polona.pl/api/download/digital-content/"
                "79b20ba7-2c99-46d6-902e-1af17065402e"
            ),
        )
        session.head.assert_called_once_with(
            info.pdf_url,
            allow_redirects=True,
            timeout=30,
        )


if __name__ == "__main__":
    unittest.main()
