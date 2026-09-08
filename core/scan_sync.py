import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import requests

from core.destinations import (
    find_legacy_scan_package_folder,
    marta_fallback_reason,
    resolve_asset_root,
    scan_package_folder_name,
)
from core.filesystem import format_file_size
from core.scan_manifest import validate_scan_manifest, write_scan_manifest
from core.scans import (
    extract_scan_source_metadata,
    find_scan_provider,
    get_part_number,
    get_scan_group_key,
)


@dataclass(frozen=True)
class ScanDownloadRequest:
    group_key: str
    transcription_name: str
    source_url: str
    destination_folder: Path
    download_info: object
    provider: object
    is_incomplete: bool
    output_folder_name: str = "skany"


@dataclass(frozen=True)
class ScanIssue:
    group_key: str
    transcription_names: tuple[str, ...]
    source_url: str
    reason: str
    source_metadata: object | None = None
    destination_folder: Path | None = None


@dataclass(frozen=True)
class ScanSyncResult:
    downloaded_packages: int
    scan_issues: tuple[ScanIssue, ...] = ()


def plan_scans(
    selected_workflow,
    scan_urls_by_group,
    scan_sources_by_url,
    existing_scans_by_url,
    target_folders,
    session,
    configuration=None,
    scan_issues=None,
    log=print,
):

    plans = []
    selected_scan_groups = {}
    uses_named_scan_folders = (
        configuration is not None
        and configuration.naming_profile
        in (
            "marta-lawrence",
            "andrzej-kubiczek",
        )
    )
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

                if score_files is None:
                    log("  ZAWARTOŚĆ: wykryta (szybkie sprawdzenie)")
                else:
                    log(f"  LICZBA PLIKÓW: {len(score_files)}")
            continue

        primary_file = min(
            group_files,
            key=lambda api_file: (
                get_part_number(api_file["name"]),
                api_file["name"],
            ),
        )

        if uses_named_scan_folders:
            workflow_name = (
                selected_workflow["name"]
                if configuration.naming_profile == "andrzej-kubiczek"
                else None
            )
            destination_folder = resolve_asset_root(
                configuration,
                primary_file["name"],
                "scans",
                workflow_name=workflow_name,
            )
            if destination_folder is None:
                if configuration.naming_profile == "marta-lawrence":
                    log("BRAK SKONFIGUROWANEGO FOLDERU SKANÓW DLA BIBLIOTEKI — POMIJAM")
                else:
                    log("BRAK SKONFIGUROWANEGO FOLDERU DOCELOWEGO DLA SKANÓW — POMIJAM")
                continue
        else:
            destination_folder = target_folders[primary_file["name"]]

        fallback_reason = (
            marta_fallback_reason(
                configuration,
                primary_file["name"],
                "scans",
            )
            if configuration is not None
            else None
        )

        if fallback_reason is not None:
            log(f"UWAGA: {primary_file['name']}")
            log(f"        -> {fallback_reason}")
            log(f"        -> skany zapiszę w folderze awaryjnym: {destination_folder}")

        provider = find_scan_provider(source["url"])

        if provider is None:
            reason = "Brak automatycznej obsługi tego źródła skanów."
            log("BRAK OBSŁUGI AUTOMATYCZNEGO POBIERANIA DLA TEJ BIBLIOTEKI")
            log(f"URL-scan: {source['url']}")

            if scan_issues is not None:
                scan_issues.append(
                    ScanIssue(
                        group_key=group_key,
                        transcription_names=tuple(
                            api_file["name"] for api_file in group_files
                        ),
                        source_url=source["url"],
                        reason=reason,
                        source_metadata=(extract_scan_source_metadata(primary_file)),
                        destination_folder=(destination_folder),
                    )
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

        output_folder_name = "skany"

        if uses_named_scan_folders:
            legacy_folder = find_legacy_scan_package_folder(
                destination_folder,
                download_info.filename,
            )
            if legacy_folder is not None:
                log(f"SKANY JUŻ ISTNIEJĄ W STARYM FOLDERZE: {legacy_folder}")
                continue

            output_folder_name = scan_package_folder_name(download_info.filename)

        scans_folder = destination_folder / output_folder_name

        if scans_folder.exists():
            manifest_status = validate_scan_manifest(scans_folder)

            if manifest_status is not False:
                log("SKANY JUŻ ISTNIEJĄ:")
                log(f"  FOLDER: {scans_folder}")
                continue

            is_incomplete = True
        else:
            is_incomplete = False

        if is_incomplete:
            log("SKANY SĄ NIEKOMPLETNE — WYMAGAJĄ NAPRAWY")
        else:
            log("BRAK SKANÓW")

        log(f"FOLDER DOCELOWY: {scans_folder}")
        log(f"URL-scan: {source['url']}")
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
            output_folder_name=output_folder_name,
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
        request.destination_folder.mkdir(
            parents=True,
            exist_ok=True,
        )
        scans_folder = request.destination_folder / request.output_folder_name
        backup_folder = None

        if scans_folder.exists() and validate_scan_manifest(scans_folder) is False:
            timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
            backup_folder = request.destination_folder / (
                f".{request.output_folder_name}_incomplete_{timestamp}"
            )
            scans_folder.rename(backup_folder)
            log("WYKRYTO NIEKOMPLETNY PAKIET — POBIERAM PONOWNIE")

        if progress_callback:
            provider_progress = lambda downloaded, total, request=request: (
                progress_callback(
                    request,
                    downloaded,
                    total,
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
                output_folder_name=(request.output_folder_name),
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
    configuration=None,
    log=print,
):
    scan_issues = []
    plans = plan_scans(
        selected_workflow,
        scan_urls_by_group,
        scan_sources_by_url,
        existing_scans_by_url,
        target_folders,
        session,
        configuration=configuration,
        scan_issues=scan_issues,
        log=log,
    )
    selected_plans = []

    for request in plans:
        if should_download(request):
            selected_plans.append(request)
        else:
            log("POMIJAM POBIERANIE")

    if progress_callback:
        adapted_progress = lambda request, downloaded, total: progress_callback(
            downloaded,
            total,
        )
    else:
        adapted_progress = None

    download_result = download_scan_plans(
        session,
        selected_plans,
        progress_callback=adapted_progress,
        log=log,
    )

    return ScanSyncResult(
        downloaded_packages=(download_result.downloaded_packages),
        scan_issues=tuple(scan_issues),
    )
