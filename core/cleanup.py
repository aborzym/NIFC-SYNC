import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CleanupResult:
    removed: tuple[Path, ...]
    failures: tuple[tuple[Path, str], ...]


def cleanup_scan_staging_folders(
    base_dir,
    log=print,
):
    base_dir = Path(base_dir)
    removed = []
    failures = []

    for project_folder in base_dir.iterdir():
        if not project_folder.is_dir():
            continue

        for staging_folder in project_folder.glob(
            ".skany_tmp_*"
        ):
            if not staging_folder.is_dir():
                continue

            try:
                shutil.rmtree(staging_folder)
            except OSError as error:
                failures.append(
                    (staging_folder, str(error))
                )
                log(
                    "NIE UDAŁO SIĘ USUNĄĆ POZOSTAŁOŚCI: "
                    f"{staging_folder} — {error}"
                )
            else:
                removed.append(staging_folder)
                log(
                    "USUNIĘTO POZOSTAŁOŚCI PO PRZERWANYM "
                    f"POBIERANIU: {staging_folder}"
                )

    return CleanupResult(
        removed=tuple(removed),
        failures=tuple(failures),
    )
