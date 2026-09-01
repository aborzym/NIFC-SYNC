from dataclasses import dataclass, field, replace
from pathlib import Path

from core.configuration import (
    AppConfiguration,
    ConfigurationStore,
    StorageKind,
)
from core.credentials import (
    CredentialStore,
    NifcCredentials,
)
from core.storage import validate_storage


class SetupError(RuntimeError):
    pass


@dataclass(frozen=True)
class SetupRequest:
    destination: Path | None
    storage_kind: StorageKind
    username: str
    password: str = field(repr=False)


def complete_setup(
    request: SetupRequest,
    configuration_store: ConfigurationStore,
    credential_store: CredentialStore,
) -> AppConfiguration:
    username = request.username.strip()

    if not username:
        raise SetupError("Podaj login NIFC.")

    if not request.password:
        raise SetupError("Podaj hasło NIFC.")

    if request.destination is None:
        raise SetupError("Wybierz katalog docelowy.")

    validation = validate_storage(
        request.destination,
        request.storage_kind,
    )

    if not validation.is_valid:
        raise SetupError(validation.message)

    credentials = NifcCredentials(
        username=username,
        password=request.password,
    )
    credential_store.save(credentials)

    configuration = replace(
        configuration_store.load(),
        destination=request.destination.expanduser().resolve(),
        storage_kind=request.storage_kind,
        nifc_username=username,
        setup_completed=True,
    )
    configuration_store.save(configuration)

    return configuration
