from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from core.configuration import AppConfiguration
from core.libraries import (
    detect_library_id,
    library_scans_path_key,
    library_transcriptions_path_key,
)

AssetKind = Literal[
    "transcriptions",
    "scans",
]

WORKFLOW_DESTINATION_NAMES = {
    "KRN-diplomatic": "diplomatic",
    "KRN-modern": "modern",
    "XML": "XML",
}


def marta_fallback_reason(
    configuration: AppConfiguration,
    filename,
    asset_kind: AssetKind,
):
    if configuration.naming_profile != "marta-lawrence":
        return None

    library_id = detect_library_id(filename)

    if library_id is None:
        return "Nie rozpoznano biblioteki na podstawie nazwy pliku."

    if asset_kind == "transcriptions":
        path_key = library_transcriptions_path_key(library_id)
    elif asset_kind == "scans":
        path_key = library_scans_path_key(library_id)
    else:
        raise ValueError(f"Nieznany rodzaj danych: {asset_kind}")

    if configuration.organization_path(path_key) is None:
        return "Nie skonfigurowano folderu dla rozpoznanej biblioteki."

    return None


def resolve_asset_root(
    configuration: AppConfiguration,
    filename,
    asset_kind: AssetKind,
    workflow_name=None,
    year=None,
):
    if configuration.naming_profile == "andrzej-kubiczek":
        if asset_kind not in ("transcriptions", "scans"):
            raise ValueError(f"Nieznany rodzaj danych: {asset_kind}")

        if configuration.destination is None:
            return None

        try:
            workflow_folder = WORKFLOW_DESTINATION_NAMES[workflow_name]
        except KeyError:
            raise ValueError(f"Nieznany workflow: {workflow_name}") from None

        if year is None:
            year = datetime.now(UTC).astimezone().year

        return configuration.destination / str(year) / "in progress" / workflow_folder

    if configuration.naming_profile != "marta-lawrence":
        return configuration.destination

    if asset_kind == "transcriptions":
        fallback_folder = "INNE.krn"
    elif asset_kind == "scans":
        fallback_folder = "INNE.źródła"
    else:
        raise ValueError(f"Nieznany rodzaj danych: {asset_kind}")

    library_id = detect_library_id(filename)

    if library_id is None:
        if configuration.destination is None:
            return None

        return configuration.destination / fallback_folder

    if asset_kind == "transcriptions":
        path_key = library_transcriptions_path_key(library_id)
    else:
        path_key = library_scans_path_key(library_id)

    configured_path = configuration.organization_path(path_key)

    if configured_path is None:
        if configuration.destination is None:
            return None

        return configuration.destination / fallback_folder

    if configured_path.is_absolute():
        return configured_path

    if configuration.destination is None:
        return None

    return configuration.destination / configured_path


def scan_package_folder_name(filename):
    filename = str(filename).strip()
    safe_name = Path(filename).name

    if not filename or safe_name != filename or safe_name in (".", ".."):
        raise ValueError("Nieprawidłowa nazwa pakietu skanów.")

    for suffix in (
        ".zip",
        ".pdf",
    ):
        if safe_name.casefold().endswith(suffix):
            safe_name = safe_name[: -len(suffix)]
            break

    if not safe_name:
        raise ValueError("Nieprawidłowa nazwa pakietu skanów.")

    return safe_name


def find_legacy_scan_package_folder(
    destination_folder,
    filename,
):
    filename = str(filename).strip()
    scan_package_folder_name(filename)

    if not filename.casefold().endswith(".zip"):
        return None

    legacy_folder = Path(destination_folder) / filename

    if not legacy_folder.is_dir():
        return None

    return legacy_folder
