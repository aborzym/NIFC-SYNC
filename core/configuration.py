from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import uuid4

from PySide6.QtCore import QSettings

from core.organization_profiles import (
    normalize_organization_profile_id,
)

StorageKind = Literal["local", "mounted"]


@dataclass(frozen=True)
class AccountInfo:
    account_id: str
    name: str


@dataclass(frozen=True)
class OrganizationPath:
    key: str
    path: Path


@dataclass(frozen=True)
class AppConfiguration:
    destination: Path | None = None
    storage_kind: StorageKind = "local"
    network_url: str = ""
    workflow: str = "KRN-diplomatic"
    naming_profile: str = "andrzej-borzym"
    organization_paths: tuple[OrganizationPath, ...] = ()
    nifc_username: str = ""

    setup_completed: bool = False

    def organization_path(self, key):
        for organization_path in self.organization_paths:
            if organization_path.key == key:
                return organization_path.path

        return None


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

    def create_account(
        self,
        name,
        configuration=None,
    ):
        name = name.strip()

        if not name:
            raise ValueError("Nazwa konta nie może być pusta.")

        account_id = self._create_account_record(name)
        self._save_account_configuration(
            account_id,
            configuration or AppConfiguration(),
        )
        self.settings.sync()

        return AccountInfo(
            account_id=account_id,
            name=name,
        )

    def delete_account(self, account_id):
        account_ids = list(self._account_ids())

        if account_id not in account_ids:
            raise ValueError("Nie znaleziono konta.")

        if len(account_ids) == 1:
            raise ValueError("Nie można usunąć jedynego konta.")

        self.settings.remove(f"accounts/{account_id}")
        account_ids.remove(account_id)
        self.settings.setValue(
            "accounts/order",
            account_ids,
        )

        if self.active_account_id() == account_id:
            self.settings.setValue(
                "accounts/active_id",
                account_ids[0],
            )

        self.settings.sync()

        return self.active_account_id()

    def set_active_account(self, account_id):
        if account_id not in self._account_ids():
            raise ValueError("Nie znaleziono konta.")

        self.settings.setValue(
            "accounts/active_id",
            account_id,
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

    def _configuration_key(self, account_id, key):
        if account_id is None:
            return key

        return f"accounts/{account_id}/{key}"

    def _organization_path_keys(self, account_id):
        value = self.settings.value(
            self._configuration_key(
                account_id,
                "organization/paths/keys",
            ),
            [],
        )

        if not value:
            return ()

        if isinstance(value, str):
            return (value,)

        return tuple(str(key) for key in value)

    def _load_organization_paths(self, account_id):
        paths = []

        for key in self._organization_path_keys(account_id):
            value = self.settings.value(
                self._configuration_key(
                    account_id,
                    f"organization/paths/values/{key}",
                ),
                "",
            )

            if value:
                paths.append(
                    OrganizationPath(
                        key=key,
                        path=Path(str(value)),
                    )
                )

        return tuple(paths)

    def _save_organization_paths(
        self,
        account_id,
        organization_paths,
    ):
        paths_group = self._configuration_key(
            account_id,
            "organization/paths",
        )
        self.settings.remove(paths_group)

        keys = [organization_path.key for organization_path in organization_paths]
        self.settings.setValue(
            self._configuration_key(
                account_id,
                "organization/paths/keys",
            ),
            keys,
        )

        for organization_path in organization_paths:
            self.settings.setValue(
                self._configuration_key(
                    account_id,
                    (f"organization/paths/values/{organization_path.key}"),
                ),
                str(organization_path.path),
            )

    def _has_account_configuration(self, account_id):
        return any(
            self.settings.contains(
                self._configuration_key(
                    account_id,
                    key,
                )
            )
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

    def _load_configuration(self, account_id):
        destination_value = self.settings.value(
            self._configuration_key(
                account_id,
                "sync/destination",
            ),
            "",
        )
        destination = Path(destination_value) if destination_value else None

        return AppConfiguration(
            destination=destination,
            storage_kind=self.settings.value(
                self._configuration_key(
                    account_id,
                    "storage/kind",
                ),
                "local",
            ),
            network_url=str(
                self.settings.value(
                    self._configuration_key(
                        account_id,
                        "storage/network_url",
                    ),
                    "",
                )
                or ""
            ),
            workflow=self.settings.value(
                self._configuration_key(
                    account_id,
                    "sync/workflow",
                ),
                "KRN-diplomatic",
            ),
            naming_profile=normalize_organization_profile_id(
                str(
                    self.settings.value(
                        self._configuration_key(
                            account_id,
                            "naming/profile",
                        ),
                        "andrzej-borzym",
                    )
                    or "andrzej-borzym"
                )
            ),
            organization_paths=(self._load_organization_paths(account_id)),
            nifc_username=str(
                self.settings.value(
                    self._configuration_key(
                        account_id,
                        "credentials/username",
                    ),
                    "",
                )
                or ""
            ),
            setup_completed=self.settings.value(
                self._configuration_key(
                    account_id,
                    "setup/completed",
                ),
                False,
                type=bool,
            ),
        )

    def _save_account_configuration(
        self,
        account_id,
        configuration,
    ):
        destination = (
            str(configuration.destination) if configuration.destination else ""
        )

        values = {
            "sync/destination": destination,
            "storage/kind": configuration.storage_kind,
            "storage/network_url": configuration.network_url,
            "sync/workflow": configuration.workflow,
            "naming/profile": configuration.naming_profile,
            "credentials/username": configuration.nifc_username,
            "setup/completed": configuration.setup_completed,
        }

        for key, value in values.items():
            self.settings.setValue(
                self._configuration_key(
                    account_id,
                    key,
                ),
                value,
            )

        self._save_organization_paths(
            account_id,
            configuration.organization_paths,
        )

    def load(self):
        account_id = self.active_account_id()

        if account_id:
            if (
                not self._has_account_configuration(account_id)
                and self._has_existing_configuration()
            ):
                configuration = self._load_configuration(None)
                self._save_account_configuration(
                    account_id,
                    configuration,
                )
                self.settings.sync()
                return configuration

            return self._load_configuration(account_id)

        if not self._has_existing_configuration():
            return AppConfiguration()

        configuration = self._load_configuration(None)
        account_id = self._create_account_record(
            configuration.nifc_username or "Dotychczasowe konto"
        )
        self._save_account_configuration(
            account_id,
            configuration,
        )
        self.settings.sync()

        return configuration

    def save(self, configuration):
        account_id = self.active_account_id()

        if not account_id:
            account_id = self._create_account_record(
                configuration.nifc_username or "Konto 1"
            )

        self._save_account_configuration(
            account_id,
            configuration,
        )
        self.settings.sync()
