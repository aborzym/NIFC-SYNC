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


def find_files_with_extensions(folder, extensions):
    matching_files = []

    for directory, _, filenames in os.walk(folder):
        directory_path = Path(directory)

        for filename in filenames:
            path = directory_path / filename

            if path.suffix.lower() in extensions:
                matching_files.append(path)

    return matching_files


def find_existing_scores(folder):
    return find_files_with_extensions(
        folder,
        SCORE_EXTENSIONS,
    )


def find_existing_transcriptions(folder, workflow_name):
    return find_files_with_extensions(
        folder,
        TRANSCRIPTION_EXTENSIONS[workflow_name],
    )


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
