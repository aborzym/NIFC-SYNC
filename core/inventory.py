import os
import re
from dataclasses import dataclass
from pathlib import Path

from core.filesystem import SCORE_EXTENSIONS
from core.scan_manifest import scan_manifest_file_paths, validate_scan_manifest
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

    with os.scandir(base_dir) as entries:
        folder_names = tuple(entry.name for entry in entries if entry.is_dir())

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
            manifest_status = validate_scan_manifest(
                scans_folder,
                verify_sizes=False,
            )

            if manifest_status is False:
                continue

            if manifest_status is True:
                existing_scores = tuple(
                    path
                    for path in scan_manifest_file_paths(scans_folder)
                    if path.suffix.lower() in SCORE_EXTENSIONS
                )

            else:
                try:
                    with os.scandir(scans_folder) as entries:
                        has_scan_content = next(entries, None) is not None
                except OSError:
                    has_scan_content = False

                if not has_scan_content:
                    continue

                existing_scores = None

            existing_scans_by_url.setdefault(
                normalized_url,
                {},
            )[folder] = existing_scores
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
