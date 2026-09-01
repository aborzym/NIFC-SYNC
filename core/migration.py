from pathlib import Path

from core.credentials import (
    CredentialStore,
    NifcCredentials,
)

LEGACY_CREDENTIALS_FILENAME = ".nifccredentials"


class LegacyCredentialError(RuntimeError):
    pass


def legacy_credentials_path():
    return Path.home() / LEGACY_CREDENTIALS_FILENAME


def load_legacy_credentials(credentials_file=None):
    path = (
        Path(credentials_file)
        if credentials_file is not None
        else legacy_credentials_path()
    )

    if not path.exists():
        return None

    if not path.is_file():
        raise LegacyCredentialError("Stara ścieżka danych logowania nie jest plikiem.")

    values = {}

    try:
        with path.open(encoding="utf-8") as file:
            for raw_line in file:
                line = raw_line.strip()

                if not line or line.startswith("#"):
                    continue

                key, separator, value = line.partition("=")

                if not separator:
                    raise LegacyCredentialError(
                        "Stary plik danych logowania ma nieprawidłowy format."
                    )

                values[key.strip()] = value.strip()
    except (OSError, UnicodeError):
        raise LegacyCredentialError(
            "Nie udało się odczytać starego pliku danych logowania."
        ) from None

    username = values.get("login", "")
    password = values.get("password", "")

    if not username or not password:
        raise LegacyCredentialError(
            "Stary plik nie zawiera kompletnego loginu i hasła."
        )

    return NifcCredentials(
        username=username,
        password=password,
    )


def migrate_legacy_credentials(
    credential_store: CredentialStore,
    credentials_file=None,
):
    credentials = load_legacy_credentials(credentials_file)

    if credentials is None:
        return None

    credential_store.save(credentials)
    return credentials
