from pathlib import Path
import subprocess
from threading import Event

import requests
from PySide6.QtCore import QObject, Signal, Slot

from core.catalog import (
    build_scan_indexes,
    get_available_workflows,
)
from core.client import NifcClient, load_credentials
from core.cleanup import cleanup_scan_staging_folders
from core.filesystem import format_file_size
from core.inventory import build_storage_inventory
from core.scan_sync import download_scan_plans, plan_scans
from core.sync import sync_transcriptions


class CatalogLoadingCancelled(Exception):
    pass


class CatalogLoader(QObject):
    log = Signal(str)
    loaded = Signal(object, str)
    failed = Signal(str)
    cancelled = Signal()
    finished = Signal()

    def __init__(self):
        super().__init__()
        self.cancel_event = Event()

    def cancel(self):
        self.cancel_event.set()

    def _check_cancelled(self):
        if self.cancel_event.is_set():
            raise CatalogLoadingCancelled

    @Slot()
    def run(self):
        try:
            self.log.emit("Łączenie z NIFC…")
            self._check_cancelled()

            credentials = load_credentials(
                Path.home() / ".nifccredentials"
            )
            client = NifcClient()

            login_response = client.login(
                credentials["login"],
                credentials["password"],
            )
            self._check_cancelled()

            if not login_response.ok:
                raise RuntimeError(
                    "Błąd logowania do NIFC "
                    f"(HTTP {login_response.status_code})."
                )

            user = login_response.json()
            user_name = user.get("name", credentials["login"])

            self.log.emit("Pobieranie danych…")
            self._check_cancelled()
            files_response = client.get_files()
            self._check_cancelled()

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
                    "NIFC nie zwrócił dostępnych rodzajów "
                    "transkrypcji."
                )

            self._check_cancelled()
            self.loaded.emit(workflows, user_name)
            self.log.emit("Pobrano dane z NIFC.")

        except CatalogLoadingCancelled:
            self.cancelled.emit()
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
    progress = Signal(int)
    completed = Signal(object, object)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        selected_workflow,
        available_workflows,
        destination,
    ):
        super().__init__()
        self.selected_workflow = selected_workflow
        self.available_workflows = available_workflows
        self.destination = Path(destination)

    @Slot()
    def run(self):
        try:
            self.progress.emit(5)

            self.log.emit("Sprawdzanie katalogu docelowego…")
            self._check_destination_access()

            if not self.destination.is_dir():
                raise RuntimeError(
                    "Katalog docelowy nie jest dostępny: "
                    f"{self.destination}"
                )

            self.log.emit(
                f"Katalog docelowy: {self.destination}"
            )

            self.log.emit("Analiza danych z NIFC…")
            self.progress.emit(10)
            scan_urls_by_group, scan_sources_by_url = (
                build_scan_indexes(self.available_workflows)
            )

            self.log.emit("Inwentaryzacja katalogu docelowego…")
            self.progress.emit(20)
            inventory = build_storage_inventory(
                self.destination,
                scan_urls_by_group,
            )
            self.progress.emit(40)

            self.log.emit("Synchronizacja transkrypcji…")
            self.progress.emit(45)
            transcription_result = sync_transcriptions(
                self.selected_workflow,
                self.destination,
                inventory.folder_names,
                inventory.next_number,
                log=self.log.emit,
            )
            self.progress.emit(65)

            self.log.emit(
                "Sprzątanie pozostałości dla wybranego rodzaju "
                "transkrypcji…"
            )
            cleanup_scan_staging_folders(
                self.destination,
                project_folders=set(
                    transcription_result.target_folders.values()
                ),
                log=self.log.emit,
            )
            self.progress.emit(70)

            self.log.emit("Kontrola skanów…")
            self.progress.emit(75)
            session = requests.Session()
            scan_plans = plan_scans(
                self.selected_workflow,
                scan_urls_by_group,
                scan_sources_by_url,
                inventory.existing_scans_by_url,
                transcription_result.target_folders,
                session,
                log=self.log.emit,
            )
            self.progress.emit(80)

            self.completed.emit(
                {
                    "created": transcription_result.created_count,
                    "downloaded": (
                        transcription_result.downloaded_count
                    ),
                    "skipped": transcription_result.skipped_count,
                    "scan_packages": 0,
                },
                scan_plans,
            )

        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self.finished.emit()

    def _check_destination_access(self):
        try:
            result = subprocess.run(
                ["ls", "-A", str(self.destination)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                timeout=12,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(
                "Katalog docelowy nie odpowiada. "
                "Mac lub udział sieciowy może być uśpiony albo "
                "niedostępny. Obudź Maca i spróbuj ponownie."
            ) from error

        if result.returncode != 0:
            detail = result.stderr.strip()
            message = "Nie można odczytać katalogu docelowego"
            if detail:
                message += f": {detail}"
            raise RuntimeError(message)



class ScanDownloadWorker(QObject):
    log = Signal(str)
    progress = Signal(int, str)
    completed = Signal(int)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, plans):
        super().__init__()
        self.plans = tuple(plans)

    @Slot()
    def run(self):
        try:
            session = requests.Session()
            result = download_scan_plans(
                session,
                self.plans,
                progress_callback=self._download_progress,
                log=self.log.emit,
            )
            self.completed.emit(result.downloaded_packages)
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self.finished.emit()

    def _download_progress(self, request, downloaded, total):
        package_index = self.plans.index(request)
        if total:
            package_fraction = min(downloaded / total, 1)
        else:
            package_fraction = 0
        overall_fraction = (
            package_index + package_fraction
        ) / len(self.plans)
        known_total = sum(
            plan.download_info.size or 0 for plan in self.plans
        )
        completed_size = sum(
            plan.download_info.size or 0
            for plan in self.plans[:package_index]
        )
        downloaded_size = completed_size + downloaded
        if known_total:
            detail = (
                f"Pobrano {format_file_size(downloaded_size)} "
                f"z {format_file_size(known_total)}"
            )
        else:
            detail = f"Pobrano {format_file_size(downloaded)}"
        self.progress.emit(
            80 + round(overall_fraction * 19),
            detail,
        )
