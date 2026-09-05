import json
import os
import stat
from datetime import datetime
from pathlib import Path, PurePosixPath

MANIFEST_FILENAME = ".nifc-sync-manifest.json"
MANIFEST_VERSION = 1


def write_scan_manifest(scans_folder, source_url, package_name):
    scans_folder = Path(scans_folder)
    files = []

    for path in sorted(scans_folder.rglob("*")):
        if not path.is_file() or path.name == MANIFEST_FILENAME:
            continue

        files.append(
            {
                "path": path.relative_to(scans_folder).as_posix(),
                "size": path.stat().st_size,
            }
        )

    if not files:
        raise ValueError("Nie można utworzyć manifestu pustego pakietu skanów.")

    manifest = {
        "version": MANIFEST_VERSION,
        "source_url": source_url,
        "package": package_name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "files": files,
    }
    manifest_path = scans_folder / MANIFEST_FILENAME
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def validate_scan_manifest(
    scans_folder,
    verify_sizes=True,
):
    """Return None for legacy folders, True for complete, False for invalid."""
    scans_folder = Path(scans_folder)
    manifest_path = scans_folder / MANIFEST_FILENAME

    if not manifest_path.is_file():
        return None

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        if manifest.get("version") != MANIFEST_VERSION:
            return False

        files = manifest.get("files")

        if not isinstance(files, list) or not files:
            return False

        expected_files = {}

        for entry in files:
            relative_path = entry["path"]
            expected_size = entry["size"]

            if (
                not isinstance(relative_path, str)
                or not relative_path
                or not isinstance(expected_size, int)
                or expected_size < 0
            ):
                return False

            relative = PurePosixPath(relative_path)

            if (
                relative.is_absolute()
                or ".." in relative.parts
                or "\\" in relative_path
            ):
                return False

            normalized_path = relative.as_posix()

            if normalized_path in expected_files:
                return False

            expected_files[normalized_path] = expected_size

        if verify_sizes:
            for relative_path, expected_size in expected_files.items():
                path = scans_folder.joinpath(*PurePosixPath(relative_path).parts)
                file_stat = path.stat()

                if (
                    not stat.S_ISREG(file_stat.st_mode)
                    or file_stat.st_size != expected_size
                ):
                    return False

            return True

        expected_children = {}

        for relative_path in expected_files:
            path_parts = PurePosixPath(relative_path).parts

            for index, child_name in enumerate(path_parts):
                parent_parts = path_parts[:index]
                expected_children.setdefault(
                    parent_parts,
                    set(),
                ).add(child_name)

        for parent_parts, expected_names in expected_children.items():
            directory = scans_folder.joinpath(*parent_parts)
            actual_names = set(os.listdir(directory))
            actual_names.discard(MANIFEST_FILENAME)

            if actual_names != expected_names:
                return False

        return True

    except (
        OSError,
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):
        return False
