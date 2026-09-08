import re
from pathlib import Path

LIBRARY_PREFIX_PATTERN = re.compile(
    r"^(?P<library_id>[a-z]{2}-[a-z0-9]+)--",
    re.IGNORECASE,
)

LIBRARY_DISPLAY_NAMES = {
    "pl-wtm": "WTM",
    "pl-sa": "Sandomierz",
    "pl-cz": "Częstochowa",
    "pl-kk": "Kraków",
}


def list_known_libraries():
    return tuple(LIBRARY_DISPLAY_NAMES.items())


def detect_library_id(filename):
    name = Path(filename).name
    match = LIBRARY_PREFIX_PATTERN.match(name)

    if match is None:
        return None

    return match.group("library_id").casefold()


def library_display_name(library_id):
    normalized_id = library_id.casefold()

    return LIBRARY_DISPLAY_NAMES.get(
        normalized_id,
        normalized_id.upper(),
    )


def library_transcriptions_path_key(library_id):
    normalized_id = library_id.casefold()

    return f"libraries/{normalized_id}/transcriptions"


def library_scans_path_key(library_id):
    normalized_id = library_id.casefold()

    return f"libraries/{normalized_id}/scans"
