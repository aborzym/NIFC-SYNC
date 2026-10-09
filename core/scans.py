import base64
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from providers import (
    nifc_repository,
    polish_music_sources,
    polona,
    sandomierz,
)

KRN_URL_SCAN_PATTERN = re.compile(
    r"^!!!URL-scan:\s*(.+?)\s*$",
    re.MULTILINE,
)

XML_URL_SCAN_PATTERN = re.compile(
    r"@URL-scan:\s*([^<\r\n]+)",
)

KRN_REFERENCE_PATTERN = re.compile(
    r"^!!!([^:]+):\s*(.*?)\s*$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class ScanSourceMetadata:
    rism_id: str = ""
    siglum: str = ""
    shelfmark: str = ""
    composer: str = ""
    title: str = ""


PART_NUMBER_PATTERN = re.compile(r"(?<=-\d{3})-\d{3}$")

SCAN_PROVIDERS = (
    sandomierz,
    polish_music_sources,
    polona,
    nifc_repository,
)


def clean_scan_url(value):
    return value.strip().split(maxsplit=1)[0]


def extract_scan_source_metadata(
    api_file,
):
    suffix = Path(api_file["name"]).suffix.lower()

    if suffix != ".krn":
        return ScanSourceMetadata()

    text = base64.b64decode(api_file["content"]).decode(
        "utf-8",
        errors="replace",
    )
    values = {
        key.strip(): value.strip() for key, value in KRN_REFERENCE_PATTERN.findall(text)
    }
    filename_stem = Path(api_file["name"]).stem
    filename_siglum, separator, _remainder = filename_stem.partition("--")

    if separator:
        filename_siglum = filename_siglum.upper()
    else:
        filename_siglum = ""

    return ScanSourceMetadata(
        rism_id=values.get("NIFC-rismSourceID", ""),
        siglum=(values.get("SMS-siglum") or filename_siglum),
        shelfmark=values.get("SMS-shelfmark", ""),
        composer=values.get("COM", ""),
        title=values.get("OTL", ""),
    )


def extract_scan_url(api_file):
    file_content = base64.b64decode(api_file["content"])
    suffix = Path(api_file["name"]).suffix.lower()

    if suffix == ".krn":
        text = file_content.decode(
            "utf-8",
            errors="replace",
        )
        match = KRN_URL_SCAN_PATTERN.search(text)

        if match:
            return clean_scan_url(match.group(1))

        return None

    if suffix in {".xml", ".musicxml"}:
        text = file_content.decode(
            "utf-8",
            errors="replace",
        )
        match = XML_URL_SCAN_PATTERN.search(text)

        if match:
            return clean_scan_url(match.group(1))

    return None


def get_scan_group_key(filename):
    stem = Path(filename).stem
    source_part = stem.split("_", 1)[0]

    return PART_NUMBER_PATTERN.sub(
        "",
        source_part,
    )


def get_part_number(filename):
    stem = Path(filename).stem
    source_part = stem.split("_", 1)[0]

    match = re.search(
        r"-(\d{3})$",
        source_part,
    )

    if match:
        return int(match.group(1))

    return 0


def normalize_scan_url(url):
    parsed = urlsplit(url.strip())

    normalized = parsed.netloc.lower() + parsed.path.rstrip("/")
    query = parsed.query

    if polona.supports(url):
        query = "&".join(
            parameter
            for parameter in query.split("&")
            if parameter.partition("=")[0].lower() != "page"
        )

    if query:
        normalized += f"?{query}"

    return normalized


def folder_matches_scan_group(
    folder_name,
    group_key,
):
    pattern = re.compile(
        rf"{re.escape(group_key)}"
        r"(?:-\d{3})?(?:_|$)"
    )

    return pattern.search(folder_name) is not None


def find_scan_provider(scan_url):
    return next(
        (provider for provider in SCAN_PROVIDERS if provider.supports(scan_url)),
        None,
    )
