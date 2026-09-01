import base64
from dataclasses import dataclass
from pathlib import Path

from core.filesystem import find_existing_transcriptions


WORKFLOW_CODES = {
    "XML": "XML",
    "KRN-modern": "M",
    "KRN-diplomatic": "D",
}


@dataclass(frozen=True)
class TranscriptionSyncResult:
    created_count: int
    downloaded_count: int
    skipped_count: int
    target_folders: dict[str, Path]


def sync_transcriptions(
    selected_workflow,
    base_dir,
    folder_names,
    next_number,
    log=print,
):
    base_dir = Path(base_dir)
    workflow_name = selected_workflow["name"]
    workflow_code = WORKFLOW_CODES[workflow_name]

    created_count = 0
    downloaded_count = 0
    skipped_count = 0
    target_folders = {}

    log("\nPorównanie:")

    for api_file in selected_workflow["files"]:
        api_name = api_file["name"]
        api_stem = Path(api_name).stem

        match = next(
            (folder for folder in folder_names if api_stem in folder),
            None,
        )

        if match:
            log(f"ISTNIEJE: {api_name}")
            log(f"        -> {match}")
            target_folder = base_dir / match
        else:
            log(f"BRAK:    {api_name}")
            folder_name = (
                f"{next_number:03d} - {workflow_code} - {api_stem}"
            )
            target_folder = base_dir / folder_name

            if not target_folder.exists():
                target_folder.mkdir()
                created_count += 1
                log(f"UTWORZONO FOLDER: {target_folder.name}")

            next_number += 1

        existing_transcriptions = find_existing_transcriptions(
            target_folder,
            workflow_name,
        )

        if existing_transcriptions:
            skipped_count += 1
            names = ", ".join(
                path.name for path in existing_transcriptions
            )
            log(f"POMIJAM: transkrypcja już istnieje: {names}")
        else:
            file_content = base64.b64decode(api_file["content"])
            file_path = target_folder / api_name
            file_path.write_bytes(file_content)
            downloaded_count += 1
            log(f"ZAPISANO TRANSKRYPCJĘ: {file_path.name}")

        target_folders[api_name] = target_folder

    return TranscriptionSyncResult(
        created_count=created_count,
        downloaded_count=downloaded_count,
        skipped_count=skipped_count,
        target_folders=target_folders,
    )
