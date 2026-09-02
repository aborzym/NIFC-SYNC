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


def resolve_asset_root(
    configuration: AppConfiguration,
    filename,
    asset_kind: AssetKind,
):
    if configuration.naming_profile != "marta-lawrence":
        return configuration.destination

    library_id = detect_library_id(filename)

    if library_id is None:
        return None

    if asset_kind == "transcriptions":
        path_key = library_transcriptions_path_key(library_id)
    elif asset_kind == "scans":
        path_key = library_scans_path_key(library_id)
    else:
        raise ValueError(f"Nieznany rodzaj danych: {asset_kind}")

    configured_path = configuration.organization_path(path_key)

    if configured_path is None:
        return None

    if configured_path.is_absolute():
        return configured_path

    if configuration.destination is None:
        return None

    return configuration.destination / configured_path
