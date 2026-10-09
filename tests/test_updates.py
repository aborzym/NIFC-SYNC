import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.updates import (
    expected_asset_name,
    is_newer_version,
    release_history_notes,
    update_from_release,
)
from gui.updater import UpdateManager


class UpdatesTest(unittest.TestCase):
    def make_release(self, asset_name):
        return {
            "tag_name": "v4.1.0",
            "body": "Wysyłanie plików",
            "html_url": "https://github.com/aborzym/NIFC-SYNC/releases/tag/v4.1.0",
            "assets": [
                {
                    "name": asset_name,
                    "state": "uploaded",
                    "browser_download_url": (
                        "https://github.com/aborzym/NIFC-SYNC/releases/download/"
                        f"v4.1.0/{asset_name}"
                    ),
                    "size": 52000000,
                    "digest": "sha256:" + "a" * 64,
                }
            ],
        }

    def test_compares_versions(self):
        self.assertTrue(is_newer_version("4.1.0", "4.0.1"))
        self.assertFalse(is_newer_version("4.1.0", "4.1.0"))
        self.assertFalse(is_newer_version("4.0.1", "4.1.0"))

    def test_selects_platform_installer(self):
        cases = (
            ("linux", "x86_64", "nifc-sync_4.1.0_amd64.deb"),
            ("darwin", "arm64", "NIFC-SYNC-4.1.0-arm64.dmg"),
        )
        for system, machine, filename in cases:
            with self.subTest(system=system):
                self.assertEqual(
                    expected_asset_name("4.1.0", platform_name=system, machine=machine),
                    filename,
                )
                update = update_from_release(
                    self.make_release(filename),
                    current_version="4.0.1",
                    platform_name=system,
                    machine=machine,
                )
                self.assertIsNotNone(update)
                self.assertEqual(update.asset_sha256, "a" * 64)

    def test_rejects_installer_without_checksum(self):
        release = self.make_release("nifc-sync_4.1.0_amd64.deb")
        release["assets"][0]["digest"] = None
        self.assertIsNone(
            update_from_release(
                release,
                current_version="4.0.1",
                platform_name="linux",
                machine="x86_64",
            )
        )

    def test_ignores_draft_and_skipped_version(self):
        release = self.make_release("nifc-sync_4.1.0_amd64.deb")
        options = {
            "current_version": "4.0.1",
            "platform_name": "linux",
            "machine": "x86_64",
        }
        release["draft"] = True
        self.assertIsNone(update_from_release(release, **options))
        release["draft"] = False
        self.assertIsNone(
            update_from_release(release, skipped_version="4.1.0", **options)
        )

    def test_history_excludes_installed_and_future_versions(self):
        notes = release_history_notes(
            [
                {"tag_name": "v4.0.1", "body": "Stare"},
                {"tag_name": "v4.1.0", "body": "Wysyłanie"},
                {"tag_name": "v4.2.0", "body": "Przyszłe"},
            ],
            current_version="4.0.1",
            latest_version="4.1.0",
        )
        self.assertEqual(notes, "# NIFC-SYNC 4.1.0\n\nWysyłanie")

    def test_finds_running_macos_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "NIFC-SYNC.app"
            executable = application / "Contents/MacOS/NIFC-SYNC"
            executable.parent.mkdir(parents=True)
            executable.touch()
            with patch("gui.updater.sys.executable", str(executable)):
                self.assertEqual(
                    UpdateManager._macos_application_path(),
                    application.resolve(),
                )
