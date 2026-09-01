from dataclasses import dataclass

import keyring
from keyring.errors import KeyringError

SERVICE_NAME = "NIFC-SYNC"


class CredentialStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class NifcCredentials:
    username: str
    password: str


class CredentialStore:
    def __init__(self, backend=None):
        self.backend = backend or keyring.get_keyring()

    def save(self, credentials):
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

    def load(self, username):
        if not username:
            return None

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

        return NifcCredentials(
            username=username,
            password=password,
        )

    def delete(self, username):
        if not username:
            return

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
