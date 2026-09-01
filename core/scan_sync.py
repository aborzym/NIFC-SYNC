from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import shutil

import requests

from core.filesystem import format_file_size
from core.scans import (
    find_scan_provider,
    get_part_number,
    get_scan_group_key,
)
from core.scan_manifest import validate_scan_manifest, write_scan_manifest


@dataclass(frozen=True)
class ScanDownloadRequest:
    group_key: str
    transcription_name: str
    source_url: str
    destination_folder: Path
    download_info: object
    provider: object
    is_incomplete: bool


@dataclass(frozen=True)
class ScanSyncResult:
    downloaded_packages: int


def plan_scans(
    selected_workflow,
    scan_urls_by_group,
    scan_sources_by_url,
    existing_scans_by_url,
    target_folders,
    session,
    log=print,
):
    plans = []
    selected_scan_groups = {}

    log("\nKontrola skanów:")

    for api_file in selected_workflow["files"]:
        group_key = get_scan_group_key(api_file["name"])

        selected_scan_groups.setdefault(
            group_key,
            [],
        ).append(api_file)

    for group_key, group_files in selected_scan_groups.items():
        normalized_urls = scan_urls_by_group.get(
            group_key,
            set(),
        )

        log(f"\nGRUPA: {group_key}")

        if not normalized_urls:
            log("BRAK URL-scan — pomijam")
            continue

        if len(normalized_urls) > 1:
            log("NIEJEDNOZNACZNY URL-scan:")

            for normalized_url in sorted(normalized_urls):
                log(f"  {normalized_url}")

            log("POMIJAM — wymaga ręcznego sprawdzenia")
            continue

        normalized_url = next(iter(normalized_urls))
        source = scan_sources_by_url[normalized_url]
        existing_locations = existing_scans_by_url.get(
            normalized_url,
            {},
        )

        if existing_locations:
            log("SKANY JUŻ ISTNIEJĄ:")

            for folder, score_files in sorted(
                existing_locations.items(),
                key=lambda item: item[0].name,
            ):
                log(f"  FOLDER: {folder.name}")
                log(f"  LICZBA PLIKÓW: {len(score_files)}")

            continue

        primary_file = min(
            group_files,
            key=lambda api_file: (
                get_part_number(api_file["name"]),
                api_file["name"],
            ),
        )
        destination_folder = target_folders[primary_file["name"]]
        is_incomplete = (
            validate_scan_manifest(destination_folder / "skany")
            is False
        )

        if is_incomplete:
            log("SKANY SĄ NIEKOMPLETNE — WYMAGAJĄ NAPRAWY")
        else:
            log("BRAK SKANÓW")
        log(f"FOLDER DOCELOWY: {destination_folder.name}")
        log(f"URL-scan: {source['url']}")

        provider = find_scan_provider(source["url"])

        if provider is None:
            log(
                "BRAK OBSŁUGI AUTOMATYCZNEGO POBIERANIA "
                "DLA TEJ BIBLIOTEKI"
            )
            continue

        try:
            download_info = provider.get_download_info(
                session,
                source["url"],
            )
        except requests.RequestException as error:
            log(f"NIE UDAŁO SIĘ POBRAĆ INFORMACJI O PAKIECIE: {error}")
            continue
        except ValueError as error:
            log(f"NIEPRAWIDŁOWY URL-scan: {error}")
            continue

        log(f"PAKIET: {download_info.filename}")
        log(f"FORMAT: {download_info.content_type or 'nieznany'}")
        log(f"ROZMIAR: {format_file_size(download_info.size)}")

        request = ScanDownloadRequest(
            group_key=group_key,
            transcription_name=primary_file["name"],
            source_url=source["url"],
            destination_folder=destination_folder,
            download_info=download_info,
            provider=provider,
            is_incomplete=is_incomplete,
        )

        plans.append(request)

    return tuple(plans)


def download_scan_plans(
    session,
    plans,
    progress_callback=None,
    log=print,
):
    downloaded_packages = 0

    for request in plans:
        log(f"\nPOBIERANIE: {request.download_info.filename}")
        scans_folder = request.destination_folder / "skany"
        backup_folder = None

        if (
            scans_folder.exists()
            and validate_scan_manifest(scans_folder) is False
        ):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_folder = request.destination_folder / (
                f".skany_incomplete_{timestamp}"
            )
            scans_folder.rename(backup_folder)
            log("WYKRYTO NIEKOMPLETNY PAKIET — POBIERAM PONOWNIE")

        if progress_callback:
            provider_progress = (
                lambda downloaded, total, request=request: (
                    progress_callback(
                        request,
                        downloaded,
                        total,
                    )
                )
            )
        else:
            provider_progress = None

        try:
            scans_folder = request.provider.download_and_extract(
                session,
                request.download_info,
                request.destination_folder,
                provider_progress,
            )
            write_scan_manifest(
                scans_folder,
                request.source_url,
                request.download_info.filename,
            )
        except (
            requests.RequestException,
            OSError,
            ValueError,
        ) as error:
            if backup_folder is not None and not scans_folder.exists():
                backup_folder.rename(scans_folder)
            log("")
            log(f"NIE UDAŁO SIĘ POBRAĆ SKANÓW: {error}")
            continue

        if backup_folder is not None:
            shutil.rmtree(backup_folder, ignore_errors=True)

        downloaded_packages += 1

        log("")
        log(f"ZAPISANO SKANY: {scans_folder}")

    return ScanSyncResult(
        downloaded_packages=downloaded_packages,
    )


def sync_scans(
    selected_workflow,
    scan_urls_by_group,
    scan_sources_by_url,
    existing_scans_by_url,
    target_folders,
    session,
    should_download,
    progress_callback=None,
    log=print,
):
    plans = plan_scans(
        selected_workflow,
        scan_urls_by_group,
        scan_sources_by_url,
        existing_scans_by_url,
        target_folders,
        session,
        log=log,
    )
    selected_plans = []

    for request in plans:
        if should_download(request):
            selected_plans.append(request)
        else:
            log("POMIJAM POBIERANIE")

    if progress_callback:
        adapted_progress = (
            lambda request, downloaded, total: progress_callback(
                downloaded,
                total,
            )
        )
    else:
        adapted_progress = None

    return download_scan_plans(
        session,
        selected_plans,
        progress_callback=adapted_progress,
        log=log,
    )
