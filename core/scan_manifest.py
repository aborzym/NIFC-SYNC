import json
from datetime import datetime
from pathlib import Path


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


def validate_scan_manifest(scans_folder):
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

        root = scans_folder.resolve()
        for entry in files:
            relative_path = entry["path"]
            expected_size = entry["size"]
            path = (scans_folder / relative_path).resolve()
            if root not in path.parents:
                return False
            if not path.is_file() or path.stat().st_size != expected_size:
                return False
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False

    return True
