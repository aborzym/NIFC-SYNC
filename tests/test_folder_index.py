import base64
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtCore import QSettings

from core.configuration import AppConfiguration, ConfigurationStore
from core.folder_index import FolderIndex, refresh_folder_index
from core.inventory import build_storage_inventory
from core.sync import sync_transcriptions


class FolderIndexTest(unittest.TestCase):
    def test_historic_xml_revision_folder_marks_krn_as_sent(self):
        self.refresh(self.master)
        historic = self.mac / "WYSŁANE" / "047 - XML rev - D - historyczna-nazwa"
        historic.mkdir(parents=True)
        (historic / "rzeczywista-nazwa.krn").write_text("zachowaj", encoding="utf-8")

        self.refresh(self.master)
        catalog_path = next(self.shared.rglob("catalog.json"))
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        self.assertIn("D - rzeczywista-nazwa", catalog["sent_legacy"])
        self.assertNotIn("D - rzeczywista-nazwa", catalog["entries"])

        linux_copy = self.linux / "047 - D - rzeczywista-nazwa"
        linux_copy.mkdir()
        (linux_copy / "edit.krn").write_text("edycja", encoding="utf-8")
        self.refresh(self.replica)

        self.assertFalse(linux_copy.exists())
        archives = list(
            self.linux.glob(".nifc-folder-index/*/sent/047 - D - rzeczywista-nazwa")
        )
        self.assertEqual(len(archives), 1)
        self.assertEqual(
            (archives[0] / "edit.krn").read_text(encoding="utf-8"),
            "edycja",
        )
        self.assertTrue(historic.is_dir())

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.mac = self.root / "mac"
        self.linux = self.root / "linux"
        self.shared = self.root / "dropbox"
        for path in (self.mac, self.linux, self.shared):
            path.mkdir()
        self.master = AppConfiguration(
            destination=self.mac,
            nifc_username="andrzej",
            folder_index_role="master",
            folder_index_directory=str(self.shared),
        )
        self.replica = replace(
            self.master, destination=self.linux, folder_index_role="replica"
        )

    def refresh(self, configuration):
        refresh_folder_index(configuration, lambda _: None)

    def sync(self, configuration, stem="bajka", workflow="KRN-modern"):
        name = stem + (".musicxml" if workflow == "XML" else ".krn")
        inventory = build_storage_inventory(configuration.destination, {})
        return sync_transcriptions(
            {
                "name": workflow,
                "files": [
                    {
                        "name": name,
                        "content": base64.b64encode(b"original music").decode(),
                    }
                ],
            },
            configuration.destination,
            inventory.folder_names,
            inventory.next_number,
            configuration=configuration,
            log=lambda _: None,
        ).target_folders[name]

    def test_unknown_number_is_temporary_even_with_other_local_numbers(self):
        (self.linux / "012 - D - old").mkdir()
        path = self.sync(self.replica)
        self.assertEqual(path.name, "TMP - M - bajka")
        self.assertEqual(path, self.sync(self.replica))
        self.assertEqual(len(list(self.shared.rglob("requests/*.json"))), 2)

    def test_end_to_end_assignment_preserves_edits_and_scans(self):
        (self.mac / "099 - XML - old").mkdir()
        temporary = self.sync(self.replica)
        (temporary / "bajka.krn").write_text("edited on Linux")
        scans = temporary / "skany"
        scans.mkdir()
        (scans / "scan.pdf").write_bytes(b"scan bytes")
        self.refresh(self.master)
        self.refresh(self.replica)
        final = self.linux / "100 - M - bajka"
        self.assertFalse(temporary.exists())
        self.assertEqual((final / "bajka.krn").read_text(), "edited on Linux")
        self.assertEqual((final / "skany/scan.pdf").read_bytes(), b"scan bytes")
        self.assertEqual(self.sync(self.master).name, final.name)

    def test_numbering_is_common_and_workflows_remain_distinct(self):
        paths = [
            self.sync(self.master, workflow=workflow)
            for workflow in ("KRN-diplomatic", "KRN-modern", "XML")
        ]
        self.assertEqual(
            [p.name for p in paths],
            ["001 - D - bajka", "002 - M - bajka", "003 - XML - bajka"],
        )

    def test_existing_mac_folder_is_reused_on_linux(self):
        (self.mac / "051 - M - bajka").mkdir()
        self.refresh(self.master)
        self.assertEqual(self.sync(self.replica).name, "051 - M - bajka")
        self.assertFalse(list(self.linux.glob("TMP*")))

    def test_mac_number_replaces_existing_linux_number_without_losing_files(self):
        (self.mac / "111 - XML - bajka").mkdir()
        old = self.linux / "003 - XML - bajka"
        old.mkdir()
        (old / "bajka.musicxml").write_text("edycja z Linuksa")

        self.refresh(self.master)
        self.refresh(self.replica)

        new = self.linux / "111 - XML - bajka"
        self.assertFalse(old.exists())
        self.assertEqual(
            (new / "bajka.musicxml").read_text(),
            "edycja z Linuksa",
        )

    def test_requests_reserve_numbers_before_mac_download(self):
        self.sync(self.replica)
        self.refresh(self.master)
        self.assertEqual(self.sync(self.master, "another").name, "002 - M - another")
        self.assertEqual(self.sync(self.master).name, "001 - M - bajka")

    def test_cached_assignments_work_offline_new_names_remain_temporary(self):
        self.sync(self.master)
        self.refresh(self.replica)
        self.shared.rename(self.root / "offline")
        self.assertEqual(self.sync(self.replica).name, "001 - M - bajka")
        self.assertEqual(self.sync(self.replica, "new").name, "TMP - M - new")
        self.shared.mkdir()
        self.refresh(self.replica)
        self.assertTrue(list(self.shared.rglob("requests/*.json")))

    def test_second_master_is_rejected_even_after_reading_catalog(self):
        self.refresh(self.master)
        self.refresh(self.replica)
        with self.assertRaises(ValueError):
            self.refresh(replace(self.replica, folder_index_role="master"))

    def test_colliding_local_numbers_block_without_changes(self):
        (self.mac / "001 - D - one").mkdir()
        (self.mac / "001 - M - two").mkdir()
        with self.assertRaises(ValueError):
            self.refresh(self.master)
        self.assertFalse(list(self.shared.rglob("catalog.json")))

    def test_conflicting_linux_number_does_not_overwrite(self):
        self.sync(self.master)
        (self.linux / "001 - D - other").mkdir()
        with self.assertRaises(ValueError):
            self.sync(self.replica)
        self.assertTrue((self.linux / "001 - D - other").is_dir())

    def test_mac_folders_override_stale_numbers_and_archive_sent_linux_copy(self):
        self.refresh(self.master)
        shared_catalog = next(self.shared.rglob("catalog.json"))
        local_catalog = next(self.mac.glob(".nifc-folder-index/*/catalog.json"))
        stale = json.loads(shared_catalog.read_text(encoding="utf-8"))
        stale["entries"] = {
            "XML - sent": "111 - XML - sent",
            "XML - linux-only": "105 - XML - linux-only",
        }
        for path in (shared_catalog, local_catalog):
            path.write_text(json.dumps(stale), encoding="utf-8")

        (self.mac / "WYSŁANE").mkdir()
        (self.mac / "WYSŁANE" / "105 - XML - sent").mkdir()
        (self.mac / "112 - XML - active").mkdir()
        sent_linux = self.linux / "111 - XML - sent"
        sent_linux.mkdir()
        (sent_linux / "edited.musicxml").write_text("zachowaj", encoding="utf-8")
        (self.linux / "105 - XML - linux-only").mkdir()

        self.refresh(self.master)
        updated = json.loads(shared_catalog.read_text(encoding="utf-8"))
        self.assertEqual(updated["entries"]["XML - sent"], "105 - XML - sent")
        self.assertEqual(updated["entries"]["XML - active"], "112 - XML - active")
        self.assertEqual(
            updated["entries"]["XML - linux-only"], "113 - XML - linux-only"
        )
        self.assertIn("XML - sent", updated["sent"])
        self.assertTrue((self.mac / "WYSŁANE" / "105 - XML - sent").is_dir())

        self.refresh(self.replica)
        self.assertFalse(sent_linux.exists())
        self.assertTrue((self.linux / "113 - XML - linux-only").is_dir())
        archives = list(self.linux.glob(".nifc-folder-index/*/sent/111 - XML - sent"))
        self.assertEqual(len(archives), 1)
        self.assertEqual(
            (archives[0] / "edited.musicxml").read_text(encoding="utf-8"),
            "zachowaj",
        )

    def test_rename_does_not_replace_file(self):
        temporary = self.sync(self.replica)
        self.refresh(self.master)
        occupied = self.linux / "001 - M - bajka"
        occupied.write_text("keep me")
        with self.assertRaises(FileExistsError):
            self.refresh(self.replica)
        self.assertEqual(occupied.read_text(), "keep me")
        self.assertTrue(temporary.is_dir())

    def test_malformed_or_unsafe_catalog_stops_download(self):
        self.refresh(self.master)
        catalog = next(self.shared.rglob("catalog.json"))
        data = json.loads(catalog.read_text())
        data["entries"] = {"M - ../../escape": "001 - M - ../../escape"}
        catalog.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            self.sync(self.replica)
        self.assertFalse(list(self.linux.glob("TMP*")))

    def test_configuration_roundtrip_and_disabled_default(self):
        settings = QSettings(
            str(self.root / "settings.ini"), QSettings.Format.IniFormat
        )
        store = ConfigurationStore(settings=settings)
        self.assertEqual(store.load().folder_index_role, "")
        store.save(self.replica)
        self.assertEqual(store.load(), self.replica)

    def test_numbers_above_999_and_temporary_names(self):
        (self.mac / "1000 - D - old").mkdir()
        (self.mac / "TMP - M - piece-999 - test").mkdir()
        self.assertEqual(build_storage_inventory(self.mac, {}).next_number, 1001)
        self.refresh(self.master)
        self.assertTrue((self.mac / "1001 - M - piece-999 - test").is_dir())

    def test_catalog_contains_no_music_or_secrets(self):
        self.sync(self.master)
        content = next(self.shared.rglob("catalog.json")).read_text()
        self.assertNotIn("original music", content)
        self.assertNotIn("andrzej", content)
        self.assertNotIn(str(self.mac), content)

    def test_lock_blocks_concurrent_operation(self):
        with (
            FolderIndex(self.master, self.mac, lambda _: None),
            self.assertRaises(OSError),
        ):
            self.refresh(self.master)

    def test_other_account_has_separate_index(self):
        self.sync(self.master)
        other = replace(self.replica, nifc_username="another-person")
        self.assertEqual(self.sync(other).name, "TMP - M - bajka")

    def test_gui_enables_replica_and_retains_configuration(self):
        from gui.main_window import MainWindow

        settings = QSettings(str(self.root / "gui.ini"), QSettings.Format.IniFormat)
        store = ConfigurationStore(settings=settings)
        store.save(replace(self.replica, folder_index_role=""))
        window = SimpleNamespace(
            _is_busy=lambda: False,
            configuration_store=store,
            destination_path=self.linux,
            log_view=Mock(),
        )
        with (
            patch(
                "gui.main_window.QInputDialog.getItem",
                return_value=("Linux — numery z Maca, nowe projekty tymczasowe", True),
            ),
            patch(
                "gui.main_window.QFileDialog.getExistingDirectory",
                return_value=str(self.shared),
            ),
            patch("gui.main_window.QMessageBox.warning") as warning,
        ):
            MainWindow._configure_folder_index(window)
        warning.assert_not_called()
        self.assertEqual(store.load(), self.replica)

    def test_gui_failure_does_not_save_new_role(self):
        from gui.main_window import MainWindow

        self.refresh(self.master)
        settings = QSettings(str(self.root / "gui.ini"), QSettings.Format.IniFormat)
        store = ConfigurationStore(settings=settings)
        store.save(replace(self.replica, folder_index_role=""))
        window = SimpleNamespace(
            _is_busy=lambda: False,
            configuration_store=store,
            destination_path=self.linux,
            log_view=Mock(),
        )
        with (
            patch(
                "gui.main_window.QInputDialog.getItem",
                return_value=("Mac — główny katalog i przydzielanie numerów", True),
            ),
            patch(
                "gui.main_window.QFileDialog.getExistingDirectory",
                return_value=str(self.shared),
            ),
            patch("gui.main_window.QMessageBox.warning") as warning,
        ):
            MainWindow._configure_folder_index(window)
        warning.assert_called_once()
        self.assertEqual(store.load().folder_index_role, "")


if __name__ == "__main__":
    unittest.main()
