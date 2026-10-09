import re

from pypdf import PdfReader

ROW_PATTERN = re.compile(
    r"^\s*(\d+)\s+(KRN-diplomatic|KRN-modern|XML)\s+"
    r"(.+?)\s+(\d+)\s*$"
)


def parse_settlement_text(text):
    totals = re.findall(
        r"łączna liczba znaków:\s*([0-9][0-9 \u00a0]*)",
        text,
        flags=re.IGNORECASE,
    )
    if len(totals) != 1:
        raise ValueError("Nie znaleziono jednoznacznej sumy znaków w PDF-ie.")

    declared_total = int("".join(totals[0].split()))
    performer = re.search(r"Wykonawca:\s*([^\r\n]+)", text)
    if performer is None:
        raise ValueError("Nie znaleziono wykonawcy w PDF-ie.")

    performer_name = re.split(r"\s{2,}", performer.group(1).strip())[0]
    entries = []

    for line in text.splitlines():
        match = ROW_PATTERN.fullmatch(line)
        if match:
            tranche, scheme, filename, count = match.groups()
            entries.append(
                {
                    "tranche": int(tranche),
                    "scheme": scheme,
                    "file_name": filename.strip(),
                    "note_count": int(count),
                }
            )
        elif re.match(r"^\s*\d+\s+(?:KRN-|XML\b)", line):
            raise ValueError(f"Nie udało się odczytać pozycji: {line.strip()}")

    if not entries:
        raise ValueError("Nie znaleziono pozycji rozliczenia.")

    calculated_total = sum(item["note_count"] for item in entries)
    if calculated_total != declared_total:
        raise ValueError(
            f"Suma pozycji ({calculated_total}) różni się od sumy "
            f"w dokumencie ({declared_total}). Import przerwany."
        )

    return {
        "performer": performer_name,
        "total": declared_total,
        "entries": entries,
    }


def read_settlement_pdf(path):
    reader = PdfReader(path)
    text = "\n".join(
        page.extract_text(extraction_mode="layout") or "" for page in reader.pages
    )
    return parse_settlement_text(text)


def _compare_exact_statistics(entries, paid_entries):
    statistics = {}
    settlements = {}

    for item in entries:
        key = (item["scheme"], item["file_name"])
        statistics.setdefault(key, []).append(item)

    for item in paid_entries:
        key = (item["scheme"], item["file_name"])
        settlements.setdefault(key, []).append(item)

    paid = []
    unpaid = []
    unresolved = []

    for key, items in statistics.items():
        matches = settlements.get(key, [])

        if not matches:
            unpaid.extend(items)
        elif (
            len(items) == 1
            and len(matches) == 1
            and items[0]["note_count"] == matches[0]["note_count"]
        ):
            paid.extend(items)
        else:
            unresolved.extend(items)

    outside = [
        item
        for key, items in settlements.items()
        if key not in statistics
        for item in items
    ]

    return {
        "paid": tuple(paid),
        "unpaid": tuple(unpaid),
        "unresolved": tuple(unresolved),
        "outside": tuple(outside),
        "paid_total": sum(item["note_count"] for item in paid),
        "unpaid_total": sum(item["note_count"] for item in unpaid),
        "unresolved_total": sum(item["note_count"] for item in unresolved),
    }


def _matching_filename(name):
    return name.removeprefix("*** ").strip()


def compare_statistics(entries, paid_entries, approved=()):
    result = _compare_exact_statistics(entries, paid_entries)
    paid = list(result["paid"])
    unpaid = list(result["unpaid"])
    unresolved = list(result["unresolved"])
    outside = list(result["outside"])
    differences = []

    for item in tuple(unpaid):
        name = _matching_filename(item["file_name"])
        candidates = [
            other for other in outside if _matching_filename(other["file_name"]) == name
        ]
        statistics_candidates = [
            other for other in unpaid if _matching_filename(other["file_name"]) == name
        ]
        if not candidates:
            continue

        if len(candidates) != 1 or len(statistics_candidates) != 1:
            unpaid.remove(item)
            unresolved.append(item)
            continue

        other = candidates[0]
        identity = (
            item["scheme"],
            item["file_name"],
            item["submission_time"],
            item["note_count"],
            other["scheme"],
            other["file_name"],
            other["note_count"],
        )
        unpaid.remove(item)
        outside.remove(other)

        if identity in approved and item["note_count"] == other["note_count"]:
            paid.append(item)
        else:
            unresolved.append(item)
            differences.append(
                {
                    "identity": identity,
                    "statistics": item,
                    "settlement": other,
                }
            )

    return {
        "paid": tuple(paid),
        "unpaid": tuple(unpaid),
        "unresolved": tuple(unresolved),
        "outside": tuple(outside),
        "differences": tuple(differences),
        "paid_total": sum(item["note_count"] for item in paid),
        "unpaid_total": sum(item["note_count"] for item in unpaid),
        "unresolved_total": sum(item["note_count"] for item in unresolved),
    }
