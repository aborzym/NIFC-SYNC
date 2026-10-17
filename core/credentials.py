from dataclasses import dataclass, field

import keyring
from keyring.errors import KeyringError

SERVICE_NAME = "NIFC-SYNC"


class CredentialStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class NifcCredentials:
    username: str
    password: str = field(repr=False)


class CredentialStore:
    def __init__(self, backend=None):
        self.backend = backend or keyring.get_keyring()
        self._session_credentials = {}

    def save(self, credentials):
        self._session_credentials.pop(credentials.username, None)
        try:
            self.backend.set_password(
                SERVICE_NAME,
                credentials.username,
                credentials.password,
            )
        except KeyringError:
            raise CredentialStoreError(
                "Nie udało się zapisać danych logowania."
            ) from None

        self._session_credentials[credentials.username] = credentials

    def load(self, username):
        if not username:
            return None

        if username in self._session_credentials:
            return self._session_credentials[username]

        try:
            password = self.backend.get_password(
                SERVICE_NAME,
                username,
            )
        except KeyringError:
            raise CredentialStoreError(
                "Nie udało się odczytać danych logowania."
            ) from None

        if password is None:
            return None

        credentials = NifcCredentials(username=username, password=password)
        self._session_credentials[username] = credentials
        return credentials

    def delete(self, username):
        if not username:
            return

        self._session_credentials.pop(username, None)
        try:
            self.backend.delete_password(
                SERVICE_NAME,
                username,
            )
        except keyring.errors.PasswordDeleteError:
            return

        except KeyringError:
            raise CredentialStoreError(
                "Nie udało się usunąć danych logowania."
            ) from None
