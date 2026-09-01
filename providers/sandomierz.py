import re
import shutil
import stat
import tempfile
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

import requests

DOMAIN = "bc.bdsandomierz.pl"

EDITION_PATTERN = re.compile(r"/edition/(\d+)(?:/|$)")

FILENAME_PATTERN = re.compile(
    r"filename\*=UTF-8''([^;]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DownloadInfo:
    url: str
    filename: str
    size: int | None
    content_type: str | None


def supports(scan_url: str) -> bool:
    domain = urlsplit(scan_url).netloc.lower()

    return domain == DOMAIN


def build_download_url(scan_url: str) -> str:
    parsed = urlsplit(scan_url)
    match = EDITION_PATTERN.search(parsed.path)

    if not match:
        raise ValueError(f"Nie znaleziono identyfikatora edycji w URL-scan: {scan_url}")

    edition_id = match.group(1)

    return f"https://{DOMAIN}/Content/{edition_id}/download?format_id=1"


def get_download_info(
    session: requests.Session,
    scan_url: str,
) -> DownloadInfo:
    download_url = build_download_url(scan_url)
    attempts = 3
    retry_delay = 2

    for attempt in range(1, attempts + 1):
        with session.get(
            download_url,
            stream=True,
            timeout=30,
        ) as response:
            response.raise_for_status()

            content_length = response.headers.get("Content-Length")
            content_disposition = response.headers.get(
                "Content-Disposition",
                "",
            )
            content_type = response.headers.get(
                "Content-Type",
                "",
            )

        if content_type.lower().startswith("application/zip"):
            break

        if attempt < attempts:
            time.sleep(retry_delay)

    else:
        raise ValueError(
            "Serwer nie udostępnił pakietu ZIP "
            f"po {attempts} próbach. "
            "Ostatni typ odpowiedzi: "
            f"{content_type or 'nieznany'}."
        )

    size = int(content_length) if content_length else None

    filename_match = FILENAME_PATTERN.search(content_disposition)

    if filename_match:
        filename = unquote(filename_match.group(1))
    else:
        filename = "sandomierz_DjVu.zip"

    return DownloadInfo(
        url=download_url,
        filename=filename,
        size=size,
        content_type=content_type,
    )


def validate_archive(
    archive: zipfile.ZipFile,
    destination: Path,
) -> None:
    destination = destination.resolve()

    for member in archive.infolist():
        member_path = (destination / member.filename).resolve()

        if member_path != destination and destination not in member_path.parents:
            raise ValueError(f"Niebezpieczna ścieżka w archiwum: {member.filename}")

        mode = member.external_attr >> 16

        if stat.S_ISLNK(mode):
            raise ValueError(
                f"Archiwum zawiera dowiązanie symboliczne: {member.filename}"
            )


def download_and_extract(
    session: requests.Session,
    info: DownloadInfo,
    destination_folder: Path,
    progress_callback: (Callable[[int, int | None], None] | None) = None,
) -> Path:
    scans_folder = destination_folder / "skany"

    if scans_folder.exists():
        raise FileExistsError(f"Folder już istnieje: {scans_folder}")

    if Path(info.filename).name != info.filename:
        raise ValueError(f"Niebezpieczna nazwa pakietu: {info.filename}")

    with tempfile.TemporaryDirectory(prefix="nifc_sandomierz_") as temporary_directory:
        archive_path = Path(temporary_directory) / info.filename

        attempts = 3
        retry_delay = 2
        last_error = None

        for attempt in range(1, attempts + 1):
            archive_path.unlink(missing_ok=True)

            try:
                with session.get(
                    info.url,
                    stream=True,
                    timeout=60,
                ) as response:
                    response.raise_for_status()

                    content_type = response.headers.get(
                        "Content-Type",
                        "",
                    ).lower()

                    if not content_type.startswith("application/zip"):
                        raise ValueError(
                            "Serwer zwrócił "
                            "nieoczekiwany typ danych: "
                            f"{content_type or 'nieznany'}"
                        )

                    content_length = response.headers.get("Content-Length")
                    total_size = int(content_length) if content_length else info.size
                    downloaded_size = 0

                    with archive_path.open("wb") as output:
                        for chunk in response.iter_content(chunk_size=64 * 1024):
                            if not chunk:
                                continue

                            output.write(chunk)
                            downloaded_size += len(chunk)

                            if progress_callback:
                                progress_callback(
                                    downloaded_size,
                                    total_size,
                                )

                if total_size is not None and downloaded_size != total_size:
                    raise ValueError(
                        f"Pobrano niepełny pakiet: {downloaded_size} z {total_size} B."
                    )

                with archive_path.open("rb") as archive_file:
                    signature = archive_file.read(4)

                if not signature.startswith(b"PK"):
                    raise ValueError("Pobrany plik nie jest archiwum ZIP.")

                break

            except (
                requests.RequestException,
                ValueError,
            ) as error:
                last_error = error

                if attempt < attempts:
                    time.sleep(retry_delay)

        else:
            raise ValueError(
                "Nie udało się pobrać poprawnego "
                f"pakietu ZIP po {attempts} próbach. "
                f"Ostatni błąd: {last_error}"
            )

        staging_folder = Path(
            tempfile.mkdtemp(
                prefix=".skany_tmp_",
                dir=destination_folder,
            )
        )

        try:
            try:
                with zipfile.ZipFile(archive_path) as archive:
                    bad_file = archive.testzip()

                    if bad_file:
                        raise zipfile.BadZipFile(
                            f"Uszkodzony plik w archiwum: {bad_file}"
                        )

                    validate_archive(
                        archive,
                        staging_folder,
                    )
                    archive.extractall(staging_folder)

            except zipfile.BadZipFile as error:
                raise ValueError(f"Pakiet ZIP jest uszkodzony: {error}") from error

            djvu_files = list(staging_folder.rglob("*.djvu"))

            if not djvu_files:
                raise ValueError("Archiwum nie zawiera plików DjVu.")

            staging_folder.rename(scans_folder)

        except Exception:
            shutil.rmtree(
                staging_folder,
                ignore_errors=True,
            )
            raise

    return scans_folder
