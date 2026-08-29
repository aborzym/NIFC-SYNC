from pathlib import Path

import requests
from PySide6.QtCore import QObject, Signal, Slot

from core.catalog import get_available_workflows
from core.client import NifcClient, load_credentials


class CatalogLoader(QObject):
    log = Signal(str)
    loaded = Signal(object, str)
    failed = Signal(str)
    finished = Signal()

    @Slot()
    def run(self):
        try:
            self.log.emit("Łączenie z NIFC…")

            credentials = load_credentials(
                Path.home() / ".nifccredentials"
            )
            client = NifcClient()

            login_response = client.login(
                credentials["login"],
                credentials["password"],
            )

            if not login_response.ok:
                raise RuntimeError(
                    "Błąd logowania do NIFC "
                    f"(HTTP {login_response.status_code})."
                )

            user = login_response.json()
            user_name = user.get("name", credentials["login"])
            self.log.emit(f"Zalogowano jako: {user_name}")

            files_response = client.get_files()

            if not files_response.ok:
                raise RuntimeError(
                    "Nie udało się pobrać plików z NIFC "
                    f"(HTTP {files_response.status_code})."
                )

            workflows = get_available_workflows(
                files_response.json()
            )

            if not workflows:
                raise RuntimeError(
                    "NIFC nie zwrócił obsługiwanych workflowów."
                )

            self.loaded.emit(workflows, user_name)
            self.log.emit("Pobrano listę workflowów.")

        except (
            OSError,
            KeyError,
            ValueError,
            requests.RequestException,
            RuntimeError,
        ) as error:
            self.failed.emit(str(error))
        finally:
            self.finished.emit()
