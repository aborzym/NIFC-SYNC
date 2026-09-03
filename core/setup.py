from dataclasses import dataclass, field, replace
from pathlib import Path

import requests

from core.client import NifcClient
from core.configuration import (
    AppConfiguration,
    ConfigurationStore,
    OrganizationPath,
    StorageKind,
)
from core.credentials import (
    CredentialStore,
    NifcCredentials,
)
from core.organization_profiles import (
    get_organization_profile,
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
    account_name: str = ""
    organization_profile_id: str = "andrzej-borzym"
    organization_paths: tuple[OrganizationPath, ...] = ()
    network_url: str = ""


def verify_nifc_login(
    username,
    password,
    client=None,
):
    username = username.strip()

    if not username:
        raise SetupError("Podaj login NIFC.")

    if not password:
        raise SetupError("Podaj hasło NIFC.")

    client = client or NifcClient()

    try:
        response = client.login(username, password)
    except requests.RequestException:
        raise SetupError("Nie udało się połączyć z NIFC.") from None

    if response.status_code in (401, 403):
        raise SetupError("Nieprawidłowy login lub hasło NIFC.")

    if not response.ok:
        raise SetupError(
            f"Logowanie do NIFC nie powiodło się (HTTP {response.status_code})."
        )


def complete_setup(
    request: SetupRequest,
    configuration_store: ConfigurationStore,
    credential_store: CredentialStore,
    create_new_account=False,
) -> AppConfiguration:
    username = request.username.strip()
    account_name = request.account_name.strip() or username

    try:
        organization_profile = get_organization_profile(request.organization_profile_id)
    except ValueError:
        raise SetupError("Wybierz prawidłowy profil organizacji plików.") from None

    if not username:
        raise SetupError("Podaj login NIFC.")

    if not request.password:
        raise SetupError("Podaj hasło NIFC.")

    if request.destination is None:
        raise SetupError("Wybierz główny katalog dla tego konta.")

    excluded_account_id = (
        None if create_new_account else configuration_store.active_account_id()
    )

    try:
        configuration_store.validate_nifc_username(
            username,
            excluded_account_id=excluded_account_id,
        )
        configuration_store.validate_account_name(
            account_name,
            excluded_account_id=excluded_account_id,
        )
    except ValueError as error:
        raise SetupError(str(error)) from None

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

    base_configuration = (
        AppConfiguration() if create_new_account else configuration_store.load()
    )
    configuration = replace(
        base_configuration,
        destination=(
            request.destination.expanduser().resolve()
            if request.destination is not None
            else None
        ),
        storage_kind=request.storage_kind,
        network_url=(
            request.network_url.strip() if request.storage_kind == "mounted" else ""
        ),
        naming_profile=organization_profile.profile_id,
        organization_paths=request.organization_paths,
        nifc_username=username,
        setup_completed=True,
    )

    if create_new_account:
        configuration_store.create_account(
            account_name,
            configuration,
        )
    else:
        configuration_store.save(configuration)
        account_id = configuration_store.active_account_id()

        if account_id:
            configuration_store.rename_account(
                account_id,
                account_name,
            )

    return configuration
