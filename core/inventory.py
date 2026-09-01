import re
from dataclasses import dataclass
from pathlib import Path

from core.filesystem import find_existing_scores
from core.scan_manifest import validate_scan_manifest
from core.scans import folder_matches_scan_group


NUMBER_PATTERN = re.compile(r"(?<!\d)(\d{3})\s*-\s*")


@dataclass(frozen=True)
class StorageInventory:
    folder_names: tuple[str, ...]
    existing_scans_by_url: dict
    next_number: int


def build_storage_inventory(
    base_dir,
    scan_urls_by_group,
):
    base_dir = Path(base_dir)
    folder_names = tuple(
        path.name
        for path in base_dir.iterdir()
        if path.is_dir()
    )

    scan_folders_by_url = {}

    for folder_name in folder_names:
        for group_key, normalized_urls in scan_urls_by_group.items():
            if not folder_matches_scan_group(
                folder_name,
                group_key,
            ):
                continue

            for normalized_url in normalized_urls:
                scan_folders_by_url.setdefault(
                    normalized_url,
                    set(),
                ).add(base_dir / folder_name)

    existing_scans_by_url = {}

    for normalized_url, folders in scan_folders_by_url.items():
        for folder in folders:
            scans_folder = folder / "skany"
            if validate_scan_manifest(scans_folder) is False:
                continue

            existing_scores = find_existing_scores(folder)

            if not existing_scores:
                continue

            existing_scans_by_url.setdefault(
                normalized_url,
                {},
            )[folder] = existing_scores

    numbers = []

    for folder_name in folder_names:
        match = NUMBER_PATTERN.search(folder_name)

        if match:
            numbers.append(int(match.group(1)))

    return StorageInventory(
        folder_names=folder_names,
        existing_scans_by_url=existing_scans_by_url,
        next_number=max(numbers, default=0) + 1,
    )
