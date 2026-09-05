import os
from pathlib import Path

SCORE_EXTENSIONS = {
    ".pdf",
    ".djvu",
    ".djv",
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
    ".jp2",
}

TRANSCRIPTION_EXTENSIONS = {
    "XML": {".xml", ".musicxml", ".mxl"},
    "KRN-diplomatic": {".krn"},
    "KRN-modern": {".krn"},
}


def find_files_with_extensions(
    folder,
    extensions,
    ignored_directory_prefixes=(),
):
    matching_files = []

    for directory, subdirectories, filenames in os.walk(folder):
        subdirectories[:] = [
            name
            for name in subdirectories
            if not name.startswith(ignored_directory_prefixes)
        ]
        directory_path = Path(directory)

        for filename in filenames:
            path = directory_path / filename

            if path.suffix.lower() in extensions:
                matching_files.append(path)

    return matching_files


def find_existing_scores(folder):
    folder = Path(folder)
    matching_files = []
    pending_directories = [folder]
    ignored_prefixes = (
        ".skany_tmp_",
        ".skany_incomplete_",
    )

    while pending_directories:
        directory = pending_directories.pop()

        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if entry.name.startswith(ignored_prefixes):
                        continue

                    path = Path(entry.path)

                    if path.suffix.lower() in SCORE_EXTENSIONS:
                        matching_files.append(path)
                        continue

                    if entry.is_dir(follow_symlinks=False):
                        pending_directories.append(path)
        except OSError:
            continue

    return matching_files


def find_existing_transcriptions(
    folder,
    workflow_name,
):
    folder = Path(folder)
    extensions = TRANSCRIPTION_EXTENSIONS[workflow_name]
    matching_files = []

    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                if Path(entry.name).suffix.lower() not in extensions:
                    continue

                if entry.is_file():
                    matching_files.append(folder / entry.name)
    except FileNotFoundError:
        return []

    return matching_files


def format_file_size(size):
    if size is None:
        return "nieznany"

    units = (
        "B",
        "KB",
        "MB",
        "GB",
    )
    value = float(size)

    for unit in units:
        if value < 1000 or unit == units[-1]:
            return f"{value:.2f} {unit}"

        value /= 1000

    return f"{size} B"
