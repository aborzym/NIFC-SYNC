from pathlib import Path

import requests
from PySide6.QtCore import QObject, Signal, Slot

from core.catalog import (
    build_scan_indexes,
    get_available_workflows,
)
from core.client import NifcClient, load_credentials
from core.cleanup import cleanup_scan_staging_folders
from core.inventory import build_storage_inventory
from core.scan_sync import sync_scans
from core.sync import sync_transcriptions


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


class SyncWorker(QObject):
    log = Signal(str)
    progress = Signal(int, object)
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        selected_workflow,
        available_workflows,
        destination,
        download_scans,
    ):
        super().__init__()
        self.selected_workflow = selected_workflow
        self.available_workflows = available_workflows
        self.destination = Path(destination)
        self.download_scans = download_scans

    @Slot()
    def run(self):
        try:
            if not self.destination.is_dir():
                raise RuntimeError(
                    "Katalog docelowy nie jest dostępny: "
                    f"{self.destination}"
                )

            self.log.emit(
                f"Katalog docelowy: {self.destination}"
            )

            cleanup_scan_staging_folders(
                self.destination,
                log=self.log.emit,
            )

            scan_urls_by_group, scan_sources_by_url = (
                build_scan_indexes(self.available_workflows)
            )
            inventory = build_storage_inventory(
                self.destination,
                scan_urls_by_group,
            )

            transcription_result = sync_transcriptions(
                self.selected_workflow,
                self.destination,
                inventory.folder_names,
                inventory.next_number,
                log=self.log.emit,
            )

            session = requests.Session()
            scan_result = sync_scans(
                self.selected_workflow,
                scan_urls_by_group,
                scan_sources_by_url,
                inventory.existing_scans_by_url,
                transcription_result.target_folders,
                session,
                should_download=(
                    lambda request: self.download_scans
                ),
                progress_callback=self.progress.emit,
                log=self.log.emit,
            )

            self.completed.emit(
                {
                    "created": transcription_result.created_count,
                    "downloaded": (
                        transcription_result.downloaded_count
                    ),
                    "skipped": transcription_result.skipped_count,
                    "scan_packages": scan_result.downloaded_packages,
                }
            )

        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self.finished.emit()
