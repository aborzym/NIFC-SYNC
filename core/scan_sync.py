from dataclasses import dataclass
from pathlib import Path

import requests

from core.filesystem import format_file_size
from core.scans import (
    find_scan_provider,
    get_part_number,
    get_scan_group_key,
)


@dataclass(frozen=True)
class ScanDownloadRequest:
    group_key: str
    source_url: str
    destination_folder: Path
    download_info: object


@dataclass(frozen=True)
class ScanSyncResult:
    downloaded_packages: int


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
    downloaded_packages = 0
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
            source_url=source["url"],
            destination_folder=destination_folder,
            download_info=download_info,
        )

        if not should_download(request):
            log("POMIJAM POBIERANIE")
            continue

        try:
            scans_folder = provider.download_and_extract(
                session,
                download_info,
                destination_folder,
                progress_callback,
            )
        except (
            requests.RequestException,
            OSError,
            ValueError,
        ) as error:
            log("")
            log(f"NIE UDAŁO SIĘ POBRAĆ SKANÓW: {error}")
            continue

        downloaded_packages += 1

        log("")
        log(f"ZAPISANO SKANY: {scans_folder}")

    return ScanSyncResult(
        downloaded_packages=downloaded_packages,
    )
