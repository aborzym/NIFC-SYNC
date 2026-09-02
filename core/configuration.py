from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import uuid4

from PySide6.QtCore import QSettings

StorageKind = Literal["local", "mounted"]


@dataclass(frozen=True)
class AccountInfo:
    account_id: str
    name: str


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
    def __init__(
        self,
        settings=None,
        id_factory: Callable[[], str] | None = None,
    ):
        self.settings = settings or QSettings()
        self.id_factory = id_factory or (lambda: uuid4().hex)

    def active_account_id(self):
        return str(
            self.settings.value(
                "accounts/active_id",
                "",
            )
            or ""
        )

    def list_accounts(self):
        accounts = []

        for account_id in self._account_ids():
            name = str(
                self.settings.value(
                    f"accounts/{account_id}/name",
                    "",
                )
                or ""
            )
            accounts.append(
                AccountInfo(
                    account_id=account_id,
                    name=name,
                )
            )

        return tuple(accounts)

    def rename_account(self, account_id, name):
        name = name.strip()

        if not name:
            raise ValueError("Nazwa konta nie może być pusta.")

        if account_id not in self._account_ids():
            raise ValueError("Nie znaleziono konta.")

        self.settings.setValue(
            f"accounts/{account_id}/name",
            name,
        )
        self.settings.sync()

    def _account_ids(self):
        value = self.settings.value(
            "accounts/order",
            [],
        )

        if not value:
            return ()

        if isinstance(value, str):
            return (value,)

        return tuple(str(account_id) for account_id in value)

    def _create_account_record(self, name):
        account_id = self.id_factory()
        account_ids = [
            *self._account_ids(),
            account_id,
        ]

        self.settings.setValue(
            "accounts/order",
            account_ids,
        )
        self.settings.setValue(
            "accounts/active_id",
            account_id,
        )
        self.settings.setValue(
            f"accounts/{account_id}/name",
            name,
        )

        return account_id

    def _has_existing_configuration(self):
        return any(
            self.settings.contains(key)
            for key in (
                "sync/destination",
                "storage/kind",
                "storage/network_url",
                "sync/workflow",
                "naming/profile",
                "credentials/username",
                "setup/completed",
            )
        )

    def load(self):
        destination_value = self.settings.value(
            "sync/destination",
            "",
        )
        destination = Path(destination_value) if destination_value else None

        configuration = AppConfiguration(
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
        if not self.active_account_id() and self._has_existing_configuration():
            self._create_account_record(
                configuration.nifc_username or "Dotychczasowe konto"
            )
            self.settings.sync()

        return configuration

    def save(self, configuration):
        if not self.active_account_id():
            self._create_account_record(configuration.nifc_username or "Konto 1")
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
