from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PySide6.QtCore import QSettings

StorageKind = Literal["local", "mounted"]


@dataclass(frozen=True)
class AppConfiguration:
    destination: Path | None = None
    storage_kind: StorageKind = "local"
    network_url: str = ""
    workflow: str = "KRN-diplomatic"
    naming_profile: str = "legacy-v3"
    nifc_username: str = ""
    setup_completed: bool = False


class ConfigurationStore:
    def __init__(self, settings=None):
        self.settings = settings or QSettings()

    def load(self):
        destination_value = self.settings.value(
            "sync/destination",
            "",
        )
        destination = Path(destination_value) if destination_value else None

        return AppConfiguration(
            destination=destination,
            storage_kind=self.settings.value(
                "storage/kind",
                "local",
            ),
            network_url=str(
                self.settings.value(
                    "storage/network_url",
                    "",
                )
                or ""
            ),
            workflow=self.settings.value(
                "sync/workflow",
                "KRN-diplomatic",
            ),
            naming_profile=self.settings.value(
                "naming/profile",
                "legacy-v3",
            ),
            nifc_username=str(
                self.settings.value(
                    "credentials/username",
                    "",
                )
                or ""
            ),
            setup_completed=self.settings.value(
                "setup/completed",
                False,
                type=bool,
            ),
        )

    def save(self, configuration):
        destination = (
            str(configuration.destination) if configuration.destination else ""
        )

        self.settings.setValue(
            "sync/destination",
            destination,
        )
        self.settings.setValue(
            "storage/kind",
            configuration.storage_kind,
        )
        self.settings.setValue(
            "storage/network_url",
            configuration.network_url,
        )
        self.settings.setValue(
            "sync/workflow",
            configuration.workflow,
        )
        self.settings.setValue(
            "naming/profile",
            configuration.naming_profile,
        )
        self.settings.setValue(
            "credentials/username",
            configuration.nifc_username,
        )
        self.settings.setValue(
            "setup/completed",
            configuration.setup_completed,
        )
        self.settings.sync()
