import unittest
from unittest.mock import Mock

from core.client import NifcClient


class NifcClientTest(unittest.TestCase):
    def test_gets_monthly_statistics(self):
        session = Mock()
        client = NifcClient(
            session=session,
            base_url="https://example.test",
            timeout=12,
        )

        result = client.get_statistics("2026-09-01")

        self.assertIs(result, session.get.return_value)
        session.get.assert_called_once_with(
            "https://example.test/api/files/statistics",
            params={"month": "2026-09-01", "all": "false"},
            timeout=12,
        )
        session.post.assert_not_called()

    def test_submits_file_as_base64_json(self):
        session = Mock()
        response = Mock()
        session.post.return_value = response
        client = NifcClient(
            session=session,
            base_url="https://example.test",
            timeout=12,
        )

        result = client.submit_file(
            "KRN-diplomatic",
            "pl-sa--227_msza.krn",
            b"przykladowa zawartosc",
        )

        self.assertIs(result, response)
        session.post.assert_called_once_with(
            (
                "https://example.test/api/files/content/"
                "KRN-diplomatic/pl-sa--227_msza.krn"
            ),
            json={
                "content": "cHJ6eWtsYWRvd2EgemF3YXJ0b3Nj",
            },
            timeout=12,
        )

    def test_rejects_non_bytes_content(self):
        session = Mock()
        client = NifcClient(
            session=session,
            base_url="https://example.test",
        )

        with self.assertRaises(TypeError):
            client.submit_file(
                "XML",
                "utwor.musicxml",
                "to nie sa bajty",
            )

        session.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
