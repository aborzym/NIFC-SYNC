import re
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

from providers import polish_music_sources

OBJECT_PATTERN = re.compile(
    r"^/islandora/object/([A-Za-z0-9_-]+:[A-Za-z0-9_.-]+)"
    r"/datastream/(?:OBJ|PDF)/view/?$"
)


def supports(scan_url):
    parsed = urlsplit(scan_url)
    return (
        parsed.scheme in ("http", "https")
        and parsed.netloc.lower() == "repozytorium.nifc.pl"
        and OBJECT_PATTERN.fullmatch(unquote(parsed.path)) is not None
    )


@dataclass(frozen=True)
class DownloadInfo:
    url: str
    filename: str
    size: int | None
    content_type: str
    pdf_url: str
    object_id: str
    title: str


def get_download_info(session, scan_url):
    if not supports(scan_url):
        raise ValueError(f"Nieprawidłowy adres repozytorium NIFC: {scan_url}")

    parsed = urlsplit(scan_url)
    object_id = OBJECT_PATTERN.fullmatch(unquote(parsed.path)).group(1)
    pdf_url = parsed._replace(fragment="").geturl()

    response = session.head(pdf_url, allow_redirects=True, timeout=30)
    response.raise_for_status()

    content_type = (
        response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    )
    if content_type != "application/pdf":
        raise ValueError("Repozytorium NIFC nie zwróciło pliku PDF.")

    size_header = response.headers.get("Content-Length")
    filename = object_id.replace(":", "-") + ".pdf"

    return DownloadInfo(
        url=scan_url,
        filename=filename,
        size=int(size_header) if size_header else None,
        content_type="PDF",
        pdf_url=pdf_url,
        object_id=object_id,
        title=f"Repozytorium NIFC — {object_id}",
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
