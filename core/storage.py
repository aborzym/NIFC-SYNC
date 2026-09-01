import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SHARE = "//Mac-Studio-Andrzej.local/TRANSKRYPCJE 2026"


def is_mounted(folder):
    return os.path.ismount(folder)


def mount_cifs(
    mount_point,
    credentials_file,
    share=DEFAULT_SHARE,
):
    return subprocess.run(
        [
            "sudo",
            "mount.cifs",
            share,
            str(mount_point),
            "-o",
            (
                f"credentials={Path(credentials_file)},"
                f"vers=3.0,uid={os.getuid()},gid={os.getgid()}"
            ),
        ],
        check=False,
    )


@dataclass(frozen=True)
class StorageValidationResult:
    is_valid: bool
    message: str
    mount_point: Path | None = None


def find_mount_point(folder):
    path = Path(folder).expanduser().resolve()

    while not os.path.ismount(path):
        if path.parent == path:
            return path
        path = path.parent

    return path


def validate_storage(folder, storage_kind="local"):
    path = Path(folder).expanduser()

    if not path.exists():
        return StorageValidationResult(
            False,
            f"Katalog nie istnieje: {path}",
        )

    if not path.is_dir():
        return StorageValidationResult(
            False,
            f"Wybrana ścieżka nie jest katalogiem: {path}",
        )

    if not os.access(path, os.R_OK):
        return StorageValidationResult(
            False,
            f"Brak prawa odczytu katalogu: {path}",
        )

    if not os.access(path, os.W_OK):
        return StorageValidationResult(
            False,
            f"Brak prawa zapisu w katalogu: {path}",
        )

    if storage_kind == "mounted":
        mount_point = find_mount_point(path)
        filesystem_root = Path(path.resolve().anchor)

        if mount_point == filesystem_root:
            return StorageValidationResult(
                False,
                f"Katalog sieciowy nie jest obecnie zamontowany: {path}",
            )

        return StorageValidationResult(
            True,
            f"Katalog jest dostępny: {path}",
            mount_point=mount_point,
        )

    if storage_kind != "local":
        return StorageValidationResult(
            False,
            f"Nieznany typ katalogu: {storage_kind}",
        )

    return StorageValidationResult(
        True,
        f"Katalog jest dostępny: {path}",
    )
