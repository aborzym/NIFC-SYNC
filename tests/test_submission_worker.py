import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from gui.workers import SubmissionWorker


class SubmissionWorkerTest(unittest.TestCase):
    def test_reports_validator_message_for_http_406(self):
        with tempfile.TemporaryDirectory() as directory:
            file_path = Path(directory) / "utwor.krn"
            file_path.write_bytes(b"!!!!SEGMENT: utwor.krn\n")

            client = Mock()
            client.login.return_value = SimpleNamespace(ok=True)
            client.submit_file.return_value = SimpleNamespace(
                ok=False,
                status_code=406,
                text='{"error":{"message":"Niepoprawny plik Humdrum."}}',
                json=lambda: {"error": {"message": "Niepoprawny plik Humdrum."}},
            )

            worker = SubmissionWorker(
                credentials=SimpleNamespace(
                    username="test",
                    password="haslo",
                ),
                workflow_key="workflow-key",
                filename="utwor.krn",
                file_path=file_path,
            )
            failures = []
            successes = []
            worker.failed.connect(failures.append)
            worker.submitted.connect(lambda: successes.append(True))

            with patch("gui.workers.NifcClient", return_value=client):
                worker.run()

            self.assertEqual(failures, ["Niepoprawny plik Humdrum."])
            self.assertEqual(successes, [])
            client.submit_file.assert_called_once_with(
                "workflow-key",
                "utwor.krn",
                b"!!!!SEGMENT: utwor.krn\n",
                progress_callback=worker._upload_progress,
            )

    def test_reports_success_after_accepted_post(self):
        with tempfile.TemporaryDirectory() as directory:
            file_path = Path(directory) / "utwor.krn"
            file_path.write_bytes(b"**kern\n*-\n")

            client = Mock()
            client.login.return_value = SimpleNamespace(ok=True)
            client.submit_file.return_value = SimpleNamespace(
                ok=True,
                status_code=200,
                text="Plik przyjęty.",
            )
            worker = SubmissionWorker(
                credentials=SimpleNamespace(
                    username="test",
                    password="haslo",
                ),
                workflow_key="workflow-key",
                filename="utwor.krn",
                file_path=file_path,
            )
            failures = []
            successes = []
            worker.failed.connect(failures.append)
            worker.submitted.connect(lambda: successes.append(True))

            with patch("gui.workers.NifcClient", return_value=client):
                worker.run()

            self.assertEqual(failures, [])
            self.assertEqual(successes, [True])
            client.submit_file.assert_called_once_with(
                "workflow-key",
                "utwor.krn",
                b"**kern\n*-\n",
                progress_callback=worker._upload_progress,
            )


if __name__ == "__main__":
    unittest.main()
