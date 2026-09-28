import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from providers import polish_music_sources

DOMAIN = "polona.pl"
OBJECT_PATTERN = re.compile(
    r"^/item-view/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12})/?$",
    re.IGNORECASE,
)


def supports(scan_url: str) -> bool:
    parsed = urlsplit(scan_url)

    return (
        parsed.scheme in ("http", "https")
        and parsed.netloc.casefold() == DOMAIN
        and OBJECT_PATTERN.fullmatch(parsed.path) is not None
    )


def get_object_id(scan_url: str) -> str:
    parsed = urlsplit(scan_url)

    if not supports(scan_url):
        raise ValueError(f"Nieprawidłowy URL-scan Polony: {scan_url}")

    return OBJECT_PATTERN.fullmatch(parsed.path).group(1).lower()


@dataclass(frozen=True)
class DownloadInfo:
    url: str
    filename: str
    size: int | None
    content_type: str
    pdf_url: str
    object_id: str
    title: str


def get_download_info(session, scan_url: str) -> DownloadInfo:
    object_id = get_object_id(scan_url)
    contents_url = (
        "https://polona.pl/api/library-object-query/"
        f"digital-objects/{object_id}/contents"
    )

    response = session.get(contents_url, timeout=30)
    response.raise_for_status()
    data = response.json()

    if data.get("copyrightProtected") or not data.get("shared"):
        raise ValueError("Obiekt Polony nie jest publicznie dostępny.")

    files = data.get("collective", {}).get("content", ())
    pdf_files = [item for item in files if item.get("mimeType") == "application/pdf"]

    if len(pdf_files) != 1:
        raise ValueError(
            f"Oczekiwano jednego zbiorczego PDF, znaleziono {len(pdf_files)}."
        )

    pdf = pdf_files[0]
    filename = pdf.get("fileName", "")
    file_url = pdf.get("fileUrl", "")

    if Path(filename).name != filename or not filename.lower().endswith(".pdf"):
        raise ValueError("Polona zwróciła nieprawidłową nazwę PDF.")

    if not file_url.startswith("/download/digital-content/"):
        raise ValueError("Polona zwróciła nieprawidłowy adres PDF.")

    pdf_url = f"https://polona.pl/api{file_url}"
    pdf_response = session.head(
        pdf_url,
        allow_redirects=True,
        timeout=30,
    )
    pdf_response.raise_for_status()

    content_type = pdf_response.headers.get("Content-Type", "").split(";", 1)[0]
    if content_type.lower() != "application/pdf":
        raise ValueError("Polona nie zwróciła pliku PDF.")

    size_header = pdf_response.headers.get("Content-Length")
    size = int(size_header) if size_header else None

    return DownloadInfo(
        url=scan_url,
        filename=filename,
        size=size,
        content_type="PDF",
        pdf_url=pdf_url,
        object_id=object_id,
        title=Path(filename).stem,
    )


def download_and_extract(
    session,
    info,
    destination_folder,
    progress_callback=None,
    output_folder_name="skany",
):
    return polish_music_sources.download_and_extract(
        session,
        info,
        destination_folder,
        progress_callback,
        output_folder_name=output_folder_name,
    )
