import json
import re
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlsplit

import requests

DOMAIN = "polish.musicsources.pl"

MANUSCRIPT_PATTERN = re.compile(r"/galeria/rekopisy/(\d+)(?:/\d+)?(?:/|$)")

API_URL = (
    "https://api.nifc.pl/v2/index.php/manuscripts/get_manuscript_by_id/{manuscript_id}"
)

STORAGE_URL = (
    "https://storage.nifc.pl/web_files/_plik/"
    "museum/manuscripts/{manuscript_id}/{filename}"
)

PDF_URL = (
    "https://repozytorium.nifc.pl/islandora/object/{repo_id}/datastream/PDF/download"
)

SEARCH_API_URL = (
    "https://api.nifc.pl/v2/index.php/Search_engine_popc2/search/0/{limit}?lang=pl"
)

MANUSCRIPT_PAGE_URL = (
    "https://polish.musicsources.pl/pl/lokalizacje/galeria/rekopisy/{manuscript_id}/1"
)


@dataclass(frozen=True)
class ScanInfo:
    filename: str
    url: str


@dataclass(frozen=True)
class DownloadInfo:
    url: str
    filename: str
    size: int | None
    content_type: str | None
    manuscript_id: str
    title: str
    scans: tuple[ScanInfo, ...]
    pdf_url: str


@dataclass(frozen=True)
class SearchResult:
    manuscript_id: str
    title: str
    siglum: str
    shelfmark: str
    rism_id: str
    url: str


def supports(scan_url: str) -> bool:
    parsed = urlsplit(scan_url)

    return (
        parsed.netloc.lower() == DOMAIN
        and MANUSCRIPT_PATTERN.search(parsed.path) is not None
    )


def get_manuscript_id(scan_url: str) -> str:
    parsed = urlsplit(scan_url)
    match = MANUSCRIPT_PATTERN.search(parsed.path)

    if not match:
        raise ValueError(
            f"Nie znaleziono identyfikatora rękopisu w URL-scan: {scan_url}"
        )

    return match.group(1)


def get_download_info(
    session: requests.Session,
    scan_url: str,
) -> DownloadInfo:
    manuscript_id = get_manuscript_id(scan_url)
    api_url = API_URL.format(manuscript_id=manuscript_id)

    response = session.get(
        api_url,
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()
    gallery = data.get("gallery")

    if not isinstance(gallery, list) or not gallery:
        raise ValueError(f"API nie zwróciło skanów rękopisu {manuscript_id}.")

    scans = []

    for item in gallery:
        filename = item.get("file_name")

        if not filename:
            raise ValueError("W galerii znajduje się wpis bez nazwy pliku.")

        scans.append(
            ScanInfo(
                filename=filename,
                url=STORAGE_URL.format(
                    manuscript_id=manuscript_id,
                    filename=filename,
                ),
            )
        )

    title = data.get("standardized_title") or data.get("title") or "bez tytułu"
    repo_id = str(data.get("repo_id") or "").strip()

    if not repo_id:
        raise ValueError(
            f"API nie zwróciło identyfikatora PDF rękopisu {manuscript_id}."
        )

    pdf_url = PDF_URL.format(
        repo_id=quote(
            repo_id,
            safe="",
        )
    )
    pdf_response = session.head(
        pdf_url,
        allow_redirects=True,
        timeout=30,
    )
    pdf_response.raise_for_status()

    content_type = (
        pdf_response.headers.get(
            "Content-Type",
            "",
        )
        .split(
            ";",
            1,
        )[0]
        .strip()
        .lower()
    )

    if content_type != "application/pdf":
        raise ValueError(f"Serwer nie zwrócił pliku PDF dla rękopisu {manuscript_id}.")

    size_header = pdf_response.headers.get("Content-Length")
    size = int(size_header) if size_header else None
    safe_title = re.sub(
        r'[\\/:*?"<>|]+',
        "-",
        title,
    ).strip(" .")

    return DownloadInfo(
        url=scan_url,
        filename=(f"{manuscript_id} — {safe_title or 'bez tytułu'}.pdf"),
        size=size,
        content_type="PDF",
        manuscript_id=manuscript_id,
        title=title,
        scans=tuple(scans),
        pdf_url=pdf_url,
    )


def _normalize_reference(value):
    return re.sub(
        r"[\W_]+",
        "",
        str(value or "").casefold(),
    )


def _search_api(
    session,
    keyword,
    limit=50,
):
    response = session.post(
        SEARCH_API_URL.format(limit=limit),
        data={
            "data": json.dumps(
                {
                    "keyword": keyword,
                    "search_fields": [],
                },
                ensure_ascii=False,
            ),
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    if not isinstance(data, list):
        raise TypeError(
            "Wyszukiwarka Polish Music Sources zwróciła nieprawidłową odpowiedź."
        )

    return data


def _matches_source_metadata(candidate, metadata):
    candidate_rism_id = _normalize_reference(candidate.get("rism_id"))
    expected_rism_id = _normalize_reference(metadata.rism_id)

    if expected_rism_id and candidate_rism_id == expected_rism_id:
        return True

    expected_siglum = _normalize_reference(metadata.siglum)
    expected_shelfmark = _normalize_reference(metadata.shelfmark)

    if not expected_siglum or not expected_shelfmark:
        return False

    return (
        _normalize_reference(candidate.get("library_siglum")) == expected_siglum
        and _normalize_reference(candidate.get("shelfmark")) == expected_shelfmark
    )


def search_manuscripts(
    session,
    metadata,
):
    keywords = []

    for value in (
        metadata.rism_id,
        metadata.shelfmark,
    ):
        value = str(value or "").strip()

        if value and value not in keywords:
            keywords.append(value)

    matches = {}

    for keyword in keywords:
        for candidate in _search_api(
            session,
            keyword,
        ):
            if candidate.get("type") != "manuscripts":
                continue

            if not _matches_source_metadata(
                candidate,
                metadata,
            ):
                continue

            manuscript_id = str(candidate.get("id_object") or "").strip()

            if not manuscript_id:
                continue

            title = (
                candidate.get("standardized_title")
                or candidate.get("title")
                or candidate.get("title_on_source")
                or "bez tytułu"
            )

            matches[manuscript_id] = SearchResult(
                manuscript_id=manuscript_id,
                title=str(title).strip(),
                siglum=str(candidate.get("library_siglum") or "").strip(),
                shelfmark=str(candidate.get("shelfmark") or "").strip(),
                rism_id=str(candidate.get("rism_id") or "").strip(),
                url=MANUSCRIPT_PAGE_URL.format(
                    manuscript_id=manuscript_id,
                ),
            )

        if matches:
            break

    return tuple(matches.values())


def download_and_extract(
    session: requests.Session,
    info: DownloadInfo,
    destination_folder: Path,
    progress_callback: (Callable[[int, int | None], None] | None) = None,
    output_folder_name="skany",
) -> Path:
    scans_folder = destination_folder / output_folder_name
    problem_path = (
        destination_folder / "problem.txt"
        if output_folder_name == "skany"
        else destination_folder / f"{output_folder_name}.problem.txt"
    )

    if scans_folder.exists():
        raise FileExistsError(f"Folder już istnieje: {scans_folder}")

    if Path(info.filename).name != info.filename:
        raise ValueError("Nieprawidłowa nazwa pliku PDF.")

    staging_folder = Path(
        tempfile.mkdtemp(
            prefix=".skany_tmp_",
            dir=destination_folder,
        )
    )
    partial_path = staging_folder / f"{info.filename}.part"
    target_path = staging_folder / info.filename
    downloaded_size = 0

    try:
        with session.get(
            info.pdf_url,
            stream=True,
            timeout=60,
        ) as response:
            response.raise_for_status()

            content_type = (
                response.headers.get(
                    "Content-Type",
                    "",
                )
                .split(
                    ";",
                    1,
                )[0]
                .strip()
                .lower()
            )

            if content_type != "application/pdf":
                raise ValueError(
                    "Serwer zwrócił nieoczekiwany "
                    f"typ pliku: "
                    f"{content_type or 'nieznany'}."
                )

            size_header = response.headers.get("Content-Length")
            expected_size = int(size_header) if size_header else info.size

            with partial_path.open("wb") as output:
                for chunk in response.iter_content(chunk_size=256 * 1024):
                    if not chunk:
                        continue

                    output.write(chunk)
                    downloaded_size += len(chunk)

                    if progress_callback:
                        progress_callback(
                            downloaded_size,
                            expected_size,
                        )

        if downloaded_size == 0:
            raise ValueError("Pobrano pusty plik PDF.")

        if expected_size is not None and downloaded_size != expected_size:
            raise ValueError(
                f"Niepełny plik PDF: {downloaded_size} z {expected_size} B."
            )

        with partial_path.open("rb") as pdf_file:
            if pdf_file.read(5) != b"%PDF-":
                raise ValueError("Pobrany plik nie jest prawidłowym dokumentem PDF.")

        partial_path.rename(target_path)
        staging_folder.rename(scans_folder)

        if problem_path.exists():
            existing_report = problem_path.read_text(
                encoding="utf-8",
                errors="replace",
            )

            if existing_report.startswith("NIFC-SYNC — raport problemu"):
                problem_path.unlink()

    except Exception as error:
        shutil.rmtree(
            staging_folder,
            ignore_errors=True,
        )

        report_lines = [
            "NIFC-SYNC — raport problemu",
            "",
            "Nie pobrano kompletnego pliku PDF.",
            "",
            (f"Data: {datetime.now().astimezone().isoformat(timespec='seconds')}"),
            f"Źródło: {info.url}",
            f"PDF: {info.pdf_url}",
            f"ID rękopisu: {info.manuscript_id}",
            f"Tytuł: {info.title}",
            f"Pobrano bajtów: {downloaded_size}",
            "",
            f"Problem: {error}",
        ]

        try:
            problem_path.write_text(
                "\n".join(report_lines) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass

        raise

    return scans_folder
