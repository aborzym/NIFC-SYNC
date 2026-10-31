import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QSettings

from core.settlement_store import SettlementStore
from core.settlement_sync import exchange, materialize, record_changes


def document(name="bajka.krn", count=38985):
    return {
        "performer": "Test",
        "total": count,
        "filename": "transza.pdf",
        "entries": [
            {
                "tranche": 1,
                "scheme": "KRN-modern",
                "file_name": name,
                "note_count": count,
            }
        ],
    }


class SettlementSyncTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.shared = self.root / "Dropbox"
        self.shared.mkdir()

    def store(self, device, username="andrzej", folder=True):
        settings = QSettings(
            str(self.root / f"{device}.ini"), QSettings.Format.IniFormat
        )
        configuration = SimpleNamespace(
            settings=settings,
            active_account_id=lambda: f"local-{device}",
            load=lambda: SimpleNamespace(nifc_username=username),
        )
        store = SettlementStore(configuration)
        if folder:
            store.set_sync_folder(self.shared)
        store.load()
        return store

    def test_different_local_account_ids_share_by_login(self):
        first = self.store("linux")
        first.save({"pdf": document()}, set())
        second = self.store("mac", " ANDRZEJ ")
        self.assertEqual(second.load()[0], {"pdf": document()})

    def test_other_login_is_isolated(self):
        self.store("linux").save({"pdf": document()}, set())
        self.assertEqual(self.store("mac", "other").load()[0], {})

    def test_offline_additions_merge_after_restart(self):
        first, second = self.store("linux"), self.store("mac")
        self.shared.rename(self.root / "offline")
        first.save({"a": document()}, set())
        second.save({"b": document("other.krn")}, set())
        self.assertTrue(first.sync_error)
        self.shared.mkdir()
        first = self.store("linux")
        second = self.store("mac")
        self.assertEqual(set(second.load()[0]), {"a", "b"})
        self.assertEqual(set(first.load()[0]), {"a", "b"})

    def test_delete_is_not_resurrected_by_stale_device(self):
        first = self.store("linux")
        first.save({"a": document()}, set())
        second = self.store("mac")
        old, approvals = second.load()
        first.save({}, set())
        second.save(old, approvals)
        self.assertEqual(second.load()[0], {})
        self.assertEqual(first.load()[0], {})

    def test_concurrent_add_and_delete_keep_unseen_add(self):
        initial = record_changes({}, {"a": document()}, set())
        deleted = record_changes(initial, {}, set())
        other = record_changes({}, {"a": document()}, set())
        values, _ = materialize(deleted | other)
        self.assertEqual(values["settlement"], {"a": document()})

    def test_reimport_after_delete(self):
        first = self.store("linux")
        first.save({"a": document()}, set())
        first.save({}, set())
        first.save({"a": document()}, set())
        self.assertEqual(self.store("mac").load()[0], {"a": document()})

    def test_approvals_sync_snapshot_stays_local(self):
        approval = (
            "KRN-modern",
            "a.krn",
            "2026-10-17",
            1,
            "KRN-modern",
            "a.krn-modern",
            1,
        )
        first = self.store("linux")
        first.snapshot = {
            "start_date": "2026-01-01",
            "refreshed_at": "2026-10-17",
            "entries": [{"secret-local-statistics": True}],
        }
        first.save({}, {approval})
        second = self.store("mac")
        self.assertEqual(second.load()[1], {approval})
        self.assertIsNone(second.snapshot)
        for path in self.shared.rglob("*.json"):
            self.assertNotIn("secret-local-statistics", path.read_text())

    def test_invalid_remote_keeps_local_data_and_reports_error(self):
        first = self.store("linux")
        first.save({"a": document()}, set())
        path = next(self.shared.rglob("*.json"))
        path.write_text("broken", encoding="utf-8")
        loaded = self.store("linux")
        self.assertTrue(loaded.sync_error)
        self.assertEqual(loaded.load()[0], {"a": document()})
        self.assertEqual(path.read_text(), "broken")

    def test_conflict_copy_is_read_and_duplicates_are_idempotent(self):
        first = self.store("linux")
        first.save({"a": document()}, set())
        path = next(self.shared.rglob("*.json"))
        shutil.copyfile(path, path.with_name("conflicted copy.json"))
        second = self.store("mac")
        self.assertEqual(len(second.events), 1)
        self.assertEqual(second.load()[0], {"a": document()})

    def test_conflicting_payload_is_not_silently_chosen(self):
        events = record_changes({}, {"a": document()}, set())
        exchange(self.shared, "andrzej", events)
        other = record_changes({}, {"a": document(count=1)}, set())
        with self.assertRaisesRegex(ValueError, "Sprzeczne"):
            exchange(self.shared, "andrzej", other)
        self.assertEqual(len(list(self.shared.rglob("*.json"))), 1)

    def test_legacy_migration_preserves_records_and_is_idempotent(self):
        store = self.store("linux", folder=False)
        store.settings.setValue(
            store.key,
            json.dumps(
                {"version": 1, "settlements": {"a": document()}, "approved_matches": []}
            ),
        )
        self.assertEqual(store.load()[0], {"a": document()})
        events = dict(store.events)
        store.load()
        self.assertEqual(store.events, events)

    def test_new_remote_entry_is_not_deleted_by_old_open_dialog(self):
        first, second = self.store("linux"), self.store("mac")
        first.save({"a": document()}, set())
        merged, _ = second.synchronize({"b": document("other.krn")}, set())
        self.assertEqual(set(merged), {"a", "b"})
        self.assertEqual(set(first.load()[0]), {"a", "b"})


if __name__ == "__main__":
    unittest.main()
