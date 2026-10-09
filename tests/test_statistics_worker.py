import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from gui.workers import StatisticsWorker


class StatisticsWorkerTest(unittest.TestCase):
    def test_loads_all_months_without_duplicate_requests(self):
        credentials = SimpleNamespace(username="test", password="test")
        client = Mock()
        client.login.return_value.ok = True
        august = [{"name": "KRN-modern", "files": []}]
        september = [{"name": "XML", "files": []}]

        responses = []
        for data in (august, september):
            response = Mock(ok=True)
            response.json.return_value = data
            responses.append(response)
        client.get_statistics.side_effect = responses

        worker = StatisticsWorker(
            credentials,
            ["2026-08-01", "2026-09-01", "2026-08-01"],
        )
        loaded = Mock()
        failed = Mock()
        finished = Mock()
        worker.loaded.connect(loaded)
        worker.failed.connect(failed)
        worker.finished.connect(finished)

        with patch("gui.workers.NifcClient", return_value=client):
            worker.run()

        loaded.assert_called_once_with(
            {
                "2026-08-01": august,
                "2026-09-01": september,
            }
        )
        self.assertEqual(
            client.get_statistics.call_args_list,
            [call("2026-08-01"), call("2026-09-01")],
        )
        failed.assert_not_called()
        finished.assert_called_once_with()
        client.session.close.assert_called_once_with()

    def test_failure_does_not_emit_partial_statistics(self):
        credentials = SimpleNamespace(username="test", password="test")
        client = Mock()
        client.login.return_value.ok = True

        first = Mock(ok=True)
        first.json.return_value = []
        second = Mock(ok=False, status_code=500)
        client.get_statistics.side_effect = [first, second]

        worker = StatisticsWorker(
            credentials,
            ["2026-08-01", "2026-09-01"],
        )
        loaded = Mock()
        failed = Mock()
        finished = Mock()
        worker.loaded.connect(loaded)
        worker.failed.connect(failed)
        worker.finished.connect(finished)

        with patch("gui.workers.NifcClient", return_value=client):
            worker.run()

        loaded.assert_not_called()
        failed.assert_called_once()
        self.assertIn("2026-09", failed.call_args.args[0])
        finished.assert_called_once_with()
        client.session.close.assert_called_once_with()
