import json
import subprocess

import requests
from PySide6.QtCore import QObject, Signal, Slot

from core.catalog import (
    build_scan_indexes,
    get_available_workflows,
)
from core.cleanup import cleanup_scan_staging_folders
from core.client import NifcClient
from core.filesystem import format_file_size
from core.inventory import build_storage_inventory
from core.network import format_smb_location
from core.scan_sync import download_scan_plans, plan_scans
from core.scans import get_scan_group_key
from core.sync import sync_transcriptions
from providers.polish_music_sources import (
    get_download_info as get_polish_music_sources_download_info,
)
from providers.polish_music_sources import (
    search_manuscripts,
)


class CatalogLoader(QObject):
    log = Signal(str)
    loaded = Signal(object, str)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, credentials):
        super().__init__()
        self.credentials = credentials

    @Slot()
    def run(self):
        try:
            self.log.emit("Łączenie z NIFC…")

            client = NifcClient()

            login_response = client.login(
                self.credentials.username,
                self.credentials.password,
            )
            if not login_response.ok:
                raise RuntimeError(
                    f"Błąd logowania do NIFC (HTTP {login_response.status_code})."
                )

            user = login_response.json()
            user_name = user.get(
                "name",
                self.credentials.username,
            )
            self.log.emit("Pobieranie danych…")
            files_response = client.get_files()

            if not files_response.ok:
                raise RuntimeError(
                    "Nie udało się pobrać plików z NIFC "
                    f"(HTTP {files_response.status_code})."
                )

            workflows = get_available_workflows(files_response.json())

            if not workflows:
                raise RuntimeError("NIFC nie zwrócił dostępnych rodzajów transkrypcji.")

            self.loaded.emit(workflows, user_name)
            self.log.emit("Pobrano dane z NIFC.")

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
        configuration,
    ):
        super().__init__()
        self.selected_workflow = selected_workflow
        self.available_workflows = available_workflows
        self.configuration = configuration
        self.destination = configuration.destination

        if configuration.storage_kind == "mounted" and configuration.network_url:
            self.destination_display = format_smb_location(
                configuration.network_url,
                destination=self.destination,
            )
        else:
            self.destination_display = str(self.destination)

    @Slot()
    def run(self):
        try:
            self.progress.emit(5)

            self.log.emit("Sprawdzanie katalogu docelowego…")
            self._check_destination_access()

            if not self.destination.is_dir():
                raise RuntimeError(
                    f"Katalog docelowy nie jest dostępny: {self.destination_display}"
                )

            self.log.emit(f"Katalog docelowy: {self.destination_display}")
            self.log.emit("Analiza danych z NIFC…")
            self.progress.emit(10)
            scan_urls_by_group, scan_sources_by_url = build_scan_indexes(
                self.available_workflows
            )

            selected_group_keys = {
                get_scan_group_key(api_file["name"])
                for api_file in self.selected_workflow["files"]
            }
            inventory_scan_urls_by_group = {
                group_key: scan_urls_by_group.get(
                    group_key,
                    set(),
                )
                for group_key in selected_group_keys
            }

            self.log.emit("Inwentaryzacja katalogu docelowego…")
            self.progress.emit(20)
            inventory = build_storage_inventory(
                self.destination,
                inventory_scan_urls_by_group,
            )
            self.progress.emit(40)

            self.log.emit("Synchronizacja transkrypcji…")
            self.progress.emit(45)
            transcription_result = sync_transcriptions(
                self.selected_workflow,
                self.destination,
                inventory.folder_names,
                inventory.next_number,
                configuration=self.configuration,
                log=self.log.emit,
            )
            self.progress.emit(65)

            self.log.emit("Sprzątanie pozostałości dla wybranego rodzaju transkrypcji…")
            cleanup_scan_staging_folders(
                self.destination,
                project_folders=set(transcription_result.target_folders.values()),
                log=self.log.emit,
            )
            self.progress.emit(70)

            self.log.emit("Kontrola skanów…")
            self.progress.emit(75)
            session = requests.Session()
            scan_issues = []

            scan_plans = plan_scans(
                self.selected_workflow,
                scan_urls_by_group,
                scan_sources_by_url,
                inventory.existing_scans_by_url,
                transcription_result.target_folders,
                session,
                configuration=self.configuration,
                scan_issues=scan_issues,
                log=self.log.emit,
            )
            self.progress.emit(80)

            self.completed.emit(
                {
                    "created": transcription_result.created_count,
                    "downloaded": transcription_result.downloaded_count,
                    "skipped": transcription_result.skipped_count,
                    "scan_packages": 0,
                    "scan_issues": tuple(scan_issues),
                },
                scan_plans,
            )
        except Exception as error:  # noqa: BLE001
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
                "Dysk lub udział sieciowy może być "
                "niedostępny. Sprawdź połączenie "
                "i spróbuj ponownie."
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
        except Exception as error:  # noqa: BLE001
            self.failed.emit(str(error))
        finally:
            self.finished.emit()

    def _download_progress(self, request, downloaded, total):
        package_index = self.plans.index(request)
        if total:
            package_fraction = min(downloaded / total, 1)
        else:
            package_fraction = 0
        overall_fraction = (package_index + package_fraction) / len(self.plans)
        known_total = sum(plan.download_info.size or 0 for plan in self.plans)
        completed_size = sum(
            plan.download_info.size or 0 for plan in self.plans[:package_index]
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


class PolishMusicSourcesLookupWorker(QObject):
    log = Signal(str)
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, scan_issues):
        super().__init__()
        self.scan_issues = tuple(scan_issues)

    @Slot()
    def run(self):
        try:
            session = requests.Session()
            lookup_results = []

            for issue in self.scan_issues:
                metadata = issue.source_metadata

                if metadata is None:
                    lookup_results.append(
                        (
                            issue,
                            (),
                        )
                    )
                    continue

                self.log.emit(
                    "Wyszukiwanie w Polish Music Sources: "
                    f"{metadata.siglum} "
                    f"{metadata.shelfmark}"
                )

                try:
                    search_results = search_manuscripts(
                        session,
                        metadata,
                    )
                except (
                    requests.RequestException,
                    TypeError,
                    ValueError,
                ) as error:
                    self.log.emit(
                        f"Nie udało się wyszukać źródła {issue.group_key}: {error}"
                    )
                    search_results = ()

                resolved_results = []

                for search_result in search_results:
                    try:
                        download_info = get_polish_music_sources_download_info(
                            session,
                            search_result.url,
                        )
                    except (
                        requests.RequestException,
                        TypeError,
                        ValueError,
                    ) as error:
                        self.log.emit(
                            "Nie udało się pobrać informacji "
                            f"o źródle {search_result.title}: "
                            f"{error}"
                        )
                        continue

                    resolved_results.append(
                        (
                            search_result,
                            download_info,
                        )
                    )

                lookup_results.append(
                    (
                        issue,
                        tuple(resolved_results),
                    )
                )

            self.completed.emit(tuple(lookup_results))

        except Exception as error:  # noqa: BLE001
            self.failed.emit(str(error))
        finally:
            self.finished.emit()


class SubmissionWorker(QObject):
    submitted = Signal()
    failed = Signal(str)
    finished = Signal()
    progress = Signal(int)
    stage = Signal(str)
    validation = Signal(str)

    def __init__(self, credentials, workflow_key, filename, file_path):
        super().__init__()
        self.credentials = credentials
        self.workflow_key = workflow_key
        self.filename = filename
        self.file_path = file_path
        self._last_percentage = -1

    def _upload_progress(self, sent, total):
        percentage = min(100, sent * 100 // total)
        if percentage != self._last_percentage:
            self._last_percentage = percentage
            self.progress.emit(percentage)

        if sent >= total:
            self.stage.emit("Oczekiwanie na walidację NIFC…")

    @Slot()
    def run(self):
        try:
            client = NifcClient()
            login_response = client.login(
                self.credentials.username,
                self.credentials.password,
            )
            if not login_response.ok:
                raise RuntimeError(
                    f"Błąd logowania do NIFC (HTTP {login_response.status_code})."
                )

            self.stage.emit("Przygotowanie pliku…")
            content = self.file_path.read_bytes()
            self.stage.emit("Wysyłanie pliku…")
            self.progress.emit(0)
            response = client.submit_file(
                self.workflow_key,
                self.filename,
                content,
                progress_callback=self._upload_progress,
            )

            if response.ok:
                message = "Plik został przyjęty przez NIFC."
                try:
                    result = json.loads(response.text)
                except ValueError:
                    result = None

                if isinstance(result, dict):
                    output = result.get("content")
                    if isinstance(output, dict) and output.get("name"):
                        message += f"\nPlik wynikowy: {output['name']}"

                self.validation.emit(message)

            if not response.ok:
                message = None
                try:
                    error = response.json()
                    if isinstance(error, dict):
                        message = error.get("message")
                        if isinstance(error.get("error"), dict):
                            message = error["error"].get("message") or message
                except ValueError:
                    pass

                raise RuntimeError(
                    message or f"NIFC odrzucił plik (HTTP {response.status_code})."
                )

            self.submitted.emit()

        except (OSError, requests.RequestException, RuntimeError) as error:
            self.failed.emit(str(error))
        finally:
            self.finished.emit()
